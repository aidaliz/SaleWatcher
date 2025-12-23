"""Prediction API endpoints."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()


@router.get("")
async def list_predictions(
    skip: int = 0,
    limit: int = 100,
    brand_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
):
    """List all predictions with optional filtering."""
    # TODO: Implement with database
    return {"predictions": [], "total": 0}


@router.get("/upcoming")
async def list_upcoming_predictions(
    days: int = Query(default=14, ge=1, le=90),
):
    """List predictions for the next N days."""
    # TODO: Implement with database
    return {"predictions": [], "total": 0}


@router.get("/{prediction_id}")
async def get_prediction(prediction_id: UUID):
    """Get a specific prediction by ID."""
    # TODO: Implement with database
    raise HTTPException(status_code=404, detail="Prediction not found")


@router.get("/{prediction_id}/outcome")
async def get_prediction_outcome(prediction_id: UUID):
    """Get the outcome of a prediction if it exists."""
    # TODO: Implement with database
    raise HTTPException(status_code=404, detail="Outcome not found")


@router.post("/{prediction_id}/override")
async def override_prediction_outcome(
    prediction_id: UUID,
    result: str,
    reason: str | None = None,
):
    """Manually override a prediction's auto-verified outcome."""
    # TODO: Implement with database
    raise HTTPException(status_code=404, detail="Prediction not found")
