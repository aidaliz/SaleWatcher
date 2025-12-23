"""CRUD operations for Brand entity."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Brand
from src.db.schemas import BrandCreate, BrandUpdate


async def get_brand(db: AsyncSession, brand_id: UUID) -> Brand | None:
    """Get a single brand by ID."""
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    return result.scalar_one_or_none()


async def get_brand_by_slug(db: AsyncSession, milled_slug: str) -> Brand | None:
    """Get a single brand by Milled.com slug."""
    result = await db.execute(select(Brand).where(Brand.milled_slug == milled_slug))
    return result.scalar_one_or_none()


async def get_brands(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
) -> tuple[list[Brand], int]:
    """Get a list of brands with pagination."""
    query = select(Brand)
    if active_only:
        query = query.where(Brand.is_active == True)

    # Get total count
    count_query = select(Brand)
    if active_only:
        count_query = count_query.where(Brand.is_active == True)
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())

    # Get paginated results
    query = query.order_by(Brand.name).offset(skip).limit(limit)
    result = await db.execute(query)
    brands = result.scalars().all()

    return list(brands), total


async def create_brand(db: AsyncSession, brand: BrandCreate) -> Brand:
    """Create a new brand."""
    db_brand = Brand(
        name=brand.name,
        milled_slug=brand.milled_slug,
        excluded_categories=brand.excluded_categories,
    )
    db.add(db_brand)
    await db.commit()
    await db.refresh(db_brand)
    return db_brand


async def update_brand(
    db: AsyncSession,
    brand_id: UUID,
    brand_update: BrandUpdate,
) -> Brand | None:
    """Update a brand's settings."""
    db_brand = await get_brand(db, brand_id)
    if not db_brand:
        return None

    update_data = brand_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_brand, field, value)

    await db.commit()
    await db.refresh(db_brand)
    return db_brand


async def deactivate_brand(db: AsyncSession, brand_id: UUID) -> bool:
    """Deactivate a brand (soft delete)."""
    db_brand = await get_brand(db, brand_id)
    if not db_brand:
        return False

    db_brand.is_active = False
    await db.commit()
    return True


async def activate_brand(db: AsyncSession, brand_id: UUID) -> bool:
    """Reactivate a brand."""
    db_brand = await get_brand(db, brand_id)
    if not db_brand:
        return False

    db_brand.is_active = True
    await db.commit()
    return True
