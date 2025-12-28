from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.deps import get_db
from src.db.models import Prediction, PredictionOutcome, PredictionResult
from src.db.schemas import (
    PredictionListResponse,
    PredictionOverride,
    PredictionResponse,
)

router = APIRouter()


@router.get("", response_model=PredictionListResponse)
async def list_predictions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    brand_id: Optional[UUID] = None,
    target_year: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """List predictions with optional filters."""
    query = select(Prediction).options(selectinload(Prediction.brand))
    count_query = select(func.count(Prediction.id))

    if brand_id:
        query = query.where(Prediction.brand_id == brand_id)
        count_query = count_query.where(Prediction.brand_id == brand_id)

    if target_year:
        query = query.where(Prediction.target_year == target_year)
        count_query = count_query.where(Prediction.target_year == target_year)

    # Get total
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Get predictions
    query = query.order_by(Prediction.predicted_start.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    predictions = list(result.scalars().all())

    return PredictionListResponse(
        predictions=[PredictionResponse.model_validate(p) for p in predictions],
        total=total,
    )


@router.get("/upcoming", response_model=PredictionListResponse)
async def get_upcoming_predictions(
    days: int = Query(7, ge=1, le=730),
    db: AsyncSession = Depends(get_db),
):
    """Get predictions starting within the next N days (up to 2 years)."""
    now = datetime.utcnow()
    end_date = now + timedelta(days=days)

    query = (
        select(Prediction)
        .options(selectinload(Prediction.brand))
        .where(Prediction.predicted_start >= now)
        .where(Prediction.predicted_start <= end_date)
        .order_by(Prediction.predicted_start)
    )

    result = await db.execute(query)
    predictions = list(result.scalars().all())

    return PredictionListResponse(
        predictions=[PredictionResponse.model_validate(p) for p in predictions],
        total=len(predictions),
    )


@router.get("/{prediction_id}", response_model=PredictionResponse)
async def get_prediction(
    prediction_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a prediction by ID."""
    query = (
        select(Prediction)
        .options(selectinload(Prediction.brand))
        .where(Prediction.id == prediction_id)
    )
    result = await db.execute(query)
    prediction = result.scalar_one_or_none()

    if prediction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found",
        )

    return PredictionResponse.model_validate(prediction)


@router.post("/{prediction_id}/override", response_model=PredictionResponse)
async def override_prediction(
    prediction_id: UUID,
    override: PredictionOverride,
    db: AsyncSession = Depends(get_db),
):
    """Override prediction outcome with manual result."""
    # Get prediction
    query = (
        select(Prediction)
        .options(selectinload(Prediction.brand), selectinload(Prediction.outcome))
        .where(Prediction.id == prediction_id)
    )
    result = await db.execute(query)
    prediction = result.scalar_one_or_none()

    if prediction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found",
        )

    # Create or update outcome
    if prediction.outcome is None:
        outcome = PredictionOutcome(
            prediction_id=prediction_id,
            result=override.result,
            is_override=True,
            override_reason=override.reason,
            verified_at=datetime.utcnow(),
        )
        db.add(outcome)
    else:
        prediction.outcome.result = override.result
        prediction.outcome.is_override = True
        prediction.outcome.override_reason = override.reason
        prediction.outcome.verified_at = datetime.utcnow()

    await db.flush()
    await db.refresh(prediction)

    return PredictionResponse.model_validate(prediction)
