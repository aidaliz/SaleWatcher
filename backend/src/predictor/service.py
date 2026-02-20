"""Prediction generation service.

Generates predictions for future sales based on historical sale windows.
Uses ±7 day matching window and holiday anchoring for floating holidays.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Brand, Prediction, RawEmail, SaleWindow
from src.predictor.holidays import (
    Holiday,
    adjust_date_for_holiday,
    detect_holiday_anchor,
    get_holiday_date,
)


# Configuration
PREDICTION_WINDOW_DAYS = 7  # ±7 days for date matching
MIN_CONFIDENCE_FOR_PREDICTION = 0.6  # Minimum confidence to create prediction


@dataclass
class PredictionCandidate:
    """Candidate prediction before saving to database."""
    brand_id: UUID
    source_window: SaleWindow
    predicted_start: date
    predicted_end: date
    discount_summary: str
    confidence: float
    holiday_anchor: Optional[str]
    reference_url: Optional[str]


def calculate_prediction_confidence(
    source_window: SaleWindow,
    historical_windows: list[SaleWindow],
) -> float:
    """
    Calculate confidence score for a prediction.

    Higher confidence when:
    - Multiple years of similar sales exist
    - Consistent timing year-over-year
    - Holiday-anchored sales

    Args:
        source_window: The window to base prediction on
        historical_windows: Other windows from same brand

    Returns:
        Confidence score 0.0-1.0
    """
    base_confidence = 0.5

    # Bonus for holiday anchor
    if source_window.holiday_anchor:
        base_confidence += 0.15

    # Find similar sales in other years
    similar_sales = []
    source_month = source_window.start_date.month
    source_day = source_window.start_date.day

    for window in historical_windows:
        if window.id == source_window.id:
            continue
        if window.year == source_window.year:
            continue

        # Check if similar timing (within 14 days of same calendar date)
        window_month = window.start_date.month
        window_day = window.start_date.day

        # Simple check: same month, day within 14
        if window_month == source_month and abs(window_day - source_day) <= 14:
            similar_sales.append(window)
        # Also check for holiday-aligned sales
        elif source_window.holiday_anchor and window.holiday_anchor == source_window.holiday_anchor:
            similar_sales.append(window)

    # Bonus for each year of historical data
    years_of_data = len(set(w.year for w in similar_sales))
    base_confidence += min(years_of_data * 0.1, 0.25)

    # Check discount consistency
    if similar_sales and source_window.discount_summary:
        source_discount = source_window.discount_summary.lower()
        matching_discounts = sum(
            1 for w in similar_sales
            if w.discount_summary and w.discount_summary.lower() == source_discount
        )
        if matching_discounts > 0:
            base_confidence += 0.1

    return min(base_confidence, 1.0)


def get_reference_url(source_window: SaleWindow, emails: list) -> Optional[str]:
    """Get the best reference URL from linked emails."""
    if not source_window.linked_email_ids:
        return None

    for email in emails:
        if email.id in source_window.linked_email_ids:
            return email.milled_url

    return None


class PredictionGenerator:
    """Service for generating sale predictions."""

    def __init__(self, target_year: Optional[int] = None):
        """
        Initialize the generator.

        Args:
            target_year: Year to generate predictions for (default: current year)
        """
        self.target_year = target_year or date.today().year

    async def get_historical_windows(
        self,
        db: AsyncSession,
        brand_id: UUID,
    ) -> list[SaleWindow]:
        """Get all historical sale windows for a brand."""
        query = (
            select(SaleWindow)
            .where(SaleWindow.brand_id == brand_id)
            .where(SaleWindow.year < self.target_year)
            .order_by(SaleWindow.start_date.desc())
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_existing_predictions(
        self,
        db: AsyncSession,
        brand_id: UUID,
    ) -> list[Prediction]:
        """Get existing predictions for target year."""
        start_of_year = date(self.target_year, 1, 1)
        end_of_year = date(self.target_year, 12, 31)

        query = (
            select(Prediction)
            .where(Prediction.brand_id == brand_id)
            .where(Prediction.predicted_start >= start_of_year)
            .where(Prediction.predicted_start <= end_of_year)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_emails_for_reference(
        self,
        db: AsyncSession,
        brand_id: UUID,
    ) -> list:
        """Get emails for reference URLs."""
        query = (
            select(RawEmail)
            .where(RawEmail.brand_id == brand_id)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    def generate_candidates(
        self,
        source_windows: list[SaleWindow],
        all_windows: list[SaleWindow],
        existing_predictions: list[Prediction],
        emails: list,
    ) -> list[PredictionCandidate]:
        """
        Generate prediction candidates from historical windows.

        Args:
            source_windows: Windows from last year to base predictions on
            all_windows: All historical windows for confidence calculation
            existing_predictions: Already existing predictions to avoid duplicates
            emails: Emails for reference URLs

        Returns:
            List of prediction candidates
        """
        candidates = []
        existing_window_ids = {p.source_window_id for p in existing_predictions}

        for window in source_windows:
            # Skip if already predicted
            if window.id in existing_window_ids:
                continue

            # Detect or use existing holiday anchor
            holiday_anchor = None
            if window.holiday_anchor:
                try:
                    holiday_anchor = Holiday(window.holiday_anchor)
                except ValueError:
                    pass

            if not holiday_anchor:
                holiday_anchor = detect_holiday_anchor(window.start_date)

            # Calculate predicted dates
            if holiday_anchor:
                predicted_start = adjust_date_for_holiday(
                    window.start_date,
                    window.year,
                    self.target_year,
                    holiday_anchor,
                )
                predicted_end = adjust_date_for_holiday(
                    window.end_date,
                    window.year,
                    self.target_year,
                    holiday_anchor,
                )
            else:
                # Simple year shift
                try:
                    predicted_start = window.start_date.replace(year=self.target_year)
                    predicted_end = window.end_date.replace(year=self.target_year)
                except ValueError:
                    # Handle Feb 29
                    predicted_start = date(self.target_year, window.start_date.month, 28)
                    predicted_end = date(self.target_year, window.end_date.month, 28)

            # Calculate confidence
            confidence = calculate_prediction_confidence(window, all_windows)

            # Skip low confidence predictions
            if confidence < MIN_CONFIDENCE_FOR_PREDICTION:
                continue

            # Get reference URL
            reference_url = get_reference_url(window, emails)

            candidates.append(PredictionCandidate(
                brand_id=window.brand_id,
                source_window=window,
                predicted_start=predicted_start,
                predicted_end=predicted_end,
                discount_summary=window.discount_summary or window.name,
                confidence=confidence,
                holiday_anchor=holiday_anchor.value if holiday_anchor else None,
                reference_url=reference_url,
            ))

        return candidates

    async def create_predictions(
        self,
        db: AsyncSession,
        candidates: list[PredictionCandidate],
    ) -> list[Prediction]:
        """Save prediction candidates to database."""
        predictions = []

        for candidate in candidates:
            prediction = Prediction(
                brand_id=candidate.brand_id,
                source_window_id=candidate.source_window.id,
                predicted_start=candidate.predicted_start,
                predicted_end=candidate.predicted_end,
                discount_summary=candidate.discount_summary,
                milled_reference_url=candidate.reference_url,
                confidence=candidate.confidence,
            )
            db.add(prediction)
            predictions.append(prediction)

        await db.commit()

        for prediction in predictions:
            await db.refresh(prediction)

        return predictions

    async def generate_for_brand(
        self,
        db: AsyncSession,
        brand_id: UUID,
    ) -> list[Prediction]:
        """
        Generate predictions for a single brand.

        Args:
            db: Database session
            brand_id: Brand to generate predictions for

        Returns:
            List of created predictions
        """
        # Get last year's windows as prediction source
        last_year = self.target_year - 1
        query = (
            select(SaleWindow)
            .where(SaleWindow.brand_id == brand_id)
            .where(SaleWindow.year == last_year)
        )
        result = await db.execute(query)
        source_windows = list(result.scalars().all())

        if not source_windows:
            return []

        # Get all historical windows for confidence calculation
        all_windows = await self.get_historical_windows(db, brand_id)

        # Get existing predictions to avoid duplicates
        existing = await self.get_existing_predictions(db, brand_id)

        # Get emails for reference URLs
        emails = await self.get_emails_for_reference(db, brand_id)

        # Generate candidates
        candidates = self.generate_candidates(
            source_windows,
            all_windows,
            existing,
            emails,
        )

        if not candidates:
            return []

        # Create predictions
        return await self.create_predictions(db, candidates)

    async def generate_all(
        self,
        db: AsyncSession,
    ) -> dict[UUID, list[Prediction]]:
        """
        Generate predictions for all active brands.

        Returns:
            Dict mapping brand_id to list of predictions
        """
        # Get all active brands
        brands_result = await db.execute(
            select(Brand).where(Brand.is_active == True)
        )
        brands = brands_result.scalars().all()

        results = {}
        for brand in brands:
            predictions = await self.generate_for_brand(db, brand.id)
            if predictions:
                results[brand.id] = predictions

        return results


async def generate_predictions(
    db: AsyncSession,
    brand_id: Optional[UUID] = None,
    target_year: Optional[int] = None,
) -> list[Prediction]:
    """
    Convenience function to generate predictions.

    Args:
        db: Database session
        brand_id: Optional brand filter
        target_year: Year to predict for (default: current year)

    Returns:
        List of created predictions
    """
    generator = PredictionGenerator(target_year)

    if brand_id:
        return await generator.generate_for_brand(db, brand_id)
    else:
        all_predictions = await generator.generate_all(db)
        return [p for predictions in all_predictions.values() for p in predictions]


async def get_upcoming_predictions(
    db: AsyncSession,
    days_ahead: int = 14,
    brand_id: Optional[UUID] = None,
) -> list[Prediction]:
    """
    Get predictions for the upcoming period.

    Args:
        db: Database session
        days_ahead: Number of days to look ahead
        brand_id: Optional brand filter

    Returns:
        List of upcoming predictions
    """
    today = date.today()
    end_date = today + timedelta(days=days_ahead)

    query = (
        select(Prediction)
        .where(Prediction.predicted_start >= today)
        .where(Prediction.predicted_start <= end_date)
        .options(
            selectinload(Prediction.brand),
            selectinload(Prediction.source_window),
        )
        .order_by(Prediction.predicted_start.asc())
    )

    if brand_id:
        query = query.where(Prediction.brand_id == brand_id)

    result = await db.execute(query)
    return list(result.scalars().all())
