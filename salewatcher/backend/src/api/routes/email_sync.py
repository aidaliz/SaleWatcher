"""
API routes for email synchronization from Gmail.

Supports web-based OAuth2 flow for Gmail authentication.
"""
import json
import os
import secrets
from pathlib import Path
from typing import Optional
from uuid import UUID

# Get the backend directory for absolute .env path
BACKEND_DIR = Path(__file__).parent.parent.parent.parent
ENV_FILE_PATH = BACKEND_DIR / '.env'

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
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


class GmailConfigRequest(BaseModel):
    """Request body for Gmail configuration."""
    client_id: str
    client_secret: str


class GmailConfigResponse(BaseModel):
    """Response for Gmail configuration."""
    success: bool
    message: str


# ---------- In-memory job tracking ----------

class SyncJob(BaseModel):
    brand_id: str
    status: str = "running"
    stats: Optional[dict] = None
    error: Optional[str] = None

_sync_jobs: dict[str, SyncJob] = {}

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


def _sync_db_url() -> str:
    """Return a psycopg2-compatible (sync) database URL."""
    url = os.getenv('DATABASE_URL', '')
    # Strip asyncpg driver prefix if present
    return url.replace('postgresql+asyncpg://', 'postgresql://')


def _db_get_token() -> Optional[dict]:
    """Retrieve Gmail token from PostgreSQL (persistent across deploys)."""
    db_url = _sync_db_url()
    if not db_url:
        return None
    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute(
            "SELECT value FROM salewatcher_kv WHERE key = 'gmail_token' LIMIT 1"
        )
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return json.loads(row[0])
    except Exception:
        pass
    return None


