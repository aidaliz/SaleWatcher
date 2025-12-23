"""Pytest configuration and shared fixtures."""

import pytest
from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4


@pytest.fixture
def sample_brand():
    """Create a sample brand mock."""
    brand = MagicMock()
    brand.id = uuid4()
    brand.name = "Nike"
    brand.milled_slug = "nike"
    brand.is_active = True
    brand.excluded_categories = []
    return brand


@pytest.fixture
def sample_sale_window(sample_brand):
    """Create a sample sale window mock."""
    window = MagicMock()
    window.id = uuid4()
    window.brand_id = sample_brand.id
    window.brand = sample_brand
    window.name = "Nike Black Friday Sale"
    window.discount_summary = "30% off sitewide"
    window.start_date = date(2023, 11, 24)
    window.end_date = date(2023, 11, 27)
    window.linked_email_ids = [uuid4()]
    window.holiday_anchor = "black_friday"
    window.categories = ["shoes", "apparel"]
    window.year = 2023
    return window


@pytest.fixture
def sample_extraction():
    """Create a sample extracted sale mock."""
    extraction = MagicMock()
    extraction.id = uuid4()
    extraction.email_id = uuid4()
    extraction.discount_type = "percent_off"
    extraction.discount_value = 30.0
    extraction.discount_max = None
    extraction.is_sitewide = True
    extraction.categories = ["shoes"]
    extraction.sale_start = date(2024, 1, 15)
    extraction.sale_end = date(2024, 1, 20)
    extraction.confidence = 0.85
    extraction.model_used = "claude-3-5-haiku-20241022"
    extraction.review_status = "approved"
    return extraction


@pytest.fixture
def sample_prediction(sample_brand, sample_sale_window):
    """Create a sample prediction mock."""
    prediction = MagicMock()
    prediction.id = uuid4()
    prediction.brand_id = sample_brand.id
    prediction.brand = sample_brand
    prediction.source_window_id = sample_sale_window.id
    prediction.source_window = sample_sale_window
    prediction.predicted_start = date(2024, 11, 29)
    prediction.predicted_end = date(2024, 12, 2)
    prediction.discount_summary = "30% off sitewide"
    prediction.milled_reference_url = "https://milled.com/nike/example"
    prediction.confidence = 0.75
    prediction.calendar_event_id = None
    prediction.notified_at = None
    return prediction
