"""
Sync service for pulling SalesGazer emails into the SaleWatcher database.

Mirrors the pattern used by EmailIngestionService for Gmail emails:
login → find stores → subscribe → paginate emails → save to raw_emails.
"""
import logging
import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Brand, RawEmail
from src.salesgazer.client import SalesGazerClient

logger = logging.getLogger(__name__)


def _extract_subject(html: str) -> str:
    """Extract email subject from SalesGazer email page HTML."""
    # Try <title> tag first
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    if match:
        subject = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        if subject and subject.lower() not in ("", "salesgazer", "mail content"):
            return subject[:512]

    # Try <h1> or <h2> inside the email content
    for tag in ("h1", "h2"):
        match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", html, re.DOTALL | re.IGNORECASE)
        if match:
            subject = re.sub(r"<[^>]+>", "", match.group(1)).strip()
            if subject:
                return subject[:512]

    return "SalesGazer Email"


def _extract_sent_date(html: str) -> datetime:
    """Extract sent date from SalesGazer email page HTML."""
    # Common date patterns in email pages
    date_patterns = [
        # "Jan 15, 2025" or "January 15, 2025"
        r'(\w+\s+\d{1,2},?\s+\d{4})',
        # "2025-01-15"
        r'(\d{4}-\d{2}-\d{2})',
        # "01/15/2025"
        r'(\d{2}/\d{2}/\d{4})',
    ]

    for pattern in date_patterns:
        matches = re.findall(pattern, html)
        for date_str in matches:
            for fmt in (
                "%B %d, %Y", "%b %d, %Y",
                "%B %d %Y", "%b %d %Y",
                "%Y-%m-%d",
                "%m/%d/%Y",
            ):
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except ValueError:
                    continue

    # Fallback to now
    return datetime.utcnow()


async def sync_brand_from_salesgazer(
    brand_id: UUID,
    domain: str,
    db: AsyncSession,
    max_pages: int = 50,
    subscribe: bool = True,
) -> dict:
    """
    Full sync pipeline: login → find stores → subscribe → fetch emails → save.

    Args:
        brand_id: UUID of the brand to sync for
        domain: Store domain to search on SalesGazer
        db: Async database session
        max_pages: Max inbox pages to paginate
        subscribe: Whether to subscribe to unsubscribed stores

    Returns:
        Dict with {emails_found, emails_new, emails_skipped, store_ids, errors}
    """
    stats: dict = {
        "emails_found": 0,
        "emails_new": 0,
        "emails_skipped": 0,
        "store_ids": [],
        "errors": 0,
    }

    # Verify brand exists
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise ValueError(f"Brand {brand_id} not found")

    async with SalesGazerClient() as client:
        # Step 1: Login
        await client.login()
        logger.info(f"SalesGazer: logged in, syncing '{domain}' for {brand.name}")

        # Step 2: Find matching stores
        stores = await client.find_store_ids(domain)
        if not stores:
            logger.warning(f"SalesGazer: no stores found for domain '{domain}'")
            return stats

        stats["store_ids"] = [s["store_id"] for s in stores]

        # Step 3: Subscribe if needed
        if subscribe:
            for store in stores:
                if not store["is_subscribed"]:
                    await client.subscribe_to_store(store["store_id"])
                    logger.info(f"Subscribed to store {store['store_id']} ({store['domain']})")

        # Step 4: Collect existing URLs for dedup
        existing_urls_result = await db.execute(
            select(RawEmail.milled_url).where(
                RawEmail.brand_id == brand_id,
                RawEmail.milled_url.like("salesgazer://%"),
            )
        )
        existing_urls = {row[0] for row in existing_urls_result.all()}

        # Step 5: Paginate and save emails from each store
        for store in stores:
            store_id = store["store_id"]
            try:
                email_ids = await client.get_store_email_ids(store_id, max_pages)
                stats["emails_found"] += len(email_ids)

                for eid in email_ids:
                    url = f"salesgazer://{eid}"

                    # Skip duplicates
                    if url in existing_urls:
                        stats["emails_skipped"] += 1
                        continue

                    try:
                        html = await client.get_email_html(eid)

                        subject = _extract_subject(html)
                        sent_at = _extract_sent_date(html)

                        raw_email = RawEmail(
                            brand_id=brand_id,
                            milled_url=url,
                            subject=subject,
                            sent_at=sent_at,
                            html_content=html,
                            scraped_at=datetime.utcnow(),
                            source="salesgazer",
                        )
                        db.add(raw_email)
                        existing_urls.add(url)
                        stats["emails_new"] += 1

                    except Exception as e:
                        logger.error(f"Error fetching email {eid}: {e}")
                        stats["errors"] += 1

            except Exception as e:
                logger.error(f"Error processing store {store_id}: {e}")
                stats["errors"] += 1

        await db.commit()

    logger.info(
        f"SalesGazer sync complete for {brand.name}: "
        f"{stats['emails_new']} new, {stats['emails_skipped']} skipped, "
        f"{stats['errors']} errors"
    )
    return stats
