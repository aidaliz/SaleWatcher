"""Unit tests for the sale deduplication module."""

import pytest
from datetime import date
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4

from src.deduplicator.service import (
    dates_overlap,
    discounts_match,
    get_sale_dates,
    generate_sale_name,
    generate_discount_summary,
    SaleGroup,
    SaleDeduplicator,
    DATE_PROXIMITY_DAYS,
    DISCOUNT_VALUE_TOLERANCE,
)


class TestDatesOverlap:
    """Tests for dates_overlap function."""

    def test_overlapping_ranges(self):
        """Test truly overlapping date ranges."""
        assert dates_overlap(
            date(2024, 1, 1), date(2024, 1, 10),
            date(2024, 1, 5), date(2024, 1, 15),
        ) is True

    def test_adjacent_ranges(self):
        """Test adjacent date ranges (within proximity)."""
        assert dates_overlap(
            date(2024, 1, 1), date(2024, 1, 5),
            date(2024, 1, 6), date(2024, 1, 10),
        ) is True

    def test_ranges_within_proximity(self):
        """Test ranges within proximity threshold."""
        # 3 day gap, default proximity is 3 days
        assert dates_overlap(
            date(2024, 1, 1), date(2024, 1, 5),
            date(2024, 1, 8), date(2024, 1, 12),
        ) is True

    def test_non_overlapping_ranges(self):
        """Test non-overlapping date ranges."""
        assert dates_overlap(
            date(2024, 1, 1), date(2024, 1, 5),
            date(2024, 1, 15), date(2024, 1, 20),
        ) is False

    def test_same_dates(self):
        """Test identical date ranges."""
        assert dates_overlap(
            date(2024, 1, 1), date(2024, 1, 5),
            date(2024, 1, 1), date(2024, 1, 5),
        ) is True

    def test_one_day_ranges(self):
        """Test single-day ranges."""
        assert dates_overlap(
            date(2024, 1, 1), date(2024, 1, 1),
            date(2024, 1, 2), date(2024, 1, 2),
        ) is True

    def test_custom_proximity(self):
        """Test with custom proximity value."""
        # 10 day gap, should not overlap with default proximity
        assert dates_overlap(
            date(2024, 1, 1), date(2024, 1, 5),
            date(2024, 1, 15), date(2024, 1, 20),
            proximity_days=3,
        ) is False

        # But should overlap with larger proximity
        assert dates_overlap(
            date(2024, 1, 1), date(2024, 1, 5),
            date(2024, 1, 15), date(2024, 1, 20),
            proximity_days=10,
        ) is True


class TestDiscountsMatch:
    """Tests for discounts_match function."""

    def test_same_type_same_value(self):
        """Test matching discounts with same type and value."""
        assert discounts_match("percent_off", 20.0, "percent_off", 20.0) is True

    def test_same_type_within_tolerance(self):
        """Test discounts within tolerance."""
        # Default tolerance is 5%
        assert discounts_match("percent_off", 20.0, "percent_off", 24.0) is True
        assert discounts_match("percent_off", 20.0, "percent_off", 25.0) is True

    def test_same_type_outside_tolerance(self):
        """Test discounts outside tolerance."""
        assert discounts_match("percent_off", 20.0, "percent_off", 26.0) is False
        assert discounts_match("percent_off", 20.0, "percent_off", 30.0) is False

    def test_different_types(self):
        """Test different discount types never match."""
        assert discounts_match("percent_off", 20.0, "bogo", 20.0) is False
        assert discounts_match("percent_off", 20.0, "free_shipping", None) is False

    def test_same_type_no_values(self):
        """Test same type with no values."""
        assert discounts_match("bogo", None, "bogo", None) is True
        assert discounts_match("free_shipping", None, "free_shipping", None) is True

    def test_one_value_missing(self):
        """Test when only one discount has a value."""
        assert discounts_match("percent_off", 20.0, "percent_off", None) is True
        assert discounts_match("percent_off", None, "percent_off", 20.0) is True

    def test_custom_tolerance(self):
        """Test with custom tolerance."""
        assert discounts_match("percent_off", 20.0, "percent_off", 22.0, tolerance=1.0) is False
        assert discounts_match("percent_off", 20.0, "percent_off", 22.0, tolerance=3.0) is True


