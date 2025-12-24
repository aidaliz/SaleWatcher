from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.db.models import (
    Brand,
    BrandAccuracyStats,
    Prediction,
    PredictionOutcome,
    PredictionResult,
    AdjustmentSuggestion,
    SuggestionStatus,
)
from src.db.schemas import (
    AccuracyStats,
    BrandAccuracy,
    BrandAccuracyListResponse,
    SuggestionResponse,
    SuggestionAction,
)

router = APIRouter()


@router.get("", response_model=AccuracyStats)
async def get_overall_accuracy(db: AsyncSession = Depends(get_db)):
    """Get overall prediction accuracy stats."""
    # Count predictions by outcome result
    query = (
        select(
            PredictionOutcome.result,
            func.count(PredictionOutcome.id).label("count"),
        )
        .group_by(PredictionOutcome.result)
    )

    result = await db.execute(query)
    counts = {row.result: row.count for row in result.all()}

    hits = counts.get(PredictionResult.HIT, 0)
    misses = counts.get(PredictionResult.MISS, 0)
    partials = counts.get(PredictionResult.PARTIAL, 0)
    pending = counts.get(PredictionResult.PENDING, 0)

    total = hits + misses + partials + pending
    verified = hits + misses + partials

    hit_rate = hits / verified if verified > 0 else 0.0

    return AccuracyStats(
        total_predictions=total,
        hits=hits,
        misses=misses,
        partials=partials,
        pending=pending,
        hit_rate=round(hit_rate, 3),
        verified_count=verified,
    )


@router.get("/brands", response_model=BrandAccuracyListResponse)
async def get_brand_accuracy(db: AsyncSession = Depends(get_db)):
    """Get accuracy stats per brand."""
    query = (
        select(BrandAccuracyStats, Brand.name)
        .join(Brand, BrandAccuracyStats.brand_id == Brand.id)
        .where(Brand.is_active == True)
        .order_by(BrandAccuracyStats.hit_rate.desc())
    )

    result = await db.execute(query)
    rows = result.all()

    brands = []
    for stats, brand_name in rows:
        brands.append(
            BrandAccuracy(
                brand_id=stats.brand_id,
                brand_name=brand_name,
                total_predictions=stats.total_predictions,
                hits=stats.hits,
                misses=stats.misses,
                partials=stats.partials,
                hit_rate=stats.hit_rate,
                reliability_tier=stats.reliability_tier,
            )
        )

    return BrandAccuracyListResponse(brands=brands)


@router.get("/suggestions", response_model=list[SuggestionResponse])
async def get_suggestions(
    status: SuggestionStatus = Query(SuggestionStatus.PENDING),
    db: AsyncSession = Depends(get_db),
):
    """Get adjustment suggestions."""
    query = (
        select(AdjustmentSuggestion)
        .where(AdjustmentSuggestion.status == status)
        .order_by(AdjustmentSuggestion.created_at.desc())
    )

    result = await db.execute(query)
    suggestions = list(result.scalars().all())

    return [SuggestionResponse.model_validate(s) for s in suggestions]
