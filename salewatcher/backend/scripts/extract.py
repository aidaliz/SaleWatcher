#!/usr/bin/env python
"""
CLI script for extracting sale information from scraped emails.

Usage:
    python scripts/extract.py                    # Process all unprocessed emails
    python scripts/extract.py --brand target     # Process specific brand only
    python scripts/extract.py --limit 50         # Limit to 50 emails
    python scripts/extract.py --reprocess        # Reprocess all emails (not just unprocessed)
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.config import settings
from src.db.session import get_session_factory
from src.db.models import Brand, RawEmail, ExtractedSale
from src.extractor.llm import SaleExtractor

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main(args):
    """Main extraction entry point."""
    if not settings.anthropic_api_key:
        logger.error("ANTHROPIC_API_KEY not set in environment")
        return 1

    session_factory = get_session_factory()
    extractor = SaleExtractor()

    async with session_factory() as db:
        # Build query for emails to process
        query = (
            select(RawEmail)
            .options(selectinload(RawEmail.brand))
        )

        if not args.reprocess:
            # Only get emails without extractions
            query = query.outerjoin(ExtractedSale).where(ExtractedSale.id == None)

        if args.brand:
            query = query.join(Brand).where(Brand.milled_slug == args.brand)

        query = query.order_by(RawEmail.sent_at.desc()).limit(args.limit)

        result = await db.execute(query)
        emails = list(result.scalars().all())

        logger.info(f"Found {len(emails)} emails to process")

        processed = 0
        errors = 0

        for email in emails:
            try:
                logger.info(f"Processing: {email.subject[:60]}...")

                extracted = await extractor.extract_with_fallback(
                    email,
                    email.brand.name,
                )

                # Check if extraction already exists (for reprocessing)
                if args.reprocess:
                    existing = await db.execute(
                        select(ExtractedSale).where(ExtractedSale.raw_email_id == email.id)
                    )
                    existing_extraction = existing.scalar_one_or_none()
                    if existing_extraction:
                        await db.delete(existing_extraction)
                        await db.flush()

                db.add(extracted)
                await db.commit()

                status = "SALE" if extracted.is_sale else "NO SALE"
                logger.info(
                    f"  -> {status} (confidence: {extracted.confidence:.2f}, "
                    f"status: {extracted.status.value})"
                )

                if extracted.is_sale and extracted.discount_summary:
                    logger.info(f"     {extracted.discount_summary}")

                processed += 1

            except Exception as e:
                logger.error(f"  -> ERROR: {e}")
                errors += 1
                await db.rollback()

        logger.info(f"\nExtraction complete: {processed} processed, {errors} errors")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract sale info from emails")
    parser.add_argument(
        "--brand",
        type=str,
        help="Specific brand slug to process",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Max emails to process (default: 100)",
    )
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help="Reprocess all emails, not just unprocessed",
    )

    args = parser.parse_args()

    try:
        exit_code = asyncio.run(main(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Extraction cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        sys.exit(1)
