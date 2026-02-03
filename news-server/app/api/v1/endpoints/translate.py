from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException
import httpx
import time

from app.core.config import settings
from app.core.logging import get_logger


router = APIRouter()
logger = get_logger(__name__)


class TranslateArticleRequest(BaseModel):
    id: str = Field(default="")
    original_title: str = Field(..., min_length=1, max_length=500)
    summary: str = Field(default="", max_length=5000)
    source_name: str = Field(default="Unknown")
    source_url: str = Field(default="")
    url: str = Field(default="")
    target_language: str = Field(default="Indonesian")


class TranslateArticleResponse(BaseModel):
    id: str
    original_title: str
    translated_title: str
    summary: str
    summary_id: str
    source_name: str
    source_url: str
    url: str
    sentiment: str = "neutral"
    sentiment_confidence: float = 0.5
    impact_level: str = "medium"
    impact_score: int = 5
    currency_pairs: list[str] = []
    currencies: list[str] = []
    published_at: Optional[str] = None
    image_url: Optional[str] = None
    provider: str = ""
    model: str = ""
    latency_ms: int = 0


class SimpleTranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    target_language: str = Field(default="Indonesian")


class SimpleTranslateResponse(BaseModel):
    original: str
    translated: str
    target_language: str
    provider: str
    model: str
    latency_ms: int


async def translate_with_gemini(text: str, target_language: str) -> tuple[str, str, str, int]:
    import google.generativeai as genai
    
    if not settings.gemini_api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")
    
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(settings.gemini_model)
    
    prompt = f"""Translate the following text to {target_language}.
Keep currency pairs (EUR/USD, GBP/JPY) and financial terms (NFP, CPI, FOMC, hawkish, dovish) in English.
Return ONLY the translation, no explanations.

Text: {text}"""
    
    start = time.time()
    response = await model.generate_content_async(prompt)
    latency = int((time.time() - start) * 1000)
    
    return response.text.strip(), "gemini", settings.gemini_model, latency


async def translate_with_groq(text: str, target_language: str) -> tuple[str, str, str, int]:
    if not settings.groq_api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")
    
    prompt = f"""Translate the following text to {target_language}.
Keep currency pairs (EUR/USD, GBP/JPY) and financial terms (NFP, CPI, FOMC, hawkish, dovish) in English.
Return ONLY the translation, no explanations.

Text: {text}"""
    
    start = time.time()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.groq_model_fast,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 2048,
            },
        )
        response.raise_for_status()
        data = response.json()
    
    latency = int((time.time() - start) * 1000)
    translated = data["choices"][0]["message"]["content"].strip()
    
    return translated, "groq", settings.groq_model_fast, latency


async def translate_with_openrouter(text: str, target_language: str) -> tuple[str, str, str, int]:
    if not settings.openrouter_api_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not configured")
    
    prompt = f"""Translate the following text to {target_language}.
Keep currency pairs (EUR/USD, GBP/JPY) and financial terms (NFP, CPI, FOMC, hawkish, dovish) in English.
Return ONLY the translation, no explanations.

Text: {text}"""
    
    start = time.time()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.openrouter_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 2048,
            },
        )
        response.raise_for_status()
        data = response.json()
    
    latency = int((time.time() - start) * 1000)
    translated = data["choices"][0]["message"]["content"].strip()
    
    return translated, "openrouter", settings.openrouter_model, latency


async def translate_text(text: str, target_language: str = "Indonesian") -> tuple[str, str, str, int]:
    provider = settings.ai_primary_provider
    
    try:
        if provider == "gemini":
            return await translate_with_gemini(text, target_language)
        elif provider == "groq":
            return await translate_with_groq(text, target_language)
        elif provider == "openrouter":
            return await translate_with_openrouter(text, target_language)
        else:
            return await translate_with_gemini(text, target_language)
    except Exception as primary_error:
        logger.warning(f"Primary provider {provider} failed: {primary_error}")
        
        for fallback in ["gemini", "groq", "openrouter"]:
            if fallback == provider:
                continue
            try:
                if fallback == "gemini" and settings.gemini_api_key:
                    return await translate_with_gemini(text, target_language)
                elif fallback == "groq" and settings.groq_api_key:
                    return await translate_with_groq(text, target_language)
                elif fallback == "openrouter" and settings.openrouter_api_key:
                    return await translate_with_openrouter(text, target_language)
            except Exception:
                continue
        
        raise HTTPException(status_code=500, detail=f"All translation providers failed: {primary_error}")


@router.post("/text", response_model=SimpleTranslateResponse)
async def translate_simple(request: SimpleTranslateRequest) -> SimpleTranslateResponse:
    translated, provider, model, latency = await translate_text(
        request.text, 
        request.target_language
    )
    
    return SimpleTranslateResponse(
        original=request.text,
        translated=translated,
        target_language=request.target_language,
        provider=provider,
        model=model,
        latency_ms=latency,
    )


@router.post("/article", response_model=TranslateArticleResponse)
async def translate_article(request: TranslateArticleRequest) -> TranslateArticleResponse:
    translated_title = ""
    provider = ""
    model = ""
    latency = 0
    
    if request.original_title:
        translated_title, provider, model, latency = await translate_text(
            request.original_title,
            request.target_language
        )
    
    summary_id = ""
    if request.summary:
        summary_id, _, _, summary_latency = await translate_text(
            request.summary,
            request.target_language
        )
        latency += summary_latency
    
    return TranslateArticleResponse(
        id=request.id,
        original_title=request.original_title,
        translated_title=translated_title,
        summary=request.summary,
        summary_id=summary_id,
        source_name=request.source_name,
        source_url=request.source_url,
        url=request.url,
        provider=provider,
        model=model,
        latency_ms=latency,
    )


@router.get("/providers")
async def list_translation_providers():
    return {
        "primary_provider": settings.ai_primary_provider,
        "providers": {
            "gemini": {
                "available": bool(settings.gemini_api_key),
                "model": settings.gemini_model,
            },
            "groq": {
                "available": bool(settings.groq_api_key),
                "model": settings.groq_model_fast,
            },
            "openrouter": {
                "available": bool(settings.openrouter_api_key),
                "model": settings.openrouter_model,
            },
        },
    }
