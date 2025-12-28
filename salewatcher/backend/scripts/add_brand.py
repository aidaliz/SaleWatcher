#!/usr/bin/env python
"""
Add a new brand to the database.

Usage:
    python scripts/add_brand.py --name "Huda Beauty" --slug hudabeauty
    python scripts/add_brand.py --name "GameStop" --slug gamestop
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from src.db.session import get_session_factory
from src.db.models import Brand


async def add_brand(name: str, slug: str):
    """Add a new brand to the database."""
    session_factory = get_session_factory()

    async with session_factory() as db:
        # Check if brand already exists
        result = await db.execute(
            select(Brand).where(Brand.milled_slug == slug)
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Brand '{slug}' already exists: {existing.name}")
            return

        # Create new brand
        brand = Brand(
            name=name,
            milled_slug=slug,
            is_active=True,
            excluded_categories=[],
        )

        db.add(brand)
        await db.commit()
        print(f"Added brand: {name} (slug: {slug})")


async def list_brands():
    """List all brands in the database."""
    session_factory = get_session_factory()

    async with session_factory() as db:
        result = await db.execute(select(Brand).order_by(Brand.name))
        brands = result.scalars().all()

        if not brands:
            print("No brands in database")
            return

        print("\nCurrent brands:")
        for brand in brands:
            status = "active" if brand.is_active else "inactive"
            print(f"  - {brand.name} (slug: {brand.milled_slug}) [{status}]")


async def main():
    parser = argparse.ArgumentParser(description="Add a new brand")
    parser.add_argument("--name", help="Brand display name (e.g., 'Huda Beauty')")
    parser.add_argument("--slug", help="Milled.com slug (e.g., 'hudabeauty')")
    parser.add_argument("--list", action="store_true", help="List all brands")

    args = parser.parse_args()

    if args.list:
        await list_brands()
        return

    if not args.name or not args.slug:
        parser.print_help()
        print("\nExample: python scripts/add_brand.py --name 'Huda Beauty' --slug hudabeauty")
        return

    await add_brand(args.name, args.slug)
    await list_brands()


if __name__ == "__main__":
    asyncio.run(main())
