#!/usr/bin/env python
"""
CLI script for generating sale predictions from historical data.

Usage:
    python scripts/predict.py                     # Generate predictions for current year
    python scripts/predict.py --year 2025         # Generate for specific year
    python scripts/predict.py --brand gamestop    # Generate for specific brand
    python scripts/predict.py --years-ahead 2     # Generate for next 2 years
    python scripts/predict.py --group-first       # Group sales into windows first
"""
import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from src.config import settings
from src.db.session import get_session_factory
from src.db.models import Brand, SaleWindow, Prediction
from src.deduplicator.grouper import create_sale_windows
from src.predictor.generator import generate_predictions, generate_all_future_predictions

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main(args):
    """Main prediction entry point."""
    session_factory = get_session_factory()

    async with session_factory() as db:
        brand_id = None

        if args.brand:
            # Get brand ID from slug
            result = await db.execute(
                select(Brand).where(Brand.milled_slug == args.brand)
            )
            brand = result.scalar_one_or_none()

            if not brand:
                logger.error(f"Brand with slug '{args.brand}' not found")
                return 1

            brand_id = brand.id
            logger.info(f"Processing brand: {brand.name}")

        # Step 1: Group extracted sales into windows (if requested)
        if args.group_first:
            logger.info("Step 1: Grouping extracted sales into sale windows...")
            windows = await create_sale_windows(db, brand_id=brand_id)
            logger.info(f"Created {len(windows)} new sale windows")
        else:
            # Check if there are any windows
            count_query = select(SaleWindow)
            if brand_id:
                count_query = count_query.where(SaleWindow.brand_id == brand_id)
            result = await db.execute(count_query)
            window_count = len(list(result.scalars().all()))

            if window_count == 0:
                logger.warning(
                    "No sale windows found. Run with --group-first to create them, "
                    "or run extract.py first to extract sales from emails."
                )
                return 1

            logger.info(f"Found {window_count} existing sale windows")

        # Step 2: Generate predictions
        logger.info("Step 2: Generating predictions...")

        if args.year:
            # Generate for specific year
            predictions = await generate_predictions(
                db,
                target_year=args.year,
                brand_id=brand_id,
            )
            logger.info(f"Generated {len(predictions)} predictions for {args.year}")
        else:
            # Generate for current year and ahead
            all_predictions = await generate_all_future_predictions(
                db,
                brand_id=brand_id,
                years_ahead=args.years_ahead,
            )

            total = sum(len(p) for p in all_predictions.values())
            logger.info(f"Generated {total} predictions total:")
            for year, preds in all_predictions.items():
                logger.info(f"  {year}: {len(preds)} predictions")

        # Show summary
        logger.info("\n=== Summary ===")

        pred_query = select(Prediction).options()
        if brand_id:
            pred_query = pred_query.where(Prediction.brand_id == brand_id)
        pred_query = pred_query.order_by(Prediction.predicted_start).limit(10)

        result = await db.execute(pred_query)
        upcoming = list(result.scalars().all())

        if upcoming:
            logger.info("Upcoming predictions:")
            for pred in upcoming:
                if pred.predicted_start >= datetime.utcnow():
                    logger.info(
                        f"  {pred.predicted_start.strftime('%Y-%m-%d')}: "
                        f"{pred.discount_summary[:50]} "
                        f"(confidence: {pred.confidence:.0%})"
                    )
        else:
            logger.info("No upcoming predictions")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate sale predictions")
    parser.add_argument(
        "--brand",
        type=str,
        help="Specific brand slug to process",
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Specific year to generate predictions for (default: current year)",
    )
    parser.add_argument(
        "--years-ahead",
        type=int,
        default=1,
        help="How many years ahead to predict (default: 1)",
    )
    parser.add_argument(
        "--group-first",
        action="store_true",
        help="Group extracted sales into windows before predicting",
    )

    args = parser.parse_args()

    try:
        exit_code = asyncio.run(main(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Prediction cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
