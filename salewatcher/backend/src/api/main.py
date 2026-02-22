import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from sqlalchemy import text

from src.config import settings
from src.db.session import init_db, close_db, get_async_engine
from src.api.routes import api_router


async def run_schema_migrations() -> None:
    """Apply safe idempotent schema migrations at startup.

    Every step runs in its own transaction so one failure never blocks the rest.
    """
    import logging as _log
    _logger = _log.getLogger(__name__)
    engine = get_async_engine()

    async def _run(sql: str, label: str = "") -> None:
        try:
            async with engine.begin() as c:
                await c.execute(text(sql))
        except Exception as exc:
            msg = str(exc).lower()
            if "already exists" not in msg and "duplicate" not in msg:
                _logger.warning(f"Migration skipped ({label}): {exc}")

    # Make legacy email_id nullable (old schema had it NOT NULL; new model uses raw_email_id)
    await _run(
        "ALTER TABLE extracted_sales ALTER COLUMN email_id DROP NOT NULL",
        "drop NOT NULL on email_id"
    )
    # Some columns may have been added NOT NULL in earlier partial runs — make them nullable
    for col in ["discount_type", "discount_value", "discount_summary",
                "categories", "sale_start", "sale_end", "confidence",
                "model_used", "review_notes", "reviewed_at", "sale_window_id"]:
        await _run(
            f"ALTER TABLE extracted_sales ALTER COLUMN {col} DROP NOT NULL",
            f"nullable {col}"
        )

    # Column additions — each in its own transaction
    for name, ddl in [
        ("raw_email_id",    "ADD COLUMN IF NOT EXISTS raw_email_id UUID REFERENCES raw_emails(id)"),
        ("is_sale",         "ADD COLUMN IF NOT EXISTS is_sale BOOLEAN DEFAULT TRUE"),
        ("status",          "ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT \'pending\'"),
        ("extracted_at",    "ADD COLUMN IF NOT EXISTS extracted_at TIMESTAMP DEFAULT NOW()"),
        ("discount_type",   "ADD COLUMN IF NOT EXISTS discount_type VARCHAR(50)"),
        ("discount_value",  "ADD COLUMN IF NOT EXISTS discount_value FLOAT"),
        ("discount_summary","ADD COLUMN IF NOT EXISTS discount_summary VARCHAR(512)"),
        ("categories",      "ADD COLUMN IF NOT EXISTS categories TEXT[] DEFAULT \'{}\'"),
        ("sale_start",      "ADD COLUMN IF NOT EXISTS sale_start TIMESTAMP"),
        ("sale_end",        "ADD COLUMN IF NOT EXISTS sale_end TIMESTAMP"),
        ("confidence",      "ADD COLUMN IF NOT EXISTS confidence FLOAT"),
        ("model_used",      "ADD COLUMN IF NOT EXISTS model_used VARCHAR(100)"),
        ("review_notes",    "ADD COLUMN IF NOT EXISTS review_notes TEXT"),
        ("reviewed_at",     "ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP"),
        ("sale_window_id",  "ADD COLUMN IF NOT EXISTS sale_window_id UUID"),
    ]:
        await _run(f"ALTER TABLE extracted_sales {ddl}", f"extracted_sales.{name}")

    # Data backfills
    await _run("""
        UPDATE extracted_sales SET raw_email_id = email_id
        WHERE raw_email_id IS NULL AND email_id IS NOT NULL
    """, "backfill raw_email_id")
    await _run("""
        UPDATE extracted_sales SET extracted_at = COALESCE(created_at, NOW())
        WHERE extracted_at IS NULL
    """, "backfill extracted_at")
    await _run("""
        UPDATE extracted_sales SET status = COALESCE(review_status, 'pending')
        WHERE status IS NULL
    """, "backfill status")

    # sale_windows table — add any missing columns
    for name, ddl in [
        ("year",             "ADD COLUMN IF NOT EXISTS year INTEGER"),
        ("start_date",       "ADD COLUMN IF NOT EXISTS start_date TIMESTAMP"),
        ("end_date",         "ADD COLUMN IF NOT EXISTS end_date TIMESTAMP"),
        ("discount_type",    "ADD COLUMN IF NOT EXISTS discount_type VARCHAR(50) DEFAULT 'OTHER'"),
        ("discount_value",   "ADD COLUMN IF NOT EXISTS discount_value FLOAT DEFAULT 0"),
        ("discount_summary", "ADD COLUMN IF NOT EXISTS discount_summary VARCHAR(512)"),
        ("categories",       "ADD COLUMN IF NOT EXISTS categories TEXT[] DEFAULT '{}'"),
        ("holiday_anchor",   "ADD COLUMN IF NOT EXISTS holiday_anchor VARCHAR(100)"),
        ("days_from_holiday","ADD COLUMN IF NOT EXISTS days_from_holiday INTEGER"),
        ("created_at",       "ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()"),
    ]:
        await _run(f"ALTER TABLE sale_windows {ddl}", f"sale_windows.{name}")

    # Dynamically drop NOT NULL on every non-PK column in sale_windows and predictions
    # so we don't have to know the exact legacy schema ahead of time.
    for table in ["sale_windows", "predictions"]:
        try:
            async with engine.begin() as c:
                result = await c.execute(text(f"""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = '{table}'
                      AND is_nullable = 'NO'
                      AND column_name NOT IN ('id', 'brand_id')
                """))
                cols = [r[0] for r in result.fetchall()]
            for col in cols:
                await _run(
                    f"ALTER TABLE {table} ALTER COLUMN {col} DROP NOT NULL",
                    f"{table} nullable {col}"
                )
        except Exception as exc:
            _logger.warning(f"Dynamic nullable for {table} skipped: {exc}")

    # predictions table — add all columns that may be missing from older create_all runs
    for name, ddl in [
        ("source_window_id",  "ADD COLUMN IF NOT EXISTS source_window_id UUID"),
        ("target_year",       "ADD COLUMN IF NOT EXISTS target_year INTEGER"),
        ("predicted_start",   "ADD COLUMN IF NOT EXISTS predicted_start TIMESTAMP"),
        ("predicted_end",     "ADD COLUMN IF NOT EXISTS predicted_end TIMESTAMP"),
        ("discount_type",     "ADD COLUMN IF NOT EXISTS discount_type VARCHAR(50)"),
        ("expected_discount", "ADD COLUMN IF NOT EXISTS expected_discount FLOAT"),
        ("discount_summary",  "ADD COLUMN IF NOT EXISTS discount_summary VARCHAR(512)"),
        ("categories",        "ADD COLUMN IF NOT EXISTS categories TEXT[] DEFAULT '{}'"),
        ("confidence",        "ADD COLUMN IF NOT EXISTS confidence FLOAT"),
        ("synced_to_calendar","ADD COLUMN IF NOT EXISTS synced_to_calendar BOOLEAN DEFAULT FALSE"),
        ("calendar_event_id", "ADD COLUMN IF NOT EXISTS calendar_event_id VARCHAR(255)"),
        ("created_at",        "ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()"),
    ]:
        await _run(f"ALTER TABLE predictions {ddl}", f"predictions.{name}")

    # Create any new tables
    try:
        async with engine.begin() as c:
            from src.db.models import Base
            await c.run_sync(lambda sc: Base.metadata.create_all(sc, checkfirst=True))
    except Exception as exc:
        _logger.warning(f"create_all skipped: {exc}")


# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class NoCacheMiddleware(BaseHTTPMiddleware):
    """Middleware to disable caching for all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


async def _run_startup_migrations() -> None:
    """Run lightweight column-add migrations that are safe to re-run."""
    from src.db.session import get_async_engine

    engine = get_async_engine()
    async with engine.begin() as conn:
        # Add source column to raw_emails if it doesn't exist
        await conn.execute(text(
            "ALTER TABLE raw_emails ADD COLUMN IF NOT EXISTS "
            "source VARCHAR(50) NOT NULL DEFAULT 'milled'"
        ))
        # Add salesgazer_domain column to brands if it doesn't exist
        await conn.execute(text(
            "ALTER TABLE brands ADD COLUMN IF NOT EXISTS "
            "salesgazer_domain VARCHAR(255)"
        ))
    logger.info("Startup migrations applied")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    logger.info("Starting SaleWatcher API...")
    try:
        await run_schema_migrations()
        logger.info("Schema migrations applied successfully")
    except Exception as e:
        logger.warning(f"Schema migration warning (non-fatal): {e}")
    if settings.debug:
        await init_db()
        logger.info("Database tables created (debug mode)")
    await _run_startup_migrations()
    yield
    # Shutdown
    logger.info("Shutting down SaleWatcher API...")
    await close_db()


app = FastAPI(
    title=settings.app_name,
    description="Sales prediction system for Amazon Online Arbitrage",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware - allow all localhost ports for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.dashboard_url,
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$|^https://.*\.up\.railway\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add no-cache middleware
app.add_middleware(NoCacheMiddleware)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# Include API routes
app.include_router(api_router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": settings.app_name,
        "status": "running",
        "docs": "/docs",
    }
