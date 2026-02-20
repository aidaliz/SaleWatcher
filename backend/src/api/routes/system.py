"""System API endpoints."""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session


router = APIRouter()


class TriggerResponse(BaseModel):
    """Standard response for trigger endpoints."""
    status: str
    message: str
    details: dict | None = None


@router.get("/health")
async def health_check():
    """Health check endpoint - simple ping for Railway."""
    return {"status": "healthy"}


@router.get("/health/detailed")
async def health_check_detailed(
    db: AsyncSession = Depends(get_db_session),
):
    """Detailed health check with database status."""
    from sqlalchemy import text
    try:
        # Test database connection
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return {"status": "healthy" if db_status == "connected" else "degraded", "database": db_status}


@router.post("/scrape/trigger", response_model=TriggerResponse)
async def trigger_scrape(
    brand_id: Optional[UUID] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db_session),
):
    """Manually trigger a scrape cycle."""
    from src.scraper.service import scrape_brands
    from src.db.crud.brands import get_brand, get_brands

    if brand_id:
        brand = await get_brand(db, brand_id)
        if not brand:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Brand not found",
            )
        brands = [brand]
    else:
        brands, _ = await get_brands(db, limit=1000, active_only=True)

    # Queue scraping task
    async def scrape_task():
        results = await scrape_brands(db, brands)
        total_new = sum(r.get("new", 0) for r in results)
        total_errors = sum(r.get("errors", 0) for r in results)
        print(f"Scrape complete: {total_new} new emails, {total_errors} errors")

    background_tasks.add_task(scrape_task)

    return TriggerResponse(
        status="queued",
        message=f"Scrape job queued for {len(brands)} brand(s)",
        details={"brand_count": len(brands)},
    )


@router.post("/extract/trigger", response_model=TriggerResponse)
async def trigger_extraction(
    brand_id: Optional[UUID] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db_session),
):
    """Trigger LLM extraction for unprocessed emails."""
    from src.extractor.service import process_pending_emails

    extractions = await process_pending_emails(db, brand_id=brand_id, limit=limit)

    return TriggerResponse(
        status="completed",
        message=f"Processed {len(extractions)} email(s)",
        details={
            "processed_count": len(extractions),
            "ids": [str(e.id) for e in extractions[:10]],  # First 10 IDs
        },
    )


@router.post("/deduplicate/trigger", response_model=TriggerResponse)
async def trigger_deduplication(
    brand_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db_session),
):
    """Trigger sale deduplication to create sale windows."""
    from src.deduplicator.service import run_deduplication

    windows = await run_deduplication(db, brand_id=brand_id)

    return TriggerResponse(
        status="completed",
        message=f"Created {len(windows)} sale window(s)",
        details={
            "window_count": len(windows),
            "windows": [
                {"id": str(w.id), "name": w.name, "start_date": str(w.start_date)}
                for w in windows[:10]
            ],
        },
    )


@router.post("/predict/trigger", response_model=TriggerResponse)
async def trigger_prediction(
    brand_id: Optional[UUID] = None,
    target_year: Optional[int] = None,
    db: AsyncSession = Depends(get_db_session),
):
    """Trigger prediction generation from historical sale windows."""
    from src.predictor.service import generate_predictions

    if target_year is None:
        target_year = date.today().year

    predictions = await generate_predictions(db, brand_id=brand_id, target_year=target_year)

    return TriggerResponse(
        status="completed",
        message=f"Generated {len(predictions)} prediction(s) for {target_year}",
        details={
            "prediction_count": len(predictions),
            "target_year": target_year,
            "predictions": [
                {
                    "id": str(p.id),
                    "discount": p.discount_summary,
                    "start": str(p.predicted_start),
                }
                for p in predictions[:10]
            ],
        },
    )


