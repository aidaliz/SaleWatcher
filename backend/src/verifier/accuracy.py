"""Accuracy calculation and statistics service.

Calculates prediction accuracy metrics per brand and generates
adjustment suggestions when patterns shift.
"""

from dataclasses import dataclass
from datetime import datetime
from statistics import mean, stdev
from typing import Literal, Optional
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    Brand,
    BrandAccuracyStats,
    AdjustmentSuggestion,
    Prediction,
    PredictionOutcome,
)


# Reliability tier thresholds
EXCELLENT_HIT_RATE = 0.8
GOOD_HIT_RATE = 0.6
FAIR_HIT_RATE = 0.4

# Alert thresholds
HIT_RATE_DROP_THRESHOLD = 0.15  # Alert if hit rate drops by this much
MIN_PREDICTIONS_FOR_STATS = 3  # Minimum predictions to calculate stats


@dataclass
class AccuracyMetrics:
    """Calculated accuracy metrics for a brand."""
    brand_id: UUID
    total_predictions: int
    correct_predictions: int
    partial_predictions: int
    missed_predictions: int
    hit_rate: float
    avg_timing_delta_days: Optional[float]
    timing_delta_std: Optional[float]
    avg_discount_delta_percent: Optional[float]
    reliability_score: int
    reliability_tier: str


def calculate_reliability_score(hit_rate: float, total_predictions: int) -> int:
    """
    Calculate a 0-100 reliability score.

    Based on hit rate and sample size.
    """
    # Base score from hit rate (0-80 points)
    base_score = int(hit_rate * 80)

    # Bonus for more data (0-20 points)
    # Logarithmic scale: 5 predictions = 10 points, 20+ = 20 points
    import math
    data_bonus = min(20, int(math.log2(total_predictions + 1) * 5))

    return min(100, base_score + data_bonus)


def determine_reliability_tier(hit_rate: float) -> str:
    """Determine reliability tier based on hit rate."""
    if hit_rate >= EXCELLENT_HIT_RATE:
        return "excellent"
    elif hit_rate >= GOOD_HIT_RATE:
        return "good"
    elif hit_rate >= FAIR_HIT_RATE:
        return "fair"
    else:
        return "poor"


