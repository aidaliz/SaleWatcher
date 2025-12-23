"""Accuracy and suggestion API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("")
async def get_overall_accuracy():
    """Get overall prediction accuracy statistics."""
    # TODO: Implement with database
    return {
        "total_predictions": 0,
        "correct_predictions": 0,
        "hit_rate": 0.0,
        "avg_timing_delta_days": None,
    }


@router.get("/brands")
async def get_brand_accuracy_breakdown():
    """Get per-brand accuracy breakdown."""
    # TODO: Implement with database
    return {"brands": []}


@router.get("/brands/{brand_id}")
async def get_brand_accuracy(brand_id: UUID):
    """Get accuracy statistics for a specific brand."""
    # TODO: Implement with database
    raise HTTPException(status_code=404, detail="Brand not found")


@router.get("/suggestions")
async def list_adjustment_suggestions(
    status: str = "pending",
):
    """List pending adjustment suggestions."""
    # TODO: Implement with database
    return {"suggestions": [], "total": 0}


@router.post("/suggestions/{suggestion_id}/approve")
async def approve_suggestion(suggestion_id: UUID):
    """Approve and apply an adjustment suggestion."""
    # TODO: Implement with database
    raise HTTPException(status_code=404, detail="Suggestion not found")


@router.post("/suggestions/{suggestion_id}/dismiss")
async def dismiss_suggestion(suggestion_id: UUID):
    """Dismiss an adjustment suggestion."""
    # TODO: Implement with database
    raise HTTPException(status_code=404, detail="Suggestion not found")
