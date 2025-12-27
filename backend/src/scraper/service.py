"""Scraper service - orchestrates scraping and saves to database."""

import logging
from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Brand, RawEmail
from src.db.crud.raw_emails import create_raw_email_if_not_exists
from src.scraper.auth import MilledClient
from src.scraper.milled import MilledScraper, ScrapedEmail


logger = logging.getLogger(__name__)


class ScraperService:
    """Service for scraping emails and saving to database."""

    async def scrape_brand(
        self,
        db: AsyncSession,
        brand: Brand,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """
        Scrape emails for a brand and save to database.

        Args:
            db: Database session
            brand: Brand to scrape
            start_date: Start of date range (default: 7 days ago)
            end_date: End of date range (default: today)

        Returns:
            Dict with scraping stats: {scraped, new, duplicates, errors}
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=7)

        stats = {
            "brand_id": str(brand.id),
            "brand_name": brand.name,
            "scraped": 0,
            "new": 0,
            "duplicates": 0,
            "errors": 0,
            "start_date": str(start_date),
            "end_date": str(end_date),
        }

        logger.info(f"Starting scrape for {brand.name} ({brand.milled_slug}) from {start_date} to {end_date}")

        try:
            async with MilledClient() as client:
                scraper = MilledScraper(client)

                async for scraped_email in scraper.scrape_brand(
                    brand_slug=brand.milled_slug,
                    start_date=start_date,
                    end_date=end_date,
                ):
                    stats["scraped"] += 1

                    try:
                        email, created = await create_raw_email_if_not_exists(
                            db=db,
                            brand_id=brand.id,
                            milled_url=scraped_email.milled_url,
                            subject=scraped_email.subject,
                            sent_at=scraped_email.sent_at,
                            html_content=scraped_email.html_content,
                        )

                        if created:
                            stats["new"] += 1
                            logger.debug(f"Saved new email: {scraped_email.subject}")
                        else:
                            stats["duplicates"] += 1
                            logger.debug(f"Skipped duplicate: {scraped_email.milled_url}")

                    except Exception as e:
                        stats["errors"] += 1
                        logger.error(f"Error saving email {scraped_email.milled_url}: {e}")

        except Exception as e:
            logger.error(f"Error scraping brand {brand.name}: {e}")
            stats["error_message"] = str(e)

        logger.info(
            f"Scrape complete for {brand.name}: "
            f"{stats['scraped']} scraped, {stats['new']} new, "
            f"{stats['duplicates']} duplicates, {stats['errors']} errors"
        )

        return stats

    async def backfill_brand(
        self,
        db: AsyncSession,
        brand: Brand,
        months_back: int = 12,
    ) -> dict:
        """
        Backfill historical emails for a brand.

        Args:
            db: Database session
            brand: Brand to backfill
            months_back: Number of months of history to fetch

        Returns:
            Dict with scraping stats
        """
        end_date = date.today()
        start_date = date(
            end_date.year - (months_back // 12),
            ((end_date.month - (months_back % 12) - 1) % 12) + 1,
            1,
        )

        # Adjust year if month wrapped around
        if end_date.month <= (months_back % 12):
            start_date = date(start_date.year - 1, start_date.month, start_date.day)

        logger.info(f"Starting backfill for {brand.name}: {months_back} months ({start_date} to {end_date})")

        return await self.scrape_brand(
            db=db,
            brand=brand,
            start_date=start_date,
            end_date=end_date,
        )


async def scrape_brands(
    db: AsyncSession,
    brands: list[Brand],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> list[dict]:
    """
    Scrape multiple brands.

    Args:
        db: Database session
        brands: List of brands to scrape
        start_date: Start of date range
        end_date: End of date range

    Returns:
        List of stats dicts, one per brand
    """
    service = ScraperService()
    results = []

    for brand in brands:
        try:
            stats = await service.scrape_brand(
                db=db,
                brand=brand,
                start_date=start_date,
                end_date=end_date,
            )
            results.append(stats)
        except Exception as e:
            logger.error(f"Failed to scrape {brand.name}: {e}")
            results.append({
                "brand_id": str(brand.id),
                "brand_name": brand.name,
                "error": str(e),
            })

    return results