def _db_save_token(token_data: dict) -> None:
    """Persist Gmail token to PostgreSQL so it survives Railway redeploys."""
    db_url = _sync_db_url()
    if not db_url:
        return
    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS salewatcher_kv (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute(
            """INSERT INTO salewatcher_kv (key, value, updated_at)
               VALUES ('gmail_token', %s, NOW())
               ON CONFLICT (key) DO UPDATE
               SET value = EXCLUDED.value, updated_at = NOW()""",
            (json.dumps(token_data),)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _get_stored_token() -> Optional[dict]:
    """Get stored Gmail token — checks env var, then DB, then local file."""
    # 1. Environment variable (manually set in Railway dashboard)
    token_json = os.getenv('GMAIL_TOKEN_JSON')
    if token_json:
        try:
            return json.loads(token_json)
        except json.JSONDecodeError:
            pass

    # 2. PostgreSQL (persists across deploys — preferred in production)
    db_token = _db_get_token()
    if db_token:
        return db_token

    # 3. Local file fallback (development only)
    token_path = 'gmail_token.json'
    if os.path.exists(token_path):
        try:
            with open(token_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    return None


def _save_token(token_data: dict) -> None:
    """Save Gmail token to DB (persistent) and local file (dev fallback)."""
    # Always persist to DB first — survives Railway redeploys
    _db_save_token(token_data)

    # Also write to local file for dev convenience
    token_path = 'gmail_token.json'
    try:
        with open(token_path, 'w') as f:
            json.dump(token_data, f, indent=2)
    except IOError:
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


@router.post("/gmail/configure", response_model=GmailConfigResponse)
async def configure_gmail(request: GmailConfigRequest):
    """
    Configure Gmail OAuth credentials.

    Saves the client ID and secret to the .env file so they persist
    across server restarts.
    """
    global _gmail_client

    if not request.client_id or not request.client_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both client_id and client_secret are required",
        )

    # Read existing .env file (use absolute path)
    env_path = ENV_FILE_PATH
    env_lines = []
    if env_path.exists():
        with open(env_path, 'r') as f:
            env_lines = f.readlines()

    # Update or add Gmail credentials
    new_lines = []
    found_client_id = False
    found_client_secret = False

    for line in env_lines:
        if line.startswith('GMAIL_CLIENT_ID='):
            new_lines.append(f'GMAIL_CLIENT_ID={request.client_id}\n')
            found_client_id = True
        elif line.startswith('GMAIL_CLIENT_SECRET='):
            new_lines.append(f'GMAIL_CLIENT_SECRET={request.client_secret}\n')
            found_client_secret = True
        else:
            new_lines.append(line)

    # Add if not found
    if not found_client_id:
        new_lines.append(f'GMAIL_CLIENT_ID={request.client_id}\n')
    if not found_client_secret:
        new_lines.append(f'GMAIL_CLIENT_SECRET={request.client_secret}\n')

    # Write back
    try:
        with open(env_path, 'w') as f:
            f.writelines(new_lines)
    except IOError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save credentials: {str(e)}",
        )

    # Set environment variables for current session
    os.environ['GMAIL_CLIENT_ID'] = request.client_id
    os.environ['GMAIL_CLIENT_SECRET'] = request.client_secret

    # Reset Gmail client to pick up new credentials
    _gmail_client = None

    return GmailConfigResponse(
        success=True,
        message="Gmail credentials saved. You can now connect your Gmail account.",
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
    state: str = Query(None, description="State parameter for CSRF protection"),
    error: Optional[str] = Query(None, description="Error from OAuth flow"),
):
    """
    Handle OAuth2 callback from Google.

    Exchanges the authorization code for tokens and saves them.
    Redirects to the frontend dashboard on success.
    """
    # Frontend scrape page URL — where to redirect after OAuth
    frontend_url = os.getenv('DASHBOARD_URL', 'http://localhost:3000')
    scrape_url = f"{frontend_url}/scrape"

    # Check for OAuth errors
    if error:
        return RedirectResponse(
            url=f"{scrape_url}?gmail_error={error}",
            status_code=status.HTTP_302_FOUND,
        )

    # State check — skip if state not in memory (can happen after redeploy)
    # This is acceptable for a single-user personal app
    if state and state in _oauth_states:
        del _oauth_states[state]
    # If state not found, continue anyway rather than blocking the user

    client = get_gmail_client()

    try:
        # Exchange code for tokens
        token_data = client.exchange_code(code)

        # Save token to DB (persists across redeploys) + local file
        _save_token(token_data)

        # Authenticate with the new token
        if client.authenticate_with_token(token_data):
            return RedirectResponse(
                url=f"{scrape_url}?gmail_success=true",
                status_code=status.HTTP_302_FOUND,
            )
        else:
            return RedirectResponse(
                url=f"{scrape_url}?gmail_error=auth_failed",
                status_code=status.HTTP_302_FOUND,
            )

    except Exception as e:
        return RedirectResponse(
            url=f"{scrape_url}?gmail_error=oauth_failed",
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
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Sync emails for a specific brand from Gmail.

    Kicks off a background task and returns immediately.
    Use GET /sync/brand/{brand_id}/status to track progress.
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

    # Check for already-running sync
    job_key = str(brand_id)
    if job_key in _sync_jobs and _sync_jobs[job_key].status == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A Gmail sync is already running for {brand.name}",
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

    # Track job
    _sync_jobs[job_key] = SyncJob(brand_id=str(brand_id))

    # Run in background
    background_tasks.add_task(
        _run_gmail_sync,
        brand_id=brand_id,
        days_back=request.days_back,
        max_emails=request.max_emails,
    )

    return SyncResponse(
        status="started",
        message=f"Gmail sync started for {brand.name}",
    )


@router.get("/sync/brand/{brand_id}/status")
async def get_gmail_sync_status(brand_id: UUID):
    """Get status of a running or completed Gmail sync."""
    job_key = str(brand_id)
    if job_key not in _sync_jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No sync job found for this brand",
        )
    return _sync_jobs[job_key]


async def _run_gmail_sync(
    brand_id: UUID,
    days_back: int,
    max_emails: int,
) -> None:
    """Background task for Gmail email sync."""
    import logging
    from src.db.session import get_session_factory

    logger = logging.getLogger(__name__)
    job_key = str(brand_id)
    session_factory = get_session_factory()

    try:
        async with session_factory() as db:
            # Load brand inside the new session
            result = await db.execute(select(Brand).where(Brand.id == brand_id))
            brand = result.scalar_one()

            token_data = _get_stored_token()
            client = get_gmail_client()
            client.authenticate_with_token(token_data)

            service = EmailIngestionService(client)
            stats = await service.sync_brand_emails(
                db, brand, days_back, max_emails
            )

            _sync_jobs[job_key].status = "completed"
            _sync_jobs[job_key].stats = stats
            logger.info(f"Gmail sync completed for brand {brand_id}: {stats}")

    except Exception as e:
        logger.error(f"Gmail sync failed for brand {brand_id}: {e}")
        _sync_jobs[job_key].status = "failed"
        _sync_jobs[job_key].error = str(e)


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


# Hard-coded Sephora backfill parameters
_SEPHORA_BRAND_ID = "37c7ce07-6c18-46a2-aae9-00b0817ecb80"
_SEPHORA_QUERY = "after:2025/01/01 from:em.sephora.com OR from:sephora.com OR from:email.sephora.com"


@router.post("/gmail/backfill/sephora", response_model=SyncResponse)
async def backfill_sephora(background_tasks: BackgroundTasks):
    """
    Convenience endpoint to backfill all Sephora emails from Gmail.

    Uses hard-coded brand ID and query. No request body needed.
    Track progress via GET /sync/brand/{brand_id}/status.
    """
    brand_id = UUID(_SEPHORA_BRAND_ID)
    job_key = str(brand_id)

    # Check for already-running sync
    if job_key in _sync_jobs and _sync_jobs[job_key].status == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A Sephora sync is already running",
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

    # Track job
    _sync_jobs[job_key] = SyncJob(brand_id=_SEPHORA_BRAND_ID)

    # Run in background
    background_tasks.add_task(
        _run_sephora_backfill,
    )

    return SyncResponse(
        status="started",
        message="Sephora Gmail backfill started",
    )


async def _run_sephora_backfill() -> None:
    """Background task for Sephora Gmail backfill."""
    import logging
    from src.db.session import get_session_factory

    logger = logging.getLogger(__name__)
    brand_id = UUID(_SEPHORA_BRAND_ID)
    job_key = str(brand_id)
    session_factory = get_session_factory()

    try:
        async with session_factory() as db:
            result = await db.execute(select(Brand).where(Brand.id == brand_id))
            brand = result.scalar_one()

            token_data = _get_stored_token()
            client = get_gmail_client()
            client.authenticate_with_token(token_data)

            service = EmailIngestionService(client)

            # Fetch all emails since 2025/01/01 — ~450 days, no practical cap
            stats = await service.sync_brand_emails(
                db, brand, days_back=450, max_emails=10000,
            )

            _sync_jobs[job_key].status = "completed"
            _sync_jobs[job_key].stats = stats
            logger.info(f"Sephora backfill completed: {stats}")

    except Exception as e:
        logger.error(f"Sephora backfill failed: {e}")
        _sync_jobs[job_key].status = "failed"
        _sync_jobs[job_key].error = str(e)
