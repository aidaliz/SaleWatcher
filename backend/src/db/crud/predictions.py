"""CRUD operations for Prediction and related models."""

from datetime import date, datetime, timedelta
from typing import Literal, Optional
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Brand, Prediction, PredictionOutcome, SaleWindow


async def get_predictions(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    brand_id: Optional[UUID] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> tuple[list[Prediction], int]:
    """
    Get predictions with optional filtering.

    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum records to return
        brand_id: Filter by brand
        start_date: Filter by predicted_start >= this date
        end_date: Filter by predicted_start <= this date

    Returns:
        Tuple of (predictions, total_count)
    """
    # Build query
    query = select(Prediction).options(
        selectinload(Prediction.brand),
        selectinload(Prediction.source_window),
        selectinload(Prediction.outcome),
    )

    # Apply filters
    if brand_id:
        query = query.where(Prediction.brand_id == brand_id)
    if start_date:
        query = query.where(Prediction.predicted_start >= start_date)
    if end_date:
        query = query.where(Prediction.predicted_start <= end_date)

    # Get count
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Get paginated results
    query = query.order_by(Prediction.predicted_start.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    predictions = list(result.scalars().all())

    return predictions, total


async def get_upcoming_predictions(
    db: AsyncSession,
    days: int = 14,
    brand_id: Optional[UUID] = None,
) -> list[Prediction]:
    """Get predictions for the upcoming period."""
    today = date.today()
    end_date = today + timedelta(days=days)

    query = (
        select(Prediction)
        .where(Prediction.predicted_start >= today)
        .where(Prediction.predicted_start <= end_date)
        .options(
            selectinload(Prediction.brand),
            selectinload(Prediction.source_window),
            selectinload(Prediction.outcome),
        )
        .order_by(Prediction.predicted_start.asc())
    )

    if brand_id:
        query = query.where(Prediction.brand_id == brand_id)

    result = await db.execute(query)
    return list(result.scalars().all())


async def get_prediction(
    db: AsyncSession,
    prediction_id: UUID,
) -> Optional[Prediction]:
    """Get a single prediction by ID."""
    query = (
        select(Prediction)
        .where(Prediction.id == prediction_id)
        .options(
            selectinload(Prediction.brand),
            selectinload(Prediction.source_window),
            selectinload(Prediction.outcome),
        )
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_prediction_outcome(
    db: AsyncSession,
    prediction_id: UUID,
) -> Optional[PredictionOutcome]:
    """Get the outcome for a prediction."""
    query = (
        select(PredictionOutcome)
        .where(PredictionOutcome.prediction_id == prediction_id)
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def create_prediction_outcome(
    db: AsyncSession,
    prediction_id: UUID,
    auto_result: Optional[str] = None,
    matched_email_ids: Optional[list[UUID]] = None,
) -> PredictionOutcome:
    """Create an auto-verified outcome for a prediction."""
    outcome = PredictionOutcome(
        prediction_id=prediction_id,
        auto_result=auto_result,
        auto_verified_at=datetime.utcnow() if auto_result else None,
        matched_email_ids=matched_email_ids or [],
    )
    db.add(outcome)
    await db.commit()
    await db.refresh(outcome)
    return outcome


async def override_prediction_outcome(
    db: AsyncSession,
    prediction_id: UUID,
    result: Literal["hit", "miss", "partial"],
    reason: Optional[str] = None,
) -> Optional[PredictionOutcome]:
    """
    Manually override a prediction's outcome.

    Creates the outcome if it doesn't exist.
    """
    # Get or create outcome
    outcome = await get_prediction_outcome(db, prediction_id)

    if not outcome:
        # Check prediction exists
        prediction = await get_prediction(db, prediction_id)
        if not prediction:
            return None

        outcome = PredictionOutcome(
            prediction_id=prediction_id,
            manual_override=True,
            manual_result=result,
            override_reason=reason,
            overridden_at=datetime.utcnow(),
        )
        db.add(outcome)
    else:
        outcome.manual_override = True
        outcome.manual_result = result
        outcome.override_reason = reason
        outcome.overridden_at = datetime.utcnow()

    await db.commit()
    await db.refresh(outcome)
    return outcome


async def get_predictions_needing_verification(
    db: AsyncSession,
    limit: int = 100,
) -> list[Prediction]:
    """Get predictions that have passed their end date and need verification."""
    today = date.today()

    query = (
        select(Prediction)
        .outerjoin(PredictionOutcome)
        .where(Prediction.predicted_end < today)
        .where(PredictionOutcome.id.is_(None))  # No outcome yet
        .options(
            selectinload(Prediction.brand),
        )
        .order_by(Prediction.predicted_end.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    return list(result.scalars().all())


async def update_calendar_event_id(
    db: AsyncSession,
    prediction_id: UUID,
    calendar_event_id: str,
) -> Optional[Prediction]:
    """Update the Google Calendar event ID for a prediction."""
    prediction = await get_prediction(db, prediction_id)
    if not prediction:
        return None

    prediction.calendar_event_id = calendar_event_id
    await db.commit()
    await db.refresh(prediction)
    return prediction


async def mark_notification_sent(
    db: AsyncSession,
    prediction_id: UUID,
) -> Optional[Prediction]:
    """Mark a prediction as having been notified."""
    prediction = await get_prediction(db, prediction_id)
    if not prediction:
        return None

    prediction.notified_at = datetime.utcnow()
    await db.commit()
    await db.refresh(prediction)
    return prediction
