"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-12-23

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Brands table
    op.create_table(
        "brands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("milled_slug", sa.String(255), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("excluded_categories", postgresql.ARRAY(sa.Text()), default=[]),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Raw emails table
    op.create_table(
        "raw_emails",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("milled_url", sa.String(1024), nullable=False, unique=True),
        sa.Column("subject", sa.String(512)),
        sa.Column("sent_at", sa.Date(), nullable=False),
        sa.Column("html_content", sa.Text()),
        sa.Column("scraped_at", sa.DateTime(), default=sa.func.now()),
    )
    op.create_index("idx_raw_emails_brand_date", "raw_emails", ["brand_id", "sent_at"])

    # Extracted sales table
    op.create_table(
        "extracted_sales",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("raw_emails.id"), nullable=False),
        sa.Column("discount_type", sa.String(50), nullable=False),
        sa.Column("discount_value", sa.Float()),
        sa.Column("discount_max", sa.Float()),
        sa.Column("is_sitewide", sa.Boolean(), default=False),
        sa.Column("categories", postgresql.ARRAY(sa.Text()), default=[]),
        sa.Column("excluded_categories", postgresql.ARRAY(sa.Text()), default=[]),
        sa.Column("conditions", postgresql.ARRAY(sa.Text()), default=[]),
        sa.Column("sale_start", sa.Date()),
        sa.Column("sale_end", sa.Date()),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("raw_discount_text", sa.Text()),
        sa.Column("model_used", sa.String(50)),
        sa.Column("review_status", sa.String(20), default="pending"),
        sa.Column("reviewed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
    )
    op.create_index("idx_extracted_sales_review", "extracted_sales", ["review_status", "confidence"])

    # Sale windows table
    op.create_table(
        "sale_windows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("discount_summary", sa.String(255)),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("linked_email_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), default=[]),
        sa.Column("holiday_anchor", sa.String(50)),
        sa.Column("categories", postgresql.ARRAY(sa.Text()), default=[]),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
    )
    op.create_index("idx_sale_windows_brand_year", "sale_windows", ["brand_id", "year"])

    # Predictions table
    op.create_table(
        "predictions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("source_window_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sale_windows.id"), nullable=False),
        sa.Column("predicted_start", sa.Date(), nullable=False),
        sa.Column("predicted_end", sa.Date(), nullable=False),
        sa.Column("discount_summary", sa.String(255)),
        sa.Column("milled_reference_url", sa.String(1024)),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("calendar_event_id", sa.String(255)),
        sa.Column("notified_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
    )
    op.create_index("idx_predictions_dates", "predictions", ["predicted_start", "predicted_end"])
    op.create_index("idx_predictions_brand", "predictions", ["brand_id"])

    # Prediction outcomes table
    op.create_table(
        "prediction_outcomes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("prediction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("predictions.id"), unique=True, nullable=False),
        sa.Column("auto_result", sa.String(20)),
        sa.Column("auto_verified_at", sa.DateTime()),
        sa.Column("matched_email_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), default=[]),
        sa.Column("manual_override", sa.Boolean(), default=False),
        sa.Column("manual_result", sa.String(20)),
        sa.Column("override_reason", sa.Text()),
        sa.Column("overridden_at", sa.DateTime()),
        sa.Column("actual_start", sa.Date()),
        sa.Column("actual_end", sa.Date()),
        sa.Column("actual_discount", sa.Float()),
        sa.Column("timing_delta_days", sa.Integer()),
        sa.Column("discount_delta_percent", sa.Float()),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
    )
    op.create_index("idx_outcomes_result", "prediction_outcomes", ["auto_result", "manual_override"])

    # Brand accuracy stats table
    op.create_table(
        "brand_accuracy_stats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), unique=True, nullable=False),
        sa.Column("total_predictions", sa.Integer(), default=0),
        sa.Column("correct_predictions", sa.Integer(), default=0),
        sa.Column("hit_rate", sa.Float(), default=0),
        sa.Column("avg_timing_delta_days", sa.Float()),
        sa.Column("timing_delta_std", sa.Float()),
        sa.Column("avg_discount_delta_percent", sa.Float()),
        sa.Column("reliability_score", sa.Integer(), default=0),
        sa.Column("reliability_tier", sa.String(20)),
        sa.Column("last_calculated_at", sa.DateTime(), default=sa.func.now()),
    )

    # Adjustment suggestions table
    op.create_table(
        "adjustment_suggestions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("suggestion_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("supporting_data", postgresql.JSONB(), default={}),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("resolved_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("adjustment_suggestions")
    op.drop_table("brand_accuracy_stats")
    op.drop_index("idx_outcomes_result", table_name="prediction_outcomes")
    op.drop_table("prediction_outcomes")
    op.drop_index("idx_predictions_brand", table_name="predictions")
    op.drop_index("idx_predictions_dates", table_name="predictions")
    op.drop_table("predictions")
    op.drop_index("idx_sale_windows_brand_year", table_name="sale_windows")
    op.drop_table("sale_windows")
    op.drop_index("idx_extracted_sales_review", table_name="extracted_sales")
    op.drop_table("extracted_sales")
    op.drop_index("idx_raw_emails_brand_date", table_name="raw_emails")
    op.drop_table("raw_emails")
    op.drop_table("brands")
