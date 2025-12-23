"""Brand management API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.db.schemas import BrandCreate, BrandUpdate, BrandResponse, BrandListResponse
from src.db.crud import brands as crud_brands

router = APIRouter()


@router.get("", response_model=BrandListResponse)
async def list_brands(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db_session),
):
    """List all brands with optional filtering."""
    brands, total = await crud_brands.get_brands(
        db, skip=skip, limit=limit, active_only=active_only
    )
    return BrandListResponse(
        brands=[BrandResponse.model_validate(b) for b in brands],
        total=total,
    )


@router.post("", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
async def create_brand(
    brand: BrandCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new brand to track."""
    # Check if slug already exists
    existing = await crud_brands.get_brand_by_slug(db, brand.milled_slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Brand with slug '{brand.milled_slug}' already exists",
        )

    db_brand = await crud_brands.create_brand(db, brand)
    return BrandResponse.model_validate(db_brand)


@router.get("/{brand_id}", response_model=BrandResponse)
async def get_brand(
    brand_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Get a specific brand by ID."""
    db_brand = await crud_brands.get_brand(db, brand_id)
    if not db_brand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )
    return BrandResponse.model_validate(db_brand)


@router.patch("/{brand_id}", response_model=BrandResponse)
async def update_brand(
    brand_id: UUID,
    brand: BrandUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Update a brand's settings."""
    # If updating slug, check it's not taken by another brand
    if brand.milled_slug:
        existing = await crud_brands.get_brand_by_slug(db, brand.milled_slug)
        if existing and existing.id != brand_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Brand with slug '{brand.milled_slug}' already exists",
            )

    db_brand = await crud_brands.update_brand(db, brand_id, brand)
    if not db_brand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )
    return BrandResponse.model_validate(db_brand)


@router.delete("/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_brand(
    brand_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Deactivate a brand (soft delete)."""
    success = await crud_brands.deactivate_brand(db, brand_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )


@router.post("/{brand_id}/activate", response_model=BrandResponse)
async def activate_brand(
    brand_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Reactivate a deactivated brand."""
    success = await crud_brands.activate_brand(db, brand_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )
    db_brand = await crud_brands.get_brand(db, brand_id)
    return BrandResponse.model_validate(db_brand)


@router.get("/{brand_id}/emails")
async def list_brand_emails(
    brand_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db_session),
):
    """List emails scraped for a specific brand."""
    db_brand = await crud_brands.get_brand(db, brand_id)
    if not db_brand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )
    # TODO: Implement email listing with crud_emails
    return {"emails": [], "total": 0}


@router.get("/{brand_id}/predictions")
async def list_brand_predictions(
    brand_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db_session),
):
    """List predictions for a specific brand."""
    db_brand = await crud_brands.get_brand(db, brand_id)
    if not db_brand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )
    # TODO: Implement prediction listing with crud_predictions
    return {"predictions": [], "total": 0}
