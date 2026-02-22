import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import settings
from src.db.session import init_db, close_db
from src.api.routes import api_router

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
    if settings.debug:
        # Only create tables in debug mode; use Alembic in production
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
