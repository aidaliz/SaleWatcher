import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
