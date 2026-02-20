"""Milled.com email scraper."""

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import AsyncGenerator, Optional

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config.settings import get_settings
from src.scraper.auth import MilledClient


@dataclass
class ScrapedEmail:
    """Represents a scraped email from Milled.com."""
    milled_url: str
    subject: str
    sent_at: date
    html_content: str
    brand_slug: str


class MilledScraper:
    """Scraper for extracting promotional emails from Milled.com."""

    BASE_URL = "https://milled.com"

    def __init__(self, client: MilledClient):
        self.client = client
        self.settings = get_settings()

    @property
    def page(self) -> Page:
        return self.client.page

    async def scrape_brand(
        self,
        brand_slug: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> AsyncGenerator[ScrapedEmail, None]:
        """
        Scrape emails for a brand within a date range.

        Args:
            brand_slug: The Milled.com slug for the brand (e.g., "target")
            start_date: Start of date range (default: 7 days ago)
            end_date: End of date range (default: today)

        Yields:
            ScrapedEmail objects for each email found
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=7)

        await self.client.ensure_authenticated()

        # Navigate to brand page
        brand_url = f"{self.BASE_URL}/{brand_slug}"
        await self._navigate_with_retry(brand_url)

        # Get all email links on the page
        email_links = await self._get_email_links(start_date, end_date)

        for link_info in email_links:
            try:
                email = await self._scrape_email(link_info, brand_slug)
                if email:
                    yield email
                # Polite delay between requests
                await asyncio.sleep(self.settings.scrape_delay_seconds / 2)
            except Exception as e:
                # Log error but continue with other emails
                print(f"Error scraping email {link_info['url']}: {e}")
                continue

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=30),
        retry=retry_if_exception_type((PlaywrightTimeout, TimeoutError)),
    )
    async def _navigate_with_retry(self, url: str):
        """Navigate to a URL with retry logic."""
        await self.page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(self.settings.scrape_delay_seconds)

    async def _get_email_links(
        self,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        """Extract email links from the brand page."""
        email_links = []

        # Scroll to load more emails if needed
        await self._scroll_to_load_all()

        # Find all email cards/links
        email_elements = await self.page.query_selector_all(
            "a[href*='/emails/'], .email-card, [data-email-id]"
        )

        for element in email_elements:
            try:
                href = await element.get_attribute("href")
                if not href or "/emails/" not in href:
                    continue

                # Extract date from the element
                date_text = await self._extract_date_from_element(element)
                if date_text:
                    email_date = self._parse_date(date_text)
                    if email_date and start_date <= email_date <= end_date:
                        # Get subject
                        subject_el = await element.query_selector(
                            "h3, h4, .subject, [class*='subject'], [class*='title']"
                        )
                        subject = ""
                        if subject_el:
                            subject = (await subject_el.text_content() or "").strip()

                        full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                        email_links.append({
                            "url": full_url,
                            "subject": subject,
                            "date": email_date,
                        })
            except Exception:
                continue

        return email_links

    async def _extract_date_from_element(self, element) -> Optional[str]:
        """Extract date text from an email element."""
        # Try various selectors for date
        date_selectors = [
            "time",
            "[datetime]",
            ".date",
            "[class*='date']",
            "span:has-text('202')",  # Year pattern
        ]

        for selector in date_selectors:
            date_el = await element.query_selector(selector)
            if date_el:
                # Try datetime attribute first
                datetime_attr = await date_el.get_attribute("datetime")
                if datetime_attr:
                    return datetime_attr

                # Fall back to text content
                text = await date_el.text_content()
                if text:
                    return text.strip()

        return None

    def _parse_date(self, date_text: str) -> Optional[date]:
        """Parse a date string into a date object."""
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%B %d, %Y",
            "%b %d, %Y",
            "%m/%d/%Y",
            "%m/%d/%y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_text[:len(date_text)], fmt).date()
            except ValueError:
                continue

        # Try to extract date with regex as fallback
        import re
        match = re.search(r"(\d{4})-(\d{2})-(\d{2})", date_text)
        if match:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))

        return None

    async def _scroll_to_load_all(self, max_scrolls: int = 10):
        """Scroll down to load all emails (for infinite scroll pages)."""
        for _ in range(max_scrolls):
            # Get current height
            prev_height = await self.page.evaluate("document.body.scrollHeight")

            # Scroll to bottom
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)

            # Check if we've loaded more content
            new_height = await self.page.evaluate("document.body.scrollHeight")
            if new_height == prev_height:
                break

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type((PlaywrightTimeout, TimeoutError)),
    )
    async def _scrape_email(
        self,
        link_info: dict,
        brand_slug: str,
    ) -> Optional[ScrapedEmail]:
        """Scrape the content of a single email."""
        await self.page.goto(link_info["url"], wait_until="networkidle", timeout=30000)

        # Wait for email content to load
        await self.page.wait_for_selector(
            "iframe, .email-content, [class*='email-body'], article",
            timeout=10000,
        )

        # Try to get email content from iframe first (common pattern)
        html_content = await self._extract_email_html()

        if not html_content:
            return None

        # Get subject if not already extracted
        subject = link_info.get("subject", "")
        if not subject:
            subject_el = await self.page.query_selector(
                "h1, h2, [class*='subject'], [class*='title']"
            )
            if subject_el:
                subject = (await subject_el.text_content() or "").strip()

        return ScrapedEmail(
            milled_url=link_info["url"],
            subject=subject,
            sent_at=link_info["date"],
            html_content=html_content,
            brand_slug=brand_slug,
        )

    async def _extract_email_html(self) -> Optional[str]:
        """Extract the HTML content of the email."""
        # Try iframe first (most common)
        iframe = await self.page.query_selector("iframe[src*='email'], iframe.email-frame")
        if iframe:
            frame = await iframe.content_frame()
            if frame:
                return await frame.content()

        # Try direct email content container
        content_selectors = [
            ".email-content",
            ".email-body",
            "[class*='email-html']",
            "article.email",
            "#email-content",
        ]

        for selector in content_selectors:
            element = await self.page.query_selector(selector)
            if element:
                return await element.inner_html()

        # Fallback: get the main content area
        main = await self.page.query_selector("main, .main-content, #content")
        if main:
            return await main.inner_html()

        return None


async def scrape_brand_emails(
    brand_slug: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> list[ScrapedEmail]:
    """
    Convenience function to scrape emails for a brand.

    Args:
        brand_slug: The Milled.com slug for the brand
        start_date: Start of date range (default: 7 days ago)
        end_date: End of date range (default: today)

    Returns:
        List of ScrapedEmail objects
    """
    async with MilledClient() as client:
        scraper = MilledScraper(client)
        emails = []
        async for email in scraper.scrape_brand(brand_slug, start_date, end_date):
            emails.append(email)
        return emails
