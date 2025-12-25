#!/usr/bin/env python
"""
CLI script for scraping Milled.com emails.

Usage:
    python scripts/scrape.py                    # Scrape all active brands
    python scripts/scrape.py --brand target     # Scrape specific brand by slug
    python scripts/scrape.py --days 30          # Scrape last 30 days only
    python scripts/scrape.py --max 100          # Limit to 100 emails per brand
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from src.config import settings
from src.db.session import get_session_factory
from src.db.models import Brand
from src.scraper.milled import MilledScraper, scrape_all_brands

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main(args):
    """Main scraper entry point."""
    session_factory = get_session_factory()

    async with session_factory() as db:
        if args.brand:
            # Scrape specific brand
            result = await db.execute(
                select(Brand).where(Brand.milled_slug == args.brand)
            )
            brand = result.scalar_one_or_none()

            if not brand:
                logger.error(f"Brand with slug '{args.brand}' not found")
                return 1

            logger.info(f"Scraping brand: {brand.name}")

            async with MilledScraper(db) as scraper:
                emails = await scraper.scrape_brand(
                    brand,
                    days_back=args.days,
                    max_emails=args.max,
                )

            await db.commit()
            logger.info(f"Scraped {len(emails)} emails for {brand.name}")

        else:
            # Scrape all brands
            logger.info("Scraping all active brands...")
            results = await scrape_all_brands(
                db,
                days_back=args.days,
                max_emails_per_brand=args.max,
            )

            logger.info("Scraping complete:")
            for brand_name, count in results.items():
                status = f"{count} emails" if count >= 0 else "FAILED"
                logger.info(f"  {brand_name}: {status}")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Milled.com emails")
    parser.add_argument(
        "--brand",
        type=str,
        help="Specific brand slug to scrape (e.g., 'target')",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Days of history to scrape (default: 365)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=500,
        help="Max emails per brand (default: 500)",
    )

    args = parser.parse_args()

    try:
        exit_code = asyncio.run(main(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Scraping cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        sys.exit(1)
