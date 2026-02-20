"""Resend email client wrapper."""

from typing import Optional

import resend

from src.config.settings import get_settings


class EmailClient:
    """Wrapper for Resend email API."""

    def __init__(self):
        self.settings = get_settings()
        if self.settings.resend_api_key:
            resend.api_key = self.settings.resend_api_key

    @property
    def is_configured(self) -> bool:
        """Check if email sending is configured."""
        return bool(
            self.settings.resend_api_key
            and self.settings.notification_email
        )

    def send(
        self,
        subject: str,
        html: str,
        to: Optional[str] = None,
        from_email: str = "SaleWatcher <salewatcher@resend.dev>",
    ) -> Optional[str]:
        """
        Send an email.

        Args:
            subject: Email subject
            html: HTML content
            to: Recipient email (defaults to configured notification email)
            from_email: Sender email

        Returns:
            Email ID if sent, None if sending is disabled
        """
        if not self.is_configured:
            print("Email sending not configured, skipping...")
            return None

        to_email = to or self.settings.notification_email

        try:
            response = resend.Emails.send({
                "from": from_email,
                "to": to_email,
                "subject": subject,
                "html": html,
            })
            return response.get("id")
        except Exception as e:
            print(f"Failed to send email: {e}")
            return None


# Singleton instance
_client: Optional[EmailClient] = None


def get_email_client() -> EmailClient:
    """Get or create the email client singleton."""
    global _client
    if _client is None:
        _client = EmailClient()
    return _client
