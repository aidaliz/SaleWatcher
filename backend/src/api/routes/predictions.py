"""Prediction API endpoints."""

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.db.crud import predictions as crud_predictions


router = APIRouter()


class BrandInfo(BaseModel):
    """Nested brand info."""
    id: UUID
    name: str

    class Config:
        from_attributes = True


class SaleWindowInfo(BaseModel):
    """Nested sale window info."""
    id: UUID
    name: str
    start_date: date
    end_date: date
    discount_summary: str | None

    class Config:
        from_attributes = True


class OutcomeInfo(BaseModel):
    """Nested outcome info."""
    id: UUID
    auto_result: str | None
    manual_override: bool
    manual_result: str | None
    actual_start: date | None
    actual_end: date | None
    timing_delta_days: int | None

    class Config:
        from_attributes = True


class PredictionItem(BaseModel):
    """Response model for prediction items."""
    id: UUID
    brand_id: UUID
    brand: BrandInfo | None
    source_window_id: UUID
    predicted_start: date
    predicted_end: date
    discount_summary: str | None
    milled_reference_url: str | None
    confidence: float
    calendar_event_id: str | None
    notified_at: str | None

    class Config:
        from_attributes = True


class PredictionDetail(PredictionItem):
    """Detailed prediction response."""
    source_window: SaleWindowInfo | None
    outcome: OutcomeInfo | None


class PredictionListResponse(BaseModel):
    """Response for list of predictions."""
    predictions: list[PredictionItem]
    total: int


class UpcomingPredictionsResponse(BaseModel):
    """Response for upcoming predictions."""
    predictions: list[PredictionDetail]
    total: int


class OutcomeResponse(BaseModel):
    """Response for prediction outcome."""
    id: UUID
    prediction_id: UUID
    auto_result: str | None
    auto_verified_at: str | None
    manual_override: bool
    manual_result: str | None
    override_reason: str | None
    overridden_at: str | None
    actual_start: date | None
    actual_end: date | None
    actual_discount: float | None
    timing_delta_days: int | None
    discount_delta_percent: float | None

    class Config:
        from_attributes = True


class OverrideRequest(BaseModel):
    """Request to override prediction outcome."""
    result: Literal["hit", "miss", "partial"]
    reason: str | None = None


