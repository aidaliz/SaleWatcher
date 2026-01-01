#!/usr/bin/env python
"""
Add or fix brand milled_slugs in database.

The milled_slug needs to match the exact case used in Milled.com URLs.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import update, select
from src.db.session import get_session_factory
from src.db.models import Brand


async def main():
    session_factory = get_session_factory()

    async with session_factory() as db:
        # First, show current brands
        result = await db.execute(select(Brand))
        brands = result.scalars().all()

        print("Current brands in database:")
        for brand in brands:
            print(f"  - {brand.name}: milled_slug='{brand.milled_slug}'")

        # Check if Bath & Body Works exists
        result = await db.execute(
            select(Brand).where(
                (Brand.milled_slug == 'bathbodyworks') |
                (Brand.milled_slug == 'BathBodyWorks') |
                (Brand.name == 'Bath & Body Works')
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update slug if needed
            if existing.milled_slug != 'BathBodyWorks':
                existing.milled_slug = 'BathBodyWorks'
                print(f"\n✅ Updated slug for {existing.name} to 'BathBodyWorks'")
            else:
                print(f"\n✅ Bath & Body Works already has correct slug")
        else:
            # Add Bath & Body Works brand
            new_brand = Brand(
                name='Bath & Body Works',
                milled_slug='BathBodyWorks',
                is_active=True,
            )
            db.add(new_brand)
            print("\n✅ Added Bath & Body Works brand with slug 'BathBodyWorks'")

        await db.commit()

        # Show updated brands
        result = await db.execute(select(Brand))
        brands = result.scalars().all()

        print("\nBrands after update:")
        for brand in brands:
            print(f"  - {brand.name}: milled_slug='{brand.milled_slug}'")


if __name__ == "__main__":
    asyncio.run(main())