@router.post("/backfill/{brand_id}", response_model=TriggerResponse)
async def backfill_brand(
    brand_id: UUID,
    months: int = 12,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db_session),
):
    """Trigger historical backfill for a brand."""
    from src.db.crud.brands import get_brand
    from src.scraper.service import ScraperService

    brand = await get_brand(db, brand_id)
    if not brand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )

    # Queue backfill task
    async def backfill_task():
        service = ScraperService()
        result = await service.backfill_brand(db, brand, months_back=months)
        print(f"Backfill complete for {brand.name}: {result.get('new', 0)} new emails")

    background_tasks.add_task(backfill_task)

    return TriggerResponse(
        status="queued",
        message=f"Backfill queued for {brand.name} ({months} months)",
        details={"brand_id": str(brand_id), "brand_name": brand.name, "months": months},
    )


@router.post("/pipeline/trigger", response_model=TriggerResponse)
async def trigger_full_pipeline(
    brand_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Trigger the full processing pipeline:
    1. Extract pending emails
    2. Deduplicate into sale windows
    3. Generate predictions

    Note: Scraping is not included - use /scrape/trigger separately.
    """
    from src.extractor.service import process_pending_emails
    from src.deduplicator.service import run_deduplication
    from src.predictor.service import generate_predictions

    results = {}

    # Step 1: Extract
    extractions = await process_pending_emails(db, brand_id=brand_id)
    results["extractions"] = len(extractions)

    # Step 2: Deduplicate
    windows = await run_deduplication(db, brand_id=brand_id)
    results["windows"] = len(windows)

    # Step 3: Predict
    predictions = await generate_predictions(db, brand_id=brand_id)
    results["predictions"] = len(predictions)

    return TriggerResponse(
        status="completed",
        message="Pipeline completed",
        details=results,
    )


@router.post("/calendar/sync", response_model=TriggerResponse)
async def trigger_calendar_sync(
    brand_id: Optional[UUID] = None,
    days_ahead: int = 30,
    db: AsyncSession = Depends(get_db_session),
):
    """Sync upcoming predictions to Google Calendar."""
    from src.calendar.service import sync_predictions_to_calendar

    try:
        result = await sync_predictions_to_calendar(
            db,
            days_ahead=days_ahead,
            brand_id=brand_id,
        )

        return TriggerResponse(
            status="completed",
            message=f"Synced {result['synced']} prediction(s) to calendar",
            details=result,
        )
    except Exception as e:
        return TriggerResponse(
            status="error",
            message=f"Calendar sync failed: {str(e)}",
            details={"error": str(e)},
        )


@router.post("/notify/digest", response_model=TriggerResponse)
async def trigger_review_digest(
    db: AsyncSession = Depends(get_db_session),
):
    """Send the daily review digest email."""
    from src.notifier.service import send_daily_digest

    email_id = await send_daily_digest(db)

    if email_id:
        return TriggerResponse(
            status="sent",
            message="Review digest email sent",
            details={"email_id": email_id},
        )
    else:
        return TriggerResponse(
            status="skipped",
            message="No pending reviews or email not configured",
        )


@router.post("/notify/weekly", response_model=TriggerResponse)
async def trigger_weekly_summary(
    db: AsyncSession = Depends(get_db_session),
):
    """Send the weekly prediction summary email."""
    from src.notifier.service import send_weekly_summary

    email_id = await send_weekly_summary(db)

    if email_id:
        return TriggerResponse(
            status="sent",
            message="Weekly summary email sent",
            details={"email_id": email_id},
        )
    else:
        return TriggerResponse(
            status="skipped",
            message="Email not configured",
        )


@router.post("/verify/trigger", response_model=TriggerResponse)
async def trigger_verification(
    brand_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db_session),
):
    """Trigger auto-verification of past predictions."""
    from src.verifier.service import run_verification

    results = await run_verification(db, brand_id=brand_id)

    return TriggerResponse(
        status="completed",
        message=f"Verified {results['total']} prediction(s)",
        details=results,
    )


@router.post("/accuracy/recalculate", response_model=TriggerResponse)
async def trigger_accuracy_recalculation(
    db: AsyncSession = Depends(get_db_session),
):
    """Recalculate accuracy statistics for all brands."""
    from src.verifier.accuracy import calculate_all_accuracy

    stats = await calculate_all_accuracy(db)

    return TriggerResponse(
        status="completed",
        message=f"Recalculated accuracy for {stats['brands_tracked']} brand(s)",
        details=stats,
    )
