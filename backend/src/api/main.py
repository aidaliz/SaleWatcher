"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from src.config.settings import get_settings
from src.api.routes import brands, predictions, review, accuracy, system


class NoCacheMiddleware(BaseHTTPMiddleware):
    """Middleware to add no-cache headers to all responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    # Startup
    settings = get_settings()
    app.state.settings = settings
    yield
    # Shutdown
    pass


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="Sales prediction system for Amazon Online Arbitrage",
        version="0.1.0",
        lifespan=lifespan,
    )

    # No-cache middleware (must be added before CORS)
    app.add_middleware(NoCacheMiddleware)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(brands.router, prefix="/api/brands", tags=["brands"])
    app.include_router(predictions.router, prefix="/api/predictions", tags=["predictions"])
    app.include_router(review.router, prefix="/api/review", tags=["review"])
    app.include_router(accuracy.router, prefix="/api/accuracy", tags=["accuracy"])
    app.include_router(system.router, prefix="/api", tags=["system"])

    return app


app = create_app()