class AccuracyCalculator:
    """Service for calculating prediction accuracy."""

    async def calculate_brand_accuracy(
        self,
        db: AsyncSession,
        brand_id: UUID,
    ) -> Optional[AccuracyMetrics]:
        """
        Calculate accuracy metrics for a single brand.

        Args:
            db: Database session
            brand_id: The brand to calculate for

        Returns:
            AccuracyMetrics or None if insufficient data
        """
        # Get all outcomes for this brand's predictions
        query = (
            select(PredictionOutcome)
            .join(Prediction)
            .where(Prediction.brand_id == brand_id)
            .where(
                or_(
                    PredictionOutcome.auto_result.isnot(None),
                    PredictionOutcome.manual_result.isnot(None),
                )
            )
        )

        result = await db.execute(query)
        outcomes = result.scalars().all()

        if len(outcomes) < MIN_PREDICTIONS_FOR_STATS:
            return None

        # Count results
        total = len(outcomes)
        hits = 0
        partials = 0
        misses = 0
        timing_deltas = []
        discount_deltas = []

        for outcome in outcomes:
            # Use manual result if overridden, otherwise auto
            result = outcome.manual_result if outcome.manual_override else outcome.auto_result

            if result == "hit":
                hits += 1
            elif result == "partial":
                partials += 1
            else:
                misses += 1

            # Collect timing data
            if outcome.timing_delta_days is not None:
                timing_deltas.append(outcome.timing_delta_days)

            # Collect discount data
            if outcome.discount_delta_percent is not None:
                discount_deltas.append(outcome.discount_delta_percent)

        # Calculate metrics
        hit_rate = (hits + partials * 0.5) / total  # Partial counts as half
        correct = hits  # Strict count

        avg_timing = mean(timing_deltas) if timing_deltas else None
        timing_std = stdev(timing_deltas) if len(timing_deltas) > 1 else None
        avg_discount = mean(discount_deltas) if discount_deltas else None

        reliability_score = calculate_reliability_score(hit_rate, total)
        reliability_tier = determine_reliability_tier(hit_rate)

        return AccuracyMetrics(
            brand_id=brand_id,
            total_predictions=total,
            correct_predictions=correct,
            partial_predictions=partials,
            missed_predictions=misses,
            hit_rate=hit_rate,
            avg_timing_delta_days=avg_timing,
            timing_delta_std=timing_std,
            avg_discount_delta_percent=avg_discount,
            reliability_score=reliability_score,
            reliability_tier=reliability_tier,
        )

    async def update_brand_stats(
        self,
        db: AsyncSession,
        brand_id: UUID,
    ) -> Optional[BrandAccuracyStats]:
        """
        Update stored accuracy stats for a brand.

        Args:
            db: Database session
            brand_id: The brand to update

        Returns:
            Updated BrandAccuracyStats or None
        """
        metrics = await self.calculate_brand_accuracy(db, brand_id)
        if not metrics:
            return None

        # Get or create stats record
        query = select(BrandAccuracyStats).where(
            BrandAccuracyStats.brand_id == brand_id
        )
        result = await db.execute(query)
        stats = result.scalar_one_or_none()

        if stats:
            # Check for significant drop (for alerting)
            previous_hit_rate = stats.hit_rate

            # Update existing
            stats.total_predictions = metrics.total_predictions
            stats.correct_predictions = metrics.correct_predictions
            stats.hit_rate = metrics.hit_rate
            stats.avg_timing_delta_days = metrics.avg_timing_delta_days
            stats.timing_delta_std = metrics.timing_delta_std
            stats.avg_discount_delta_percent = metrics.avg_discount_delta_percent
            stats.reliability_score = metrics.reliability_score
            stats.reliability_tier = metrics.reliability_tier
            stats.last_calculated_at = datetime.utcnow()

            # Check if we should create a suggestion
            if (
                previous_hit_rate
                and previous_hit_rate - metrics.hit_rate >= HIT_RATE_DROP_THRESHOLD
            ):
                await self._create_accuracy_drop_suggestion(
                    db, brand_id, previous_hit_rate, metrics.hit_rate
                )
        else:
            # Create new
            stats = BrandAccuracyStats(
                brand_id=brand_id,
                total_predictions=metrics.total_predictions,
                correct_predictions=metrics.correct_predictions,
                hit_rate=metrics.hit_rate,
                avg_timing_delta_days=metrics.avg_timing_delta_days,
                timing_delta_std=metrics.timing_delta_std,
                avg_discount_delta_percent=metrics.avg_discount_delta_percent,
                reliability_score=metrics.reliability_score,
                reliability_tier=metrics.reliability_tier,
            )
            db.add(stats)

        await db.commit()
        await db.refresh(stats)
        return stats

    async def _create_accuracy_drop_suggestion(
        self,
        db: AsyncSession,
        brand_id: UUID,
        previous_rate: float,
        current_rate: float,
    ) -> AdjustmentSuggestion:
        """Create a suggestion for accuracy drop."""
        drop_pct = (previous_rate - current_rate) * 100

        suggestion = AdjustmentSuggestion(
            brand_id=brand_id,
            suggestion_type="accuracy_drop",
            description=f"Hit rate dropped by {drop_pct:.0f}% (from {previous_rate:.0%} to {current_rate:.0%})",
            recommended_action="Review recent predictions and consider adjusting timing windows or checking for pattern changes",
            supporting_data={
                "previous_hit_rate": previous_rate,
                "current_hit_rate": current_rate,
                "drop_percentage": drop_pct,
            },
            status="pending",
        )
        db.add(suggestion)
        await db.commit()
        await db.refresh(suggestion)
        return suggestion

    async def update_all_brand_stats(
        self,
        db: AsyncSession,
    ) -> dict[UUID, BrandAccuracyStats]:
        """
        Update accuracy stats for all active brands.

        Returns:
            Dict mapping brand_id to updated stats
        """
        # Get all active brands
        brands_query = select(Brand).where(Brand.is_active == True)
        brands_result = await db.execute(brands_query)
        brands = brands_result.scalars().all()

        results = {}
        for brand in brands:
            stats = await self.update_brand_stats(db, brand.id)
            if stats:
                results[brand.id] = stats

        return results

    async def get_overall_stats(
        self,
        db: AsyncSession,
    ) -> dict:
        """
        Get aggregate stats across all brands.

        Returns:
            Dict with overall accuracy metrics
        """
        query = select(BrandAccuracyStats)
        result = await db.execute(query)
        all_stats = result.scalars().all()

        if not all_stats:
            return {
                "total_predictions": 0,
                "correct_predictions": 0,
                "hit_rate": 0,
                "brands_tracked": 0,
                "avg_timing_delta_days": None,
            }

        total_preds = sum(s.total_predictions for s in all_stats)
        correct_preds = sum(s.correct_predictions for s in all_stats)
        hit_rate = correct_preds / total_preds if total_preds > 0 else 0

        timing_deltas = [s.avg_timing_delta_days for s in all_stats if s.avg_timing_delta_days is not None]
        avg_timing = mean(timing_deltas) if timing_deltas else None

        return {
            "total_predictions": total_preds,
            "correct_predictions": correct_preds,
            "hit_rate": hit_rate,
            "brands_tracked": len(all_stats),
            "avg_timing_delta_days": avg_timing,
        }

    async def check_for_timing_drift(
        self,
        db: AsyncSession,
        brand_id: UUID,
    ) -> Optional[AdjustmentSuggestion]:
        """
        Check if a brand's predictions are consistently early or late.

        Creates a suggestion if there's significant timing drift.
        """
        # Get recent outcomes
        query = (
            select(PredictionOutcome)
            .join(Prediction)
            .where(Prediction.brand_id == brand_id)
            .where(PredictionOutcome.timing_delta_days.isnot(None))
            .order_by(Prediction.predicted_start.desc())
            .limit(10)
        )

        result = await db.execute(query)
        outcomes = result.scalars().all()

        if len(outcomes) < 5:
            return None

        timing_deltas = [o.timing_delta_days for o in outcomes]
        avg_delta = mean(timing_deltas)

        # Check for consistent drift (more than 3 days average)
        if abs(avg_delta) > 3:
            direction = "early" if avg_delta < 0 else "late"
            suggestion = AdjustmentSuggestion(
                brand_id=brand_id,
                suggestion_type="timing_drift",
                description=f"Predictions are consistently {abs(avg_delta):.1f} days {direction}",
                recommended_action=f"Consider adjusting prediction dates by {int(avg_delta)} days",
                supporting_data={
                    "avg_timing_delta": avg_delta,
                    "sample_size": len(timing_deltas),
                    "direction": direction,
                },
                status="pending",
            )
            db.add(suggestion)
            await db.commit()
            await db.refresh(suggestion)
            return suggestion

        return None


async def calculate_all_accuracy(db: AsyncSession) -> dict:
    """
    Convenience function to calculate accuracy for all brands.

    Returns:
        Overall stats summary
    """
    calculator = AccuracyCalculator()
    await calculator.update_all_brand_stats(db)
    return await calculator.get_overall_stats(db)


async def get_brand_accuracy(
    db: AsyncSession,
    brand_id: UUID,
) -> Optional[BrandAccuracyStats]:
    """Get accuracy stats for a specific brand."""
    query = select(BrandAccuracyStats).where(
        BrandAccuracyStats.brand_id == brand_id
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()
