"""Auto-verification service for predictions.

Checks if predicted sales actually occurred by looking for matching
emails/extractions within the prediction window.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal, Optional
from uuid import UUID

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import (
    Brand,
    ExtractedSale,
    Prediction,
    PredictionOutcome,
    RawEmail,
    SaleWindow,
)


# Verification thresholds
TIMING_TOLERANCE_DAYS = 7  # How many days before/after prediction to look
DISCOUNT_TOLERANCE_PERCENT = 10  # How different the discount can be


VerificationResult = Literal["hit", "miss", "partial"]


@dataclass
class VerificationMatch:
    """Details of a matched sale for a prediction."""
    email_ids: list[UUID]
    actual_start: Optional[date]
    actual_end: Optional[date]
    actual_discount: Optional[float]
    timing_delta_days: int  # Negative = early, positive = late
    discount_delta_percent: Optional[float]


def calculate_timing_delta(predicted_start: date, actual_start: date) -> int:
    """Calculate days between predicted and actual start dates."""
    return (actual_start - predicted_start).days


def calculate_discount_delta(
    predicted_discount: Optional[str],
    actual_discount: Optional[float],
) -> Optional[float]:
    """Calculate percentage point difference in discounts."""
    if not predicted_discount or actual_discount is None:
        return None

    # Try to extract number from predicted discount
    import re
    match = re.search(r'(\d+)', predicted_discount)
    if not match:
        return None

    predicted_value = float(match.group(1))
    return actual_discount - predicted_value


def determine_result(
    has_match: bool,
    timing_delta: Optional[int],
    discount_delta: Optional[float],
) -> VerificationResult:
    """Determine verification result based on match quality."""
    if not has_match:
        return "miss"

    # Check if timing is too far off
    if timing_delta is not None and abs(timing_delta) > TIMING_TOLERANCE_DAYS:
        return "partial"

    # Check if discount is too different
    if discount_delta is not None and abs(discount_delta) > DISCOUNT_TOLERANCE_PERCENT:
        return "partial"

    return "hit"


class PredictionVerifier:
    """Service for verifying prediction outcomes."""

    async def find_matching_sales(
        self,
        db: AsyncSession,
        prediction: Prediction,
    ) -> Optional[VerificationMatch]:
        """
        Find sales that match a prediction.

        Looks for approved extractions within the prediction window
        (± TIMING_TOLERANCE_DAYS) for the same brand.

        Args:
            db: Database session
            prediction: The prediction to verify

        Returns:
            VerificationMatch if found, None otherwise
        """
        # Calculate search window
        search_start = prediction.predicted_start - timedelta(days=TIMING_TOLERANCE_DAYS)
        search_end = prediction.predicted_end + timedelta(days=TIMING_TOLERANCE_DAYS)

        # Find approved extractions in the window
        query = (
            select(ExtractedSale)
            .join(RawEmail)
            .where(RawEmail.brand_id == prediction.brand_id)
            .where(ExtractedSale.review_status == "approved")
            .where(
                or_(
                    # Sale start is within search window
                    and_(
                        ExtractedSale.sale_start >= search_start,
                        ExtractedSale.sale_start <= search_end,
                    ),
                    # Or email sent date is within window (if no sale dates)
                    and_(
                        ExtractedSale.sale_start.is_(None),
                        RawEmail.sent_at >= search_start,
                        RawEmail.sent_at <= search_end,
                    ),
                )
            )
            .options(selectinload(ExtractedSale.email))
        )

        result = await db.execute(query)
        extractions = result.scalars().all()

        if not extractions:
            return None

        # Collect match data
        email_ids = [e.email_id for e in extractions]

        # Find earliest and latest dates
        actual_starts = [e.sale_start or e.email.sent_at for e in extractions if e.sale_start or e.email]
        actual_ends = [e.sale_end or e.sale_start or e.email.sent_at for e in extractions if e.sale_end or e.sale_start or e.email]

        actual_start = min(actual_starts) if actual_starts else None
        actual_end = max(actual_ends) if actual_ends else None

        # Get best discount value (highest confidence extraction)
        best_extraction = max(extractions, key=lambda e: e.confidence)
        actual_discount = best_extraction.discount_value

        # Calculate deltas
        timing_delta = 0
        if actual_start:
            timing_delta = calculate_timing_delta(prediction.predicted_start, actual_start)

        discount_delta = calculate_discount_delta(
            prediction.discount_summary,
            actual_discount,
        )

        return VerificationMatch(
            email_ids=email_ids,
            actual_start=actual_start,
            actual_end=actual_end,
            actual_discount=actual_discount,
            timing_delta_days=timing_delta,
            discount_delta_percent=discount_delta,
        )

    async def verify_prediction(
        self,
        db: AsyncSession,
        prediction: Prediction,
    ) -> PredictionOutcome:
        """
        Verify a single prediction and create/update its outcome.

        Args:
            db: Database session
            prediction: The prediction to verify

        Returns:
            The created or updated PredictionOutcome
        """
        # Check if outcome already exists
        existing_query = select(PredictionOutcome).where(
            PredictionOutcome.prediction_id == prediction.id
        )
        existing_result = await db.execute(existing_query)
        outcome = existing_result.scalar_one_or_none()

        # Find matching sales
        match = await self.find_matching_sales(db, prediction)

        # Determine result
        if match:
            result = determine_result(
                has_match=True,
                timing_delta=match.timing_delta_days,
                discount_delta=match.discount_delta_percent,
            )
        else:
            result = "miss"

        if outcome:
            # Update existing outcome (only if not manually overridden)
            if not outcome.manual_override:
                outcome.auto_result = result
                outcome.auto_verified_at = datetime.utcnow()
                if match:
                    outcome.matched_email_ids = match.email_ids
                    outcome.actual_start = match.actual_start
                    outcome.actual_end = match.actual_end
                    outcome.actual_discount = match.actual_discount
                    outcome.timing_delta_days = match.timing_delta_days
                    outcome.discount_delta_percent = match.discount_delta_percent
        else:
            # Create new outcome
            outcome = PredictionOutcome(
                prediction_id=prediction.id,
                auto_result=result,
                auto_verified_at=datetime.utcnow(),
                matched_email_ids=match.email_ids if match else [],
                actual_start=match.actual_start if match else None,
                actual_end=match.actual_end if match else None,
                actual_discount=match.actual_discount if match else None,
                timing_delta_days=match.timing_delta_days if match else None,
                discount_delta_percent=match.discount_delta_percent if match else None,
            )
            db.add(outcome)

        await db.commit()
        await db.refresh(outcome)
        return outcome

    async def get_predictions_to_verify(
        self,
        db: AsyncSession,
        brand_id: Optional[UUID] = None,
        limit: int = 100,
    ) -> list[Prediction]:
        """
        Get predictions that are past their end date and need verification.

        Args:
            db: Database session
            brand_id: Optional brand filter
            limit: Maximum predictions to return

        Returns:
            List of predictions needing verification
        """
        today = date.today()

        query = (
            select(Prediction)
            .outerjoin(PredictionOutcome)
            .where(Prediction.predicted_end < today)
            .where(
                or_(
                    PredictionOutcome.id.is_(None),  # No outcome yet
                    and_(
                        PredictionOutcome.auto_result.is_(None),
                        PredictionOutcome.manual_override == False,
                    ),
                )
            )
            .options(selectinload(Prediction.brand))
            .order_by(Prediction.predicted_end.desc())
            .limit(limit)
        )

        if brand_id:
            query = query.where(Prediction.brand_id == brand_id)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def verify_all_pending(
        self,
        db: AsyncSession,
        brand_id: Optional[UUID] = None,
    ) -> dict:
        """
        Verify all pending predictions.

        Args:
            db: Database session
            brand_id: Optional brand filter

        Returns:
            Summary of verification results
        """
        predictions = await self.get_predictions_to_verify(db, brand_id)

        results = {"hit": 0, "miss": 0, "partial": 0, "total": len(predictions)}

        for prediction in predictions:
            outcome = await self.verify_prediction(db, prediction)
            if outcome.auto_result:
                results[outcome.auto_result] += 1

        return results


async def run_verification(
    db: AsyncSession,
    brand_id: Optional[UUID] = None,
) -> dict:
    """
    Convenience function to run verification.

    Args:
        db: Database session
        brand_id: Optional brand filter

    Returns:
        Verification results summary
    """
    verifier = PredictionVerifier()
    return await verifier.verify_all_pending(db, brand_id)


async def verify_single_prediction(
    db: AsyncSession,
    prediction_id: UUID,
) -> Optional[PredictionOutcome]:
    """
    Verify a single prediction by ID.

    Args:
        db: Database session
        prediction_id: The prediction to verify

    Returns:
        The outcome, or None if prediction not found
    """
    # Get prediction
    query = select(Prediction).where(Prediction.id == prediction_id)
    result = await db.execute(query)
    prediction = result.scalar_one_or_none()

    if not prediction:
        return None

    verifier = PredictionVerifier()
    return await verifier.verify_prediction(db, prediction)
