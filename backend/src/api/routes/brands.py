"""Brand management API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import get_db_session
from src.db.schemas import BrandCreate, BrandUpdate, BrandResponse, BrandListResponse

router = APIRouter()


@router.get("", response_model=BrandListResponse)
async def list_brands(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
):
    """List all brands with optional filtering."""
    # TODO: Implement with database
    return {"brands": [], "total": 0}


@router.post("", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
async def create_brand(brand: BrandCreate):
    """Create a new brand to track."""
    # TODO: Implement with database
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{brand_id}", response_model=BrandResponse)
async def get_brand(brand_id: UUID):
    """Get a specific brand by ID."""
    # TODO: Implement with database
    raise HTTPException(status_code=404, detail="Brand not found")


@router.patch("/{brand_id}", response_model=BrandResponse)
async def update_brand(brand_id: UUID, brand: BrandUpdate):
    """Update a brand's settings."""
    # TODO: Implement with database
    raise HTTPException(status_code=404, detail="Brand not found")


@router.delete("/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_brand(brand_id: UUID):
    """Deactivate a brand (soft delete)."""
    # TODO: Implement with database
    raise HTTPException(status_code=404, detail="Brand not found")


@router.get("/{brand_id}/emails")
async def list_brand_emails(
    brand_id: UUID,
    skip: int = 0,
    limit: int = 100,
):
    """List emails scraped for a specific brand."""
    # TODO: Implement with database
    return {"emails": [], "total": 0}


@router.get("/{brand_id}/predictions")
async def list_brand_predictions(
    brand_id: UUID,
    skip: int = 0,
    limit: int = 100,
):
    """List predictions for a specific brand."""
    # TODO: Implement with database
    return {"predictions": [], "total": 0}
