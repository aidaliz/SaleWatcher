"""
Email ingestion service that fetches emails from Gmail and stores them.

Handles deduplication to avoid processing the same promotional email
received at multiple +N addresses.
"""
import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Brand, RawEmail
from src.email_ingest.gmail import GmailClient, get_brand_email_query

logger = logging.getLogger(__name__)


class EmailIngestionService:
    """Service for ingesting emails from Gmail into the database."""

    def __init__(self, gmail_client: GmailClient):
        self.gmail = gmail_client

    async def sync_brand_emails(
        self,
        db: AsyncSession,
        brand: Brand,
        days_back: int = 365,
        max_emails: int = 100,
    ) -> dict:
        """
        Sync emails for a brand from Gmail.

        Args:
            db: Database session
            brand: Brand to sync emails for
            days_back: How many days of history to fetch
            max_emails: Maximum emails to fetch

        Returns:
            Dict with sync statistics
        """
        stats = {
            'brand': brand.name,
            'fetched': 0,
            'new': 0,
            'duplicates': 0,
            'errors': 0,
        }

        # Get existing Gmail message IDs for this brand (dedup by message ID)
        existing_gmail_ids = await self._get_existing_gmail_ids(db, brand.id)
        logger.info(f"Found {len(existing_gmail_ids)} existing Gmail emails for {brand.name}")

        # Search Gmail for brand emails using multi-domain query
        query = get_brand_email_query(brand.milled_slug)
        after_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')
        full_query = f"{query} after:{after_date}"
        messages = self.gmail.search_emails_by_query(
            query=full_query,
            max_results=max_emails,
        )

        stats['fetched'] = len(messages)

        for msg in messages:
            try:
                msg_id = msg['id']
                gmail_url = f"gmail://{msg_id}"

                # Dedup by Gmail message ID
                if msg_id in existing_gmail_ids:
                    stats['duplicates'] += 1
                    continue

                # Fetch full email content
                email_data = self.gmail.get_email_content(msg_id)
                if not email_data:
                    stats['errors'] += 1
                    continue

                # Convert timezone-aware datetime to naive (database uses TIMESTAMP WITHOUT TIME ZONE)
                sent_at = email_data['sent_at']
                if sent_at.tzinfo is not None:
                    sent_at = sent_at.replace(tzinfo=None)

                # Create new email record
                raw_email = RawEmail(
                    brand_id=brand.id,
                    milled_url=gmail_url,
                    subject=email_data['subject'],
                    sent_at=sent_at,
                    html_content=email_data['html_content'],
                    scraped_at=datetime.utcnow(),
                    source='gmail',
                )

                db.add(raw_email)
                existing_gmail_ids.add(msg_id)
                stats['new'] += 1

                logger.info(f"Imported: {email_data['subject'][:60]}...")

            except Exception as e:
                logger.error(f"Error processing email {msg['id']}: {e}")
                stats['errors'] += 1

        await db.commit()
        logger.info(
            f"Sync complete for {brand.name}: "
            f"{stats['new']} new, {stats['duplicates']} duplicates, {stats['errors']} errors"
        )

        return stats

    async def _get_existing_gmail_ids(self, db: AsyncSession, brand_id: UUID) -> set[str]:
        """Get existing Gmail message IDs for a brand (from gmail:// URLs)."""
        query = select(RawEmail.milled_url).where(
            RawEmail.brand_id == brand_id,
            RawEmail.milled_url.like('gmail://%'),
        )
        result = await db.execute(query)
        urls = result.scalars().all()

        # Extract message ID from gmail://<message_id>
        return {url.removeprefix('gmail://') for url in urls}

    async def sync_all_brands(
        self,
        db: AsyncSession,
        days_back: int = 365,
        max_emails_per_brand: int = 100,
    ) -> list[dict]:
        """
        Sync emails for all active brands.

        Args:
            db: Database session
            days_back: How many days of history to fetch
            max_emails_per_brand: Maximum emails per brand

        Returns:
            List of sync statistics for each brand
        """
        # Get all active brands
        query = select(Brand).where(Brand.is_active == True)
        result = await db.execute(query)
        brands = list(result.scalars().all())

        all_stats = []
        for brand in brands:
            try:
                stats = await self.sync_brand_emails(
                    db, brand, days_back, max_emails_per_brand
                )
                all_stats.append(stats)
            except Exception as e:
                logger.error(f"Failed to sync {brand.name}: {e}")
                all_stats.append({
                    'brand': brand.name,
                    'error': str(e),
                })

        return all_stats
