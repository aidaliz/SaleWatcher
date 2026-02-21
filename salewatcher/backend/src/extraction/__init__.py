"""Extraction service for sale information extraction from emails."""
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select, not_, exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Brand, RawEmail, ExtractedSale
from src.extractor.llm import SaleExtractor

logger = logging.getLogger(__name__)


class ExtractionService:
    """Service for extracting sale information from emails."""

    def __init__(self):
        self.extractor = SaleExtractor()

    async def extract_batch(
        self,
        db: AsyncSession,
        brand_id: Optional[UUID] = None,
        limit: int = 100,
        reprocess: bool = False,
    ) -> dict:
        """
        Extract sale information from multiple emails.

        Loads all ORM data into plain dicts up front so no lazy-loading
        can occur during the async LLM calls (avoids MissingGreenlet).
        """
        # ── 1. Load emails + brand names in one query ─────────────────────────
        query = (
            select(
                RawEmail.id,
                RawEmail.subject,
                RawEmail.sent_at,
                RawEmail.html_content,
                RawEmail.brand_id,
                Brand.name.label("brand_name"),
            )
            .join(Brand, Brand.id == RawEmail.brand_id, isouter=True)
        )

        if not reprocess:
            # Exclude emails that already have an extraction
            query = query.where(
                not_(
                    exists(
                        select(ExtractedSale.id).where(
                            ExtractedSale.raw_email_id == RawEmail.id
                        )
                    )
                )
            )

        if brand_id:
            query = query.where(RawEmail.brand_id == brand_id)

        query = query.order_by(RawEmail.sent_at.desc()).limit(limit)

        rows = (await db.execute(query)).mappings().all()

        # ── 2. Convert to plain dicts — no ORM objects past this point ─────────
        email_dicts = [dict(r) for r in rows]
        total = len(email_dicts)
        processed = 0
        errors = 0
        results = []

        # ── 3. Process each email ──────────────────────────────────────────────
        for ed in email_dicts:
            email_id = ed["id"]
            try:
                logger.info(f"Processing: {str(ed['subject'])[:60]}...")

                # Build a lightweight stub so the extractor gets what it needs
                stub = _EmailStub(
                    id=email_id,
                    subject=ed["subject"] or "",
                    sent_at=ed["sent_at"],
                    html_content=ed["html_content"] or "",
                )
                brand_name = ed["brand_name"] or "Unknown"

                # Call LLM — no SQLAlchemy session involved here
                extracted = await self.extractor.extract_with_fallback(stub, brand_name)

                # Flush to DB in its own mini-commit
                db.add(extracted)
                is_sale = extracted.is_sale
                confidence = extracted.confidence
                discount_summary = extracted.discount_summary
                await db.commit()

                processed += 1
                results.append({
                    "status": "success",
                    "email_id": str(email_id),
                    "is_sale": is_sale,
                    "confidence": confidence,
                    "discount_summary": discount_summary,
                })

            except Exception as e:
                logger.error(f"Error extracting email {email_id}: {e}", exc_info=True)
                errors += 1
                results.append({
                    "status": "error",
                    "email_id": str(email_id),
                    "error": str(e),
                })
                try:
                    await db.rollback()
                except Exception:
                    pass

        return {
            "total": total,
            "processed": processed,
            "errors": errors,
            "results": results,
        }

    async def extract_single_email(
        self,
        db: AsyncSession,
        email: RawEmail,
        reprocess: bool = False,
    ) -> dict:
        """Extract sale information from a single ORM email object."""
        if not reprocess:
            existing = (await db.execute(
                select(ExtractedSale).where(ExtractedSale.raw_email_id == email.id)
            )).scalar_one_or_none()
            if existing:
                return {"status": "skipped", "message": "Already extracted", "email_id": str(email.id)}

        if reprocess:
            existing = (await db.execute(
                select(ExtractedSale).where(ExtractedSale.raw_email_id == email.id)
            )).scalar_one_or_none()
            if existing:
                await db.delete(existing)
                await db.flush()

        # Get brand name via explicit query (avoids lazy-load)
        brand_row = (await db.execute(
            select(Brand.name).where(Brand.id == email.brand_id)
        )).scalar_one_or_none()
        brand_name = brand_row or "Unknown"

        stub = _EmailStub(
            id=email.id,
            subject=email.subject or "",
            sent_at=email.sent_at,
            html_content=email.html_content or "",
        )
        extracted = await self.extractor.extract_with_fallback(stub, brand_name)
        db.add(extracted)

        is_sale = extracted.is_sale
        confidence = extracted.confidence
        discount_summary = extracted.discount_summary
        await db.commit()

        return {
            "status": "success",
            "email_id": str(email.id),
            "is_sale": is_sale,
            "confidence": confidence,
            "discount_summary": discount_summary,
        }


class _EmailStub:
    """Lightweight stand-in for RawEmail that carries only the fields the
    extractor needs — avoids passing SQLAlchemy ORM objects into async LLM calls."""

    def __init__(self, id, subject: str, sent_at, html_content: str):
        self.id = id
        self.subject = subject
        self.sent_at = sent_at
        self.html_content = html_content
