"""
API routes for email synchronization from Gmail.

Supports web-based OAuth2 flow for Gmail authentication.
"""
import json
import os
import secrets
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.db.models import Brand
from src.email_ingest import GmailClient, EmailIngestionService
from src.config import settings

router = APIRouter()


class SyncRequest(BaseModel):
    """Request body for email sync."""
    days_back: int = 365
    max_emails: int = 100


class SyncResponse(BaseModel):
    """Response for sync operation."""
    status: str
    message: str
    stats: Optional[dict] = None


class GmailStatusResponse(BaseModel):
    """Response for Gmail setup status."""
    configured: bool
    authenticated: bool
    message: str


class OAuthUrlResponse(BaseModel):
    """Response containing OAuth authorization URL."""
    auth_url: str
    state: str


# In-memory state storage for OAuth (use Redis in production)
_oauth_states: dict[str, bool] = {}

# Global Gmail client instance
_gmail_client: Optional[GmailClient] = None


def get_gmail_client() -> GmailClient:
    """Get or create Gmail client instance."""
    global _gmail_client
    if _gmail_client is None:
        _gmail_client = GmailClient()
    return _gmail_client


def _is_gmail_configured() -> bool:
    """Check if Gmail OAuth credentials are configured."""
    client_id = os.getenv('GMAIL_CLIENT_ID')
    client_secret = os.getenv('GMAIL_CLIENT_SECRET')
    return bool(client_id and client_secret)


def _get_stored_token() -> Optional[dict]:
    """Get stored Gmail token from environment or file."""
    # First try environment variable (for production deployment)
    token_json = os.getenv('GMAIL_TOKEN_JSON')
    if token_json:
        try:
            return json.loads(token_json)
        except json.JSONDecodeError:
            pass

    # Fall back to token file (for local development)
    token_path = 'gmail_token.json'
    if os.path.exists(token_path):
        try:
            with open(token_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    return None


def _save_token(token_data: dict) -> None:
    """Save token to file for local development."""
    token_path = 'gmail_token.json'
    try:
        with open(token_path, 'w') as f:
            json.dump(token_data, f, indent=2)
    except IOError as e:
        # In production, token should be set via GMAIL_TOKEN_JSON env var
        pass


@router.get("/gmail/status", response_model=GmailStatusResponse)
async def get_gmail_status():
    """
    Check Gmail API configuration and authentication status.

    Returns:
        - configured: Whether OAuth credentials are set
        - authenticated: Whether we have valid tokens
        - message: Human-readable status message
    """
    if not _is_gmail_configured():
        return GmailStatusResponse(
            configured=False,
            authenticated=False,
            message="Gmail not configured. Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET environment variables.",
        )

    token_data = _get_stored_token()
    if not token_data:
        return GmailStatusResponse(
            configured=True,
            authenticated=False,
            message="Gmail configured but not authenticated. Start the OAuth flow to connect your Gmail account.",
        )

    # Try to authenticate with stored token
    client = get_gmail_client()
    try:
        if client.authenticate_with_token(token_data):
            return GmailStatusResponse(
                configured=True,
                authenticated=True,
                message="Gmail connected and ready to sync emails.",
            )
    except Exception as e:
        return GmailStatusResponse(
            configured=True,
            authenticated=False,
            message=f"Gmail token invalid or expired: {str(e)}",
        )

    return GmailStatusResponse(
        configured=True,
        authenticated=False,
        message="Gmail authentication required. Token may have expired.",
    )


@router.get("/gmail/auth/start", response_model=OAuthUrlResponse)
async def start_gmail_oauth():
    """
    Start the Gmail OAuth2 flow.

    Returns the authorization URL to redirect the user to Google's consent screen.
    The user will be redirected back to /api/email/gmail/auth/callback after authorizing.
    """
    if not _is_gmail_configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gmail not configured. Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET environment variables.",
        )

    client = get_gmail_client()

    # Generate a random state for CSRF protection
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = True

    try:
        auth_url = client.get_auth_url(state=state)
        return OAuthUrlResponse(auth_url=auth_url, state=state)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate auth URL: {str(e)}",
        )


