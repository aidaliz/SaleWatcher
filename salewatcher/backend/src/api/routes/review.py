from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.deps import get_db
from src.db.models import ExtractedSale, ExtractionStatus, RawEmail, Brand
from src.db.schemas import ReviewAction, ReviewItem, ReviewListResponse

router = APIRouter()


@router.get("", response_model=ReviewListResponse)
async def list_review_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List items pending review."""
    # Get total count
    count_query = select(func.count(ExtractedSale.id)).where(
        ExtractedSale.status == ExtractionStatus.NEEDS_REVIEW
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Get review items with related data
    query = (
        select(ExtractedSale, RawEmail, Brand)
        .join(RawEmail, ExtractedSale.raw_email_id == RawEmail.id)
        .join(Brand, RawEmail.brand_id == Brand.id)
        .where(ExtractedSale.status == ExtractionStatus.NEEDS_REVIEW)
        .order_by(ExtractedSale.extracted_at.desc())
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    items = []
    for extracted_sale, raw_email, brand in rows:
        items.append(
            ReviewItem(
                id=extracted_sale.id,
                raw_email_id=raw_email.id,
                brand_name=brand.name,
                email_subject=raw_email.subject,
                sent_at=raw_email.sent_at,
                is_sale=extracted_sale.is_sale,
                discount_summary=extracted_sale.discount_summary,
                confidence=extracted_sale.confidence,
                model_used=extracted_sale.model_used,
                extracted_at=extracted_sale.extracted_at,
            )
        )

    return ReviewListResponse(items=items, total=total)


@router.post("/{extraction_id}/approve", status_code=status.HTTP_200_OK)
async def approve_extraction(
    extraction_id: UUID,
    action: ReviewAction = ReviewAction(),
    db: AsyncSession = Depends(get_db),
):
    """Approve an extraction from the review queue."""
    result = await db.execute(
        select(ExtractedSale).where(ExtractedSale.id == extraction_id)
    )
    extraction = result.scalar_one_or_none()

    if extraction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extraction not found",
        )

    if extraction.status != ExtractionStatus.NEEDS_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Extraction is not pending review",
        )

    extraction.status = ExtractionStatus.APPROVED
    extraction.review_notes = action.notes
    extraction.reviewed_at = datetime.utcnow()

    await db.flush()

    return {"status": "approved", "id": str(extraction_id)}


@router.post("/{extraction_id}/reject", status_code=status.HTTP_200_OK)
async def reject_extraction(
    extraction_id: UUID,
    action: ReviewAction = ReviewAction(),
    db: AsyncSession = Depends(get_db),
):
    """Reject an extraction from the review queue."""
    result = await db.execute(
        select(ExtractedSale).where(ExtractedSale.id == extraction_id)
    )
    extraction = result.scalar_one_or_none()

    if extraction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extraction not found",
        )

    if extraction.status != ExtractionStatus.NEEDS_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Extraction is not pending review",
        )

    extraction.status = ExtractionStatus.REJECTED
    extraction.review_notes = action.notes
    extraction.reviewed_at = datetime.utcnow()

    await db.flush()

    return {"status": "rejected", "id": str(extraction_id)}
