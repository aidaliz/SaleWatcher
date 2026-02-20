"""
Milled.com scraper using ZenRows API to bypass Cloudflare.

Replaces Playwright-based scraping with ZenRows HTTP requests.
"""
import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from html.parser import HTMLParser
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models import Brand, RawEmail

logger = logging.getLogger(__name__)

ZENROWS_API = "https://api.zenrows.com/v1/"


def _get_zenrows_key() -> str:
    """Get ZenRows API key from settings or env."""
    return settings.zenrows_api_key or os.environ.get("ZENROWS_API_KEY", "")


class _LinkParser(HTMLParser):
    """Simple HTML parser to extract href links."""

    def __init__(self, slug: str):
        super().__init__()
        self.slug = slug.lower()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple]) -> None:
        if tag != "a":
            return
        for attr, val in attrs:
            if attr == "href" and val:
                vl = val.lower()
                prefix = f"/{self.slug}/"
                if vl.startswith(prefix) and len(val) > len(prefix) + 5:
                    self.links.append(val)


class _TextExtractor(HTMLParser):
    """Extract all text from HTML."""

    def __init__(self):
        super().__init__()
        self.text_parts: list[str] = []

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if stripped:
            self.text_parts.append(stripped)

    @property
    def text(self) -> str:
        return " ".join(self.text_parts)


async def _zenrows_fetch(url: str, client: httpx.AsyncClient, js_render: bool = True) -> Optional[str]:
    """Fetch a URL via ZenRows API, returning HTML content or None on failure."""
    api_key = _get_zenrows_key()
    if not api_key:
        logger.error("ZENROWS_API_KEY not set — cannot scrape Milled.com")
        return None

    params = {
        "apikey": api_key,
        "url": url,
    }
    if js_render:
        params["js_render"] = "true"
        params["wait"] = "2000"  # 2s for page to load

    try:
        resp = await client.get(ZENROWS_API, params=params, timeout=60.0)
        if resp.status_code == 200:
            return resp.text
        logger.warning(f"ZenRows returned {resp.status_code} for {url}: {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"ZenRows request failed for {url}: {e}")
        return None


class MilledScraper:
    """Scrapes promotional emails from Milled.com via ZenRows."""

    BASE_URL = "https://milled.com"

    def __init__(self, db: AsyncSession, headless: bool = True):
        self.db = db
        self.headless = headless  # kept for API compat, not used
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def scrape_brand(
        self,
        brand: Brand,
        days_back: int = 730,
        max_emails: int = 2000,
    ) -> list[RawEmail]:
        """Scrape emails for a brand from Milled.com."""
        logger.info(f"Scraping {brand.name} via ZenRows (slug: {brand.milled_slug})")

        # Get existing email URLs to avoid duplicates
        existing = await self.db.execute(
            select(RawEmail.milled_url).where(RawEmail.brand_id == brand.id)
        )
        seen_urls = {row[0] for row in existing.all()}
        logger.info(f"Found {len(seen_urls)} existing emails for {brand.name}")

        date_threshold = datetime.utcnow() - timedelta(days=days_back)
        scraped_emails: list[RawEmail] = []

        # Fetch brand listing pages (Milled paginates with ?p=N)
        page_num = 1
        while len(scraped_emails) < max_emails:
            brand_url = f"{self.BASE_URL}/{brand.milled_slug}"
            if page_num > 1:
                brand_url += f"?p={page_num}"

            logger.info(f"Fetching page {page_num}: {brand_url}")
            html = await _zenrows_fetch(brand_url, self._client, js_render=True)

            if not html:
                logger.warning(f"No HTML returned for page {page_num}, stopping.")
                break

            # Check for Cloudflare block
            if "just a moment" in html.lower() or "cf-challenge" in html.lower():
                logger.error("Cloudflare challenge on brand page — ZenRows key may be insufficient tier.")
                break

            # Check for 404 / brand not found
            if "not found" in html.lower() and len(html) < 5000:
                logger.error(f"Brand page not found: {brand_url}")
                break

            # Parse email links
            parser = _LinkParser(brand.milled_slug)
            parser.feed(html)
            new_links = [l for l in parser.links if l not in seen_urls]

            if not new_links:
                logger.info(f"No new links on page {page_num} — reached end.")
                break

            logger.info(f"Found {len(new_links)} new email links on page {page_num}")

            for href in new_links:
                if len(scraped_emails) >= max_emails:
                    break
                seen_urls.add(href)

                full_url = f"{self.BASE_URL}{href}"
                email = await self._scrape_email(brand, full_url, date_threshold)
                if email:
                    scraped_emails.append(email)
                    logger.info(f"  [{len(scraped_emails)}] {email.subject[:60]}")

                await asyncio.sleep(settings.scrape_delay_seconds)

            page_num += 1

        logger.info(f"=== Scraping complete: {len(scraped_emails)} emails scraped ===")
        return scraped_emails

    async def _scrape_email(
        self,
        brand: Brand,
        url: str,
        date_threshold: datetime,
    ) -> Optional[RawEmail]:
        """Scrape a single email page via ZenRows."""
        try:
            # Individual email pages don't need JS rendering
            html = await _zenrows_fetch(url, self._client, js_render=False)
            if not html:
                return None

            # Extract subject from <h1> or <title>
            subject = "No Subject"
            h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
            if h1_match:
                raw = h1_match.group(1)
                # Strip inner tags
                subject = re.sub(r"<[^>]+>", "", raw).strip() or "No Subject"
            else:
                title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
                if title_match:
                    subject = re.sub(r"<[^>]+>", "", title_match.group(1)).strip()

            # Extract date
            sent_at: Optional[datetime] = None
            datetime_match = re.search(r'datetime=["\']([^"\']+)["\']', html)
            if datetime_match:
                sent_at = self._parse_date(datetime_match.group(1))
            if not sent_at:
                sent_at = self._extract_date_from_content(html)
            if not sent_at:
                sent_at = datetime.utcnow()
                logger.warning(f"Could not find date for {url}, using now")

            if sent_at < date_threshold:
                logger.debug(f"Skipping old email ({sent_at}): {url}")
                return None

            # Extract email body — prefer .email-content / article / main
            content_match = re.search(
                r'<(?:div[^>]+class="[^"]*email-content[^"]*"|article|main)[^>]*>(.*?)</(?:div|article|main)>',
                html,
                re.IGNORECASE | re.DOTALL,
            )
            html_content = content_match.group(0) if content_match else html

            raw_email = RawEmail(
                brand_id=brand.id,
                milled_url=url,
                subject=subject[:500],
                sent_at=sent_at,
                html_content=html_content,
            )
            self.db.add(raw_email)
            await self.db.flush()
            return raw_email

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
        patterns = [
            r"(\d{4}-\d{2}-\d{2})",
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4})",
            r"(\d{1,2}/\d{1,2}/\d{4})",
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                date = self._parse_date(match.group(1))
                if date:
                    return date
        return None


# ---------------------------------------------------------------------------
# Convenience helpers (API compat)
# ---------------------------------------------------------------------------

async def scrape_brand_emails(
    db: AsyncSession,
    brand_id: UUID,
    days_back: int = 365,
    max_emails: int = 500,
) -> list[RawEmail]:
    """Scrape emails for a single brand."""
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
    """Scrape emails for all active brands."""
    result = await db.execute(select(Brand).where(Brand.is_active == True))  # noqa: E712
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
