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
    """Apply safe, idempotent schema migrations at startup.

    Handles the gap between the old backend schema (email_id, review_status)
    and the new backend model (raw_email_id, status).
    """
    engine = get_async_engine()
    async with engine.begin() as conn:
        # 1. Add raw_email_id to extracted_sales (was email_id in old schema)
        await conn.execute(text("""
            ALTER TABLE extracted_sales
            ADD COLUMN IF NOT EXISTS raw_email_id UUID REFERENCES raw_emails(id)
        """))
        # Copy email_id → raw_email_id for existing rows
        await conn.execute(text("""
            UPDATE extracted_sales
            SET raw_email_id = email_id
            WHERE raw_email_id IS NULL
              AND email_id IS NOT NULL
        """))

        # 2. Create extractionstatus enum type if it doesn't exist
        await conn.execute(text("""
            DO $$ BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'extractionstatus') THEN
                CREATE TYPE extractionstatus AS ENUM
                  ('pending', 'processed', 'needs_review', 'approved', 'rejected');
              END IF;
            END $$
        """))

        # 3. Add status column as proper enum (was review_status / VARCHAR in old schema)
        await conn.execute(text("""
            ALTER TABLE extracted_sales
            ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'pending'
        """))
        await conn.execute(text("""
            UPDATE extracted_sales
            SET status = COALESCE(review_status, 'pending')
            WHERE status IS NULL
        """))
        # Cast column to enum type
        await conn.execute(text("""
            ALTER TABLE extracted_sales
            ALTER COLUMN status TYPE extractionstatus
            USING status::extractionstatus
        """))

        # 3. Add is_sale column if missing
        await conn.execute(text("""
            ALTER TABLE extracted_sales
            ADD COLUMN IF NOT EXISTS is_sale BOOLEAN DEFAULT TRUE
        """))

        # 4. Add extracted_at if missing (was created_at)
        await conn.execute(text("""
            ALTER TABLE extracted_sales
            ADD COLUMN IF NOT EXISTS extracted_at TIMESTAMP DEFAULT NOW()
        """))
        await conn.execute(text("""
            UPDATE extracted_sales
            SET extracted_at = COALESCE(created_at, NOW())
            WHERE extracted_at IS NULL
        """))

        # 5. Add columns added by newer schema that may not exist in older DBs
        for col_sql in [
            "ADD COLUMN IF NOT EXISTS discount_type VARCHAR(50)",
            "ADD COLUMN IF NOT EXISTS discount_value FLOAT",
            "ADD COLUMN IF NOT EXISTS discount_summary VARCHAR(512)",
            "ADD COLUMN IF NOT EXISTS categories TEXT[] DEFAULT '{}'",
            "ADD COLUMN IF NOT EXISTS sale_start TIMESTAMP",
            "ADD COLUMN IF NOT EXISTS sale_end TIMESTAMP",
            "ADD COLUMN IF NOT EXISTS confidence FLOAT",
            "ADD COLUMN IF NOT EXISTS model_used VARCHAR(100)",
            "ADD COLUMN IF NOT EXISTS review_notes TEXT",
            "ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP",
            "ADD COLUMN IF NOT EXISTS sale_window_id UUID REFERENCES sale_windows(id)",
        ]:
            try:
                await conn.execute(text(f"ALTER TABLE extracted_sales {col_sql}"))
            except Exception:
                pass  # column already exists or FK target missing — safe to skip

        # 6. Ensure new tables exist (create_all for new models only)
        from src.db.models import Base
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(
            sync_conn, checkfirst=True
        ))

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
