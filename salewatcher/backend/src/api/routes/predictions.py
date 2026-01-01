from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.deps import get_db
from src.db.models import Prediction, PredictionOutcome, PredictionResult, SaleWindow, ExtractedSale, Brand
from src.db.schemas import (
    PredictionListResponse,
    PredictionOverride,
    PredictionResponse,
)

router = APIRouter()


class PredictionStats(BaseModel):
    """Statistics about predictions."""
    total_predictions: int
    upcoming_predictions: int
    past_predictions: int
    total_sale_windows: int
    total_extracted_sales: int
    by_brand: list[dict]


class GeneratePredictionsRequest(BaseModel):
    """Request to generate predictions."""
    brand_id: Optional[UUID] = None
    target_year: Optional[int] = None
    years_ahead: int = 1


class GeneratePredictionsResponse(BaseModel):
    """Response from prediction generation."""
    status: str
    windows_created: int
    predictions_created: int
    message: str


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


@router.get("/stats", response_model=PredictionStats)
async def get_prediction_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get prediction statistics."""
    now = datetime.utcnow()

    # Total predictions
    total_result = await db.execute(select(func.count(Prediction.id)))
    total_predictions = total_result.scalar_one()

    # Upcoming predictions
    upcoming_result = await db.execute(
        select(func.count(Prediction.id)).where(Prediction.predicted_start >= now)
    )
    upcoming_predictions = upcoming_result.scalar_one()

    # Past predictions
    past_predictions = total_predictions - upcoming_predictions

    # Total sale windows
    windows_result = await db.execute(select(func.count(SaleWindow.id)))
    total_sale_windows = windows_result.scalar_one()

    # Total extracted sales (is_sale=True)
    sales_result = await db.execute(
        select(func.count(ExtractedSale.id)).where(ExtractedSale.is_sale == True)
    )
    total_extracted_sales = sales_result.scalar_one()

    # By brand stats
    brand_query = (
        select(
            Brand.id,
            Brand.name,
            func.count(Prediction.id).label("prediction_count"),
        )
        .outerjoin(Prediction, Brand.id == Prediction.brand_id)
        .group_by(Brand.id, Brand.name)
        .order_by(func.count(Prediction.id).desc())
    )
    brand_result = await db.execute(brand_query)
    by_brand = [
        {"brand_id": str(row.id), "brand_name": row.name, "predictions": row.prediction_count}
        for row in brand_result.all()
    ]

    return PredictionStats(
        total_predictions=total_predictions,
        upcoming_predictions=upcoming_predictions,
        past_predictions=past_predictions,
        total_sale_windows=total_sale_windows,
        total_extracted_sales=total_extracted_sales,
        by_brand=by_brand,
    )


@router.post("/generate", response_model=GeneratePredictionsResponse)
async def generate_predictions_endpoint(
    request: GeneratePredictionsRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate predictions from extracted sales.

    This endpoint:
    1. Groups extracted sales (is_sale=True) into SaleWindows
    2. Generates Predictions for future years based on historical patterns
    """
    from src.deduplicator.grouper import create_sale_windows
    from src.predictor.generator import generate_predictions, generate_all_future_predictions

    # Step 1: Group sales into windows
    windows = await create_sale_windows(db, brand_id=request.brand_id)
    windows_created = len(windows)

    # Step 2: Generate predictions
    if request.target_year:
        predictions = await generate_predictions(
            db,
            target_year=request.target_year,
            brand_id=request.brand_id,
        )
        predictions_created = len(predictions)
    else:
        all_predictions = await generate_all_future_predictions(
            db,
            brand_id=request.brand_id,
            years_ahead=request.years_ahead,
        )
        predictions_created = sum(len(p) for p in all_predictions.values())

    return GeneratePredictionsResponse(
        status="success",
        windows_created=windows_created,
        predictions_created=predictions_created,
        message=f"Created {windows_created} sale windows and {predictions_created} predictions",
    )
