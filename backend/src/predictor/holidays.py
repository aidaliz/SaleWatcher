"""Holiday calendar utilities for prediction anchoring.

Computes dates for major US retail holidays for any given year.
Used to anchor predictions to floating holidays (Memorial Day, Labor Day,
Thanksgiving, etc.) rather than fixed calendar dates.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from functools import lru_cache
from typing import Optional


class Holiday(str, Enum):
    """US retail holidays tracked by SaleWatcher."""
    NEW_YEARS_DAY = "new_years_day"
    MLK_DAY = "mlk_day"
    VALENTINES_DAY = "valentines_day"
    PRESIDENTS_DAY = "presidents_day"
    EASTER = "easter"
    MOTHERS_DAY = "mothers_day"
    MEMORIAL_DAY = "memorial_day"
    FATHERS_DAY = "fathers_day"
    INDEPENDENCE_DAY = "independence_day"
    LABOR_DAY = "labor_day"
    COLUMBUS_DAY = "columbus_day"
    HALLOWEEN = "halloween"
    VETERANS_DAY = "veterans_day"
    THANKSGIVING = "thanksgiving"
    BLACK_FRIDAY = "black_friday"
    CYBER_MONDAY = "cyber_monday"
    CHRISTMAS_EVE = "christmas_eve"
    CHRISTMAS = "christmas"
    NEW_YEARS_EVE = "new_years_eve"
    # Season markers
    BACK_TO_SCHOOL = "back_to_school"
    END_OF_SUMMER = "end_of_summer"


@dataclass
class HolidayInfo:
    """Information about a holiday occurrence."""
    holiday: Holiday
    date: date
    name: str
    is_floating: bool  # Whether the date varies by year


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """
    Get the nth occurrence of a weekday in a month.

    Args:
        year: The year
        month: The month (1-12)
        weekday: The weekday (0=Monday, 6=Sunday)
        n: Which occurrence (1=first, 2=second, etc.)

    Returns:
        The date of the nth weekday
    """
    first_day = date(year, month, 1)
    # Find first occurrence of weekday
    days_ahead = weekday - first_day.weekday()
    if days_ahead < 0:
        days_ahead += 7
    first_occurrence = first_day + timedelta(days=days_ahead)
    # Move to nth occurrence
    return first_occurrence + timedelta(weeks=n - 1)


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    """
    Get the last occurrence of a weekday in a month.

    Args:
        year: The year
        month: The month (1-12)
        weekday: The weekday (0=Monday, 6=Sunday)

    Returns:
        The date of the last weekday
    """
    # Start from first day of next month and go back
    if month == 12:
        first_of_next = date(year + 1, 1, 1)
    else:
        first_of_next = date(year, month + 1, 1)

    last_day = first_of_next - timedelta(days=1)
    days_back = last_day.weekday() - weekday
    if days_back < 0:
        days_back += 7
    return last_day - timedelta(days=days_back)


def _compute_easter(year: int) -> date:
    """
    Compute Easter Sunday for a given year using the Anonymous Gregorian algorithm.
    """
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


@lru_cache(maxsize=32)
def get_holiday_date(holiday: Holiday, year: int) -> date:
    """
    Get the date of a holiday for a specific year.

    Args:
        holiday: The holiday to look up
        year: The year

    Returns:
        The date of the holiday
    """
    match holiday:
        # Fixed date holidays
        case Holiday.NEW_YEARS_DAY:
            return date(year, 1, 1)
        case Holiday.VALENTINES_DAY:
            return date(year, 2, 14)
        case Holiday.INDEPENDENCE_DAY:
            return date(year, 7, 4)
        case Holiday.HALLOWEEN:
            return date(year, 10, 31)
        case Holiday.VETERANS_DAY:
            return date(year, 11, 11)
        case Holiday.CHRISTMAS_EVE:
            return date(year, 12, 24)
        case Holiday.CHRISTMAS:
            return date(year, 12, 25)
        case Holiday.NEW_YEARS_EVE:
            return date(year, 12, 31)

        # Floating holidays
        case Holiday.MLK_DAY:
            # Third Monday of January
            return _nth_weekday_of_month(year, 1, 0, 3)
        case Holiday.PRESIDENTS_DAY:
            # Third Monday of February
            return _nth_weekday_of_month(year, 2, 0, 3)
        case Holiday.EASTER:
            return _compute_easter(year)
        case Holiday.MOTHERS_DAY:
            # Second Sunday of May
            return _nth_weekday_of_month(year, 5, 6, 2)
        case Holiday.MEMORIAL_DAY:
            # Last Monday of May
            return _last_weekday_of_month(year, 5, 0)
        case Holiday.FATHERS_DAY:
            # Third Sunday of June
            return _nth_weekday_of_month(year, 6, 6, 3)
        case Holiday.LABOR_DAY:
            # First Monday of September
            return _nth_weekday_of_month(year, 9, 0, 1)
        case Holiday.COLUMBUS_DAY:
            # Second Monday of October
            return _nth_weekday_of_month(year, 10, 0, 2)
        case Holiday.THANKSGIVING:
            # Fourth Thursday of November
            return _nth_weekday_of_month(year, 11, 3, 4)
        case Holiday.BLACK_FRIDAY:
            # Day after Thanksgiving
            return get_holiday_date(Holiday.THANKSGIVING, year) + timedelta(days=1)
        case Holiday.CYBER_MONDAY:
            # Monday after Thanksgiving
            return get_holiday_date(Holiday.THANKSGIVING, year) + timedelta(days=4)

        # Season markers (approximate dates used for retail)
        case Holiday.BACK_TO_SCHOOL:
            # Mid-August
            return date(year, 8, 15)
        case Holiday.END_OF_SUMMER:
            # Labor Day weekend start
            return get_holiday_date(Holiday.LABOR_DAY, year) - timedelta(days=2)

        case _:
            raise ValueError(f"Unknown holiday: {holiday}")


def get_holiday_info(holiday: Holiday, year: int) -> HolidayInfo:
    """Get full information about a holiday for a specific year."""
    holiday_date = get_holiday_date(holiday, year)

    # Human-readable names
    names = {
        Holiday.NEW_YEARS_DAY: "New Year's Day",
        Holiday.MLK_DAY: "Martin Luther King Jr. Day",
        Holiday.VALENTINES_DAY: "Valentine's Day",
        Holiday.PRESIDENTS_DAY: "Presidents' Day",
        Holiday.EASTER: "Easter",
        Holiday.MOTHERS_DAY: "Mother's Day",
        Holiday.MEMORIAL_DAY: "Memorial Day",
        Holiday.FATHERS_DAY: "Father's Day",
        Holiday.INDEPENDENCE_DAY: "Independence Day",
        Holiday.LABOR_DAY: "Labor Day",
        Holiday.COLUMBUS_DAY: "Columbus Day",
        Holiday.HALLOWEEN: "Halloween",
        Holiday.VETERANS_DAY: "Veterans Day",
        Holiday.THANKSGIVING: "Thanksgiving",
        Holiday.BLACK_FRIDAY: "Black Friday",
        Holiday.CYBER_MONDAY: "Cyber Monday",
        Holiday.CHRISTMAS_EVE: "Christmas Eve",
        Holiday.CHRISTMAS: "Christmas",
        Holiday.NEW_YEARS_EVE: "New Year's Eve",
        Holiday.BACK_TO_SCHOOL: "Back to School",
        Holiday.END_OF_SUMMER: "End of Summer",
    }

    # Floating holidays
    floating = {
        Holiday.MLK_DAY,
        Holiday.PRESIDENTS_DAY,
        Holiday.EASTER,
        Holiday.MOTHERS_DAY,
        Holiday.MEMORIAL_DAY,
        Holiday.FATHERS_DAY,
        Holiday.LABOR_DAY,
        Holiday.COLUMBUS_DAY,
        Holiday.THANKSGIVING,
        Holiday.BLACK_FRIDAY,
        Holiday.CYBER_MONDAY,
        Holiday.END_OF_SUMMER,
    }

    return HolidayInfo(
        holiday=holiday,
        date=holiday_date,
        name=names.get(holiday, holiday.value.replace("_", " ").title()),
        is_floating=holiday in floating,
    )


def get_all_holidays_for_year(year: int) -> list[HolidayInfo]:
    """Get all holidays for a year, sorted by date."""
    holidays = [get_holiday_info(h, year) for h in Holiday]
    return sorted(holidays, key=lambda h: h.date)


def find_nearest_holiday(
    target_date: date,
    max_days: int = 14,
) -> Optional[HolidayInfo]:
    """
    Find the nearest holiday to a target date.

    Args:
        target_date: The date to search around
        max_days: Maximum days away to consider

    Returns:
        The nearest holiday info, or None if none within max_days
    """
    year = target_date.year
    holidays = get_all_holidays_for_year(year)

    # Also check adjacent years for edge cases (late December, early January)
    if target_date.month == 12:
        holidays.extend(get_all_holidays_for_year(year + 1))
    elif target_date.month == 1:
        holidays.extend(get_all_holidays_for_year(year - 1))

    nearest = None
    min_distance = max_days + 1

    for holiday_info in holidays:
        distance = abs((holiday_info.date - target_date).days)
        if distance <= max_days and distance < min_distance:
            min_distance = distance
            nearest = holiday_info

    return nearest


def adjust_date_for_holiday(
    original_date: date,
    from_year: int,
    to_year: int,
    holiday: Optional[Holiday] = None,
) -> date:
    """
    Adjust a date from one year to another, accounting for floating holidays.

    If a holiday anchor is provided and the holiday is floating, the date
    will be adjusted relative to the holiday's position in each year.

    Args:
        original_date: The date in the original year
        from_year: The year of the original date
        to_year: The target year
        holiday: Optional holiday anchor

    Returns:
        The adjusted date in the target year
    """
    if holiday is None:
        # No holiday anchor, just shift the year
        try:
            return original_date.replace(year=to_year)
        except ValueError:
            # Handle Feb 29 in non-leap years
            return date(to_year, original_date.month, 28)

    # Get holiday dates for both years
    original_holiday = get_holiday_date(holiday, from_year)
    target_holiday = get_holiday_date(holiday, to_year)

    # Calculate offset from original holiday
    offset = original_date - original_holiday

    # Apply offset to target holiday
    return target_holiday + offset


def detect_holiday_anchor(
    sale_date: date,
    max_days: int = 7,
) -> Optional[Holiday]:
    """
    Detect if a sale date is likely anchored to a holiday.

    Args:
        sale_date: The date of a sale
        max_days: Maximum days from holiday to consider anchored

    Returns:
        The holiday if anchored, None otherwise
    """
    nearest = find_nearest_holiday(sale_date, max_days)
    if nearest:
        return nearest.holiday
    return None
