from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import get_settings
from app.schemas import SentimentResult

ATTACK_WORDS = {
    '垃圾', '骗子', '投诉', 'sb', '傻', '滚', '诈骗', '失望', '退钱', 'fuck', 'idiot', 'stupid'
}


@dataclass
class RiskAssessment:
    level: str
    reasons: list[str]


class SentimentAnalyzer:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._transformer_pipe = None
        self._openai_client = None

    async def analyze(self, text: str) -> SentimentResult:
        provider = self.settings.sentiment_provider.lower()
        if provider == 'openai':
            return await self._analyze_openai(text)
        if provider == 'transformers':
            return await self._analyze_transformers(text)
        return self._analyze_mock(text)

    async def _analyze_transformers(self, text: str) -> SentimentResult:
        if self._transformer_pipe is None:
            from transformers import pipeline

            self._transformer_pipe = pipeline('sentiment-analysis')

        result = self._transformer_pipe(text[:512])[0]
        label = result['label'].lower()
        score = float(result['score'])

        if 'neg' in label:
            sentiment = 'negative'
        elif 'pos' in label:
            sentiment = 'positive'
        else:
            sentiment = 'neutral'

        toxicity = self._estimate_toxicity(text, sentiment)
        return SentimentResult(sentiment=sentiment, score=round(score, 4), toxicity_score=toxicity)

    async def _analyze_openai(self, text: str) -> SentimentResult:
        if self._openai_client is None:
            from openai import AsyncOpenAI

            self._openai_client = AsyncOpenAI(api_key=self.settings.openai_api_key)

        prompt = (
            'You are a sentiment and toxicity classifier. Return strict JSON with keys '
            'sentiment(positive|neutral|negative), score(0-1), toxicity_score(0-1). '
            f'Text: {text}'
        )
        response = await self._openai_client.responses.create(
            model=self.settings.openai_model,
            input=prompt,
            temperature=0,
        )
        content = response.output_text
        import json

        data = json.loads(content)
        return SentimentResult(**data)

    def _analyze_mock(self, text: str) -> SentimentResult:
        lowered = text.lower()
        negative_hits = sum(1 for w in ATTACK_WORDS if w in lowered)
        if negative_hits >= 2:
            sentiment = 'negative'
            score = min(1.0, 0.7 + 0.05 * negative_hits)
        elif negative_hits == 1:
            sentiment = 'neutral'
            score = 0.55
        else:
            sentiment = 'positive'
            score = 0.75
        return SentimentResult(
            sentiment=sentiment,
            score=score,
            toxicity_score=self._estimate_toxicity(text, sentiment),
        )

    def _estimate_toxicity(self, text: str, sentiment: str) -> float:
        lowered = text.lower()
        hits = sum(1 for w in ATTACK_WORDS if w in lowered)
        base = 0.2 if sentiment != 'negative' else 0.45
        return round(min(1.0, base + hits * 0.15), 4)


class CommentProcessor:
    def __init__(self) -> None:
        self.analyzer = SentimentAnalyzer()

    def clean_text(self, text: str) -> str:
        text = re.sub(r'https?://\S+', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    async def process(self, text: str) -> tuple[SentimentResult, RiskAssessment]:
        cleaned = self.clean_text(text)
        sentiment_result = await self.analyzer.analyze(cleaned)
        risk = self._assess_risk(cleaned, sentiment_result)
        return sentiment_result, risk

    def _assess_risk(self, text: str, sentiment: SentimentResult) -> RiskAssessment:
        lowered = text.lower()
        has_attack_word = any(w in lowered for w in ATTACK_WORDS)

        reasons: list[str] = []
        if sentiment.sentiment == 'negative':
            reasons.append('negative_sentiment')
        if sentiment.toxicity_score > 0.7:
            reasons.append('high_toxicity')
        if has_attack_word:
            reasons.append('attack_words')

        if sentiment.sentiment == 'negative' and sentiment.toxicity_score > 0.7 and has_attack_word:
            return RiskAssessment(level='high', reasons=reasons)
        if sentiment.sentiment == 'negative' or sentiment.score > 0.75 and sentiment.sentiment != 'positive':
            return RiskAssessment(level='medium', reasons=reasons or ['clear_negative_emotion'])
        return RiskAssessment(level='low', reasons=reasons or ['normal_complaint'])
