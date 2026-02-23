"""
API routes for SalesGazer integration.

Provides endpoints to look up stores, subscribe, and sync email history.
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.db.models import Brand
from src.salesgazer.client import SalesGazerClient
from src.salesgazer.sync import sync_brand_from_salesgazer

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/debug")
async def debug_salesgazer():
    """
    Diagnostic endpoint: test SalesGazer login + Playwright settings page.
    Returns cookies, current URL, and HTML snippet for debugging.
    """
    from playwright.async_api import async_playwright
    try:
        from playwright_stealth import stealth_async
    except ImportError:
        stealth_async = None

    result: dict = {
        "httpx_login": False,
        "httpx_cookies": [],
        "playwright_url": None,
        "playwright_html_snippet": None,
        "tr_store_id_count": 0,
        "error": None,
    }

    try:
        async with SalesGazerClient() as client:
            # Step 1: httpx login
            await client.login()
            result["httpx_login"] = True

            httpx_client = await client._get_client()
            cookies = list(httpx_client.cookies.jar)
            result["httpx_cookies"] = [
                {"name": c.name, "domain": c.domain, "path": c.path}
                for c in cookies
            ]

            # Step 2: Playwright settings page
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )

                # Inject httpx cookies
                pw_cookies = [
                    {
                        "name": c.name,
                        "value": c.value,
                        "domain": c.domain.lstrip(".") if c.domain else "salesgazer.com",
                        "path": c.path or "/",
                    }
                    for c in cookies
                ]
                if pw_cookies:
                    await context.add_cookies(pw_cookies)

                page = await context.new_page()
                if stealth_async:
                    await stealth_async(page)

                await page.goto("https://salesgazer.com/mailbox/settings/", wait_until="domcontentloaded")
                result["playwright_url"] = page.url

                html = await page.content()
                result["playwright_html_snippet"] = html[:5000]

                rows = await page.query_selector_all("tr[store-id]")
                result["tr_store_id_count"] = len(rows)

                # Extract sample row data so we know what domains/attributes are present
                sample_rows = []
                for row in rows[:5]:
                    store_id = await row.get_attribute("store-id")
                    tds = await row.query_selector_all("td")
                    td_texts = [(await td.inner_text()).strip() for td in tds[:6]]
                    outer = await row.inner_html()
                    sample_rows.append({
                        "store_id": store_id,
                        "td_texts": td_texts,
                        "inner_html_snippet": outer[:300],
                    })
                result["sample_rows"] = sample_rows

                # Look for any search/filter inputs anywhere on page
                all_inputs = await page.query_selector_all("input")
                input_info = []
                for inp in all_inputs[:20]:
                    input_info.append({
                        "type": await inp.get_attribute("type"),
                        "name": await inp.get_attribute("name"),
                        "id": await inp.get_attribute("id"),
                        "placeholder": await inp.get_attribute("placeholder"),
                    })
                result["all_inputs"] = input_info

                # Full page HTML (up to 15000 chars to see the table)
                result["playwright_html_snippet"] = (await page.content())[:15000]

                await browser.close()

    except Exception as e:
        result["error"] = str(e)

    return result


# ---------- Schemas ----------

class SyncRequest(BaseModel):
    """Request body for SalesGazer sync."""
    domain: str
    max_pages: int = 50
    subscribe: bool = True


class SyncResponse(BaseModel):
    """Response for sync operation."""
    status: str
    message: str
    stats: Optional[dict] = None


class StoreResult(BaseModel):
    """Single store from SalesGazer lookup."""
    store_id: str
    domain: str
    is_subscribed: bool


class StoreListResponse(BaseModel):
    """Response for store lookup."""
    stores: list[StoreResult]


class SubscribeRequest(BaseModel):
    """Request body for subscribing to a store."""
    domain: str


class SubscribeResponse(BaseModel):
    """Response for subscribe operation."""
    status: str
    message: str
    store_ids: list[str]


# ---------- In-memory job tracking ----------

class SyncJob(BaseModel):
    brand_id: str
    domain: str
    status: str = "running"
    stats: Optional[dict] = None
    error: Optional[str] = None


_sync_jobs: dict[str, SyncJob] = {}


# ---------- Endpoints ----------

@router.get("/stores", response_model=StoreListResponse)
async def lookup_stores(
    domain: str = Query(..., min_length=2, description="Domain to search for"),
):
    """
    Look up stores on SalesGazer matching a domain.

    Logs in and scrapes the settings page for matching store rows.
    """
    async with SalesGazerClient() as client:
        await client.login()
        stores = await client.find_store_ids(domain)

    return StoreListResponse(
        stores=[StoreResult(**s) for s in stores]
    )


@router.post("/subscribe", response_model=SubscribeResponse)
async def subscribe_to_store(
    request: SubscribeRequest,
):
    """
    Find stores matching domain and subscribe to all of them.
    """
    async with SalesGazerClient() as client:
        await client.login()
        stores = await client.find_store_ids(request.domain)

        if not stores:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No stores found for domain '{request.domain}'",
            )

        subscribed_ids: list[str] = []
        for store in stores:
            if not store["is_subscribed"]:
                success = await client.subscribe_to_store(store["store_id"])
                if success:
                    subscribed_ids.append(store["store_id"])
            else:
                subscribed_ids.append(store["store_id"])

    return SubscribeResponse(
        status="success",
        message=f"Subscribed to {len(subscribed_ids)} store(s) for {request.domain}",
        store_ids=subscribed_ids,
    )


@router.post("/sync/{brand_id}", response_model=SyncResponse)
async def sync_brand(
    brand_id: UUID,
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Sync SalesGazer emails for a brand.

    Finds stores matching the domain, subscribes, fetches all emails,
    and saves them to the database. Runs in the background.
    """
    # Verify brand exists
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )

    # Check for already-running sync
    job_key = str(brand_id)
    if job_key in _sync_jobs and _sync_jobs[job_key].status == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A SalesGazer sync is already running for {brand.name}",
        )

    # Track job
    _sync_jobs[job_key] = SyncJob(
        brand_id=str(brand_id),
        domain=request.domain,
    )

    # Run in background
    background_tasks.add_task(
        _run_sync,
        brand_id=brand_id,
        domain=request.domain,
        max_pages=request.max_pages,
        subscribe=request.subscribe,
    )

    return SyncResponse(
        status="started",
        message=f"SalesGazer sync started for {brand.name} (domain: {request.domain})",
    )


@router.get("/sync/{brand_id}/status")
async def get_sync_status(brand_id: UUID):
    """Get status of a running or completed SalesGazer sync."""
    job_key = str(brand_id)
    if job_key not in _sync_jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No sync job found for this brand",
        )
    return _sync_jobs[job_key]


async def _run_sync(
    brand_id: UUID,
    domain: str,
    max_pages: int,
    subscribe: bool,
) -> None:
    """Background task for SalesGazer sync."""
    from src.db.session import get_session_factory

    job_key = str(brand_id)
    session_factory = get_session_factory()

    try:
        async with session_factory() as db:
            stats = await sync_brand_from_salesgazer(
                brand_id=brand_id,
                domain=domain,
                db=db,
                max_pages=max_pages,
                subscribe=subscribe,
            )
            _sync_jobs[job_key].status = "completed"
            _sync_jobs[job_key].stats = stats
            logger.info(f"SalesGazer sync completed for brand {brand_id}: {stats}")

    except Exception as e:
        logger.error(f"SalesGazer sync failed for brand {brand_id}: {e}")
        _sync_jobs[job_key].status = "failed"
        _sync_jobs[job_key].error = str(e)
