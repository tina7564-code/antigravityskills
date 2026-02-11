from __future__ import annotations

import asyncio
from collections.abc import Sequence

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Account
from app.schemas import CommentPayload


class SocialMediaClient:
    """Replace with real platform API integration."""

    async def fetch_new_comments(self, account: Account, since_id: str | None = None) -> list[dict]:
        # Demo stub: return no comment by default.
        return []


class CommentListener:
    def __init__(self, queue: asyncio.Queue[CommentPayload]) -> None:
        self.settings = get_settings()
        self.queue = queue
        self.client = SocialMediaClient()
        self.redis = redis.from_url(self.settings.redis_url, decode_responses=True)
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def ingest_webhook(self, payload: CommentPayload) -> None:
        if await self._is_duplicate(payload.platform_comment_id):
            return
        await self.queue.put(payload)

    async def start_polling(self, session_factory) -> None:
        self._stop_event.clear()
        self._task = asyncio.create_task(self._polling_loop(session_factory))

    async def stop_polling(self) -> None:
        self._stop_event.set()
        if self._task:
            await self._task

    async def _polling_loop(self, session_factory) -> None:
        while not self._stop_event.is_set():
            async with session_factory() as session:
                accounts = await self._get_accounts(session)
                await asyncio.gather(*(self._poll_account(account) for account in accounts))
            await asyncio.sleep(self.settings.polling_interval_seconds)

    async def _poll_account(self, account: Account) -> None:
        cursor_key = f'cursor:{account.external_account_id}'
        since_id = await self.redis.get(cursor_key)
        comments = await self.client.fetch_new_comments(account, since_id)
        for item in comments:
            payload = CommentPayload(
                platform_comment_id=item['comment_id'],
                account_external_id=account.external_account_id,
                author=item['author'],
                content=item['content'],
                metadata=item,
            )
            if not await self._is_duplicate(payload.platform_comment_id):
                await self.queue.put(payload)
                await self.redis.set(cursor_key, payload.platform_comment_id, ex=86400 * 30)

    async def _is_duplicate(self, comment_id: str) -> bool:
        key = f'comment_seen:{comment_id}'
        added = await self.redis.set(key, '1', ex=86400, nx=True)
        return added is None

    @staticmethod
    async def _get_accounts(session: AsyncSession) -> Sequence[Account]:
        result = await session.execute(select(Account))
        return result.scalars().all()
