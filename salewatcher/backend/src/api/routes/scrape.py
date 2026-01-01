"""
API routes for Milled.com scraping.

Provides endpoints to trigger and monitor scraping jobs from the web.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.db.models import Brand, RawEmail, ExtractedSale
from src.scraper.milled import MilledScraper
from src.extractor.llm import SaleExtractor
from src.deduplicator.grouper import create_sale_windows
from src.predictor.generator import generate_all_future_predictions

router = APIRouter()
logger = logging.getLogger(__name__)


# In-memory job tracking (could be moved to Redis/DB for production)
class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScrapeJob(BaseModel):
    id: str
    brand_id: str
    brand_name: str
    status: JobStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    emails_scraped: int = 0
    emails_extracted: int = 0
    predictions_generated: int = 0
    error: Optional[str] = None
    current_step: str = "pending"


# Job storage
_jobs: dict[str, ScrapeJob] = {}


class ScrapeRequest(BaseModel):
    days_back: int = 730  # 2 years of history
    max_emails: int = 2000  # Increased for larger brands
    run_extraction: bool = True
    run_predictions: bool = True


class ScrapeResponse(BaseModel):
    job_id: str
    message: str


class BrandStatsResponse(BaseModel):
    brand_id: str
    brand_name: str
    total_emails: int
    extracted_sales: int
    pending_review: int
    predictions: int


@router.get("/jobs")
async def list_jobs() -> list[ScrapeJob]:
    """List all scrape jobs."""
    return list(_jobs.values())


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> ScrapeJob:
    """Get status of a specific scrape job."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return _jobs[job_id]


