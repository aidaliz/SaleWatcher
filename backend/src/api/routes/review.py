"""Review queue API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("")
async def list_pending_reviews(
    skip: int = 0,
    limit: int = 100,
):
    """List extractions pending review."""
    # TODO: Implement with database
    return {"reviews": [], "total": 0}


@router.get("/{extraction_id}")
async def get_review_details(extraction_id: UUID):
    """Get detailed information about a pending review."""
    # TODO: Implement with database
    raise HTTPException(status_code=404, detail="Extraction not found")


@router.post("/{extraction_id}/approve")
async def approve_extraction(extraction_id: UUID):
    """Approve a borderline extraction."""
    # TODO: Implement with database
    raise HTTPException(status_code=404, detail="Extraction not found")


@router.post("/{extraction_id}/reject")
async def reject_extraction(extraction_id: UUID):
    """Reject a borderline extraction."""
    # TODO: Implement with database
    raise HTTPException(status_code=404, detail="Extraction not found")
