from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.db import crud
from src.db.schemas import (
    BrandCreate,
    BrandListResponse,
    BrandResponse,
    BrandUpdate,
)

router = APIRouter()


@router.get("", response_model=BrandListResponse)
async def list_brands(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """List all brands with pagination."""
    brands, total = await crud.get_brands(db, skip=skip, limit=limit, active_only=active_only)
    return BrandListResponse(
        brands=[BrandResponse.model_validate(b) for b in brands],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
async def create_brand(
    brand: BrandCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new brand."""
    # Check if slug already exists
    existing = await crud.get_brand_by_slug(db, brand.milled_slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Brand with slug '{brand.milled_slug}' already exists",
        )

    db_brand = await crud.create_brand(db, brand)
    return BrandResponse.model_validate(db_brand)


@router.get("/{brand_id}", response_model=BrandResponse)
async def get_brand(
    brand_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a brand by ID."""
    db_brand = await crud.get_brand(db, brand_id)
    if db_brand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )
    return BrandResponse.model_validate(db_brand)


@router.patch("/{brand_id}", response_model=BrandResponse)
async def update_brand(
    brand_id: UUID,
    brand_update: BrandUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a brand."""
    # If updating slug, check for uniqueness
    if brand_update.milled_slug:
        existing = await crud.get_brand_by_slug(db, brand_update.milled_slug)
        if existing and existing.id != brand_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Brand with slug '{brand_update.milled_slug}' already exists",
            )

    db_brand = await crud.update_brand(db, brand_id, brand_update)
    if db_brand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )
    return BrandResponse.model_validate(db_brand)


@router.delete("/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_brand(
    brand_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a brand (set is_active=False)."""
    success = await crud.deactivate_brand(db, brand_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )
    return None


@router.post("/{brand_id}/activate", response_model=BrandResponse)
async def activate_brand(
    brand_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Reactivate a deactivated brand."""
    success = await crud.activate_brand(db, brand_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )

    db_brand = await crud.get_brand(db, brand_id)
    return BrandResponse.model_validate(db_brand)
