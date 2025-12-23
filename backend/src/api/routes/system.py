"""System API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    # TODO: Add database connection check
    return {"status": "healthy", "database": "connected"}


@router.post("/scrape/trigger")
async def trigger_scrape():
    """Manually trigger a scrape cycle."""
    # TODO: Implement scrape trigger
    return {"status": "queued", "message": "Scrape job queued"}


@router.post("/backfill/{brand_id}")
async def backfill_brand(brand_id: UUID):
    """Trigger historical backfill for a brand."""
    # TODO: Implement backfill
    raise HTTPException(status_code=404, detail="Brand not found")
