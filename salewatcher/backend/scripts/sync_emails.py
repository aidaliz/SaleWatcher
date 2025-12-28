#!/usr/bin/env python
"""
CLI script for syncing emails from Gmail.

Usage:
    python scripts/sync_emails.py                    # Sync all brands
    python scripts/sync_emails.py --brand gamestop  # Sync specific brand
    python scripts/sync_emails.py --days 30         # Last 30 days only
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from src.config import settings
from src.db.session import get_session_factory
from src.db.models import Brand
from src.email_ingest import GmailClient, EmailIngestionService

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_token_data() -> dict | None:
    """Load Gmail token from environment or file."""
    # First try environment variable (for production)
    token_json = os.getenv('GMAIL_TOKEN_JSON')
    if token_json:
        try:
            return json.loads(token_json)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid GMAIL_TOKEN_JSON: {e}")
            return None

    # Fall back to token file (for local development)
    token_path = Path("gmail_token.json")
    if token_path.exists():
        try:
            with open(token_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error reading gmail_token.json: {e}")
            return None

    return None


async def main(args):
    """Main sync entry point."""
    # Load token
    token_data = get_token_data()
    if not token_data:
        logger.error("Gmail not authenticated.")
        logger.error("Run: python scripts/gmail_auth.py")
        logger.error("Or set GMAIL_TOKEN_JSON environment variable")
        return 1

    # Initialize Gmail client
    client = GmailClient()

    if not client.authenticate_with_token(token_data):
        logger.error("Gmail authentication failed. Token may be expired.")
        logger.error("Run: python scripts/gmail_auth.py")
        return 1

    logger.info("Gmail authenticated successfully")

    # Initialize service
    service = EmailIngestionService(client)
    session_factory = get_session_factory()

    async with session_factory() as db:
        if args.brand:
            # Sync specific brand
            result = await db.execute(
                select(Brand).where(Brand.milled_slug == args.brand)
            )
            brand = result.scalar_one_or_none()

            if not brand:
                logger.error(f"Brand '{args.brand}' not found")
                return 1

            logger.info(f"Syncing emails for {brand.name}...")
            stats = await service.sync_brand_emails(
                db, brand, args.days, args.limit
            )

            logger.info(f"\nSync Results for {brand.name}:")
            logger.info(f"  Fetched: {stats['fetched']}")
            logger.info(f"  New: {stats['new']}")
            logger.info(f"  Duplicates: {stats['duplicates']}")
            logger.info(f"  Errors: {stats['errors']}")

        else:
            # Sync all brands
            logger.info("Syncing emails for all active brands...")
            all_stats = await service.sync_all_brands(
                db, args.days, args.limit
            )

            logger.info("\nSync Results:")
            total_new = 0
            total_dupes = 0
            for stats in all_stats:
                if 'error' in stats:
                    logger.error(f"  {stats['brand']}: ERROR - {stats['error']}")
                else:
                    logger.info(
                        f"  {stats['brand']}: {stats['new']} new, "
                        f"{stats['duplicates']} duplicates"
                    )
                    total_new += stats.get('new', 0)
                    total_dupes += stats.get('duplicates', 0)

            logger.info(f"\nTotal: {total_new} new emails, {total_dupes} duplicates")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync emails from Gmail")
    parser.add_argument(
        "--brand",
        type=str,
        help="Specific brand slug to sync",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Days of history to sync (default: 365)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max emails per brand (default: unlimited, fetches all within date range)",
    )

    args = parser.parse_args()

    try:
        exit_code = asyncio.run(main(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Sync cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
