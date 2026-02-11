from datetime import datetime
from pydantic import BaseModel, Field


class SentimentResult(BaseModel):
    sentiment: str = Field(pattern='^(positive|neutral|negative)$')
    score: float = Field(ge=0, le=1)
    toxicity_score: float = Field(ge=0, le=1)


class CommentPayload(BaseModel):
    platform_comment_id: str
    account_external_id: str
    author: str
    content: str
    metadata: dict = Field(default_factory=dict)


class ProcessedComment(BaseModel):
    platform_comment_id: str
    account_id: int
    author: str
    content: str
    sentiment: SentimentResult
    risk_level: str
    risk_reasons: list[str]
    reply_suggestion: str
    raw_payload: dict


class CommentEventOut(BaseModel):
    id: int
    platform_comment_id: str
    risk_level: str
    sentiment: str
    toxicity_score: float
    reply_suggestion: str
    created_at: datetime


class AccountCreate(BaseModel):
    platform: str = 'mock_platform'
    external_account_id: str
    display_name: str
    access_token: str | None = None
