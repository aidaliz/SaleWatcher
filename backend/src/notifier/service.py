"""Notification service for email digests and alerts."""

from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import (
    Brand,
    BrandAccuracyStats,
    ExtractedSale,
    Prediction,
    PredictionOutcome,
)
from src.notifier.email_client import get_email_client
from src.notifier.templates import (
    review_digest_template,
    weekly_summary_template,
    accuracy_alert_template,
)


class NotificationService:
    """Service for sending notification emails."""

    def __init__(self):
        self.client = get_email_client()

    async def send_review_digest(
        self,
        db: AsyncSession,
    ) -> Optional[str]:
        """
        Send the daily review digest email.

        Args:
            db: Database session

        Returns:
            Email ID if sent
        """
        # Get pending reviews
        query = (
            select(ExtractedSale)
            .where(ExtractedSale.review_status == "pending")
            .options(
                selectinload(ExtractedSale.email).selectinload(lambda x: x.brand)
            )
            .order_by(ExtractedSale.confidence.asc())
            .limit(10)
        )
        result = await db.execute(query)
        extractions = result.scalars().all()

        # Get total count
        count_query = select(func.count()).select_from(ExtractedSale).where(
            ExtractedSale.review_status == "pending"
        )
        count_result = await db.execute(count_query)
        pending_count = count_result.scalar() or 0

        if pending_count == 0:
            print("No pending reviews, skipping digest...")
            return None

        # Format reviews for template
        reviews = []
        for ext in extractions:
            brand_name = "Unknown"
            if ext.email and ext.email.brand:
                brand_name = ext.email.brand.name

            reviews.append({
                "id": str(ext.id),
                "brand_name": brand_name,
                "discount_summary": ext.raw_discount_text or ext.discount_type,
                "confidence": ext.confidence,
                "model_used": ext.model_used or "Unknown",
            })

        html = review_digest_template(pending_count, reviews)
        return self.client.send(
            subject=f"[SaleWatcher] {pending_count} extraction(s) pending review",
            html=html,
        )

    async def send_weekly_summary(
        self,
        db: AsyncSession,
    ) -> Optional[str]:
        """
        Send the weekly prediction summary email.

        Args:
            db: Database session

        Returns:
            Email ID if sent
        """
        today = date.today()
        end_date = today + timedelta(days=14)

        # Get upcoming predictions
        query = (
            select(Prediction)
            .where(Prediction.predicted_start >= today)
            .where(Prediction.predicted_start <= end_date)
            .options(selectinload(Prediction.brand))
            .order_by(Prediction.predicted_start.asc())
            .limit(15)
        )
        result = await db.execute(query)
        predictions = result.scalars().all()

        # Get total count
        count_query = (
            select(func.count())
            .select_from(Prediction)
            .where(Prediction.predicted_start >= today)
            .where(Prediction.predicted_start <= end_date)
        )
        count_result = await db.execute(count_query)
        upcoming_count = count_result.scalar() or 0

        # Get accuracy stats
        stats_query = select(BrandAccuracyStats)
        stats_result = await db.execute(stats_query)
        all_stats = stats_result.scalars().all()

        accuracy_stats = None
        if all_stats:
            total_predictions = sum(s.total_predictions for s in all_stats)
            correct_predictions = sum(s.correct_predictions for s in all_stats)
            hit_rate = correct_predictions / total_predictions if total_predictions > 0 else 0

            accuracy_stats = {
                "hit_rate": hit_rate,
                "total_predictions": total_predictions,
                "brands_tracked": len(all_stats),
            }

        # Format predictions for template
        pred_list = []
        for pred in predictions:
            brand_name = pred.brand.name if pred.brand else "Unknown"
            pred_list.append({
                "brand_name": brand_name,
                "discount_summary": pred.discount_summary or "Sale",
                "predicted_start": str(pred.predicted_start),
                "predicted_end": str(pred.predicted_end),
                "confidence": pred.confidence,
            })

        html = weekly_summary_template(upcoming_count, pred_list, accuracy_stats)
        return self.client.send(
            subject="[SaleWatcher] Weekly Prediction Summary",
            html=html,
        )

    async def send_accuracy_alert(
        self,
        db: AsyncSession,
        brand_id: UUID,
        current_hit_rate: float,
        previous_hit_rate: float,
    ) -> Optional[str]:
        """
        Send an accuracy alert for a brand.

        Args:
            db: Database session
            brand_id: The brand with low accuracy
            current_hit_rate: Current hit rate
            previous_hit_rate: Previous hit rate

        Returns:
            Email ID if sent
        """
        # Get brand
        brand_query = select(Brand).where(Brand.id == brand_id)
        brand_result = await db.execute(brand_query)
        brand = brand_result.scalar_one_or_none()

        if not brand:
            return None

        # Get recent misses
        miss_query = (
            select(Prediction)
            .join(PredictionOutcome)
            .where(Prediction.brand_id == brand_id)
            .where(
                (PredictionOutcome.auto_result == "miss")
                | (PredictionOutcome.manual_result == "miss")
            )
            .order_by(Prediction.predicted_start.desc())
            .limit(5)
        )
        miss_result = await db.execute(miss_query)
        misses = miss_result.scalars().all()

        recent_misses = []
        for miss in misses:
            recent_misses.append({
                "predicted_start": str(miss.predicted_start),
                "discount_summary": miss.discount_summary or "Sale",
                "reason": "No matching sale found",
            })

        html = accuracy_alert_template(
            brand.name,
            current_hit_rate,
            previous_hit_rate,
            recent_misses,
        )
        return self.client.send(
            subject=f"[SaleWatcher] Accuracy Alert: {brand.name}",
            html=html,
        )


async def send_daily_digest(db: AsyncSession) -> Optional[str]:
    """Convenience function to send daily review digest."""
    service = NotificationService()
    return await service.send_review_digest(db)


async def send_weekly_summary(db: AsyncSession) -> Optional[str]:
    """Convenience function to send weekly summary."""
    service = NotificationService()
    return await service.send_weekly_summary(db)
