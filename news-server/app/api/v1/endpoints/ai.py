from typing import Literal
from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException

from workers.ai.providers.factory import get_ai_provider, AIProviderFactory
from workers.ai.translator import NewsTranslator
from workers.ai.summarizer import NewsSummarizer
from workers.ai.sentiment_analyzer import SentimentAnalyzer
from workers.ai.entity_extractor import EntityExtractor
from workers.ai.impact_analyzer import ImpactAnalyzer
from workers.ai.processor import NewsProcessor


router = APIRouter()


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=10, max_length=10000)
    target_language: str = "Indonesian"


class SummarizeRequest(BaseModel):
    text: str = Field(..., min_length=50, max_length=20000)
    style: Literal["brief", "detailed", "bullet", "forex_impact"] = "brief"


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=50, max_length=20000)


class ProcessArticleRequest(BaseModel):
    title: str = Field(..., min_length=5, max_length=500)
    content: str = Field(..., min_length=50, max_length=30000)
    source_url: str = ""
    translate: bool = True
    analyze_sentiment: bool = True
    analyze_impact: bool = True
    extract_entities: bool = True


@router.get("/providers")
async def list_providers():
    from app.core.config import settings
    
    return {
        "primary_provider": settings.ai_primary_provider,
        "providers": {
            "groq": {
                "available": bool(settings.groq_api_key),
                "models": [
                    settings.groq_model_fast,
                    settings.groq_model_quality,
                    settings.groq_model_mixtral,
                ],
                "rate_limit": f"{settings.groq_rpm} RPM",
            },
            "gemini": {
                "available": bool(settings.gemini_api_key),
                "models": [settings.gemini_model],
                "rate_limit": f"{settings.gemini_rpm} RPM, {settings.gemini_tpd} RPD",
            },
            "openrouter": {
                "available": bool(settings.openrouter_api_key),
                "models": [settings.openrouter_model],
                "rate_limit": "Varies by model",
            },
        },
    }


@router.post("/translate")
async def translate_text(request: TranslateRequest):
    try:
        provider = get_ai_provider()
        translator = NewsTranslator(provider)
        response = await translator.translate(
            text=request.text,
            target_language=request.target_language,
        )
        return {
            "original": request.text,
            "translated": response.content,
            "target_language": request.target_language,
            "provider": response.provider,
            "model": response.model,
            "tokens_used": response.tokens_used,
            "latency_ms": response.latency_ms,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summarize")
async def summarize_text(request: SummarizeRequest):
    try:
        provider = get_ai_provider()
        summarizer = NewsSummarizer(provider)
        response = await summarizer.summarize(
            text=request.text,
            style=request.style,
        )
        return {
            "summary": response.content,
            "style": request.style,
            "provider": response.provider,
            "model": response.model,
            "tokens_used": response.tokens_used,
            "latency_ms": response.latency_ms,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sentiment")
async def analyze_sentiment(request: AnalyzeRequest):
    try:
        provider = get_ai_provider()
        analyzer = SentimentAnalyzer(provider)
        response = await analyzer.analyze(request.text)
        
        import json
        try:
            result = json.loads(response.content)
        except json.JSONDecodeError:
            result = {"raw": response.content}
        
        return {
            "analysis": result,
            "provider": response.provider,
            "model": response.model,
            "tokens_used": response.tokens_used,
            "latency_ms": response.latency_ms,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/entities")
async def extract_entities(request: AnalyzeRequest):
    try:
        provider = get_ai_provider()
        extractor = EntityExtractor(provider)
        response = await extractor.extract(request.text)
        
        import json
        try:
            result = json.loads(response.content)
        except json.JSONDecodeError:
            result = {"raw": response.content}
        
        return {
            "entities": result,
            "provider": response.provider,
            "model": response.model,
            "tokens_used": response.tokens_used,
            "latency_ms": response.latency_ms,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/impact")
async def analyze_impact(request: AnalyzeRequest):
    try:
        provider = get_ai_provider()
        analyzer = ImpactAnalyzer(provider)
        response = await analyzer.analyze(request.text)
        
        import json
        try:
            result = json.loads(response.content)
        except json.JSONDecodeError:
            result = {"raw": response.content}
        
        return {
            "impact": result,
            "provider": response.provider,
            "model": response.model,
            "tokens_used": response.tokens_used,
            "latency_ms": response.latency_ms,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process")
async def process_article(request: ProcessArticleRequest):
    try:
        provider = get_ai_provider()
        processor = NewsProcessor(provider)
        
        result = await processor.process_article(
            title=request.title,
            content=request.content,
            source_url=request.source_url,
            translate=request.translate,
            analyze_sentiment=request.analyze_sentiment,
            analyze_impact=request.analyze_impact,
            extract_entities=request.extract_entities,
        )
        
        return result.to_dict()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def ai_health_check():
    from app.core.config import settings
    
    results = {}
    
    if settings.groq_api_key:
        try:
            provider = AIProviderFactory.create("groq")
            healthy = await provider.health_check()
            results["groq"] = {"status": "healthy" if healthy else "unhealthy"}
        except Exception as e:
            results["groq"] = {"status": "error", "message": str(e)}
    else:
        results["groq"] = {"status": "not_configured"}

    if settings.gemini_api_key:
        try:
            provider = AIProviderFactory.create("gemini")
            healthy = await provider.health_check()
            results["gemini"] = {"status": "healthy" if healthy else "unhealthy"}
        except Exception as e:
            results["gemini"] = {"status": "error", "message": str(e)}
    else:
        results["gemini"] = {"status": "not_configured"}

    if settings.openrouter_api_key:
        try:
            provider = AIProviderFactory.create("openrouter")
            healthy = await provider.health_check()
            results["openrouter"] = {"status": "healthy" if healthy else "unhealthy"}
        except Exception as e:
            results["openrouter"] = {"status": "error", "message": str(e)}
    else:
        results["openrouter"] = {"status": "not_configured"}

    return {
        "primary_provider": settings.ai_primary_provider,
        "providers": results,
    }
