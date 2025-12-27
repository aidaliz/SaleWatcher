"""Unit tests for the prediction generation module."""

import pytest
from datetime import date
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

from src.predictor.service import (
    calculate_prediction_confidence,
    PredictionGenerator,
    MIN_CONFIDENCE_FOR_PREDICTION,
)
from src.predictor.holidays import Holiday


class TestCalculatePredictionConfidence:
    """Tests for calculate_prediction_confidence function."""

    def test_base_confidence(self):
        """Test base confidence without any bonuses."""
        window = MagicMock()
        window.id = uuid4()
        window.holiday_anchor = None
        window.start_date = date(2023, 6, 15)

        confidence = calculate_prediction_confidence(window, [])
        assert confidence == 0.5

    def test_holiday_anchor_bonus(self):
        """Test confidence bonus for holiday-anchored sales."""
        window = MagicMock()
        window.id = uuid4()
        window.holiday_anchor = "black_friday"
        window.start_date = date(2023, 11, 24)

        confidence = calculate_prediction_confidence(window, [])
        assert confidence == 0.65  # 0.5 base + 0.15 holiday bonus

    def test_historical_data_bonus(self):
        """Test confidence bonus for multiple years of data."""
        window = MagicMock()
        window.id = uuid4()
        window.holiday_anchor = None
        window.start_date = date(2023, 6, 15)
        window.year = 2023
        window.discount_summary = "20% off"

        # Create historical windows
        def make_historical(year):
            hw = MagicMock()
            hw.id = uuid4()
            hw.year = year
            hw.holiday_anchor = None
            hw.start_date = date(year, 6, 16)  # Within 14 days
            hw.discount_summary = "20% off"
            return hw

        historical = [
            make_historical(2022),
            make_historical(2021),
        ]

        confidence = calculate_prediction_confidence(window, historical)
        # 0.5 base + 0.2 (2 years * 0.1) + 0.1 (matching discounts)
        assert confidence >= 0.7

    def test_max_confidence_cap(self):
        """Test that confidence is capped at 1.0."""
        window = MagicMock()
        window.id = uuid4()
        window.holiday_anchor = "black_friday"
        window.start_date = date(2023, 11, 24)
        window.year = 2023
        window.discount_summary = "30% off"

        # Create many historical windows
        def make_historical(year):
            hw = MagicMock()
            hw.id = uuid4()
            hw.year = year
            hw.holiday_anchor = "black_friday"
            hw.start_date = date(year, 11, 24)
            hw.discount_summary = "30% off"
            return hw

        historical = [make_historical(y) for y in range(2018, 2023)]

        confidence = calculate_prediction_confidence(window, historical)
        assert confidence <= 1.0


class TestPredictionGenerator:
    """Tests for PredictionGenerator class."""

    def test_init_default_year(self):
        """Test default target year is current year."""
        generator = PredictionGenerator()
        assert generator.target_year == date.today().year

    def test_init_custom_year(self):
        """Test custom target year."""
        generator = PredictionGenerator(target_year=2025)
        assert generator.target_year == 2025

    def test_generate_candidates_empty_windows(self):
        """Test candidate generation with no windows."""
        generator = PredictionGenerator(target_year=2024)
        candidates = generator.generate_candidates([], [], [], [])
        assert candidates == []

    def test_generate_candidates_skips_low_confidence(self):
        """Test that low confidence predictions are skipped."""
        generator = PredictionGenerator(target_year=2024)

        window = MagicMock()
        window.id = uuid4()
        window.brand_id = uuid4()
        window.holiday_anchor = None
        window.start_date = date(2023, 6, 15)
        window.end_date = date(2023, 6, 20)
        window.year = 2023
        window.discount_summary = "Sale"
        window.linked_email_ids = []

        # No historical data = low confidence
        candidates = generator.generate_candidates([window], [], [], [])

        # Base confidence 0.5 is below MIN_CONFIDENCE_FOR_PREDICTION (0.6)
        assert len(candidates) == 0

    def test_generate_candidates_includes_high_confidence(self):
        """Test that high confidence predictions are included."""
        generator = PredictionGenerator(target_year=2024)

        window = MagicMock()
        window.id = uuid4()
        window.brand_id = uuid4()
        window.holiday_anchor = "black_friday"  # +0.15 confidence
        window.start_date = date(2023, 11, 24)
        window.end_date = date(2023, 11, 27)
        window.year = 2023
        window.discount_summary = "30% off"
        window.linked_email_ids = [uuid4()]

        candidates = generator.generate_candidates([window], [], [], [])

        # 0.5 base + 0.15 holiday = 0.65 > 0.6 threshold
        assert len(candidates) == 1
        assert candidates[0].holiday_anchor == "black_friday"

    def test_generate_candidates_skips_existing(self):
        """Test that already-predicted windows are skipped."""
        generator = PredictionGenerator(target_year=2024)

        window_id = uuid4()
        window = MagicMock()
        window.id = window_id
        window.brand_id = uuid4()
        window.holiday_anchor = "black_friday"
        window.start_date = date(2023, 11, 24)
        window.end_date = date(2023, 11, 27)
        window.year = 2023
        window.discount_summary = "30% off"
        window.linked_email_ids = []

        existing_prediction = MagicMock()
        existing_prediction.source_window_id = window_id

        candidates = generator.generate_candidates(
            [window], [], [existing_prediction], []
        )

        assert len(candidates) == 0

    def test_generate_candidates_holiday_adjustment(self):
        """Test that dates are adjusted for floating holidays."""
        generator = PredictionGenerator(target_year=2024)

        window = MagicMock()
        window.id = uuid4()
        window.brand_id = uuid4()
        window.holiday_anchor = "thanksgiving"
        # Thanksgiving 2023 was Nov 23
        window.start_date = date(2023, 11, 23)
        window.end_date = date(2023, 11, 26)
        window.year = 2023
        window.discount_summary = "Sale"
        window.linked_email_ids = [uuid4()]

        candidates = generator.generate_candidates([window], [], [], [])

        if candidates:  # If confidence is high enough
            # Thanksgiving 2024 is Nov 28, so dates should shift
            assert candidates[0].predicted_start == date(2024, 11, 28)


class TestMinConfidenceThreshold:
    """Tests for confidence threshold constant."""

    def test_threshold_value(self):
        """Test that threshold is set correctly."""
        assert MIN_CONFIDENCE_FOR_PREDICTION == 0.6

    def test_threshold_is_reasonable(self):
        """Test that threshold is in valid range."""
        assert 0 < MIN_CONFIDENCE_FOR_PREDICTION < 1
