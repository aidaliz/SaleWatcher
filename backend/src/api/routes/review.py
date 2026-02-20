"""Review queue API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.db.crud import extracted_sales as crud_reviews

router = APIRouter()


class ReviewItem(BaseModel):
    """Response model for review queue items."""
    id: UUID
    email_id: UUID
    brand_name: str
    email_subject: str
    discount_type: str
    discount_value: float | None
    discount_max: float | None
    is_sitewide: bool
    categories: list[str]
    confidence: float
    raw_discount_text: str | None
    model_used: str | None

    class Config:
        from_attributes = True


class ReviewListResponse(BaseModel):
    """Response for list of review items."""
    reviews: list[ReviewItem]
    total: int


class ReviewDetailResponse(ReviewItem):
    """Detailed review response including email content."""
    email_html: str | None
    sale_start: str | None
    sale_end: str | None
    conditions: list[str]


@router.get("", response_model=ReviewListResponse)
async def list_pending_reviews(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db_session),
):
    """List extractions pending review."""
    extractions, total = await crud_reviews.get_pending_reviews(db, skip=skip, limit=limit)

    reviews = []
    for ext in extractions:
        reviews.append(ReviewItem(
            id=ext.id,
            email_id=ext.email_id,
            brand_name=ext.email.brand.name if ext.email and ext.email.brand else "Unknown",
            email_subject=ext.email.subject if ext.email else "",
            discount_type=ext.discount_type,
            discount_value=ext.discount_value,
            discount_max=ext.discount_max,
            is_sitewide=ext.is_sitewide,
            categories=list(ext.categories or []),
            confidence=ext.confidence,
            raw_discount_text=ext.raw_discount_text,
            model_used=ext.model_used,
        ))

    return ReviewListResponse(reviews=reviews, total=total)


@router.get("/{extraction_id}", response_model=ReviewDetailResponse)
async def get_review_details(
    extraction_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Get detailed information about a pending review."""
    extraction = await crud_reviews.get_extraction(db, extraction_id)
    if not extraction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extraction not found",
        )

    return ReviewDetailResponse(
        id=extraction.id,
        email_id=extraction.email_id,
        brand_name=extraction.email.brand.name if extraction.email and extraction.email.brand else "Unknown",
        email_subject=extraction.email.subject if extraction.email else "",
        discount_type=extraction.discount_type,
        discount_value=extraction.discount_value,
        discount_max=extraction.discount_max,
        is_sitewide=extraction.is_sitewide,
        categories=list(extraction.categories or []),
        confidence=extraction.confidence,
        raw_discount_text=extraction.raw_discount_text,
        model_used=extraction.model_used,
        email_html=extraction.email.html_content if extraction.email else None,
        sale_start=str(extraction.sale_start) if extraction.sale_start else None,
        sale_end=str(extraction.sale_end) if extraction.sale_end else None,
        conditions=list(extraction.conditions or []),
    )


@router.post("/{extraction_id}/approve")
async def approve_extraction(
    extraction_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Approve a borderline extraction."""
    extraction = await crud_reviews.approve_extraction(db, extraction_id)
    if not extraction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extraction not found",
        )
    return {"status": "approved", "id": str(extraction_id)}


@router.post("/{extraction_id}/reject")
async def reject_extraction(
    extraction_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Reject a borderline extraction."""
    extraction = await crud_reviews.reject_extraction(db, extraction_id)
    if not extraction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extraction not found",
        )
    return {"status": "rejected", "id": str(extraction_id)}
