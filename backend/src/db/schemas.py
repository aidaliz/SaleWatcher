"""Pydantic schemas for request/response validation."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# Brand schemas
class BrandBase(BaseModel):
    """Base brand fields."""

    name: str = Field(..., min_length=1, max_length=255)
    milled_slug: str = Field(..., min_length=1, max_length=255)
    excluded_categories: list[str] = Field(default_factory=list)


class BrandCreate(BrandBase):
    """Schema for creating a brand."""

    pass


class BrandUpdate(BaseModel):
    """Schema for updating a brand."""

    name: str | None = None
    milled_slug: str | None = None
    is_active: bool | None = None
    excluded_categories: list[str] | None = None


class BrandResponse(BrandBase):
    """Schema for brand response."""

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BrandListResponse(BaseModel):
    """Schema for list of brands response."""

    brands: list[BrandResponse]
    total: int


# Extracted sale schemas
class ExtractedSaleBase(BaseModel):
    """Base extracted sale fields."""

    discount_type: Literal["percent_off", "bogo", "fixed_price", "free_shipping", "other"]
    discount_value: float | None = None
    discount_max: float | None = None
    is_sitewide: bool = False
    categories: list[str] = Field(default_factory=list)
    excluded_categories: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    sale_start: date | None = None
    sale_end: date | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    raw_discount_text: str | None = None


class ExtractedSaleResponse(ExtractedSaleBase):
    """Schema for extracted sale response."""

    id: UUID
    email_id: UUID
    model_used: str
    review_status: Literal["pending", "approved", "rejected"]
    reviewed_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


# Prediction schemas
class PredictionBase(BaseModel):
    """Base prediction fields."""

    predicted_start: date
    predicted_end: date
    discount_summary: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class PredictionResponse(PredictionBase):
    """Schema for prediction response."""

    id: UUID
    brand_id: UUID
    source_window_id: UUID
    milled_reference_url: str | None
    calendar_event_id: str | None
    notified_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class PredictionListResponse(BaseModel):
    """Schema for list of predictions response."""

    predictions: list[PredictionResponse]
    total: int


# Outcome schemas
class PredictionOutcomeResponse(BaseModel):
    """Schema for prediction outcome response."""

    id: UUID
    prediction_id: UUID
    auto_result: Literal["hit", "miss", "pending"] | None
    auto_verified_at: datetime | None
    manual_override: bool
    manual_result: Literal["hit", "miss"] | None
    override_reason: str | None
    overridden_at: datetime | None
    actual_start: date | None
    actual_end: date | None
    actual_discount: float | None
    timing_delta_days: int | None
    discount_delta_percent: float | None

    class Config:
        from_attributes = True


# Accuracy schemas
class BrandAccuracyResponse(BaseModel):
    """Schema for brand accuracy stats response."""

    brand_id: UUID
    total_predictions: int
    correct_predictions: int
    hit_rate: float
    avg_timing_delta_days: float | None
    timing_delta_std: float | None
    avg_discount_delta_percent: float | None
    reliability_score: int
    reliability_tier: Literal["excellent", "good", "fair", "poor"]
    last_calculated_at: datetime

    class Config:
        from_attributes = True


# Suggestion schemas
class AdjustmentSuggestionResponse(BaseModel):
    """Schema for adjustment suggestion response."""

    id: UUID
    brand_id: UUID
    suggestion_type: Literal["timing_shift", "pattern_change", "confidence_adjust"]
    description: str
    recommended_action: str
    supporting_data: dict
    status: Literal["pending", "approved", "dismissed"]
    resolved_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True
