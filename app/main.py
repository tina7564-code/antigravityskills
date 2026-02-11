from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alert_system import AlertSystem
from app.config import get_settings
from app.database import SessionLocal, get_db_session, init_db
from app.listener import CommentListener
from app.models import Account, CommentEvent
from app.processor import CommentProcessor
from app.reply_generator import ReplyGenerator
from app.schemas import AccountCreate, CommentEventOut, CommentPayload

settings = get_settings()
queue: asyncio.Queue[CommentPayload] = asyncio.Queue(maxsize=10000)
listener = CommentListener(queue)
processor = CommentProcessor()
reply_generator = ReplyGenerator()
alert_system = AlertSystem()
worker_tasks: list[asyncio.Task] = []


async def worker(name: str) -> None:
    while True:
        payload = await queue.get()
        try:
            async with SessionLocal() as session:
                await handle_comment(session, payload)
        finally:
            queue.task_done()


async def handle_comment(session: AsyncSession, payload: CommentPayload) -> None:
    account = await _get_account(session, payload.account_external_id)
    if account is None:
        return

    sentiment_result, risk = await processor.process(payload.content)
    reply = reply_generator.generate(payload.content, risk.level, sentiment_result)

    event = CommentEvent(
        account_id=account.id,
        platform_comment_id=payload.platform_comment_id,
        author=payload.author,
        content=payload.content,
        sentiment=sentiment_result.sentiment,
        sentiment_score=sentiment_result.score,
        toxicity_score=sentiment_result.toxicity_score,
        risk_level=risk.level,
        risk_reasons={'items': risk.reasons},
        reply_suggestion=reply,
        raw_payload=payload.model_dump(),
    )
    session.add(event)
    await session.commit()

    if risk.level == 'high':
        await alert_system.send_high_risk_alert(
            title=f'[高风险评论] {payload.account_external_id}',
            body=f'评论人: {payload.author}\n内容: {payload.content}\n建议回复: {reply}',
        )


async def _get_account(session: AsyncSession, external_id: str) -> Account | None:
    result = await session.execute(select(Account).where(Account.external_account_id == external_id))
    return result.scalar_one_or_none()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    for idx in range(settings.worker_concurrency):
        worker_tasks.append(asyncio.create_task(worker(f'w{idx}')))
    await listener.start_polling(SessionLocal)
    yield
    await listener.stop_polling()
    for task in worker_tasks:
        task.cancel()


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.post('/accounts')
async def create_account(payload: AccountCreate, db: AsyncSession = Depends(get_db_session)):
    account = Account(**payload.model_dump())
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return {'id': account.id, 'external_account_id': account.external_account_id}


@app.post('/webhook/comments')
async def receive_comment_webhook(
    payload: CommentPayload,
    x_webhook_secret: str = Header(default=''),
):
    if x_webhook_secret != settings.webhook_secret:
        raise HTTPException(status_code=401, detail='Invalid webhook secret')
    await listener.ingest_webhook(payload)
    return {'status': 'queued'}


@app.get('/comments', response_model=list[CommentEventOut])
async def list_comments(limit: int = 50, db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(CommentEvent).order_by(desc(CommentEvent.created_at)).limit(limit))
    rows = result.scalars().all()
    return [
        CommentEventOut(
            id=row.id,
            platform_comment_id=row.platform_comment_id,
            risk_level=row.risk_level,
            sentiment=row.sentiment,
            toxicity_score=row.toxicity_score,
            reply_suggestion=row.reply_suggestion,
            created_at=row.created_at,
        )
        for row in rows
    ]


@app.get('/healthz')
async def healthz():
    return {'status': 'ok'}
