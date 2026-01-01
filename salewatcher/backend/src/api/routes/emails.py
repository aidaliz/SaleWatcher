"""
API routes for viewing emails and extractions.
"""
from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func, case, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.api.deps import get_db
from src.db.models import RawEmail, ExtractedSale, Brand, ExtractionStatus

router = APIRouter()


class EmailDetailResponse(BaseModel):
    """Response for a single email with full content."""
    id: str
    brand_id: str
    brand_name: str
    subject: str
    sent_at: datetime
    source: str
    scraped_at: datetime
    html_content: str
    milled_url: str
    # Extraction info
    is_extracted: bool
    is_sale: Optional[bool] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    discount_summary: Optional[str] = None
    categories: Optional[list[str]] = None
    sale_start: Optional[datetime] = None
    sale_end: Optional[datetime] = None
    confidence: Optional[float] = None
    status: Optional[str] = None


class EmailResponse(BaseModel):
    """Response for a single email."""
    id: str
    brand_id: str
    brand_name: str
    subject: str
    sent_at: datetime
    source: str  # 'gmail' or 'milled'
    scraped_at: datetime
    # Extraction info
    is_extracted: bool
    is_sale: Optional[bool] = None
    discount_summary: Optional[str] = None
    confidence: Optional[float] = None
    review_status: Optional[str] = None


class EmailListResponse(BaseModel):
    """Response for email list."""
    emails: list[EmailResponse]
    total: int
    skip: int
    limit: int


class EmailStatsResponse(BaseModel):
    """Statistics about emails."""
    total_emails: int
    gmail_emails: int
    milled_emails: int
    extracted: int
    not_extracted: int
    sales_found: int
    non_sales: int
    pending_review: int
    by_brand: list[dict]


@router.get("", response_model=EmailListResponse)
async def list_emails(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    brand_id: Optional[UUID] = None,
    source: Optional[Literal["gmail", "milled"]] = None,
    extracted: Optional[bool] = None,
    is_sale: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    List emails with their extraction status.

    Filters:
    - brand_id: Filter by brand
    - source: Filter by source ('gmail' or 'milled')
    - extracted: Filter by extraction status
    - is_sale: Filter by whether the email contains a sale
    """
    # Build query
    query = (
        select(RawEmail)
        .options(
            joinedload(RawEmail.brand),
            joinedload(RawEmail.extracted_sale),
        )
        .order_by(desc(RawEmail.sent_at))
    )

    # Apply filters
    if brand_id:
        query = query.where(RawEmail.brand_id == brand_id)

    if source == "gmail":
        query = query.where(RawEmail.milled_url.like("gmail://%"))
    elif source == "milled":
        query = query.where(~RawEmail.milled_url.like("gmail://%"))

    if extracted is not None:
        if extracted:
            query = query.where(RawEmail.extracted_sale != None)
        else:
            query = query.where(RawEmail.extracted_sale == None)

    if is_sale is not None:
        query = query.join(ExtractedSale).where(ExtractedSale.is_sale == is_sale)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # Apply pagination
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    emails = result.unique().scalars().all()

    # Convert to response
    email_responses = []
    for email in emails:
        source_type = "gmail" if email.milled_url.startswith("gmail://") else "milled"  # Python startswith is fine here
        extraction = email.extracted_sale

        email_responses.append(EmailResponse(
            id=str(email.id),
            brand_id=str(email.brand_id),
            brand_name=email.brand.name if email.brand else "Unknown",
            subject=email.subject,
            sent_at=email.sent_at,
            source=source_type,
            scraped_at=email.scraped_at,
            is_extracted=extraction is not None,
            is_sale=extraction.is_sale if extraction else None,
            discount_summary=extraction.discount_summary if extraction else None,
            confidence=extraction.confidence if extraction else None,
            review_status=extraction.status.value if extraction and extraction.status else None,
        ))

    return EmailListResponse(
        emails=email_responses,
        total=total or 0,
        skip=skip,
        limit=limit,
    )


@router.get("/stats", response_model=EmailStatsResponse)
async def get_email_stats(
    db: AsyncSession = Depends(get_db),
):
    """
    Get statistics about emails and extractions.
    """
    # Total emails
    total_query = select(func.count()).select_from(RawEmail)
    total_emails = await db.scalar(total_query) or 0

    # Gmail vs Milled
    gmail_query = select(func.count()).select_from(RawEmail).where(
        RawEmail.milled_url.like("gmail://%")
    )
    gmail_emails = await db.scalar(gmail_query) or 0
    milled_emails = total_emails - gmail_emails

    # Extracted vs not
    extracted_query = (
        select(func.count())
        .select_from(RawEmail)
        .join(ExtractedSale, RawEmail.id == ExtractedSale.raw_email_id)
    )
    extracted = await db.scalar(extracted_query) or 0
    not_extracted = total_emails - extracted

    # Sales found
    sales_query = (
        select(func.count())
        .select_from(ExtractedSale)
        .where(ExtractedSale.is_sale == True)
    )
    sales_found = await db.scalar(sales_query) or 0

    # Non-sales
    non_sales_query = (
        select(func.count())
        .select_from(ExtractedSale)
        .where(ExtractedSale.is_sale == False)
    )
    non_sales = await db.scalar(non_sales_query) or 0

    # Pending review
    pending_query = (
        select(func.count())
        .select_from(ExtractedSale)
        .where(ExtractedSale.status == ExtractionStatus.PENDING)
    )
    pending_review = await db.scalar(pending_query) or 0

    # Stats by brand - simpler approach without case statements
    brand_stats_query = (
        select(
            Brand.id,
            Brand.name,
            func.count(RawEmail.id).label("total"),
        )
        .select_from(Brand)
        .join(RawEmail, Brand.id == RawEmail.brand_id)
        .group_by(Brand.id, Brand.name)
        .order_by(desc("total"))
    )
    brand_result = await db.execute(brand_stats_query)

    # Get Gmail counts separately for each brand
    brand_stats = []
    for row in brand_result:
        gmail_count_query = (
            select(func.count())
            .select_from(RawEmail)
            .where(RawEmail.brand_id == row.id)
            .where(RawEmail.milled_url.like("gmail://%"))
        )
        gmail_count = await db.scalar(gmail_count_query) or 0
        brand_stats.append({
            "brand_id": str(row.id),
            "brand_name": row.name,
            "total": row.total,
            "gmail": gmail_count,
            "milled": row.total - gmail_count,
        })

    return EmailStatsResponse(
        total_emails=total_emails,
        gmail_emails=gmail_emails,
        milled_emails=milled_emails,
        extracted=extracted,
        not_extracted=not_extracted,
        sales_found=sales_found,
        non_sales=non_sales,
        pending_review=pending_review,
        by_brand=brand_stats,
    )


@router.get("/{email_id}", response_model=EmailDetailResponse)
async def get_email(
    email_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a single email with full content.
    """
    query = (
        select(RawEmail)
        .options(
            joinedload(RawEmail.brand),
            joinedload(RawEmail.extracted_sale),
        )
        .where(RawEmail.id == email_id)
    )

    result = await db.execute(query)
    email = result.unique().scalar_one_or_none()

    if not email:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found",
        )

    source_type = "gmail" if email.milled_url.startswith("gmail://") else "milled"
    extraction = email.extracted_sale

    return EmailDetailResponse(
        id=str(email.id),
        brand_id=str(email.brand_id),
        brand_name=email.brand.name if email.brand else "Unknown",
        subject=email.subject,
        sent_at=email.sent_at,
        source=source_type,
        scraped_at=email.scraped_at,
        html_content=email.html_content,
        milled_url=email.milled_url,
        is_extracted=extraction is not None,
        is_sale=extraction.is_sale if extraction else None,
        discount_type=extraction.discount_type.value if extraction and extraction.discount_type else None,
        discount_value=extraction.discount_value if extraction else None,
        discount_summary=extraction.discount_summary if extraction else None,
        categories=extraction.categories if extraction else None,
        sale_start=extraction.sale_start if extraction else None,
        sale_end=extraction.sale_end if extraction else None,
        confidence=extraction.confidence if extraction else None,
        status=extraction.status.value if extraction and extraction.status else None,
    )


