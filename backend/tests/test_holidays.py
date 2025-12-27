"""Unit tests for the holiday calendar module."""

import pytest
from datetime import date

from src.predictor.holidays import (
    Holiday,
    get_holiday_date,
    get_holiday_info,
    get_all_holidays_for_year,
    find_nearest_holiday,
    adjust_date_for_holiday,
    detect_holiday_anchor,
)


class TestGetHolidayDate:
    """Tests for get_holiday_date function."""

    def test_fixed_holidays(self):
        """Test fixed-date holidays."""
        assert get_holiday_date(Holiday.NEW_YEARS_DAY, 2024) == date(2024, 1, 1)
        assert get_holiday_date(Holiday.VALENTINES_DAY, 2024) == date(2024, 2, 14)
        assert get_holiday_date(Holiday.INDEPENDENCE_DAY, 2024) == date(2024, 7, 4)
        assert get_holiday_date(Holiday.HALLOWEEN, 2024) == date(2024, 10, 31)
        assert get_holiday_date(Holiday.CHRISTMAS, 2024) == date(2024, 12, 25)

    def test_thanksgiving_calculation(self):
        """Test Thanksgiving (4th Thursday of November)."""
        # Thanksgiving dates for multiple years
        assert get_holiday_date(Holiday.THANKSGIVING, 2023) == date(2023, 11, 23)
        assert get_holiday_date(Holiday.THANKSGIVING, 2024) == date(2024, 11, 28)
        assert get_holiday_date(Holiday.THANKSGIVING, 2025) == date(2025, 11, 27)
        assert get_holiday_date(Holiday.THANKSGIVING, 2026) == date(2026, 11, 26)

    def test_black_friday_calculation(self):
        """Test Black Friday (day after Thanksgiving)."""
        assert get_holiday_date(Holiday.BLACK_FRIDAY, 2024) == date(2024, 11, 29)
        assert get_holiday_date(Holiday.BLACK_FRIDAY, 2025) == date(2025, 11, 28)

    def test_cyber_monday_calculation(self):
        """Test Cyber Monday (Monday after Thanksgiving)."""
        assert get_holiday_date(Holiday.CYBER_MONDAY, 2024) == date(2024, 12, 2)
        assert get_holiday_date(Holiday.CYBER_MONDAY, 2025) == date(2025, 12, 1)

    def test_memorial_day_calculation(self):
        """Test Memorial Day (last Monday of May)."""
        assert get_holiday_date(Holiday.MEMORIAL_DAY, 2024) == date(2024, 5, 27)
        assert get_holiday_date(Holiday.MEMORIAL_DAY, 2025) == date(2025, 5, 26)
        assert get_holiday_date(Holiday.MEMORIAL_DAY, 2026) == date(2026, 5, 25)

    def test_labor_day_calculation(self):
        """Test Labor Day (first Monday of September)."""
        assert get_holiday_date(Holiday.LABOR_DAY, 2024) == date(2024, 9, 2)
        assert get_holiday_date(Holiday.LABOR_DAY, 2025) == date(2025, 9, 1)

    def test_mothers_day_calculation(self):
        """Test Mother's Day (second Sunday of May)."""
        assert get_holiday_date(Holiday.MOTHERS_DAY, 2024) == date(2024, 5, 12)
        assert get_holiday_date(Holiday.MOTHERS_DAY, 2025) == date(2025, 5, 11)

    def test_fathers_day_calculation(self):
        """Test Father's Day (third Sunday of June)."""
        assert get_holiday_date(Holiday.FATHERS_DAY, 2024) == date(2024, 6, 16)
        assert get_holiday_date(Holiday.FATHERS_DAY, 2025) == date(2025, 6, 15)

    def test_easter_calculation(self):
        """Test Easter calculation."""
        assert get_holiday_date(Holiday.EASTER, 2024) == date(2024, 3, 31)
        assert get_holiday_date(Holiday.EASTER, 2025) == date(2025, 4, 20)
        assert get_holiday_date(Holiday.EASTER, 2026) == date(2026, 4, 5)

    def test_mlk_day_calculation(self):
        """Test MLK Day (third Monday of January)."""
        assert get_holiday_date(Holiday.MLK_DAY, 2024) == date(2024, 1, 15)
        assert get_holiday_date(Holiday.MLK_DAY, 2025) == date(2025, 1, 20)

    def test_presidents_day_calculation(self):
        """Test Presidents Day (third Monday of February)."""
        assert get_holiday_date(Holiday.PRESIDENTS_DAY, 2024) == date(2024, 2, 19)
        assert get_holiday_date(Holiday.PRESIDENTS_DAY, 2025) == date(2025, 2, 17)


