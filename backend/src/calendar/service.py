"""Calendar sync service for predictions."""

from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.calendar.client import get_calendar_client, CalendarError
from src.db.models import Brand, Prediction
from src.db.crud.predictions import update_calendar_event_id


# How many days before a prediction to create the calendar event
ADVANCE_NOTICE_DAYS = 7


def format_event_summary(prediction: Prediction) -> str:
    """Format the calendar event summary."""
    brand_name = prediction.brand.name if prediction.brand else "Unknown Brand"
    discount = prediction.discount_summary or "Sale"
    return f"[SaleWatcher] {brand_name}: {discount}"


def format_event_description(prediction: Prediction) -> str:
    """Format the calendar event description."""
    lines = []

    lines.append(f"Predicted Sale: {prediction.discount_summary or 'See details'}")
    lines.append("")

    if prediction.source_window:
        lines.append(f"Based on: {prediction.source_window.name}")
        lines.append(
            f"Last year: {prediction.source_window.start_date} - {prediction.source_window.end_date}"
        )
        lines.append("")

    lines.append(f"Confidence: {prediction.confidence:.0%}")

    if prediction.milled_reference_url:
        lines.append("")
        lines.append(f"Reference: {prediction.milled_reference_url}")

    return "\n".join(lines)


class CalendarSyncService:
    """Service for syncing predictions to Google Calendar."""

    def __init__(self):
        self.client = get_calendar_client()

    async def sync_prediction(
        self,
        db: AsyncSession,
        prediction: Prediction,
    ) -> Optional[str]:
        """
        Sync a single prediction to the calendar.

        Creates a new event or updates an existing one.

        Args:
            db: Database session
            prediction: The prediction to sync

        Returns:
            The calendar event ID, or None if sync failed
        """
        summary = format_event_summary(prediction)
        description = format_event_description(prediction)

        try:
            if prediction.calendar_event_id:
                # Update existing event
                event_id = self.client.update_event(
                    event_id=prediction.calendar_event_id,
                    summary=summary,
                    start_date=prediction.predicted_start,
                    end_date=prediction.predicted_end,
                    description=description,
                )
            else:
                # Create new event
                event_id = self.client.create_event(
                    summary=summary,
                    start_date=prediction.predicted_start,
                    end_date=prediction.predicted_end,
                    description=description,
                )

                # Save event ID to database
                await update_calendar_event_id(db, prediction.id, event_id)

            return event_id

        except CalendarError as e:
            print(f"Calendar sync error for prediction {prediction.id}: {e}")
            return None

    async def sync_upcoming(
        self,
        db: AsyncSession,
        days_ahead: int = 30,
        brand_id: Optional[UUID] = None,
    ) -> dict:
        """
        Sync all upcoming predictions to the calendar.

        Only syncs predictions that:
        - Start within `days_ahead` days
        - Don't have a calendar event yet

        Args:
            db: Database session
            days_ahead: How far ahead to look
            brand_id: Optional brand filter

        Returns:
            Dict with sync results
        """
        today = date.today()
        end_date = today + timedelta(days=days_ahead)

        # Get predictions needing sync
        query = (
            select(Prediction)
            .where(Prediction.predicted_start >= today)
            .where(Prediction.predicted_start <= end_date)
            .where(Prediction.calendar_event_id.is_(None))
            .options(
                selectinload(Prediction.brand),
                selectinload(Prediction.source_window),
            )
        )

        if brand_id:
            query = query.where(Prediction.brand_id == brand_id)

        result = await db.execute(query)
        predictions = result.scalars().all()

        synced = []
        failed = []

        for prediction in predictions:
            event_id = await self.sync_prediction(db, prediction)
            if event_id:
                synced.append(str(prediction.id))
            else:
                failed.append(str(prediction.id))

        return {
            "synced": len(synced),
            "failed": len(failed),
            "synced_ids": synced,
            "failed_ids": failed,
        }

    async def delete_prediction_event(
        self,
        db: AsyncSession,
        prediction: Prediction,
    ) -> bool:
        """
        Delete the calendar event for a prediction.

        Args:
            db: Database session
            prediction: The prediction whose event to delete

        Returns:
            True if deleted successfully
        """
        if not prediction.calendar_event_id:
            return True

        try:
            self.client.delete_event(prediction.calendar_event_id)
            await update_calendar_event_id(db, prediction.id, "")
            return True
        except CalendarError as e:
            print(f"Failed to delete event for prediction {prediction.id}: {e}")
            return False


async def sync_predictions_to_calendar(
    db: AsyncSession,
    days_ahead: int = 30,
    brand_id: Optional[UUID] = None,
) -> dict:
    """
    Convenience function to sync predictions.

    Args:
        db: Database session
        days_ahead: How far ahead to look
        brand_id: Optional brand filter

    Returns:
        Sync results dict
    """
    service = CalendarSyncService()
    return await service.sync_upcoming(db, days_ahead, brand_id)
