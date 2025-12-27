"""
Groups extracted sales into deduplicated sale windows.

Sale windows represent distinct sale events, combining multiple emails
that announce or promote the same sale.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import (
    Brand,
    ExtractedSale,
    ExtractionStatus,
    SaleWindow,
    DiscountType,
)

logger = logging.getLogger(__name__)

# US Holidays with typical month/day (approximate)
HOLIDAYS = {
    "new_years": (1, 1),
    "mlk_day": (1, 15),  # 3rd Monday in January
    "valentines": (2, 14),
    "presidents_day": (2, 15),  # 3rd Monday in February
    "st_patricks": (3, 17),
    "easter": (4, 10),  # Varies, approximate
    "mothers_day": (5, 10),  # 2nd Sunday in May
    "memorial_day": (5, 25),  # Last Monday in May
    "fathers_day": (6, 15),  # 3rd Sunday in June
    "july_4th": (7, 4),
    "labor_day": (9, 1),  # 1st Monday in September
    "columbus_day": (10, 10),  # 2nd Monday in October
    "halloween": (10, 31),
    "veterans_day": (11, 11),
    "thanksgiving": (11, 25),  # 4th Thursday in November
    "black_friday": (11, 26),  # Day after Thanksgiving
    "cyber_monday": (11, 29),  # Monday after Thanksgiving
    "christmas_eve": (12, 24),
    "christmas": (12, 25),
    "boxing_day": (12, 26),
    "new_years_eve": (12, 31),
}

# Days to consider "close" to a holiday for anchoring
HOLIDAY_PROXIMITY_DAYS = 7


def find_holiday_anchor(date: datetime) -> tuple[Optional[str], Optional[int]]:
    """
    Find if a date is close to a known holiday.

    Returns:
        Tuple of (holiday_name, days_from_holiday) or (None, None)
    """
    year = date.year

    for holiday_name, (month, day) in HOLIDAYS.items():
        try:
            holiday_date = datetime(year, month, day)
            delta = (date - holiday_date).days

            if abs(delta) <= HOLIDAY_PROXIMITY_DAYS:
                return holiday_name, delta
        except ValueError:
            # Invalid date (e.g., Feb 30)
            continue

    return None, None


def sales_are_similar(
    sale1: ExtractedSale,
    sale2: ExtractedSale,
    max_days_apart: int = 5,
) -> bool:
    """
    Check if two extracted sales are likely from the same sale event.
    """
    # Must have dates to compare
    if not sale1.sale_start or not sale2.sale_start:
        return False

    # Check date proximity
    days_apart = abs((sale1.sale_start - sale2.sale_start).days)
    if days_apart > max_days_apart:
        return False

    # Check discount type match (if both have one)
    if sale1.discount_type and sale2.discount_type:
        if sale1.discount_type != sale2.discount_type:
            return False

    return True


async def create_sale_windows(
    db: AsyncSession,
    brand_id: Optional[UUID] = None,
) -> list[SaleWindow]:
    """
    Group extracted sales into sale windows.

    Args:
        db: Database session
        brand_id: Optional brand ID to process only one brand

    Returns:
        List of created SaleWindow objects
    """
    # Get approved/processed extracted sales that aren't in a window yet
    query = (
        select(ExtractedSale)
        .options(selectinload(ExtractedSale.raw_email))
        .where(ExtractedSale.is_sale == True)
        .where(ExtractedSale.sale_window_id == None)
        .where(
            ExtractedSale.status.in_([
                ExtractionStatus.PROCESSED,
                ExtractionStatus.APPROVED,
            ])
        )
    )

    if brand_id:
        from src.db.models import RawEmail
        query = query.join(RawEmail).where(RawEmail.brand_id == brand_id)

    query = query.order_by(ExtractedSale.sale_start)

    result = await db.execute(query)
    sales = list(result.scalars().all())

    if not sales:
        logger.info("No unassigned sales to group")
        return []

    logger.info(f"Grouping {len(sales)} extracted sales into windows")

    # Group sales by brand first
    sales_by_brand: dict[UUID, list[ExtractedSale]] = {}
    for sale in sales:
        bid = sale.raw_email.brand_id
        if bid not in sales_by_brand:
            sales_by_brand[bid] = []
        sales_by_brand[bid].append(sale)

    created_windows = []

    for bid, brand_sales in sales_by_brand.items():
        # Group similar sales together
        groups: list[list[ExtractedSale]] = []

        for sale in brand_sales:
            added_to_group = False

            for group in groups:
                if sales_are_similar(sale, group[0]):
                    group.append(sale)
                    added_to_group = True
                    break

            if not added_to_group:
                groups.append([sale])

        # Create a window for each group
        for group in groups:
            if not group:
                continue

            # Calculate window properties from group
            start_dates = [s.sale_start for s in group if s.sale_start]
            end_dates = [s.sale_end for s in group if s.sale_end]

            if not start_dates:
                continue

            window_start = min(start_dates)
            window_end = max(end_dates) if end_dates else window_start + timedelta(days=3)

            # Use the highest-confidence sale for discount info
            best_sale = max(group, key=lambda s: s.confidence)

            # Find holiday anchor
            holiday_anchor, days_from_holiday = find_holiday_anchor(window_start)

            # Create the window
            window = SaleWindow(
                brand_id=bid,
                year=window_start.year,
                start_date=window_start,
                end_date=window_end,
                discount_type=best_sale.discount_type or DiscountType.OTHER,
                discount_value=best_sale.discount_value or 0.0,
                discount_summary=best_sale.discount_summary or "Sale",
                categories=best_sale.categories or [],
                holiday_anchor=holiday_anchor,
                days_from_holiday=days_from_holiday,
            )

            db.add(window)
            await db.flush()  # Get the window ID

            # Link sales to window
            for sale in group:
                sale.sale_window_id = window.id

            created_windows.append(window)
            logger.info(
                f"Created window: {window.discount_summary[:50]} "
                f"({window.start_date.strftime('%Y-%m-%d')} - {window.end_date.strftime('%Y-%m-%d')})"
            )

    await db.commit()
    logger.info(f"Created {len(created_windows)} sale windows")

    return created_windows
