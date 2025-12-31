from fastapi import APIRouter

from .brands import router as brands_router
from .health import router as health_router
from .predictions import router as predictions_router
from .review import router as review_router
from .accuracy import router as accuracy_router
from .email_sync import router as email_sync_router
from .scrape import router as scrape_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(brands_router, prefix="/brands", tags=["brands"])
api_router.include_router(predictions_router, prefix="/predictions", tags=["predictions"])
api_router.include_router(review_router, prefix="/review", tags=["review"])
api_router.include_router(accuracy_router, prefix="/accuracy", tags=["accuracy"])
api_router.include_router(email_sync_router, prefix="/email", tags=["email"])
api_router.include_router(scrape_router, prefix="/scrape", tags=["scrape"])
