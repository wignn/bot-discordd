import json
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from workers.ai.providers.base import AIProvider, AIResponse
from workers.ai.providers.factory import get_ai_provider
from workers.ai.translator import NewsTranslator
from workers.ai.summarizer import NewsSummarizer
from workers.ai.sentiment_analyzer import SentimentAnalyzer
from workers.ai.entity_extractor import EntityExtractor
from workers.ai.impact_analyzer import ImpactAnalyzer


@dataclass
class ProcessedArticle:
    original_title: str
    original_content: str
    source_url: str
    
    translated_title: str = ""
    translated_content: str = ""
    
    summary: str = ""
    summary_bullets: list[str] = field(default_factory=list)
    
    sentiment: str = "neutral"
    sentiment_confidence: float = 0.5
    sentiment_reasoning: str = ""
    
    currencies: list[str] = field(default_factory=list)
    currency_pairs: list[str] = field(default_factory=list)
    organizations: list[str] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    
    impact_level: str = "low"
    impact_score: int = 1
    trading_recommendation: dict = field(default_factory=dict)
    
    processed_at: datetime = field(default_factory=datetime.utcnow)
    processing_time_ms: float = 0.0
    tokens_used: int = 0
    
    def to_dict(self) -> dict:
        return {
            "content": {
                "original": {
                    "title": self.original_title,
                    "content": self.original_content,
                },
                "translated": {
                    "title": self.translated_title,
                    "content": self.translated_content,
                },
                "summary": self.summary,
                "summary_bullets": self.summary_bullets,
            },
            "analysis": {
                "sentiment": {
                    "value": self.sentiment,
                    "confidence": self.sentiment_confidence,
                    "reasoning": self.sentiment_reasoning,
                },
                "impact": {
                    "level": self.impact_level,
                    "score": self.impact_score,
                    "recommendation": self.trading_recommendation,
                },
                "entities": {
                    "currencies": self.currencies,
                    "currency_pairs": self.currency_pairs,
                    "organizations": self.organizations,
                    "people": self.people,
                    "events": self.events,
                },
            },
            "metadata": {
                "source_url": self.source_url,
                "processed_at": self.processed_at.isoformat(),
                "processing_time_ms": self.processing_time_ms,
                "tokens_used": self.tokens_used,
            },
        }


class NewsProcessor:

    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider or get_ai_provider()
        self.translator = NewsTranslator(self.provider)
        self.summarizer = NewsSummarizer(self.provider)
        self.sentiment_analyzer = SentimentAnalyzer(self.provider)
        self.entity_extractor = EntityExtractor(self.provider)
        self.impact_analyzer = ImpactAnalyzer(self.provider)

    async def process_article(
        self,
        title: str,
        content: str,
        source_url: str = "",
        translate: bool = True,
        analyze_sentiment: bool = True,
        analyze_impact: bool = True,
        extract_entities: bool = True,
    ) -> ProcessedArticle:
        import time
        start_time = time.perf_counter()
        total_tokens = 0

        result = ProcessedArticle(
            original_title=title,
            original_content=content,
            source_url=source_url,
        )

        tasks = []
        
        if translate:
            tasks.append(("translate_title", self.translator.translate_title(title)))
            tasks.append(("translate_content", self.translator.translate(content)))
        
        tasks.append(("summarize", self.summarizer.summarize(content, style="bullet")))

        task_names = [t[0] for t in tasks]
        task_coros = [t[1] for t in tasks]
        responses = await asyncio.gather(*task_coros, return_exceptions=True)

        for name, response in zip(task_names, responses):
            if isinstance(response, Exception):
                continue
            
            total_tokens += response.tokens_used
            
            if name == "translate_title":
                result.translated_title = response.content
            elif name == "translate_content":
                result.translated_content = response.content
            elif name == "summarize":
                result.summary = response.content
                try:
                    lines = response.content.strip().split("\n")
                    result.summary_bullets = [
                        l.strip().lstrip("•-*123456789. ")
                        for l in lines
                        if l.strip()
                    ]
                except Exception:
                    pass

        analysis_tasks = []
        
        if analyze_sentiment:
            analysis_tasks.append(("sentiment", self.sentiment_analyzer.analyze(content)))
        
        if analyze_impact:
            analysis_tasks.append(("impact", self.impact_analyzer.analyze(content)))
        
        if extract_entities:
            analysis_tasks.append(("entities", self.entity_extractor.extract(content)))

        if analysis_tasks:
            task_names = [t[0] for t in analysis_tasks]
            task_coros = [t[1] for t in analysis_tasks]
            responses = await asyncio.gather(*task_coros, return_exceptions=True)

            for name, response in zip(task_names, responses):
                if isinstance(response, Exception):
                    continue
                
                total_tokens += response.tokens_used

                try:
                    data = json.loads(response.content)
                except json.JSONDecodeError:
                    continue

                if name == "sentiment":
                    result.sentiment = data.get("sentiment", "neutral")
                    result.sentiment_confidence = data.get("confidence", 0.5)
                    result.sentiment_reasoning = data.get("reasoning", "")
                
                elif name == "impact":
                    result.impact_level = data.get("impact_level", "low")
                    result.impact_score = data.get("impact_score", 1)
                    result.trading_recommendation = data.get("trading_recommendation", {})
                
                elif name == "entities":
                    result.currencies = data.get("currencies", [])
                    result.currency_pairs = data.get("currency_pairs", [])
                    result.organizations = data.get("organizations", [])
                    result.people = data.get("people", [])
                    result.events = data.get("events", [])

        result.processing_time_ms = (time.perf_counter() - start_time) * 1000
        result.tokens_used = total_tokens
        result.processed_at = datetime.utcnow()

        return result

    async def quick_process(
        self,
        title: str,
        content: str,
    ) -> dict:
        tasks = [
            self.translator.translate_title(title),
            self.summarizer.summarize(content[:1000], style="brief"),
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            "translated_title": responses[0].content if not isinstance(responses[0], Exception) else "",
            "summary": responses[1].content if not isinstance(responses[1], Exception) else "",
        }
