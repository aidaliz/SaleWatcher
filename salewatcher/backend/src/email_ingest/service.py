"""
Email ingestion service that fetches emails from Gmail and stores them.

Handles deduplication to avoid processing the same promotional email
received at multiple +N addresses.
"""
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Brand, RawEmail
from src.email_ingest.gmail import GmailClient, generate_email_hash, get_brand_email_query

logger = logging.getLogger(__name__)


class EmailIngestionService:
    """Service for ingesting emails from Gmail into the database."""

    def __init__(self, gmail_client: GmailClient):
        self.gmail = gmail_client
        # Track hashes we've already processed in this session
        self._processed_hashes: set[str] = set()

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

        # Get existing email hashes for this brand
        existing_hashes = await self._get_existing_hashes(db, brand.id)
        logger.info(f"Found {len(existing_hashes)} existing emails for {brand.name}")

        # Search Gmail for brand emails
        query = get_brand_email_query(brand.milled_slug)
        messages = self.gmail.search_emails(
            sender_email=query.split('from:')[1].split()[0] if 'from:' in query else brand.milled_slug,
            days_back=days_back,
            max_results=max_emails,
        )

        stats['fetched'] = len(messages)

        for msg in messages:
            try:
                # Fetch full email content
                email_data = self.gmail.get_email_content(msg['id'])
                if not email_data:
                    stats['errors'] += 1
                    continue

                # Generate dedup hash
                email_hash = generate_email_hash(
                    brand.milled_slug,
                    email_data['subject'],
                    email_data['sent_at'],
                )

                # Check for duplicates
                if email_hash in existing_hashes or email_hash in self._processed_hashes:
                    stats['duplicates'] += 1
                    continue

                # Convert timezone-aware datetime to naive (database uses TIMESTAMP WITHOUT TIME ZONE)
                sent_at = email_data['sent_at']
                if sent_at.tzinfo is not None:
                    sent_at = sent_at.replace(tzinfo=None)

                # Create new email record
                raw_email = RawEmail(
                    brand_id=brand.id,
                    milled_url=f"gmail://{msg['id']}",  # Use Gmail message ID as URL
                    subject=email_data['subject'],
                    sent_at=sent_at,
                    html_content=email_data['html_content'],
                    scraped_at=datetime.utcnow(),
                )

                db.add(raw_email)
                self._processed_hashes.add(email_hash)
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

    async def _get_existing_hashes(self, db: AsyncSession, brand_id: UUID) -> set[str]:
        """Get hashes of existing emails for a brand."""
        query = select(RawEmail.subject, RawEmail.sent_at).where(RawEmail.brand_id == brand_id)
        result = await db.execute(query)
        rows = result.all()

        hashes = set()
        for subject, sent_at in rows:
            # Get brand slug for hash
            brand_query = select(Brand.milled_slug).where(Brand.id == brand_id)
            brand_result = await db.execute(brand_query)
            brand_slug = brand_result.scalar_one()

            email_hash = generate_email_hash(brand_slug, subject, sent_at)
            hashes.add(email_hash)

        return hashes

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
