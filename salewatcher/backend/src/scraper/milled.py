import asyncio
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from uuid import UUID

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models import Brand, RawEmail
from src.scraper.auth import MilledAuth

logger = logging.getLogger(__name__)


class MilledScraper:
    """Scrapes promotional emails from Milled.com."""

    BASE_URL = "https://milled.com"

    def __init__(self, db: AsyncSession, headless: bool = True):
        self.db = db
        self.headless = headless
        self.auth: Optional[MilledAuth] = None
        self.page: Optional[Page] = None

    async def __aenter__(self):
        self.auth = MilledAuth(headless=self.headless)
        await self.auth.setup()
        self.page = await self.auth.get_page()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.auth:
            await self.auth.close()

    async def scrape_brand(
        self,
        brand: Brand,
        days_back: int = 730,  # 2 years of history
        max_emails: int = 2000,  # Increased limit
    ) -> list[RawEmail]:
        """
        Scrape emails for a brand from the past N days.

        Args:
            brand: Brand to scrape
            days_back: How many days of history to scrape
            max_emails: Maximum number of emails to scrape

        Returns:
            List of newly scraped RawEmail objects
        """
        logger.info(f"Scraping {brand.name} (slug: {brand.milled_slug})")

        brand_url = f"{self.BASE_URL}/{brand.milled_slug}"
        await self.page.goto(brand_url, wait_until="networkidle")

        # Debug: Log current URL and page state
        current_url = self.page.url
        logger.info(f"Navigated to: {current_url}")

        # Check for Cloudflare challenge
        page_content = await self.page.content()
        if "challenge" in page_content.lower() or "cloudflare" in page_content.lower():
            logger.warning("Cloudflare challenge detected! Try running with --visible or re-login.")
            # Save debug screenshot
            screenshot_path = Path(__file__).parent.parent.parent / "debug_screenshot.png"
            await self.page.screenshot(path=str(screenshot_path))
            logger.info(f"Debug screenshot saved to: {screenshot_path}")
            return []

        # Check if brand page exists
        if "not found" in page_content.lower():
            logger.error(f"Brand page not found: {brand_url}")
            return []

        scraped_emails = []
        seen_urls = set()

        # Get existing email URLs to avoid duplicates
        existing = await self.db.execute(
            select(RawEmail.milled_url).where(RawEmail.brand_id == brand.id)
        )
        seen_urls = {row[0] for row in existing.all()}
        logger.info(f"Found {len(seen_urls)} existing emails for {brand.name}")

        # Calculate date threshold
        date_threshold = datetime.utcnow() - timedelta(days=days_back)

        # Scroll and load emails
        emails_found = 0
        scroll_attempts = 0
        max_scroll_attempts = 100  # Increased for larger brands

        prev_link_count = 0
        while emails_found < max_emails and scroll_attempts < max_scroll_attempts:
            # Get all email links on page - links that start with /{brand_slug}/ and have more path
            # Email links look like: /BathBodyWorks/some-email-title-abc123
            all_brand_links = await self.page.query_selector_all(f'a[href^="/{brand.milled_slug}/"]')

            # Filter out links that are just the brand page itself
            email_links = []
            for link in all_brand_links:
                href = await link.get_attribute("href")
                # Must have content after /{brand_slug}/
                if href and len(href) > len(f"/{brand.milled_slug}/") + 5:
                    email_links.append(link)

            # Debug: Log number of links found on first scroll
            if scroll_attempts == 0:
                logger.info(f"Found {len(email_links)} email links on page")
                if len(email_links) == 0:
                    # Try alternative selectors
                    all_links = await self.page.query_selector_all('a')
                    logger.info(f"Total links on page: {len(all_links)}")
                    # Log first few href values for debugging
                    for i, link in enumerate(all_links[:10]):
                        href = await link.get_attribute("href")
                        logger.debug(f"  Link {i}: {href}")
                    # Save debug screenshot
                    screenshot_path = Path(__file__).parent.parent.parent / "debug_screenshot.png"
                    await self.page.screenshot(path=str(screenshot_path))
                    logger.info(f"Debug screenshot saved to: {screenshot_path}")

            for link in email_links:
                if emails_found >= max_emails:
                    break

                href = await link.get_attribute("href")
                if not href or href in seen_urls:
                    continue

                full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                seen_urls.add(href)

                # Scrape individual email
                email = await self._scrape_email(brand, full_url, date_threshold)
                if email:
                    scraped_emails.append(email)
                    emails_found += 1
                    logger.info(f"  Scraped email {emails_found}: {email.subject[:50]}...")

                # Rate limiting
                await asyncio.sleep(settings.scrape_delay_seconds)

            # Scroll to load more
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
            scroll_attempts += 1

            # Check if we've reached the end (no new links loaded after scroll)
            current_link_count = len(email_links)
            if current_link_count == prev_link_count:
                logger.info("No more emails to load")
                break
            prev_link_count = current_link_count

        logger.info(f"Scraped {len(scraped_emails)} new emails for {brand.name}")
        return scraped_emails

    async def _scrape_email(
        self,
        brand: Brand,
        url: str,
        date_threshold: datetime,
    ) -> Optional[RawEmail]:
        """Scrape a single email page."""
        try:
            await self.page.goto(url, wait_until="networkidle", timeout=30000)

            # Extract subject
            subject_el = await self.page.query_selector("h1")
            subject = await subject_el.inner_text() if subject_el else "No Subject"

            # Extract date
            date_el = await self.page.query_selector('time, [datetime], .date, .sent-date')
            sent_at = None

            if date_el:
                datetime_attr = await date_el.get_attribute("datetime")
                if datetime_attr:
                    sent_at = self._parse_date(datetime_attr)
                else:
                    date_text = await date_el.inner_text()
                    sent_at = self._parse_date(date_text)

            if not sent_at:
                # Try to find date in page content
                page_text = await self.page.content()
                sent_at = self._extract_date_from_content(page_text)

            if not sent_at:
                sent_at = datetime.utcnow()
                logger.warning(f"Could not find date for {url}, using current time")

            # Skip if too old
            if sent_at < date_threshold:
                logger.debug(f"Skipping old email: {sent_at}")
                return None

            # Extract HTML content (the email body)
            content_el = await self.page.query_selector('.email-content, .message-content, article, main')
            html_content = await content_el.inner_html() if content_el else await self.page.content()

            # Create and save email record
            raw_email = RawEmail(
                brand_id=brand.id,
                milled_url=url,
                subject=subject.strip(),
                sent_at=sent_at,
                html_content=html_content,
            )

            self.db.add(raw_email)
            await self.db.flush()

            return raw_email

        except PlaywrightTimeout:
            logger.warning(f"Timeout scraping {url}")
            return None
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats."""
        date_str = date_str.strip()

        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
            "%B %d, %Y",
            "%b %d, %Y",
            "%m/%d/%Y",
            "%d/%m/%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    def _extract_date_from_content(self, html: str) -> Optional[datetime]:
        """Try to extract date from HTML content."""
        # Look for common date patterns
        patterns = [
            r'(\d{4}-\d{2}-\d{2})',
            r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4})',
            r'(\d{1,2}/\d{1,2}/\d{4})',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                date = self._parse_date(match.group(1))
                if date:
                    return date

        return None


async def scrape_brand_emails(
    db: AsyncSession,
    brand_id: UUID,
    days_back: int = 365,
    max_emails: int = 500,
) -> list[RawEmail]:
    """
    Convenience function to scrape emails for a brand.

    Args:
        db: Database session
        brand_id: UUID of brand to scrape
        days_back: Days of history to scrape
        max_emails: Maximum emails to scrape

    Returns:
        List of scraped RawEmail objects
    """
    # Get brand
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()

    if not brand:
        raise ValueError(f"Brand {brand_id} not found")

    if not brand.is_active:
        raise ValueError(f"Brand {brand.name} is not active")

    async with MilledScraper(db) as scraper:
        return await scraper.scrape_brand(brand, days_back, max_emails)


async def scrape_all_brands(
    db: AsyncSession,
    days_back: int = 365,
    max_emails_per_brand: int = 500,
    headless: bool = True,
) -> dict[str, int]:
    """
    Scrape emails for all active brands.

    Returns:
        Dict mapping brand name to number of emails scraped
    """
    result = await db.execute(select(Brand).where(Brand.is_active == True))
    brands = result.scalars().all()

    results = {}

    async with MilledScraper(db, headless=headless) as scraper:
        for brand in brands:
            try:
                emails = await scraper.scrape_brand(brand, days_back, max_emails_per_brand)
                results[brand.name] = len(emails)
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to scrape {brand.name}: {e}")
                results[brand.name] = -1
                await db.rollback()

    return results