@router.get("", response_model=PredictionListResponse)
async def list_predictions(
    skip: int = 0,
    limit: int = 100,
    brand_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    """List all predictions with optional filtering."""
    predictions, total = await crud_predictions.get_predictions(
        db,
        skip=skip,
        limit=limit,
        brand_id=brand_id,
        start_date=start_date,
        end_date=end_date,
    )

    items = []
    for p in predictions:
        items.append(PredictionItem(
            id=p.id,
            brand_id=p.brand_id,
            brand=BrandInfo(id=p.brand.id, name=p.brand.name) if p.brand else None,
            source_window_id=p.source_window_id,
            predicted_start=p.predicted_start,
            predicted_end=p.predicted_end,
            discount_summary=p.discount_summary,
            milled_reference_url=p.milled_reference_url,
            confidence=p.confidence,
            calendar_event_id=p.calendar_event_id,
            notified_at=str(p.notified_at) if p.notified_at else None,
        ))

    return PredictionListResponse(predictions=items, total=total)


@router.get("/upcoming", response_model=UpcomingPredictionsResponse)
async def list_upcoming_predictions(
    days: int = Query(default=14, ge=1, le=90),
    brand_id: UUID | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    """List predictions for the next N days."""
    predictions = await crud_predictions.get_upcoming_predictions(
        db,
        days=days,
        brand_id=brand_id,
    )

    items = []
    for p in predictions:
        source_window_info = None
        if p.source_window:
            source_window_info = SaleWindowInfo(
                id=p.source_window.id,
                name=p.source_window.name,
                start_date=p.source_window.start_date,
                end_date=p.source_window.end_date,
                discount_summary=p.source_window.discount_summary,
            )

        outcome_info = None
        if p.outcome:
            outcome_info = OutcomeInfo(
                id=p.outcome.id,
                auto_result=p.outcome.auto_result,
                manual_override=p.outcome.manual_override,
                manual_result=p.outcome.manual_result,
                actual_start=p.outcome.actual_start,
                actual_end=p.outcome.actual_end,
                timing_delta_days=p.outcome.timing_delta_days,
            )

        items.append(PredictionDetail(
            id=p.id,
            brand_id=p.brand_id,
            brand=BrandInfo(id=p.brand.id, name=p.brand.name) if p.brand else None,
            source_window_id=p.source_window_id,
            predicted_start=p.predicted_start,
            predicted_end=p.predicted_end,
            discount_summary=p.discount_summary,
            milled_reference_url=p.milled_reference_url,
            confidence=p.confidence,
            calendar_event_id=p.calendar_event_id,
            notified_at=str(p.notified_at) if p.notified_at else None,
            source_window=source_window_info,
            outcome=outcome_info,
        ))

    return UpcomingPredictionsResponse(predictions=items, total=len(items))


@router.get("/{prediction_id}", response_model=PredictionDetail)
async def get_prediction(
    prediction_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Get a specific prediction by ID."""
    prediction = await crud_predictions.get_prediction(db, prediction_id)
    if not prediction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found",
        )

    source_window_info = None
    if prediction.source_window:
        source_window_info = SaleWindowInfo(
            id=prediction.source_window.id,
            name=prediction.source_window.name,
            start_date=prediction.source_window.start_date,
            end_date=prediction.source_window.end_date,
            discount_summary=prediction.source_window.discount_summary,
        )

    outcome_info = None
    if prediction.outcome:
        outcome_info = OutcomeInfo(
            id=prediction.outcome.id,
            auto_result=prediction.outcome.auto_result,
            manual_override=prediction.outcome.manual_override,
            manual_result=prediction.outcome.manual_result,
            actual_start=prediction.outcome.actual_start,
            actual_end=prediction.outcome.actual_end,
            timing_delta_days=prediction.outcome.timing_delta_days,
        )

    return PredictionDetail(
        id=prediction.id,
        brand_id=prediction.brand_id,
        brand=BrandInfo(id=prediction.brand.id, name=prediction.brand.name) if prediction.brand else None,
        source_window_id=prediction.source_window_id,
        predicted_start=prediction.predicted_start,
        predicted_end=prediction.predicted_end,
        discount_summary=prediction.discount_summary,
        milled_reference_url=prediction.milled_reference_url,
        confidence=prediction.confidence,
        calendar_event_id=prediction.calendar_event_id,
        notified_at=str(prediction.notified_at) if prediction.notified_at else None,
        source_window=source_window_info,
        outcome=outcome_info,
    )


@router.get("/{prediction_id}/outcome", response_model=OutcomeResponse)
async def get_prediction_outcome(
    prediction_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Get the outcome of a prediction if it exists."""
    outcome = await crud_predictions.get_prediction_outcome(db, prediction_id)
    if not outcome:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outcome not found",
        )

    return OutcomeResponse(
        id=outcome.id,
        prediction_id=outcome.prediction_id,
        auto_result=outcome.auto_result,
        auto_verified_at=str(outcome.auto_verified_at) if outcome.auto_verified_at else None,
        manual_override=outcome.manual_override,
        manual_result=outcome.manual_result,
        override_reason=outcome.override_reason,
        overridden_at=str(outcome.overridden_at) if outcome.overridden_at else None,
        actual_start=outcome.actual_start,
        actual_end=outcome.actual_end,
        actual_discount=outcome.actual_discount,
        timing_delta_days=outcome.timing_delta_days,
        discount_delta_percent=outcome.discount_delta_percent,
    )


@router.post("/{prediction_id}/override")
async def override_prediction_outcome(
    prediction_id: UUID,
    request: OverrideRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Manually override a prediction's auto-verified outcome."""
    outcome = await crud_predictions.override_prediction_outcome(
        db,
        prediction_id,
        result=request.result,
        reason=request.reason,
    )

    if not outcome:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found",
        )

    return {
        "status": "overridden",
        "prediction_id": str(prediction_id),
        "result": request.result,
    }
