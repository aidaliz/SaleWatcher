"""
Generates predictions for future sales based on historical sale windows.

The predictor analyzes past sale patterns and projects them forward,
using holiday anchoring when available for more accurate timing.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import (
    Brand,
    Prediction,
    SaleWindow,
    DiscountType,
)
from src.deduplicator.grouper import HOLIDAYS

logger = logging.getLogger(__name__)


def get_holiday_date(holiday_name: str, year: int) -> Optional[datetime]:
    """Get the date of a holiday for a specific year."""
    if holiday_name not in HOLIDAYS:
        return None

    month, day = HOLIDAYS[holiday_name]
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def project_date_to_year(
    original_date: datetime,
    target_year: int,
    holiday_anchor: Optional[str] = None,
    days_from_holiday: Optional[int] = None,
) -> datetime:
    """
    Project a date from one year to another.

    If holiday anchoring is available, uses the holiday as reference.
    Otherwise, uses the same month/day in the target year.
    """
    if holiday_anchor and days_from_holiday is not None:
        # Use holiday-relative positioning
        holiday_date = get_holiday_date(holiday_anchor, target_year)
        if holiday_date:
            return holiday_date + timedelta(days=days_from_holiday)

    # Fall back to same month/day
    try:
        return datetime(
            target_year,
            original_date.month,
            original_date.day,
            original_date.hour,
            original_date.minute,
        )
    except ValueError:
        # Handle Feb 29 -> Feb 28 for non-leap years
        if original_date.month == 2 and original_date.day == 29:
            return datetime(target_year, 2, 28)
        raise


def calculate_confidence(
    window: SaleWindow,
    years_of_data: int,
    pattern_consistency: float,
) -> float:
    """
    Calculate prediction confidence based on various factors.

    Args:
        window: The source sale window
        years_of_data: How many years of historical data we have
        pattern_consistency: How consistent the pattern is (0-1)

    Returns:
        Confidence score (0-1)
    """
    base_confidence = 0.5

    # Boost for holiday anchoring (more predictable timing)
    if window.holiday_anchor:
        base_confidence += 0.15

    # Boost for more years of data
    if years_of_data >= 3:
        base_confidence += 0.15
    elif years_of_data >= 2:
        base_confidence += 0.10
    elif years_of_data >= 1:
        base_confidence += 0.05

    # Boost for pattern consistency
    base_confidence += pattern_consistency * 0.2

    return min(base_confidence, 0.95)


async def generate_predictions(
    db: AsyncSession,
    target_year: int,
    brand_id: Optional[UUID] = None,
    min_years_history: int = 1,
) -> list[Prediction]:
    """
    Generate predictions for a target year based on historical data.

    Args:
        db: Database session
        target_year: Year to generate predictions for
        brand_id: Optional brand ID to process only one brand
        min_years_history: Minimum years of data required to make predictions

    Returns:
        List of created Prediction objects
    """
    logger.info(f"Generating predictions for {target_year}")

    # Get all sale windows, grouped by brand and pattern
    query = (
        select(SaleWindow)
        .options(selectinload(SaleWindow.brand))
    )

    if brand_id:
        query = query.where(SaleWindow.brand_id == brand_id)

    # Only use windows from before target year
    query = query.where(SaleWindow.year < target_year)
    query = query.order_by(SaleWindow.brand_id, SaleWindow.start_date)

    result = await db.execute(query)
    windows = list(result.scalars().all())

    if not windows:
        logger.warning("No historical sale windows found")
        return []

    logger.info(f"Found {len(windows)} historical sale windows")

    # Check for existing predictions to avoid duplicates
    existing_query = (
        select(Prediction.source_window_id)
        .where(Prediction.target_year == target_year)
    )
    if brand_id:
        existing_query = existing_query.where(Prediction.brand_id == brand_id)

    existing_result = await db.execute(existing_query)
    existing_source_ids = {row[0] for row in existing_result.all()}

    # Group windows by brand and holiday/month pattern
    pattern_groups: dict[tuple, list[SaleWindow]] = {}

    for window in windows:
        if window.id in existing_source_ids:
            continue

        # Create pattern key based on timing
        if window.holiday_anchor:
            pattern_key = (window.brand_id, "holiday", window.holiday_anchor)
        else:
            # Use month as pattern key for non-holiday sales
            pattern_key = (window.brand_id, "month", window.start_date.month)

        if pattern_key not in pattern_groups:
            pattern_groups[pattern_key] = []
        pattern_groups[pattern_key].append(window)

    created_predictions = []

    for pattern_key, group_windows in pattern_groups.items():
        brand_id_key = pattern_key[0]
        years = {w.year for w in group_windows}

        # Skip if not enough history
        if len(years) < min_years_history:
            continue

        # Use most recent window as template
        template_window = max(group_windows, key=lambda w: w.year)

        # Calculate pattern consistency (how many years had this sale)
        years_span = max(years) - min(years) + 1
        pattern_consistency = len(years) / years_span if years_span > 0 else 0

        # Project dates to target year
        predicted_start = project_date_to_year(
            template_window.start_date,
            target_year,
            template_window.holiday_anchor,
            template_window.days_from_holiday,
        )

        duration = template_window.end_date - template_window.start_date
        predicted_end = predicted_start + duration

        # Skip if prediction is in the past
        if predicted_end < datetime.utcnow():
            continue

        # Calculate confidence
        confidence = calculate_confidence(
            template_window,
            len(years),
            pattern_consistency,
        )

        # Average discount from all years
        avg_discount = sum(w.discount_value for w in group_windows) / len(group_windows)

        # Create prediction
        prediction = Prediction(
            brand_id=brand_id_key,
            source_window_id=template_window.id,
            target_year=target_year,
            predicted_start=predicted_start,
            predicted_end=predicted_end,
            discount_type=template_window.discount_type,
            expected_discount=avg_discount,
            discount_summary=template_window.discount_summary,
            categories=template_window.categories,
            confidence=confidence,
        )

        db.add(prediction)
        created_predictions.append(prediction)

        logger.info(
            f"Created prediction: {template_window.brand.name} - "
            f"{template_window.discount_summary[:40]} on "
            f"{predicted_start.strftime('%Y-%m-%d')} (confidence: {confidence:.2f})"
        )

    await db.commit()
    logger.info(f"Generated {len(created_predictions)} predictions for {target_year}")

    return created_predictions


async def generate_all_future_predictions(
    db: AsyncSession,
    brand_id: Optional[UUID] = None,
    years_ahead: int = 1,
) -> dict[int, list[Prediction]]:
    """
    Generate predictions for the current year and optionally future years.

    Args:
        db: Database session
        brand_id: Optional brand ID to process only one brand
        years_ahead: How many years ahead to predict (default 1 = current year only)

    Returns:
        Dict mapping year to list of predictions
    """
    current_year = datetime.utcnow().year
    all_predictions = {}

    for offset in range(years_ahead + 1):
        target_year = current_year + offset
        predictions = await generate_predictions(
            db,
            target_year=target_year,
            brand_id=brand_id,
        )
        all_predictions[target_year] = predictions

    return all_predictions