@router.post("/{email_id}/extract")
async def extract_email(
    email_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger extraction for a single email.
    """
    from src.extraction import ExtractionService

    # Get the email
    query = (
        select(RawEmail)
        .options(joinedload(RawEmail.brand))
        .where(RawEmail.id == email_id)
    )
    result = await db.execute(query)
    email = result.unique().scalar_one_or_none()

    if not email:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found",
        )

    # Run extraction
    service = ExtractionService()
    extraction_result = await service.extract_single_email(db, email, reprocess=True)

    return {
        "status": "success",
        "message": f"Extraction completed for email: {email.subject}",
        "result": extraction_result,
    }


class BatchExtractRequest(BaseModel):
    """Request for batch extraction."""
    brand_id: Optional[UUID] = None
    limit: int = 100
    reprocess: bool = False


class BatchExtractResponse(BaseModel):
    """Response for batch extraction."""
    status: str
    total: int
    processed: int
    errors: int
    message: str


@router.post("/extract-batch", response_model=BatchExtractResponse)
async def extract_batch(
    request: BatchExtractRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Extract sale information from multiple emails.

    Options:
    - brand_id: Filter to specific brand
    - limit: Maximum emails to process (default 100)
    - reprocess: Re-extract already processed emails
    """
    from src.extraction import ExtractionService

    service = ExtractionService()
    result = await service.extract_batch(
        db,
        brand_id=request.brand_id,
        limit=request.limit,
        reprocess=request.reprocess,
    )

    return BatchExtractResponse(
        status="success",
        total=result["total"],
        processed=result["processed"],
        errors=result["errors"],
        message=f"Extracted {result['processed']} emails, {result['errors']} errors",
    )


class UpdateExtractionRequest(BaseModel):
    """Request to update an extraction."""
    is_sale: Optional[bool] = None
    notes: Optional[str] = None


@router.patch("/{email_id}/extraction")
async def update_extraction(
    email_id: UUID,
    request: UpdateExtractionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Update an extraction's is_sale status (manual override).
    """
    from fastapi import HTTPException, status
    from datetime import datetime

    # Get the extraction for this email
    query = select(ExtractedSale).where(ExtractedSale.raw_email_id == email_id)
    result = await db.execute(query)
    extraction = result.scalar_one_or_none()

    if not extraction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No extraction found for this email",
        )

    # Update fields
    if request.is_sale is not None:
        extraction.is_sale = request.is_sale
        extraction.status = ExtractionStatus.APPROVED
        extraction.reviewed_at = datetime.utcnow()

    if request.notes is not None:
        extraction.review_notes = request.notes

    await db.commit()

    return {
        "status": "success",
        "message": f"Extraction updated: is_sale={extraction.is_sale}",
        "is_sale": extraction.is_sale,
    }
