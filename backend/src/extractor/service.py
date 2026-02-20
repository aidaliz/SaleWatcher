"""Sale extraction service with Haiku/Sonnet fallback."""

from dataclasses import dataclass
from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.db.models import Brand, RawEmail, ExtractedSale
from src.extractor.llm import get_claude_client, ExtractionResult


@dataclass
class ExtractionOutcome:
    """Result of the extraction process."""
    result: ExtractionResult
    model_used: str
    needs_review: bool
    review_reason: Optional[str] = None


class SaleExtractor:
    """Service for extracting sale details from emails."""

    def __init__(self):
        self.settings = get_settings()
        self.client = get_claude_client()

    async def extract_from_email(
        self,
        email: RawEmail,
        brand: Brand,
    ) -> ExtractionOutcome:
        """
        Extract sale details from an email using two-stage LLM processing.

        Stage 1: Process with Haiku (fast, cheap)
        Stage 2: If confidence < threshold, reprocess with Sonnet

        Args:
            email: The raw email to process
            brand: The brand this email belongs to

        Returns:
            ExtractionOutcome with result and metadata
        """
        # Stage 1: Haiku extraction
        result, model_used = await self.client.extract_sale(
            email_html=email.html_content,
            brand_name=brand.name,
            brand_categories=[],  # Could be configured per brand
            excluded_categories=list(brand.excluded_categories or []),
            use_sonnet=False,
        )

        # Check if we need Sonnet fallback
        if result.confidence < self.settings.llm_confidence_threshold:
            # Stage 2: Sonnet extraction for low-confidence results
            sonnet_result, model_used = await self.client.extract_sale(
                email_html=email.html_content,
                brand_name=brand.name,
                brand_categories=[],
                excluded_categories=list(brand.excluded_categories or []),
                use_sonnet=True,
            )

            # Use Sonnet result if it's more confident
            if sonnet_result.confidence > result.confidence:
                result = sonnet_result

        # Determine if this needs human review
        needs_review = result.confidence < self.settings.llm_review_threshold
        review_reason = None
        if needs_review:
            if result.confidence < 0.3:
                review_reason = "Very low confidence - extraction may be unreliable"
            elif result.discount_type == "other":
                review_reason = "Unusual discount type detected"
            else:
                review_reason = "Low confidence - please verify details"

        return ExtractionOutcome(
            result=result,
            model_used=model_used,
            needs_review=needs_review,
            review_reason=review_reason,
        )

    async def process_email(
        self,
        db: AsyncSession,
        email: RawEmail,
        brand: Brand,
    ) -> ExtractedSale:
        """
        Process an email and save the extraction to the database.

        Args:
            db: Database session
            email: The raw email to process
            brand: The brand this email belongs to

        Returns:
            The created ExtractedSale record
        """
        outcome = await self.extract_from_email(email, brand)
        result = outcome.result

        # Parse dates if present
        sale_start = None
        sale_end = None
        if result.sale_start:
            try:
                sale_start = date.fromisoformat(result.sale_start)
            except ValueError:
                pass
        if result.sale_end:
            try:
                sale_end = date.fromisoformat(result.sale_end)
            except ValueError:
                pass

        # Create ExtractedSale record
        extracted_sale = ExtractedSale(
            email_id=email.id,
            discount_type=result.discount_type,
            discount_value=result.discount_value,
            discount_max=result.discount_max,
            is_sitewide=result.is_sitewide,
            categories=result.categories,
            excluded_categories=result.excluded_categories,
            conditions=result.conditions,
            sale_start=sale_start,
            sale_end=sale_end,
            confidence=result.confidence,
            raw_discount_text=result.raw_discount_text,
            model_used=outcome.model_used,
            review_status="pending" if outcome.needs_review else "approved",
        )

        db.add(extracted_sale)
        await db.commit()
        await db.refresh(extracted_sale)

        return extracted_sale


async def process_pending_emails(
    db: AsyncSession,
    brand_id: Optional[UUID] = None,
    limit: int = 100,
) -> list[ExtractedSale]:
    """
    Process emails that haven't been extracted yet.

    Args:
        db: Database session
        brand_id: Optional brand filter
        limit: Maximum emails to process

    Returns:
        List of created ExtractedSale records
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    # Find emails without extractions
    query = (
        select(RawEmail)
        .outerjoin(ExtractedSale)
        .where(ExtractedSale.id.is_(None))
        .options(selectinload(RawEmail.brand))
        .limit(limit)
    )

    if brand_id:
        query = query.where(RawEmail.brand_id == brand_id)

    result = await db.execute(query)
    emails = result.scalars().all()

    extractor = SaleExtractor()
    extracted = []

    for email in emails:
        try:
            extraction = await extractor.process_email(db, email, email.brand)
            extracted.append(extraction)
        except Exception as e:
            # Log error but continue with other emails
            print(f"Error extracting email {email.id}: {e}")
            continue

    return extracted
