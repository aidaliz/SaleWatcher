import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class DiscountType(str, Enum):
    """Type of discount offered in a sale."""
    PERCENTAGE = "percentage"
    FIXED_AMOUNT = "fixed_amount"
    BOGO = "bogo"
    FREE_SHIPPING = "free_shipping"
    OTHER = "other"


class ExtractionStatus(str, Enum):
    """Status of LLM extraction."""
    PENDING = "pending"
    PROCESSED = "processed"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class PredictionResult(str, Enum):
    """Result of a prediction verification."""
    PENDING = "pending"
    HIT = "hit"
    MISS = "miss"
    PARTIAL = "partial"


class SuggestionType(str, Enum):
    """Type of adjustment suggestion."""
    TIMING_SHIFT = "timing_shift"
    DISCOUNT_CHANGE = "discount_change"
    PATTERN_CHANGE = "pattern_change"
    BRAND_UNRELIABLE = "brand_unreliable"


class SuggestionStatus(str, Enum):
    """Status of an adjustment suggestion."""
    PENDING = "pending"
    APPROVED = "approved"
    DISMISSED = "dismissed"


class Brand(Base):
    """Retail brand being tracked for sales."""
    __tablename__ = "brands"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    milled_slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    excluded_categories: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    raw_emails: Mapped[list["RawEmail"]] = relationship("RawEmail", back_populates="brand", cascade="all, delete-orphan")
    sale_windows: Mapped[list["SaleWindow"]] = relationship("SaleWindow", back_populates="brand", cascade="all, delete-orphan")
    predictions: Mapped[list["Prediction"]] = relationship("Prediction", back_populates="brand", cascade="all, delete-orphan")
    accuracy_stats: Mapped[Optional["BrandAccuracyStats"]] = relationship("BrandAccuracyStats", back_populates="brand", uselist=False, cascade="all, delete-orphan")


class RawEmail(Base):
    """Raw email scraped from Milled.com."""
    __tablename__ = "raw_emails"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False)
    milled_url: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    html_content: Mapped[str] = mapped_column(Text, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    brand: Mapped["Brand"] = relationship("Brand", back_populates="raw_emails")
    extracted_sale: Mapped[Optional["ExtractedSale"]] = relationship("ExtractedSale", back_populates="raw_email", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_raw_emails_brand_date", "brand_id", "sent_at"),
    )


class ExtractedSale(Base):
    """Sale details extracted from an email by LLM."""
    __tablename__ = "extracted_sales"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_email_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("raw_emails.id"), unique=True, nullable=False)

    # Extraction results
    is_sale: Mapped[bool] = mapped_column(Boolean, nullable=False)
    discount_type: Mapped[Optional[DiscountType]] = mapped_column(SQLEnum(DiscountType), nullable=True)
    discount_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    discount_summary: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    categories: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    sale_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sale_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # LLM metadata
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[ExtractionStatus] = mapped_column(SQLEnum(ExtractionStatus), default=ExtractionStatus.PENDING, nullable=False)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    extracted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    raw_email: Mapped["RawEmail"] = relationship("RawEmail", back_populates="extracted_sale")
    sale_window_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("sale_windows.id"), nullable=True)
    sale_window: Mapped[Optional["SaleWindow"]] = relationship("SaleWindow", back_populates="extracted_sales")

    __table_args__ = (
        Index("idx_extracted_sales_review", "status"),
    )


class SaleWindow(Base):
    """Deduplicated sale event grouping related emails."""
    __tablename__ = "sale_windows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False)

    # Sale details (aggregated from extracted sales)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    discount_type: Mapped[DiscountType] = mapped_column(SQLEnum(DiscountType), nullable=False)
    discount_value: Mapped[float] = mapped_column(Float, nullable=False)
    discount_summary: Mapped[str] = mapped_column(String(512), nullable=False)
    categories: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)

    # Holiday anchoring
    holiday_anchor: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    days_from_holiday: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    brand: Mapped["Brand"] = relationship("Brand", back_populates="sale_windows")
    extracted_sales: Mapped[list["ExtractedSale"]] = relationship("ExtractedSale", back_populates="sale_window")
    prediction: Mapped[Optional["Prediction"]] = relationship("Prediction", back_populates="source_window", uselist=False)

    __table_args__ = (
        Index("idx_sale_windows_brand_year", "brand_id", "year"),
    )


class Prediction(Base):
    """Predicted future sale based on historical data."""
    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False)
    source_window_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sale_windows.id"), nullable=False)

    # Prediction details
    target_year: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    predicted_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    discount_type: Mapped[DiscountType] = mapped_column(SQLEnum(DiscountType), nullable=False)
    expected_discount: Mapped[float] = mapped_column(Float, nullable=False)
    discount_summary: Mapped[str] = mapped_column(String(512), nullable=False)
    categories: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)

    # Confidence and status
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    synced_to_calendar: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    calendar_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    brand: Mapped["Brand"] = relationship("Brand", back_populates="predictions")
    source_window: Mapped["SaleWindow"] = relationship("SaleWindow", back_populates="prediction")
    outcome: Mapped[Optional["PredictionOutcome"]] = relationship("PredictionOutcome", back_populates="prediction", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_predictions_dates", "predicted_start", "predicted_end"),
        Index("idx_predictions_brand", "brand_id"),
    )


class PredictionOutcome(Base):
    """Verification result for a prediction."""
    __tablename__ = "prediction_outcomes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prediction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("predictions.id"), unique=True, nullable=False)

    # Verification result
    result: Mapped[PredictionResult] = mapped_column(SQLEnum(PredictionResult), default=PredictionResult.PENDING, nullable=False)
    actual_discount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timing_offset_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Override info
    is_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    prediction: Mapped["Prediction"] = relationship("Prediction", back_populates="outcome")

    __table_args__ = (
        Index("idx_outcomes_result", "result", "is_override"),
    )


class BrandAccuracyStats(Base):
    """Accuracy statistics for a brand."""
    __tablename__ = "brand_accuracy_stats"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), unique=True, nullable=False)

    # Stats
    total_predictions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    misses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    partials: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pending: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Calculated metrics
    hit_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reliability_tier: Mapped[str] = mapped_column(String(50), default="unknown", nullable=False)

    last_calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    brand: Mapped["Brand"] = relationship("Brand", back_populates="accuracy_stats")


class AdjustmentSuggestion(Base):
    """System-generated suggestion for prediction adjustments."""
    __tablename__ = "adjustment_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False)

    # Suggestion details
    suggestion_type: Mapped[SuggestionType] = mapped_column(SQLEnum(SuggestionType), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)

    # Evidence
    evidence_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string

    # Status
    status: Mapped[SuggestionStatus] = mapped_column(SQLEnum(SuggestionStatus), default=SuggestionStatus.PENDING, nullable=False)
    dismiss_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    brand: Mapped["Brand"] = relationship("Brand")
