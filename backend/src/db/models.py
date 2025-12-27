"""SQLAlchemy ORM models."""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Brand(Base):
    """Brand to track for promotional emails."""

    __tablename__ = "brands"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    milled_slug = Column(String(255), nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    excluded_categories = Column(ARRAY(Text), default=[])
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    raw_emails = relationship("RawEmail", back_populates="brand")
    sale_windows = relationship("SaleWindow", back_populates="brand")
    predictions = relationship("Prediction", back_populates="brand")


class RawEmail(Base):
    """Raw scraped email from Milled.com."""

    __tablename__ = "raw_emails"
    __table_args__ = (
        Index("idx_raw_emails_brand_date", "brand_id", "sent_at"),
    )

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    brand_id = Column(PG_UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False)
    milled_url = Column(String(1024), nullable=False, unique=True)
    subject = Column(String(512))
    sent_at = Column(Date, nullable=False)
    html_content = Column(Text)
    scraped_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    brand = relationship("Brand", back_populates="raw_emails")
    extracted_sale = relationship("ExtractedSale", back_populates="email", uselist=False)


class ExtractedSale(Base):
    """LLM-extracted sale details from an email."""

    __tablename__ = "extracted_sales"
    __table_args__ = (
        Index("idx_extracted_sales_review", "review_status", "confidence"),
    )

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email_id = Column(PG_UUID(as_uuid=True), ForeignKey("raw_emails.id"), nullable=False)
    discount_type = Column(String(50), nullable=False)
    discount_value = Column(Float)
    discount_max = Column(Float)
    is_sitewide = Column(Boolean, default=False)
    categories = Column(ARRAY(Text), default=[])
    excluded_categories = Column(ARRAY(Text), default=[])
    conditions = Column(ARRAY(Text), default=[])
    sale_start = Column(Date)
    sale_end = Column(Date)
    confidence = Column(Float, nullable=False)
    raw_discount_text = Column(Text)
    model_used = Column(String(50))
    review_status = Column(String(20), default="pending")
    reviewed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    email = relationship("RawEmail", back_populates="extracted_sale")


class SaleWindow(Base):
    """Deduplicated sale event grouping multiple emails."""

    __tablename__ = "sale_windows"
    __table_args__ = (
        Index("idx_sale_windows_brand_year", "brand_id", "year"),
    )

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    brand_id = Column(PG_UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False)
    name = Column(String(255), nullable=False)
    discount_summary = Column(String(255))
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    linked_email_ids = Column(ARRAY(PG_UUID(as_uuid=True)), default=[])
    holiday_anchor = Column(String(50))
    categories = Column(ARRAY(Text), default=[])
    year = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    brand = relationship("Brand", back_populates="sale_windows")
    predictions = relationship("Prediction", back_populates="source_window")


class Prediction(Base):
    """Predicted future sale based on historical patterns."""

    __tablename__ = "predictions"
    __table_args__ = (
        Index("idx_predictions_dates", "predicted_start", "predicted_end"),
        Index("idx_predictions_brand", "brand_id"),
    )

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    brand_id = Column(PG_UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False)
    source_window_id = Column(PG_UUID(as_uuid=True), ForeignKey("sale_windows.id"), nullable=False)
    predicted_start = Column(Date, nullable=False)
    predicted_end = Column(Date, nullable=False)
    discount_summary = Column(String(255))
    milled_reference_url = Column(String(1024))
    confidence = Column(Float, nullable=False)
    calendar_event_id = Column(String(255))
    notified_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    brand = relationship("Brand", back_populates="predictions")
    source_window = relationship("SaleWindow", back_populates="predictions")
    outcome = relationship("PredictionOutcome", back_populates="prediction", uselist=False)


class PredictionOutcome(Base):
    """Verification result for a prediction."""

    __tablename__ = "prediction_outcomes"
    __table_args__ = (
        Index("idx_outcomes_result", "auto_result", "manual_override"),
    )

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    prediction_id = Column(PG_UUID(as_uuid=True), ForeignKey("predictions.id"), unique=True, nullable=False)
    auto_result = Column(String(20))
    auto_verified_at = Column(DateTime)
    matched_email_ids = Column(ARRAY(PG_UUID(as_uuid=True)), default=[])
    manual_override = Column(Boolean, default=False)
    manual_result = Column(String(20))
    override_reason = Column(Text)
    overridden_at = Column(DateTime)
    actual_start = Column(Date)
    actual_end = Column(Date)
    actual_discount = Column(Float)
    timing_delta_days = Column(Integer)
    discount_delta_percent = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    prediction = relationship("Prediction", back_populates="outcome")


class BrandAccuracyStats(Base):
    """Materialized accuracy statistics per brand."""

    __tablename__ = "brand_accuracy_stats"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    brand_id = Column(PG_UUID(as_uuid=True), ForeignKey("brands.id"), unique=True, nullable=False)
    total_predictions = Column(Integer, default=0)
    correct_predictions = Column(Integer, default=0)
    hit_rate = Column(Float, default=0)
    avg_timing_delta_days = Column(Float)
    timing_delta_std = Column(Float)
    avg_discount_delta_percent = Column(Float)
    reliability_score = Column(Integer, default=0)
    reliability_tier = Column(String(20))
    last_calculated_at = Column(DateTime, default=datetime.utcnow)


class AdjustmentSuggestion(Base):
    """System-generated suggestion for prediction adjustment."""

    __tablename__ = "adjustment_suggestions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    brand_id = Column(PG_UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False)
    suggestion_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    recommended_action = Column(Text, nullable=False)
    supporting_data = Column(JSONB, default={})
    status = Column(String(20), default="pending")
    resolved_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
