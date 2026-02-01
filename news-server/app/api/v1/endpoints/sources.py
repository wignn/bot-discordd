from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.schemas import NewsSourceCreate, NewsSourceResponse


router = APIRouter()


@router.get("")
async def list_sources(
    is_active: Optional[bool] = None,
    source_type: Optional[str] = None,
    category: Optional[str] = None,
):
    return {"items": [], "count": 0}


@router.post("", response_model=NewsSourceResponse)
async def create_source(source: NewsSourceCreate):
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{source_id}", response_model=NewsSourceResponse)
async def get_source(source_id: UUID):
    raise HTTPException(status_code=404, detail="Source not found")


@router.put("/{source_id}", response_model=NewsSourceResponse)
async def update_source(source_id: UUID, source: NewsSourceCreate):
    raise HTTPException(status_code=404, detail="Source not found")


@router.delete("/{source_id}")
async def delete_source(source_id: UUID):
    return {"message": "Source deleted", "id": str(source_id)}


@router.post("/{source_id}/fetch")
async def trigger_fetch(source_id: UUID):
    return {"message": "Fetch queued", "source_id": str(source_id)}


@router.get("/{source_id}/stats")
async def get_source_stats(source_id: UUID):
    return {
        "source_id": str(source_id),
        "total_articles": 0,
        "articles_today": 0,
        "average_reliability": 0.0,
        "last_fetched_at": None,
    }
