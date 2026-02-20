"""CRUD operations for ExtractedSale (review queue)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import ExtractedSale, RawEmail, Brand


async def get_pending_reviews(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[ExtractedSale], int]:
    """Get extractions pending review."""
    # Count query
    count_query = select(ExtractedSale).where(ExtractedSale.review_status == "pending")
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())

    # Paginated query with relationships
    query = (
        select(ExtractedSale)
        .where(ExtractedSale.review_status == "pending")
        .options(
            selectinload(ExtractedSale.email).selectinload(RawEmail.brand)
        )
        .order_by(ExtractedSale.confidence.asc())  # Lowest confidence first
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(query)
    extractions = result.scalars().all()

    return list(extractions), total


async def get_extraction(db: AsyncSession, extraction_id: UUID) -> ExtractedSale | None:
    """Get a single extraction by ID."""
    query = (
        select(ExtractedSale)
        .where(ExtractedSale.id == extraction_id)
        .options(
            selectinload(ExtractedSale.email).selectinload(RawEmail.brand)
        )
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def update_review_status(
    db: AsyncSession,
    extraction_id: UUID,
    status: Literal["approved", "rejected"],
) -> ExtractedSale | None:
    """Approve or reject an extraction."""
    extraction = await get_extraction(db, extraction_id)
    if not extraction:
        return None

    extraction.review_status = status
    extraction.reviewed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(extraction)

    return extraction


async def approve_extraction(db: AsyncSession, extraction_id: UUID) -> ExtractedSale | None:
    """Approve an extraction."""
    return await update_review_status(db, extraction_id, "approved")


async def reject_extraction(db: AsyncSession, extraction_id: UUID) -> ExtractedSale | None:
    """Reject an extraction."""
    return await update_review_status(db, extraction_id, "rejected")


async def get_extractions_by_brand(
    db: AsyncSession,
    brand_id: UUID,
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
) -> tuple[list[ExtractedSale], int]:
    """Get extractions for a specific brand."""
    # Build base query
    query = (
        select(ExtractedSale)
        .join(RawEmail)
        .where(RawEmail.brand_id == brand_id)
        .options(selectinload(ExtractedSale.email))
    )

    if status:
        query = query.where(ExtractedSale.review_status == status)

    # Get count
    count_result = await db.execute(query)
    total = len(count_result.scalars().all())

    # Get paginated results
    query = query.order_by(ExtractedSale.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    extractions = result.scalars().all()

    return list(extractions), total
