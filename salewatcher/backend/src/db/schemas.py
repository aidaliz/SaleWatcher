from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from src.db.models import DiscountType, ExtractionStatus, PredictionResult, SuggestionType, SuggestionStatus


# ============== Brand Schemas ==============

class BrandBase(BaseModel):
    """Base schema for brand data."""
    name: str = Field(..., min_length=1, max_length=255)
    milled_slug: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9-]+$")
    excluded_categories: list[str] = Field(default_factory=list)


class BrandCreate(BrandBase):
    """Schema for creating a new brand."""
    pass


class BrandUpdate(BaseModel):
    """Schema for updating a brand."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    milled_slug: Optional[str] = Field(None, min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9-]+$")
    is_active: Optional[bool] = None
    excluded_categories: Optional[list[str]] = None


class BrandResponse(BrandBase):
    """Schema for brand response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BrandListResponse(BaseModel):
    """Schema for paginated brand list."""
    brands: list[BrandResponse]
    total: int
    skip: int
    limit: int


# ============== Extracted Sale Schemas ==============

class ExtractedSaleBase(BaseModel):
    """Base schema for extracted sale."""
    is_sale: bool
    discount_type: Optional[DiscountType] = None
    discount_value: Optional[float] = None
    discount_summary: Optional[str] = None
    categories: list[str] = Field(default_factory=list)
    sale_start: Optional[datetime] = None
    sale_end: Optional[datetime] = None
    confidence: float = Field(..., ge=0.0, le=1.0)


class ExtractedSaleResponse(ExtractedSaleBase):
    """Schema for extracted sale response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    raw_email_id: UUID
    model_used: str
    status: ExtractionStatus
    review_notes: Optional[str] = None
    extracted_at: datetime
    reviewed_at: Optional[datetime] = None


class ReviewAction(BaseModel):
    """Schema for review queue actions."""
    notes: Optional[str] = None


# ============== Prediction Schemas ==============

class PredictionBase(BaseModel):
    """Base schema for prediction."""
    target_year: int
    predicted_start: datetime
    predicted_end: datetime
    discount_type: DiscountType
    expected_discount: float
    discount_summary: str
    categories: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)


class PredictionResponse(PredictionBase):
    """Schema for prediction response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    brand_id: UUID
    source_window_id: UUID
    synced_to_calendar: bool
    calendar_event_id: Optional[str] = None
    created_at: datetime
    brand: Optional[BrandResponse] = None


class PredictionListResponse(BaseModel):
    """Schema for paginated prediction list."""
    predictions: list[PredictionResponse]
    total: int


class PredictionOverride(BaseModel):
    """Schema for overriding prediction outcome."""
    result: PredictionResult
    reason: Optional[str] = None


# ============== Accuracy Schemas ==============

class AccuracyStats(BaseModel):
    """Schema for overall accuracy stats."""
    total_predictions: int
    hits: int
    misses: int
    partials: int
    pending: int
    hit_rate: float
    verified_count: int


class BrandAccuracy(BaseModel):
    """Schema for per-brand accuracy."""
    model_config = ConfigDict(from_attributes=True)

    brand_id: UUID
    brand_name: str
    total_predictions: int
    hits: int
    misses: int
    partials: int
    hit_rate: float
    reliability_tier: str


class BrandAccuracyListResponse(BaseModel):
    """Schema for brand accuracy list."""
    brands: list[BrandAccuracy]


# ============== Suggestion Schemas ==============

class SuggestionResponse(BaseModel):
    """Schema for adjustment suggestion."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    brand_id: UUID
    suggestion_type: SuggestionType
    description: str
    recommended_action: str
    status: SuggestionStatus
    created_at: datetime


class SuggestionAction(BaseModel):
    """Schema for suggestion actions."""
    reason: Optional[str] = None


# ============== Review Queue Schemas ==============

class ReviewItem(BaseModel):
    """Schema for review queue item."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    raw_email_id: UUID
    brand_name: str
    email_subject: str
    sent_at: datetime
    is_sale: bool
    discount_summary: Optional[str] = None
    confidence: float
    model_used: str
    extracted_at: datetime


class ReviewListResponse(BaseModel):
    """Schema for review queue list."""
    items: list[ReviewItem]
    total: int