class TestGetHolidayInfo:
    """Tests for get_holiday_info function."""

    def test_returns_correct_info(self):
        """Test that holiday info is correct."""
        info = get_holiday_info(Holiday.THANKSGIVING, 2024)
        assert info.holiday == Holiday.THANKSGIVING
        assert info.date == date(2024, 11, 28)
        assert info.name == "Thanksgiving"
        assert info.is_floating is True

    def test_fixed_holiday_not_floating(self):
        """Test that fixed holidays are marked correctly."""
        info = get_holiday_info(Holiday.CHRISTMAS, 2024)
        assert info.is_floating is False

    def test_floating_holiday_marked_correctly(self):
        """Test that floating holidays are marked correctly."""
        info = get_holiday_info(Holiday.MEMORIAL_DAY, 2024)
        assert info.is_floating is True


class TestGetAllHolidaysForYear:
    """Tests for get_all_holidays_for_year function."""

    def test_returns_all_holidays(self):
        """Test that all holidays are returned."""
        holidays = get_all_holidays_for_year(2024)
        assert len(holidays) == len(Holiday)

    def test_holidays_sorted_by_date(self):
        """Test that holidays are sorted by date."""
        holidays = get_all_holidays_for_year(2024)
        dates = [h.date for h in holidays]
        assert dates == sorted(dates)

    def test_first_holiday_is_new_years(self):
        """Test that first holiday is New Year's Day."""
        holidays = get_all_holidays_for_year(2024)
        assert holidays[0].holiday == Holiday.NEW_YEARS_DAY


class TestFindNearestHoliday:
    """Tests for find_nearest_holiday function."""

    def test_finds_exact_match(self):
        """Test finding holiday on exact date."""
        result = find_nearest_holiday(date(2024, 11, 28))
        assert result is not None
        assert result.holiday == Holiday.THANKSGIVING

    def test_finds_nearby_holiday(self):
        """Test finding holiday within range."""
        result = find_nearest_holiday(date(2024, 11, 30), max_days=7)
        assert result is not None
        assert result.holiday in [Holiday.THANKSGIVING, Holiday.BLACK_FRIDAY]

    def test_returns_none_when_too_far(self):
        """Test returns None when no holiday in range."""
        result = find_nearest_holiday(date(2024, 6, 1), max_days=3)
        assert result is None

    def test_respects_max_days(self):
        """Test that max_days parameter is respected."""
        # June 16, 2024 is Father's Day
        result = find_nearest_holiday(date(2024, 6, 10), max_days=5)
        assert result is None

        result = find_nearest_holiday(date(2024, 6, 10), max_days=7)
        assert result is not None


class TestAdjustDateForHoliday:
    """Tests for adjust_date_for_holiday function."""

    def test_simple_year_shift(self):
        """Test date shift without holiday anchor."""
        result = adjust_date_for_holiday(
            date(2023, 6, 15),
            from_year=2023,
            to_year=2024,
        )
        assert result == date(2024, 6, 15)

    def test_leap_year_handling(self):
        """Test Feb 29 handling for non-leap years."""
        result = adjust_date_for_holiday(
            date(2024, 2, 29),
            from_year=2024,
            to_year=2025,
        )
        assert result == date(2025, 2, 28)

    def test_floating_holiday_adjustment(self):
        """Test date adjustment relative to floating holiday."""
        # Black Friday 2023 was Nov 24
        # Black Friday 2024 is Nov 29
        # A sale on Nov 24, 2023 should shift to Nov 29, 2024
        result = adjust_date_for_holiday(
            date(2023, 11, 24),
            from_year=2023,
            to_year=2024,
            holiday=Holiday.BLACK_FRIDAY,
        )
        assert result == date(2024, 11, 29)

    def test_offset_from_holiday_preserved(self):
        """Test that offset from holiday is preserved."""
        # 2 days before Black Friday 2023 (Nov 24) = Nov 22
        # Should become 2 days before Black Friday 2024 (Nov 29) = Nov 27
        result = adjust_date_for_holiday(
            date(2023, 11, 22),
            from_year=2023,
            to_year=2024,
            holiday=Holiday.BLACK_FRIDAY,
        )
        assert result == date(2024, 11, 27)


class TestDetectHolidayAnchor:
    """Tests for detect_holiday_anchor function."""

    def test_detects_exact_holiday(self):
        """Test detection on exact holiday date."""
        result = detect_holiday_anchor(date(2024, 11, 29))
        assert result == Holiday.BLACK_FRIDAY

    def test_detects_nearby_holiday(self):
        """Test detection near holiday."""
        result = detect_holiday_anchor(date(2024, 11, 27), max_days=3)
        assert result in [Holiday.THANKSGIVING, Holiday.BLACK_FRIDAY]

    def test_returns_none_when_no_holiday(self):
        """Test returns None when no nearby holiday."""
        result = detect_holiday_anchor(date(2024, 6, 1), max_days=3)
        assert result is None
