"""
API routes for email synchronization from Gmail.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
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


class GmailSetupResponse(BaseModel):
    """Response for Gmail setup status."""
    configured: bool
    authenticated: bool
    message: str


# Global Gmail client instance
_gmail_client: Optional[GmailClient] = None


def get_gmail_client() -> GmailClient:
    """Get or create Gmail client instance."""
    global _gmail_client
    if _gmail_client is None:
        _gmail_client = GmailClient(
            credentials_path='gmail_credentials.json',
            token_path='gmail_token.json',
        )
    return _gmail_client


@router.get("/gmail/status", response_model=GmailSetupResponse)
async def get_gmail_status():
    """Check Gmail API configuration status."""
    import os

    credentials_exist = os.path.exists('gmail_credentials.json')
    token_exists = os.path.exists('gmail_token.json')

    if not credentials_exist:
        return GmailSetupResponse(
            configured=False,
            authenticated=False,
            message="Gmail credentials not configured. Download credentials.json from Google Cloud Console and save as gmail_credentials.json",
        )

    if not token_exists:
        return GmailSetupResponse(
            configured=True,
            authenticated=False,
            message="Gmail configured but not authenticated. Run the authentication flow to connect your Gmail account.",
        )

    # Try to authenticate
    client = get_gmail_client()
    try:
        if client.authenticate():
            return GmailSetupResponse(
                configured=True,
                authenticated=True,
                message="Gmail connected and ready to sync emails.",
            )
    except Exception as e:
        return GmailSetupResponse(
            configured=True,
            authenticated=False,
            message=f"Gmail authentication failed: {str(e)}",
        )

    return GmailSetupResponse(
        configured=True,
        authenticated=False,
        message="Gmail authentication required.",
    )


@router.post("/gmail/authenticate")
async def authenticate_gmail():
    """
    Initiate Gmail OAuth2 authentication.

    Note: This will open a browser window for authentication.
    Only works when running locally.
    """
    client = get_gmail_client()

    try:
        success = client.authenticate()
        if success:
            return {"status": "success", "message": "Gmail authentication successful"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Gmail authentication failed",
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {str(e)}",
        )


@router.post("/sync/brand/{brand_id}", response_model=SyncResponse)
async def sync_brand_emails(
    brand_id: UUID,
    request: SyncRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Sync emails for a specific brand from Gmail.
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

    # Get Gmail client
    client = get_gmail_client()
    if not client.authenticate():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gmail not authenticated. Please authenticate first.",
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
    """
    # Get Gmail client
    client = get_gmail_client()
    if not client.authenticate():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gmail not authenticated. Please authenticate first.",
        )

    # Sync all brands
    service = EmailIngestionService(client)
    all_stats = await service.sync_all_brands(
        db, request.days_back, request.max_emails_per_brand
    )

    total_new = sum(s.get('new', 0) for s in all_stats if isinstance(s.get('new'), int))
    total_duplicates = sum(s.get('duplicates', 0) for s in all_stats if isinstance(s.get('duplicates'), int))

    return SyncResponse(
        status="success",
        message=f"Synced {total_new} new emails across {len(all_stats)} brands ({total_duplicates} duplicates skipped)",
        stats={"brands": all_stats},
    )
