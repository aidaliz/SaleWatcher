from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Brand
from src.db.schemas import BrandCreate, BrandUpdate


async def get_brand(db: AsyncSession, brand_id: UUID) -> Optional[Brand]:
    """Get a brand by ID."""
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    return result.scalar_one_or_none()


async def get_brand_by_slug(db: AsyncSession, milled_slug: str) -> Optional[Brand]:
    """Get a brand by Milled.com slug."""
    result = await db.execute(select(Brand).where(Brand.milled_slug == milled_slug))
    return result.scalar_one_or_none()


async def get_brands(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
) -> tuple[list[Brand], int]:
    """Get a paginated list of brands."""
    # Build base query
    query = select(Brand)
    count_query = select(func.count(Brand.id))

    if active_only:
        query = query.where(Brand.is_active == True)
        count_query = count_query.where(Brand.is_active == True)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Get brands with pagination
    query = query.order_by(Brand.name).offset(skip).limit(limit)
    result = await db.execute(query)
    brands = list(result.scalars().all())

    return brands, total


async def create_brand(db: AsyncSession, brand: BrandCreate) -> Brand:
    """Create a new brand."""
    db_brand = Brand(
        name=brand.name,
        milled_slug=brand.milled_slug,
        excluded_categories=brand.excluded_categories,
    )
    db.add(db_brand)
    await db.flush()
    await db.refresh(db_brand)
    return db_brand


async def update_brand(
    db: AsyncSession,
    brand_id: UUID,
    brand_update: BrandUpdate,
) -> Optional[Brand]:
    """Update a brand."""
    db_brand = await get_brand(db, brand_id)
    if db_brand is None:
        return None

    update_data = brand_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_brand, field, value)

    await db.flush()
    await db.refresh(db_brand)
    return db_brand


async def deactivate_brand(db: AsyncSession, brand_id: UUID) -> bool:
    """Soft delete a brand by setting is_active to False."""
    db_brand = await get_brand(db, brand_id)
    if db_brand is None:
        return False

    db_brand.is_active = False
    await db.flush()
    return True


async def activate_brand(db: AsyncSession, brand_id: UUID) -> bool:
    """Reactivate a deactivated brand."""
    db_brand = await get_brand(db, brand_id)
    if db_brand is None:
        return False

    db_brand.is_active = True
    await db.flush()
    return True