class TestGenerateSaleName:
    """Tests for generate_sale_name function."""

    def test_percent_off_sale(self):
        """Test name generation for percent off sales."""
        name = generate_sale_name("Nike", "percent_off", 25.0, date(2024, 11, 15))
        assert name == "Nike November 25% Off"

    def test_bogo_sale(self):
        """Test name generation for BOGO sales."""
        name = generate_sale_name("Adidas", "bogo", None, date(2024, 6, 1))
        assert name == "Adidas June BOGO"

    def test_free_shipping_sale(self):
        """Test name generation for free shipping."""
        name = generate_sale_name("Puma", "free_shipping", None, date(2024, 3, 15))
        assert name == "Puma March Free Shipping"

    def test_fixed_price_sale(self):
        """Test name generation for fixed price sales."""
        name = generate_sale_name("Reebok", "fixed_price", 49.99, date(2024, 8, 1))
        assert name == "Reebok August $49 Sale"

    def test_unknown_discount_type(self):
        """Test name generation for unknown discount type."""
        name = generate_sale_name("Brand", "unknown", None, date(2024, 1, 1))
        assert name == "Brand January Sale"


class TestGenerateDiscountSummary:
    """Tests for generate_discount_summary function."""

    def test_percent_off(self):
        """Test summary for percent off."""
        assert generate_discount_summary("percent_off", 30.0, False) == "30% off"
        assert generate_discount_summary("percent_off", 30.0, True) == "30% off sitewide"

    def test_bogo(self):
        """Test summary for BOGO."""
        assert generate_discount_summary("bogo", None, False) == "Buy one get one"
        assert generate_discount_summary("bogo", None, True) == "Buy one get one sitewide"

    def test_free_shipping(self):
        """Test summary for free shipping."""
        assert generate_discount_summary("free_shipping", None, False) == "Free shipping"

    def test_fixed_price(self):
        """Test summary for fixed price."""
        assert generate_discount_summary("fixed_price", 29.99, False) == "Starting at $29"


class TestSaleGroup:
    """Tests for SaleGroup dataclass."""

    def test_creation(self):
        """Test SaleGroup creation."""
        group = SaleGroup(
            emails=[],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 5),
            discount_type="percent_off",
            discount_value=20.0,
            categories={"shoes", "apparel"},
        )
        assert group.start_date == date(2024, 1, 1)
        assert group.discount_type == "percent_off"
        assert "shoes" in group.categories


class TestSaleDeduplicator:
    """Tests for SaleDeduplicator class."""

    def test_group_extractions_single_email(self):
        """Test grouping with a single email."""
        deduplicator = SaleDeduplicator()

        # Create mock extraction
        mock_email = MagicMock()
        mock_email.sent_at = date(2024, 1, 15)

        mock_extraction = MagicMock()
        mock_extraction.email = mock_email
        mock_extraction.sale_start = date(2024, 1, 15)
        mock_extraction.sale_end = date(2024, 1, 20)
        mock_extraction.discount_type = "percent_off"
        mock_extraction.discount_value = 25.0
        mock_extraction.categories = ["shoes"]
        mock_extraction.confidence = 0.8

        groups = deduplicator.group_extractions([mock_extraction])

        assert len(groups) == 1
        assert groups[0].discount_type == "percent_off"
        assert groups[0].discount_value == 25.0

    def test_group_extractions_merges_similar(self):
        """Test that similar extractions are merged."""
        deduplicator = SaleDeduplicator()

        # Create two similar mock extractions
        def create_mock(start, end, value):
            mock_email = MagicMock()
            mock_email.sent_at = start
            mock = MagicMock()
            mock.email = mock_email
            mock.sale_start = start
            mock.sale_end = end
            mock.discount_type = "percent_off"
            mock.discount_value = value
            mock.categories = ["shoes"]
            mock.confidence = 0.8
            return mock

        extractions = [
            create_mock(date(2024, 1, 15), date(2024, 1, 20), 25.0),
            create_mock(date(2024, 1, 16), date(2024, 1, 21), 27.0),  # Similar
        ]

        groups = deduplicator.group_extractions(extractions)

        # Should be merged into one group
        assert len(groups) == 1
        assert len(groups[0].emails) == 2

    def test_group_extractions_separates_different(self):
        """Test that different extractions stay separate."""
        deduplicator = SaleDeduplicator()

        def create_mock(start, end, dtype, value):
            mock_email = MagicMock()
            mock_email.sent_at = start
            mock = MagicMock()
            mock.email = mock_email
            mock.sale_start = start
            mock.sale_end = end
            mock.discount_type = dtype
            mock.discount_value = value
            mock.categories = ["shoes"]
            mock.confidence = 0.8
            return mock

        extractions = [
            create_mock(date(2024, 1, 15), date(2024, 1, 20), "percent_off", 25.0),
            create_mock(date(2024, 6, 15), date(2024, 6, 20), "percent_off", 25.0),  # Different month
        ]

        groups = deduplicator.group_extractions(extractions)

        # Should remain separate
        assert len(groups) == 2

    def test_group_extractions_empty_list(self):
        """Test grouping with empty list."""
        deduplicator = SaleDeduplicator()
        groups = deduplicator.group_extractions([])
        assert groups == []
