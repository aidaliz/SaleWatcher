"""Google Calendar API client wrapper."""

import json
from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.config.settings import get_settings


# Required scopes for calendar access
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CalendarClient:
    """Wrapper for Google Calendar API operations."""

    def __init__(self):
        self.settings = get_settings()
        self._service = None

    def _get_service(self):
        """Get or create the calendar service."""
        if self._service is not None:
            return self._service

        # Parse credentials JSON
        credentials_json = self.settings.google_credentials_json
        if not credentials_json:
            raise ValueError("GOOGLE_CREDENTIALS_JSON not configured")

        credentials_info = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=CALENDAR_SCOPES,
        )

        self._service = build("calendar", "v3", credentials=credentials)
        return self._service

    @property
    def calendar_id(self) -> str:
        """Get the configured calendar ID."""
        if not self.settings.google_calendar_id:
            raise ValueError("GOOGLE_CALENDAR_ID not configured")
        return self.settings.google_calendar_id

    def create_event(
        self,
        summary: str,
        start_date: date,
        end_date: date,
        description: Optional[str] = None,
        location: Optional[str] = None,
    ) -> str:
        """
        Create a calendar event.

        Args:
            summary: Event title
            start_date: Event start date
            end_date: Event end date (exclusive)
            description: Event description
            location: Event location (e.g., brand website)

        Returns:
            The created event ID
        """
        service = self._get_service()

        # Build event body
        # Using all-day events (date only, not datetime)
        event = {
            "summary": summary,
            "start": {
                "date": start_date.isoformat(),
            },
            "end": {
                # Google Calendar end dates are exclusive, so add 1 day
                "date": (end_date + timedelta(days=1)).isoformat(),
            },
        }

        if description:
            event["description"] = description
        if location:
            event["location"] = location

        try:
            result = service.events().insert(
                calendarId=self.calendar_id,
                body=event,
            ).execute()
            return result["id"]
        except HttpError as e:
            raise CalendarError(f"Failed to create event: {e}")

    def update_event(
        self,
        event_id: str,
        summary: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
    ) -> str:
        """
        Update an existing calendar event.

        Args:
            event_id: The event to update
            summary: New event title (if updating)
            start_date: New start date (if updating)
            end_date: New end date (if updating)
            description: New description (if updating)
            location: New location (if updating)

        Returns:
            The updated event ID
        """
        service = self._get_service()

        # Get existing event
        try:
            event = service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id,
            ).execute()
        except HttpError as e:
            if e.resp.status == 404:
                raise CalendarError(f"Event not found: {event_id}")
            raise CalendarError(f"Failed to get event: {e}")

        # Update fields
        if summary:
            event["summary"] = summary
        if start_date:
            event["start"] = {"date": start_date.isoformat()}
        if end_date:
            event["end"] = {"date": (end_date + timedelta(days=1)).isoformat()}
        if description is not None:
            event["description"] = description
        if location is not None:
            event["location"] = location

        try:
            result = service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event,
            ).execute()
            return result["id"]
        except HttpError as e:
            raise CalendarError(f"Failed to update event: {e}")

    def delete_event(self, event_id: str) -> None:
        """
        Delete a calendar event.

        Args:
            event_id: The event to delete
        """
        service = self._get_service()

        try:
            service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id,
            ).execute()
        except HttpError as e:
            if e.resp.status == 404:
                # Already deleted, that's fine
                return
            raise CalendarError(f"Failed to delete event: {e}")

    def get_event(self, event_id: str) -> dict:
        """
        Get a calendar event.

        Args:
            event_id: The event to get

        Returns:
            The event data
        """
        service = self._get_service()

        try:
            return service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id,
            ).execute()
        except HttpError as e:
            if e.resp.status == 404:
                raise CalendarError(f"Event not found: {event_id}")
            raise CalendarError(f"Failed to get event: {e}")

    def list_upcoming_events(
        self,
        days_ahead: int = 30,
        max_results: int = 100,
    ) -> list[dict]:
        """
        List upcoming events.

        Args:
            days_ahead: Number of days to look ahead
            max_results: Maximum events to return

        Returns:
            List of event data
        """
        service = self._get_service()

        now = datetime.utcnow()
        time_min = now.isoformat() + "Z"
        time_max = (now + timedelta(days=days_ahead)).isoformat() + "Z"

        try:
            result = service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            return result.get("items", [])
        except HttpError as e:
            raise CalendarError(f"Failed to list events: {e}")


class CalendarError(Exception):
    """Error from calendar operations."""
    pass


# Singleton instance
_client: Optional[CalendarClient] = None


def get_calendar_client() -> CalendarClient:
    """Get or create the calendar client singleton."""
    global _client
    if _client is None:
        _client = CalendarClient()
    return _client
