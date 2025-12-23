"""Accuracy and suggestion API endpoints."""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.deps import get_db_session
from src.db.models import AdjustmentSuggestion, Brand, BrandAccuracyStats
from src.verifier.accuracy import AccuracyCalculator


router = APIRouter()


class OverallAccuracyResponse(BaseModel):
    """Response for overall accuracy stats."""
    total_predictions: int
    correct_predictions: int
    hit_rate: float
    brands_tracked: int
    avg_timing_delta_days: Optional[float]


class BrandAccuracyItem(BaseModel):
    """Per-brand accuracy stats."""
    brand_id: str
    brand_name: str
    total_predictions: int
    correct_predictions: int
    hit_rate: float
    avg_timing_delta_days: Optional[float]
    reliability_score: int
    reliability_tier: str

    class Config:
        from_attributes = True


class BrandAccuracyListResponse(BaseModel):
    """Response for brand accuracy breakdown."""
    brands: list[BrandAccuracyItem]


class SuggestionItem(BaseModel):
    """Adjustment suggestion item."""
    id: str
    brand_id: str
    brand_name: Optional[str]
    suggestion_type: str
    description: str
    recommended_action: str
    supporting_data: Optional[dict]
    status: str
    created_at: str

    class Config:
        from_attributes = True


class SuggestionListResponse(BaseModel):
    """Response for suggestions list."""
    suggestions: list[SuggestionItem]
    total: int


@router.get("", response_model=OverallAccuracyResponse)
async def get_overall_accuracy(
    db: AsyncSession = Depends(get_db_session),
):
    """Get overall prediction accuracy statistics."""
    calculator = AccuracyCalculator()
    stats = await calculator.get_overall_stats(db)

    return OverallAccuracyResponse(
        total_predictions=stats["total_predictions"],
        correct_predictions=stats["correct_predictions"],
        hit_rate=stats["hit_rate"],
        brands_tracked=stats["brands_tracked"],
        avg_timing_delta_days=stats["avg_timing_delta_days"],
    )


@router.get("/brands", response_model=BrandAccuracyListResponse)
async def get_brand_accuracy_breakdown(
    db: AsyncSession = Depends(get_db_session),
):
    """Get per-brand accuracy breakdown."""
    query = (
        select(BrandAccuracyStats)
        .options(selectinload(BrandAccuracyStats.brand_id))
        .order_by(BrandAccuracyStats.hit_rate.desc())
    )

    # Need to join with Brand to get names
    stats_query = select(BrandAccuracyStats)
    result = await db.execute(stats_query)
    all_stats = result.scalars().all()

    # Get brand names
    brand_ids = [s.brand_id for s in all_stats]
    if brand_ids:
        brands_query = select(Brand).where(Brand.id.in_(brand_ids))
        brands_result = await db.execute(brands_query)
        brands = {b.id: b for b in brands_result.scalars().all()}
    else:
        brands = {}

    items = []
    for stats in all_stats:
        brand = brands.get(stats.brand_id)
        items.append(BrandAccuracyItem(
            brand_id=str(stats.brand_id),
            brand_name=brand.name if brand else "Unknown",
            total_predictions=stats.total_predictions,
            correct_predictions=stats.correct_predictions,
            hit_rate=stats.hit_rate,
            avg_timing_delta_days=stats.avg_timing_delta_days,
            reliability_score=stats.reliability_score,
            reliability_tier=stats.reliability_tier,
        ))

    # Sort by hit rate descending
    items.sort(key=lambda x: x.hit_rate, reverse=True)

    return BrandAccuracyListResponse(brands=items)


@router.get("/brands/{brand_id}")
async def get_brand_accuracy(
    brand_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Get accuracy statistics for a specific brand."""
    query = select(BrandAccuracyStats).where(
        BrandAccuracyStats.brand_id == brand_id
    )
    result = await db.execute(query)
    stats = result.scalar_one_or_none()

    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand accuracy stats not found",
        )

    # Get brand name
    brand_query = select(Brand).where(Brand.id == brand_id)
    brand_result = await db.execute(brand_query)
    brand = brand_result.scalar_one_or_none()

    return BrandAccuracyItem(
        brand_id=str(stats.brand_id),
        brand_name=brand.name if brand else "Unknown",
        total_predictions=stats.total_predictions,
        correct_predictions=stats.correct_predictions,
        hit_rate=stats.hit_rate,
        avg_timing_delta_days=stats.avg_timing_delta_days,
        reliability_score=stats.reliability_score,
        reliability_tier=stats.reliability_tier,
    )


@router.get("/suggestions", response_model=SuggestionListResponse)
async def list_adjustment_suggestions(
    status_filter: str = Query(default="pending", alias="status"),
    db: AsyncSession = Depends(get_db_session),
):
    """List adjustment suggestions."""
    query = select(AdjustmentSuggestion)

    if status_filter != "all":
        query = query.where(AdjustmentSuggestion.status == status_filter)

    query = query.order_by(AdjustmentSuggestion.created_at.desc())

    result = await db.execute(query)
    suggestions = result.scalars().all()

    # Get brand names
    brand_ids = [s.brand_id for s in suggestions]
    if brand_ids:
        brands_query = select(Brand).where(Brand.id.in_(brand_ids))
        brands_result = await db.execute(brands_query)
        brands = {b.id: b for b in brands_result.scalars().all()}
    else:
        brands = {}

    items = []
    for suggestion in suggestions:
        brand = brands.get(suggestion.brand_id)
        items.append(SuggestionItem(
            id=str(suggestion.id),
            brand_id=str(suggestion.brand_id),
            brand_name=brand.name if brand else None,
            suggestion_type=suggestion.suggestion_type,
            description=suggestion.description,
            recommended_action=suggestion.recommended_action,
            supporting_data=suggestion.supporting_data,
            status=suggestion.status,
            created_at=str(suggestion.created_at),
        ))

    return SuggestionListResponse(suggestions=items, total=len(items))


@router.post("/suggestions/{suggestion_id}/approve")
async def approve_suggestion(
    suggestion_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Approve an adjustment suggestion."""
    query = select(AdjustmentSuggestion).where(
        AdjustmentSuggestion.id == suggestion_id
    )
    result = await db.execute(query)
    suggestion = result.scalar_one_or_none()

    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found",
        )

    suggestion.status = "approved"
    suggestion.resolved_at = datetime.utcnow()

    await db.commit()

    return {
        "status": "approved",
        "suggestion_id": str(suggestion_id),
    }


@router.post("/suggestions/{suggestion_id}/dismiss")
async def dismiss_suggestion(
    suggestion_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Dismiss an adjustment suggestion."""
    query = select(AdjustmentSuggestion).where(
        AdjustmentSuggestion.id == suggestion_id
    )
    result = await db.execute(query)
    suggestion = result.scalar_one_or_none()

    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found",
        )

    suggestion.status = "dismissed"
    suggestion.resolved_at = datetime.utcnow()

    await db.commit()

    return {
        "status": "dismissed",
        "suggestion_id": str(suggestion_id),
    }


@router.post("/recalculate")
async def recalculate_all_accuracy(
    db: AsyncSession = Depends(get_db_session),
):
    """Recalculate accuracy stats for all brands."""
    calculator = AccuracyCalculator()
    results = await calculator.update_all_brand_stats(db)

    return {
        "status": "completed",
        "brands_updated": len(results),
    }
