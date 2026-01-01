"""Extraction service for sale information extraction from emails."""
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Brand, RawEmail, ExtractedSale
from src.extractor.llm import SaleExtractor

logger = logging.getLogger(__name__)


class ExtractionService:
    """Service for extracting sale information from emails."""

    def __init__(self):
        self.extractor = SaleExtractor()

    async def extract_single_email(
        self,
        db: AsyncSession,
        email: RawEmail,
        reprocess: bool = False,
    ) -> dict:
        """
        Extract sale information from a single email.

        Args:
            db: Database session
            email: RawEmail to process
            reprocess: If True, will delete existing extraction first

        Returns:
            Dictionary with extraction result
        """
        # Check if already extracted
        if not reprocess:
            existing_query = select(ExtractedSale).where(
                ExtractedSale.raw_email_id == email.id
            )
            existing = await db.execute(existing_query)
            if existing.scalar_one_or_none():
                return {
                    "status": "skipped",
                    "message": "Email already extracted",
                    "email_id": str(email.id),
                }

        # If reprocessing, delete existing extraction
        if reprocess:
            existing_query = select(ExtractedSale).where(
                ExtractedSale.raw_email_id == email.id
            )
            existing = await db.execute(existing_query)
            existing_extraction = existing.scalar_one_or_none()
            if existing_extraction:
                await db.delete(existing_extraction)
                await db.flush()

        # Get brand name
        brand_name = email.brand.name if email.brand else "Unknown"

        # Run extraction
        extracted = await self.extractor.extract_with_fallback(email, brand_name)
        db.add(extracted)
        await db.commit()

        return {
            "status": "success",
            "email_id": str(email.id),
            "is_sale": extracted.is_sale,
            "confidence": extracted.confidence,
            "discount_summary": extracted.discount_summary,
        }

    async def extract_batch(
        self,
        db: AsyncSession,
        brand_id: Optional[UUID] = None,
        limit: int = 100,
        reprocess: bool = False,
    ) -> dict:
        """
        Extract sale information from multiple emails.

        Args:
            db: Database session
            brand_id: Optional brand ID to filter by
            limit: Maximum number of emails to process
            reprocess: If True, will reprocess already extracted emails

        Returns:
            Dictionary with batch extraction results
        """
        # Build query for emails to process
        query = select(RawEmail).options(selectinload(RawEmail.brand))

        if not reprocess:
            # Only get emails without extractions
            query = query.outerjoin(ExtractedSale).where(ExtractedSale.id == None)

        if brand_id:
            query = query.where(RawEmail.brand_id == brand_id)

        query = query.order_by(RawEmail.sent_at.desc()).limit(limit)

        result = await db.execute(query)
        emails = list(result.scalars().all())

        total = len(emails)
        processed = 0
        errors = 0
        results = []

        for email in emails:
            try:
                logger.info(f"Processing: {email.subject[:60]}...")

                extraction_result = await self.extract_single_email(
                    db, email, reprocess=reprocess
                )
                results.append(extraction_result)

                if extraction_result.get("status") == "success":
                    processed += 1

            except Exception as e:
                logger.error(f"Error extracting email {email.id}: {e}")
                errors += 1
                results.append({
                    "status": "error",
                    "email_id": str(email.id),
                    "error": str(e),
                })
                await db.rollback()

        return {
            "total": total,
            "processed": processed,
            "errors": errors,
            "results": results,
        }