@router.get("/gmail/auth/callback")
async def gmail_oauth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    error: Optional[str] = Query(None, description="Error from OAuth flow"),
):
    """
    Handle OAuth2 callback from Google.

    Exchanges the authorization code for tokens and saves them.
    Redirects to the dashboard on success.
    """
    # Check for OAuth errors
    if error:
        # Redirect to dashboard with error
        return RedirectResponse(
            url=f"/settings?gmail_error={error}",
            status_code=status.HTTP_302_FOUND,
        )

    # Verify state for CSRF protection
    if state not in _oauth_states:
        return RedirectResponse(
            url="/settings?gmail_error=invalid_state",
            status_code=status.HTTP_302_FOUND,
        )

    # Remove used state
    del _oauth_states[state]

    client = get_gmail_client()

    try:
        # Exchange code for tokens
        token_data = client.exchange_code(code)

        # Save token for future use
        _save_token(token_data)

        # Authenticate with the new token
        if client.authenticate_with_token(token_data):
            return RedirectResponse(
                url="/settings?gmail_success=true",
                status_code=status.HTTP_302_FOUND,
            )
        else:
            return RedirectResponse(
                url="/settings?gmail_error=auth_failed",
                status_code=status.HTTP_302_FOUND,
            )

    except Exception as e:
        return RedirectResponse(
            url=f"/settings?gmail_error={str(e)}",
            status_code=status.HTTP_302_FOUND,
        )


@router.post("/gmail/disconnect")
async def disconnect_gmail():
    """
    Disconnect Gmail by removing stored tokens.
    """
    global _gmail_client

    # Remove token file if it exists
    token_path = 'gmail_token.json'
    if os.path.exists(token_path):
        try:
            os.remove(token_path)
        except IOError:
            pass

    # Reset client
    _gmail_client = None

    return {"status": "success", "message": "Gmail disconnected"}


@router.post("/sync/brand/{brand_id}", response_model=SyncResponse)
async def sync_brand_emails(
    brand_id: UUID,
    request: SyncRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Sync emails for a specific brand from Gmail.

    Fetches promotional emails from the configured Gmail account
    for the specified brand and stores them for extraction.
    """
    # Get brand
    query = select(Brand).where(Brand.id == brand_id)
    result = await db.execute(query)
    brand = result.scalar_one_or_none()

    if not brand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )

    # Check authentication
    token_data = _get_stored_token()
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gmail not authenticated. Please connect your Gmail account first.",
        )

    client = get_gmail_client()
    if not client.authenticate_with_token(token_data):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gmail authentication failed. Please reconnect your Gmail account.",
        )

    # Sync emails
    service = EmailIngestionService(client)
    stats = await service.sync_brand_emails(
        db, brand, request.days_back, request.max_emails
    )

    return SyncResponse(
        status="success",
        message=f"Synced {stats['new']} new emails for {brand.name}",
        stats=stats,
    )


@router.post("/sync/all", response_model=SyncResponse)
async def sync_all_brands(
    request: SyncRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Sync emails for all active brands from Gmail.

    Iterates through all brands and syncs promotional emails from Gmail.
    """
    # Check authentication
    token_data = _get_stored_token()
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gmail not authenticated. Please connect your Gmail account first.",
        )

    client = get_gmail_client()
    if not client.authenticate_with_token(token_data):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gmail authentication failed. Please reconnect your Gmail account.",
        )

    # Sync all brands
    service = EmailIngestionService(client)
    all_stats = await service.sync_all_brands(
        db, request.days_back, request.max_emails
    )

    total_new = sum(s.get('new', 0) for s in all_stats if isinstance(s.get('new'), int))
    total_duplicates = sum(s.get('duplicates', 0) for s in all_stats if isinstance(s.get('duplicates'), int))

    return SyncResponse(
        status="success",
        message=f"Synced {total_new} new emails across {len(all_stats)} brands ({total_duplicates} duplicates skipped)",
        stats={"brands": all_stats},
    )
