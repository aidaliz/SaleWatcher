"""Sale deduplication service.

Groups related promotional emails into unified sale windows based on:
- Same brand
- Overlapping dates (within 3 days)
- Similar discount structure (same type, value within 5%)
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Brand, ExtractedSale, RawEmail, SaleWindow


# Deduplication thresholds
DATE_PROXIMITY_DAYS = 3
DISCOUNT_VALUE_TOLERANCE = 5.0  # percentage points


@dataclass
class SaleGroup:
    """Intermediate grouping of related emails."""
    emails: list[ExtractedSale]
    start_date: date
    end_date: date
    discount_type: str
    discount_value: Optional[float]
    categories: set[str]


def dates_overlap(
    start1: date,
    end1: date,
    start2: date,
    end2: date,
    proximity_days: int = DATE_PROXIMITY_DAYS,
) -> bool:
    """Check if two date ranges overlap or are within proximity."""
    # Extend ranges by proximity
    extended_start1 = start1 - timedelta(days=proximity_days)
    extended_end1 = end1 + timedelta(days=proximity_days)
    extended_start2 = start2 - timedelta(days=proximity_days)
    extended_end2 = end2 + timedelta(days=proximity_days)

    # Check overlap
    return extended_start1 <= extended_end2 and extended_start2 <= extended_end1


def discounts_match(
    type1: str,
    value1: Optional[float],
    type2: str,
    value2: Optional[float],
    tolerance: float = DISCOUNT_VALUE_TOLERANCE,
) -> bool:
    """Check if two discounts are similar enough to group."""
    # Types must match
    if type1 != type2:
        return False

    # If both have values, check tolerance
    if value1 is not None and value2 is not None:
        return abs(value1 - value2) <= tolerance

    # If only one has a value, still consider a match (same type is enough)
    return True


def get_sale_dates(extraction: ExtractedSale) -> tuple[date, date]:
    """Get effective start/end dates for an extraction."""
    email_date = extraction.email.sent_at if extraction.email else date.today()

    # Use extraction dates if available, otherwise use email date
    start = extraction.sale_start or email_date
    end = extraction.sale_end or start

    return start, end


def generate_sale_name(
    brand_name: str,
    discount_type: str,
    discount_value: Optional[float],
    start_date: date,
) -> str:
    """Generate a descriptive name for a sale window."""
    # Format discount
    if discount_type == "percent_off" and discount_value:
        discount_str = f"{int(discount_value)}% Off"
    elif discount_type == "bogo":
        discount_str = "BOGO"
    elif discount_type == "free_shipping":
        discount_str = "Free Shipping"
    elif discount_type == "fixed_price" and discount_value:
        discount_str = f"${int(discount_value)} Sale"
    else:
        discount_str = "Sale"

    # Format date
    month_name = start_date.strftime("%B")

    return f"{brand_name} {month_name} {discount_str}"


def generate_discount_summary(
    discount_type: str,
    discount_value: Optional[float],
    is_sitewide: bool,
) -> str:
    """Generate a human-readable discount summary."""
    if discount_type == "percent_off" and discount_value:
        base = f"{int(discount_value)}% off"
    elif discount_type == "bogo":
        base = "Buy one get one"
    elif discount_type == "free_shipping":
        base = "Free shipping"
    elif discount_type == "fixed_price" and discount_value:
        base = f"Starting at ${int(discount_value)}"
    else:
        base = "Special promotion"

    if is_sitewide:
        base += " sitewide"

    return base


class SaleDeduplicator:
    """Service for grouping related emails into sale windows."""

    async def get_unprocessed_extractions(
        self,
        db: AsyncSession,
        brand_id: Optional[UUID] = None,
    ) -> list[ExtractedSale]:
        """Get approved extractions not yet assigned to a sale window."""
        query = (
            select(ExtractedSale)
            .join(RawEmail)
            .where(ExtractedSale.review_status == "approved")
            .options(selectinload(ExtractedSale.email).selectinload(RawEmail.brand))
        )

        if brand_id:
            query = query.where(RawEmail.brand_id == brand_id)

        result = await db.execute(query)
        extractions = result.scalars().all()

        # Filter out those already in a sale window
        existing_windows_query = select(SaleWindow.linked_email_ids)
        window_result = await db.execute(existing_windows_query)
        all_linked_ids = set()
        for row in window_result.scalars().all():
            if row:
                all_linked_ids.update(row)

        return [e for e in extractions if e.email_id not in all_linked_ids]

    def group_extractions(
        self,
        extractions: list[ExtractedSale],
    ) -> list[SaleGroup]:
        """Group related extractions into sale groups."""
        if not extractions:
            return []

        groups: list[SaleGroup] = []

        for extraction in extractions:
            start, end = get_sale_dates(extraction)
            discount_type = extraction.discount_type
            discount_value = extraction.discount_value
            categories = set(extraction.categories or [])

            # Try to find a matching existing group
            matched_group = None
            for group in groups:
                if dates_overlap(start, end, group.start_date, group.end_date):
                    if discounts_match(
                        discount_type,
                        discount_value,
                        group.discount_type,
                        group.discount_value,
                    ):
                        matched_group = group
                        break

            if matched_group:
                # Add to existing group
                matched_group.emails.append(extraction)
                matched_group.start_date = min(matched_group.start_date, start)
                matched_group.end_date = max(matched_group.end_date, end)
                matched_group.categories.update(categories)
                # Update discount value to the most confident one
                if discount_value and (
                    matched_group.discount_value is None
                    or extraction.confidence > max(e.confidence for e in matched_group.emails[:-1])
                ):
                    matched_group.discount_value = discount_value
            else:
                # Create new group
                groups.append(SaleGroup(
                    emails=[extraction],
                    start_date=start,
                    end_date=end,
                    discount_type=discount_type,
                    discount_value=discount_value,
                    categories=categories,
                ))

        return groups

    async def create_sale_windows(
        self,
        db: AsyncSession,
        brand: Brand,
        groups: list[SaleGroup],
    ) -> list[SaleWindow]:
        """Create SaleWindow records from grouped extractions."""
        windows = []

        for group in groups:
            # Determine if sitewide (majority vote)
            sitewide_count = sum(1 for e in group.emails if e.is_sitewide)
            is_sitewide = sitewide_count > len(group.emails) / 2

            window = SaleWindow(
                brand_id=brand.id,
                name=generate_sale_name(
                    brand.name,
                    group.discount_type,
                    group.discount_value,
                    group.start_date,
                ),
                discount_summary=generate_discount_summary(
                    group.discount_type,
                    group.discount_value,
                    is_sitewide,
                ),
                start_date=group.start_date,
                end_date=group.end_date,
                linked_email_ids=[e.email_id for e in group.emails],
                categories=list(group.categories),
                year=group.start_date.year,
            )

            db.add(window)
            windows.append(window)

        await db.commit()

        # Refresh all windows to get IDs
        for window in windows:
            await db.refresh(window)

        return windows

    async def deduplicate_brand(
        self,
        db: AsyncSession,
        brand_id: UUID,
    ) -> list[SaleWindow]:
        """Run deduplication for a single brand."""
        # Get brand
        brand_result = await db.execute(
            select(Brand).where(Brand.id == brand_id)
        )
        brand = brand_result.scalar_one_or_none()
        if not brand:
            return []

        # Get unprocessed extractions
        extractions = await self.get_unprocessed_extractions(db, brand_id)
        if not extractions:
            return []

        # Group by brand (already filtered, but structure for future multi-brand)
        groups = self.group_extractions(extractions)

        # Create windows
        return await self.create_sale_windows(db, brand, groups)

    async def deduplicate_all(
        self,
        db: AsyncSession,
    ) -> dict[UUID, list[SaleWindow]]:
        """Run deduplication for all active brands."""
        # Get all active brands
        brands_result = await db.execute(
            select(Brand).where(Brand.is_active == True)
        )
        brands = brands_result.scalars().all()

        results = {}
        for brand in brands:
            windows = await self.deduplicate_brand(db, brand.id)
            if windows:
                results[brand.id] = windows

        return results


async def run_deduplication(
    db: AsyncSession,
    brand_id: Optional[UUID] = None,
) -> list[SaleWindow]:
    """
    Convenience function to run deduplication.

    Args:
        db: Database session
        brand_id: Optional brand filter

    Returns:
        List of created SaleWindow records
    """
    deduplicator = SaleDeduplicator()

    if brand_id:
        return await deduplicator.deduplicate_brand(db, brand_id)
    else:
        all_windows = await deduplicator.deduplicate_all(db)
        return [w for windows in all_windows.values() for w in windows]
