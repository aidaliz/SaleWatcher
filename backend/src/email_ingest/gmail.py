"""
Gmail API integration for ingesting brand emails.

This module connects to Gmail via OAuth2 and fetches promotional emails
from tracked brands for sale extraction.

Supports both local development and web deployment OAuth flows.
"""
import base64
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional
from email.utils import parsedate_to_datetime

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Gmail API scopes - read-only access to emails
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


class GmailClient:
    """Client for interacting with Gmail API."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
    ):
        """
        Initialize Gmail client.

        Args:
            client_id: OAuth2 client ID (or set GMAIL_CLIENT_ID env var)
            client_secret: OAuth2 client secret (or set GMAIL_CLIENT_SECRET env var)
            redirect_uri: OAuth2 redirect URI (or set GMAIL_REDIRECT_URI env var)
        """
        self.client_id = client_id or os.getenv('GMAIL_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('GMAIL_CLIENT_SECRET')
        self.redirect_uri = redirect_uri or os.getenv('GMAIL_REDIRECT_URI', 'http://localhost:8000/api/email/gmail/auth/callback')

        self.service = None
        self.creds = None

    def get_auth_url(self, state: Optional[str] = None) -> str:
        """
        Get the OAuth2 authorization URL for user to authenticate.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Authorization URL to redirect user to
        """
        flow = self._create_flow()
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state=state,
        )
        return auth_url

    def exchange_code(self, code: str) -> dict:
        """
        Exchange authorization code for tokens.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Token dict with access_token, refresh_token, etc.
        """
        flow = self._create_flow()
        flow.fetch_token(code=code)

        creds = flow.credentials
        token_data = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': list(creds.scopes),
        }

        return token_data

    def authenticate_with_token(self, token_data: dict) -> bool:
        """
        Authenticate using saved token data.

        Args:
            token_data: Token dict from exchange_code() or environment

        Returns:
            True if authentication successful
        """
        try:
            self.creds = Credentials(
                token=token_data.get('token'),
                refresh_token=token_data.get('refresh_token'),
                token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
                client_id=token_data.get('client_id', self.client_id),
                client_secret=token_data.get('client_secret', self.client_secret),
                scopes=token_data.get('scopes', SCOPES),
            )

            # Refresh if expired
            if self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())

            # Build the Gmail service
            self.service = build('gmail', 'v1', credentials=self.creds)
            logger.info("Gmail authentication successful")
            return True

        except Exception as e:
            logger.error(f"Gmail authentication failed: {e}")
            return False

    def authenticate_from_env(self) -> bool:
        """
        Authenticate using token stored in GMAIL_TOKEN_JSON environment variable.

        Returns:
            True if authentication successful
        """
        token_json = os.getenv('GMAIL_TOKEN_JSON')
        if not token_json:
            logger.error("GMAIL_TOKEN_JSON environment variable not set")
            return False

        try:
            token_data = json.loads(token_json)
            return self.authenticate_with_token(token_data)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid GMAIL_TOKEN_JSON: {e}")
            return False

    def _create_flow(self) -> Flow:
        """Create OAuth2 flow for web application."""
        if not self.client_id or not self.client_secret:
            raise ValueError(
                "Gmail OAuth credentials not configured. "
                "Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET environment variables."
            )

        client_config = {
            'web': {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'redirect_uris': [self.redirect_uri],
            }
        }

        return Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=self.redirect_uri,
        )

    def is_authenticated(self) -> bool:
        """Check if client is authenticated and ready."""
        return self.service is not None and self.creds is not None and self.creds.valid

    def get_token_json(self) -> Optional[str]:
        """Get current token as JSON string for storage."""
        if not self.creds:
            return None

        token_data = {
            'token': self.creds.token,
            'refresh_token': self.creds.refresh_token,
            'token_uri': self.creds.token_uri,
            'client_id': self.creds.client_id,
            'client_secret': self.creds.client_secret,
            'scopes': list(self.creds.scopes) if self.creds.scopes else SCOPES,
        }
        return json.dumps(token_data)

    def search_emails(
        self,
        sender_email: str,
        days_back: int = 365,
        max_results: Optional[int] = None,
    ) -> list[dict]:
        """
        Search for emails from a specific sender.

        Args:
            sender_email: Email address or domain to search for (e.g., "skullcandy.com")
            days_back: How many days of history to search
            max_results: Maximum number of emails to return (None = all emails in date range)

        Returns:
            List of email metadata dicts
        """
        if not self.service:
            raise RuntimeError("Not authenticated. Call authenticate first.")

        # Build search query
        after_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')
        query = f"from:{sender_email} after:{after_date}"

        logger.info(f"Searching Gmail: {query}")

        try:
            all_messages = []
            page_token = None

            while True:
                # Gmail API maxResults is capped at 500 per page
                page_size = min(500, max_results - len(all_messages)) if max_results else 500

                results = self.service.users().messages().list(
                    userId='me',
                    q=query,
                    maxResults=page_size,
                    pageToken=page_token,
                ).execute()

                messages = results.get('messages', [])
                all_messages.extend(messages)

                # Check if we've hit the limit or no more pages
                if max_results and len(all_messages) >= max_results:
                    all_messages = all_messages[:max_results]
                    break

                page_token = results.get('nextPageToken')
                if not page_token:
                    break

            logger.info(f"Found {len(all_messages)} emails from {sender_email}")
            return all_messages

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
            raise RuntimeError("Not authenticated. Call authenticate first.")

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
