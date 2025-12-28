"""
Gmail API integration for ingesting brand emails.

This module connects to Gmail via OAuth2 and fetches promotional emails
from tracked brands for sale extraction.
"""
import base64
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional
from email.utils import parsedate_to_datetime

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Gmail API scopes - read-only access to emails
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


class GmailClient:
    """Client for interacting with Gmail API."""

    def __init__(self, credentials_path: str = 'credentials.json', token_path: str = 'token.json'):
        """
        Initialize Gmail client.

        Args:
            credentials_path: Path to OAuth2 credentials JSON from Google Cloud Console
            token_path: Path to store/load the user's access token
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        self.creds = None

    def authenticate(self) -> bool:
        """
        Authenticate with Gmail API using OAuth2.

        Returns:
            True if authentication successful
        """
        try:
            # Try to load existing token
            try:
                self.creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            except FileNotFoundError:
                self.creds = None

            # If no valid credentials, get new ones
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, SCOPES
                    )
                    self.creds = flow.run_local_server(port=0)

                # Save the credentials for next run
                with open(self.token_path, 'w') as token:
                    token.write(self.creds.to_json())

            # Build the Gmail service
            self.service = build('gmail', 'v1', credentials=self.creds)
            logger.info("Gmail authentication successful")
            return True

        except Exception as e:
            logger.error(f"Gmail authentication failed: {e}")
            return False

    def search_emails(
        self,
        sender_email: str,
        days_back: int = 365,
        max_results: int = 100,
    ) -> list[dict]:
        """
        Search for emails from a specific sender.

        Args:
            sender_email: Email address or domain to search for (e.g., "skullcandy.com")
            days_back: How many days of history to search
            max_results: Maximum number of emails to return

        Returns:
            List of email metadata dicts
        """
        if not self.service:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        # Build search query
        after_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')
        query = f"from:{sender_email} after:{after_date}"

        logger.info(f"Searching Gmail: {query}")

        try:
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results,
            ).execute()

            messages = results.get('messages', [])
            logger.info(f"Found {len(messages)} emails from {sender_email}")

            return messages

        except HttpError as e:
            logger.error(f"Gmail search failed: {e}")
            return []

    def get_email_content(self, message_id: str) -> Optional[dict]:
        """
        Fetch full email content by message ID.

        Args:
            message_id: Gmail message ID

        Returns:
            Dict with email details or None if failed
        """
        if not self.service:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full',
            ).execute()

            # Extract headers
            headers = {h['name'].lower(): h['value'] for h in message['payload']['headers']}

            subject = headers.get('subject', '')
            from_header = headers.get('from', '')
            date_str = headers.get('date', '')

            # Parse date
            try:
                sent_at = parsedate_to_datetime(date_str)
            except:
                sent_at = datetime.now()

            # Extract HTML body
            html_content = self._extract_html_body(message['payload'])

            return {
                'message_id': message_id,
                'subject': subject,
                'from': from_header,
                'sent_at': sent_at,
                'html_content': html_content or '',
            }

        except HttpError as e:
            logger.error(f"Failed to fetch email {message_id}: {e}")
            return None

    def _extract_html_body(self, payload: dict) -> Optional[str]:
        """Extract HTML body from email payload."""

        # Check if this part is HTML
        if payload.get('mimeType') == 'text/html':
            data = payload.get('body', {}).get('data', '')
            if data:
                return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')

        # Check nested parts
        parts = payload.get('parts', [])
        for part in parts:
            html = self._extract_html_body(part)
            if html:
                return html

        return None


def generate_email_hash(brand_slug: str, subject: str, sent_date: datetime) -> str:
    """
    Generate a unique hash for deduplication.

    Args:
        brand_slug: Brand identifier
        subject: Email subject line
        sent_date: Date the email was sent

    Returns:
        SHA256 hash string
    """
    # Normalize the date to just the date part (ignore time)
    date_str = sent_date.strftime('%Y-%m-%d')

    # Create composite key
    key = f"{brand_slug.lower()}|{subject}|{date_str}"

    # Generate hash
    return hashlib.sha256(key.encode()).hexdigest()


# Brand email domain mappings
BRAND_EMAIL_DOMAINS = {
    'gamestop': ['gamestop.com', 'em.gamestop.com'],
    'skullcandy': ['skullcandy.com', 'e.skullcandy.com'],
    'target': ['target.com', 'em.target.com'],
    'bestbuy': ['bestbuy.com', 'emailinfo.bestbuy.com'],
    'walmart': ['walmart.com', 'email.walmart.com'],
    'amazon': ['amazon.com', 'email.amazon.com'],
    'kohls': ['kohls.com', 'e.kohls.com'],
    'macys': ['macys.com', 'e.macys.com'],
    'nordstrom': ['nordstrom.com', 'e.nordstrom.com'],
    'nike': ['nike.com', 'email.nike.com'],
    'adidas': ['adidas.com', 'email.adidas.com'],
}


def get_brand_email_query(brand_slug: str) -> str:
    """
    Get Gmail search query for a brand.

    Args:
        brand_slug: Brand identifier

    Returns:
        Gmail search query string
    """
    domains = BRAND_EMAIL_DOMAINS.get(brand_slug.lower(), [f"{brand_slug}.com"])

    # Build OR query for multiple domains
    domain_queries = [f"from:{domain}" for domain in domains]
    return " OR ".join(domain_queries)
