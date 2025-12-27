#!/usr/bin/env python
"""
Import emails from manually saved HTML pages.

Usage:
    1. Go to https://milled.com/stores/gamestop in your browser
    2. Scroll down to load all emails you want
    3. Save the page as HTML: File -> Save Page As -> gamestop.html
    4. Save to: salewatcher/backend/saved_pages/
    5. Run: python scripts/import_html.py --brand gamestop --file saved_pages/gamestop.html
"""
import argparse
import asyncio
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from src.config import settings
from src.db.session import get_session_factory
from src.db.models import Brand, RawEmail

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BASE_URL = "https://milled.com"


def parse_date(date_str: str) -> datetime:
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
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return datetime.utcnow()


def extract_emails_from_html(html_path: Path, brand_slug: str) -> list[dict]:
    """Extract email links and metadata from saved HTML page."""
    logger.info(f"Parsing: {html_path}")

    with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    emails = []

    # Email links are in format: /{brand_slug}/{email-title-with-id}
    # e.g., /gamestop/buy-2-get-1-free-on-pre-owned-games-XaJ_lDiJB24GL_zV
    # Find all links and filter by prefix
    all_links = soup.find_all('a')
    prefix = f'/{brand_slug}/'
    email_links = [a for a in all_links if a.get('href', '').startswith(prefix) and '-' in a.get('href', '')[len(prefix):]]

    logger.info(f"Found {len(email_links)} email links")

    seen_urls = set()

    for link in email_links:
        href = link.get('href', '')

        # Skip duplicates
        if href in seen_urls:
            continue
        seen_urls.add(href)

        # Build full URL
        full_url = href if href.startswith('http') else f"{BASE_URL}{href}"

        # Try to find subject - look for text in the link or nearby elements
        subject = link.get_text(strip=True)
        if not subject or len(subject) < 5:
            # Try parent elements
            parent = link.parent
            if parent:
                subject = parent.get_text(strip=True)[:200]

        if not subject:
            subject = "No Subject"

        # Try to find date - look for time elements nearby
        date_el = link.find('time') or link.find_next('time')
        sent_at = None

        if date_el:
            datetime_attr = date_el.get('datetime', '')
            if datetime_attr:
                sent_at = parse_date(datetime_attr)
            else:
                sent_at = parse_date(date_el.get_text())

        if not sent_at:
            # Try to extract from URL or use current time
            sent_at = datetime.utcnow()

        emails.append({
            'url': full_url,
            'subject': subject[:500],  # Limit length
            'sent_at': sent_at,
        })

    return emails


async def import_emails(brand_slug: str, html_path: Path):
    """Import emails from HTML file into database."""

    # Parse HTML
    emails = extract_emails_from_html(html_path, brand_slug)

    if not emails:
        logger.error("No emails found in HTML file")
        return

    logger.info(f"Extracted {len(emails)} unique emails")

    session_factory = get_session_factory()

    async with session_factory() as db:
        # Get brand
        result = await db.execute(
            select(Brand).where(Brand.milled_slug == brand_slug)
        )
        brand = result.scalar_one_or_none()

        if not brand:
            logger.error(f"Brand '{brand_slug}' not found in database")
            return

        logger.info(f"Importing for brand: {brand.name}")

        # Get existing URLs to avoid duplicates
        existing = await db.execute(
            select(RawEmail.milled_url).where(RawEmail.brand_id == brand.id)
        )
        existing_urls = {row[0] for row in existing.all()}
        logger.info(f"Found {len(existing_urls)} existing emails in database")

        # Import new emails
        imported = 0
        for email_data in emails:
            if email_data['url'] in existing_urls:
                continue

            raw_email = RawEmail(
                brand_id=brand.id,
                milled_url=email_data['url'],
                subject=email_data['subject'],
                sent_at=email_data['sent_at'],
                html_content="",  # We'll fetch content separately if needed
            )

            db.add(raw_email)
            imported += 1
            logger.info(f"  Added: {email_data['subject'][:50]}...")

        await db.commit()
        logger.info(f"Imported {imported} new emails for {brand.name}")


async def main():
    parser = argparse.ArgumentParser(description="Import emails from saved HTML")
    parser.add_argument(
        "--brand",
        required=True,
        help="Brand slug (e.g., 'gamestop')",
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Path to saved HTML file",
    )

    args = parser.parse_args()

    html_path = Path(args.file)
    if not html_path.is_absolute():
        html_path = Path(__file__).parent.parent / html_path

    if not html_path.exists():
        logger.error(f"File not found: {html_path}")
        sys.exit(1)

    await import_emails(args.brand, html_path)


if __name__ == "__main__":
    asyncio.run(main())
