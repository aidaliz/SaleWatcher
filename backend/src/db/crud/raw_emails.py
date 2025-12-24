"""CRUD operations for RawEmail entity."""

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import RawEmail


async def get_raw_email(db: AsyncSession, email_id: UUID) -> RawEmail | None:
    """Get a single raw email by ID."""
    result = await db.execute(select(RawEmail).where(RawEmail.id == email_id))
    return result.scalar_one_or_none()


async def get_raw_email_by_url(db: AsyncSession, milled_url: str) -> RawEmail | None:
    """Get a raw email by Milled.com URL (to check for duplicates)."""
    result = await db.execute(select(RawEmail).where(RawEmail.milled_url == milled_url))
    return result.scalar_one_or_none()


async def get_raw_emails_for_brand(
    db: AsyncSession,
    brand_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[RawEmail], int]:
    """Get raw emails for a brand with optional date filtering."""
    query = select(RawEmail).where(RawEmail.brand_id == brand_id)

    if start_date:
        query = query.where(RawEmail.sent_at >= start_date)
    if end_date:
        query = query.where(RawEmail.sent_at <= end_date)

    # Get total count
    count_result = await db.execute(query)
    total = len(count_result.scalars().all())

    # Get paginated results
    query = query.order_by(RawEmail.sent_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    emails = result.scalars().all()

    return list(emails), total


async def create_raw_email(
    db: AsyncSession,
    brand_id: UUID,
    milled_url: str,
    subject: str,
    sent_at: date,
    html_content: str,
) -> RawEmail:
    """Create a new raw email record."""
    db_email = RawEmail(
        brand_id=brand_id,
        milled_url=milled_url,
        subject=subject,
        sent_at=sent_at,
        html_content=html_content,
    )
    db.add(db_email)
    await db.commit()
    await db.refresh(db_email)
    return db_email


async def create_raw_email_if_not_exists(
    db: AsyncSession,
    brand_id: UUID,
    milled_url: str,
    subject: str,
    sent_at: date,
    html_content: str,
) -> tuple[RawEmail, bool]:
    """
    Create a raw email if it doesn't already exist.

    Returns:
        Tuple of (email, created) where created is True if new, False if existing.
    """
    existing = await get_raw_email_by_url(db, milled_url)
    if existing:
        return existing, False

    email = await create_raw_email(
        db=db,
        brand_id=brand_id,
        milled_url=milled_url,
        subject=subject,
        sent_at=sent_at,
        html_content=html_content,
    )
    return email, True