@router.post("/brand/{brand_slug}", response_model=ScrapeResponse)
async def scrape_brand(
    brand_slug: str,
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Start a scraping job for a brand.

    This runs in the background and scrapes emails from Milled.com,
    optionally extracts sales and generates predictions.
    """
    # Get brand
    result = await db.execute(
        select(Brand).where(Brand.milled_slug == brand_slug)
    )
    brand = result.scalar_one_or_none()

    if not brand:
        raise HTTPException(status_code=404, detail=f"Brand '{brand_slug}' not found")

    # Check if there's already a running job for this brand
    for job in _jobs.values():
        if job.brand_id == str(brand.id) and job.status == JobStatus.RUNNING:
            raise HTTPException(
                status_code=409,
                detail=f"A scrape job is already running for {brand.name}"
            )

    # Create job
    job_id = str(uuid4())
    job = ScrapeJob(
        id=job_id,
        brand_id=str(brand.id),
        brand_name=brand.name,
        status=JobStatus.PENDING,
        current_step="Queued",
    )
    _jobs[job_id] = job

    # Start background task
    background_tasks.add_task(
        run_scrape_pipeline,
        job_id=job_id,
        brand_id=brand.id,
        brand_slug=brand_slug,
        days_back=request.days_back,
        max_emails=request.max_emails,
        run_extraction=request.run_extraction,
        run_predictions=request.run_predictions,
    )

    return ScrapeResponse(
        job_id=job_id,
        message=f"Scrape job started for {brand.name}",
    )


@router.get("/brand/{brand_slug}/stats", response_model=BrandStatsResponse)
async def get_brand_stats(
    brand_slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Get scraping/extraction stats for a brand."""
    # Get brand
    result = await db.execute(
        select(Brand).where(Brand.milled_slug == brand_slug)
    )
    brand = result.scalar_one_or_none()

    if not brand:
        raise HTTPException(status_code=404, detail=f"Brand '{brand_slug}' not found")

    # Count emails
    result = await db.execute(
        select(func.count()).where(RawEmail.brand_id == brand.id)
    )
    total_emails = result.scalar() or 0

    # Count extracted sales
    result = await db.execute(
        select(func.count())
        .select_from(ExtractedSale)
        .join(RawEmail)
        .where(RawEmail.brand_id == brand.id)
    )
    extracted_sales = result.scalar() or 0

    # Count pending review
    result = await db.execute(
        select(func.count())
        .select_from(ExtractedSale)
        .join(RawEmail)
        .where(RawEmail.brand_id == brand.id)
        .where(ExtractedSale.status == "pending")
    )
    pending_review = result.scalar() or 0

    # Count predictions
    from src.db.models import Prediction
    result = await db.execute(
        select(func.count()).where(Prediction.brand_id == brand.id)
    )
    predictions = result.scalar() or 0

    return BrandStatsResponse(
        brand_id=str(brand.id),
        brand_name=brand.name,
        total_emails=total_emails,
        extracted_sales=extracted_sales,
        pending_review=pending_review,
        predictions=predictions,
    )


async def run_scrape_pipeline(
    job_id: str,
    brand_id: UUID,
    brand_slug: str,
    days_back: int,
    max_emails: int,
    run_extraction: bool,
    run_predictions: bool,
):
    """
    Run the full scrape -> extract -> predict pipeline.

    This runs as a background task.
    """
    from src.db.session import get_session_factory

    job = _jobs[job_id]
    job.status = JobStatus.RUNNING
    job.started_at = datetime.utcnow()

    session_factory = get_session_factory()

    try:
        async with session_factory() as db:
            # Get brand
            result = await db.execute(
                select(Brand).where(Brand.id == brand_id)
            )
            brand = result.scalar_one()

            # Step 1: Scrape emails
            job.current_step = "Scraping emails from Milled.com..."
            logger.info(f"[Job {job_id}] Starting scrape for {brand.name}")

            try:
                async with MilledScraper(db, headless=True) as scraper:
                    emails = await scraper.scrape_brand(
                        brand,
                        days_back=days_back,
                        max_emails=max_emails,
                    )
                    await db.commit()
                    job.emails_scraped = len(emails)
                    logger.info(f"[Job {job_id}] Scraped {len(emails)} emails")
            except Exception as e:
                logger.error(f"[Job {job_id}] Scrape error: {e}")
                # Continue with existing emails if scraping fails
                job.current_step = f"Scrape failed: {str(e)[:100]}. Continuing with existing emails..."

            # Step 2: Extract sales (if requested)
            if run_extraction:
                job.current_step = "Extracting sales from emails..."
                logger.info(f"[Job {job_id}] Starting extraction")

                # Get unprocessed emails
                from sqlalchemy.orm import selectinload
                result = await db.execute(
                    select(RawEmail)
                    .options(selectinload(RawEmail.brand))
                    .where(RawEmail.brand_id == brand_id)
                    .outerjoin(ExtractedSale)
                    .where(ExtractedSale.id == None)
                    .limit(100)  # Process in batches
                )
                unprocessed = result.scalars().all()

                extractor = SaleExtractor()
                extracted_count = 0
                for email in unprocessed:
                    try:
                        extracted = await extractor.extract_with_fallback(
                            email,
                            brand.name,
                        )
                        db.add(extracted)
                        extracted_count += 1
                        job.emails_extracted = extracted_count
                        job.current_step = f"Extracted {extracted_count}/{len(unprocessed)} emails..."
                    except Exception as e:
                        logger.warning(f"[Job {job_id}] Extract error for email {email.id}: {e}")

                await db.commit()
                logger.info(f"[Job {job_id}] Extracted {extracted_count} sales")

            # Step 3: Generate predictions (if requested)
            if run_predictions:
                job.current_step = "Grouping sales and generating predictions..."
                logger.info(f"[Job {job_id}] Starting prediction generation")

                # Group into windows
                windows = await create_sale_windows(db, brand_id=brand_id)
                await db.commit()

                # Generate predictions
                predictions = await generate_all_future_predictions(
                    db,
                    brand_id=brand_id,
                    years_ahead=1,
                )
                await db.commit()

                total_preds = sum(len(p) for p in predictions.values())
                job.predictions_generated = total_preds
                logger.info(f"[Job {job_id}] Generated {total_preds} predictions")

            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.current_step = "Completed"
            logger.info(f"[Job {job_id}] Pipeline completed successfully")

    except Exception as e:
        logger.error(f"[Job {job_id}] Pipeline failed: {e}")
        job.status = JobStatus.FAILED
        job.error = str(e)
        job.completed_at = datetime.utcnow()
        job.current_step = f"Failed: {str(e)[:100]}"
