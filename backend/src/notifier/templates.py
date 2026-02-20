"""Email templates for notifications."""

from datetime import date
from typing import Optional

from src.config.settings import get_settings


def get_base_style() -> str:
    """Get base CSS styles for emails."""
    return """
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        h1 { color: #2563eb; font-size: 24px; margin-bottom: 20px; }
        h2 { color: #1e40af; font-size: 18px; margin-top: 24px; }
        .card {
            background: #f8fafc;
            border-radius: 8px;
            padding: 16px;
            margin: 12px 0;
            border-left: 4px solid #2563eb;
        }
        .card-title { font-weight: 600; margin-bottom: 8px; }
        .card-meta { color: #64748b; font-size: 14px; }
        .btn {
            display: inline-block;
            background: #2563eb;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 6px;
            margin: 8px 4px 8px 0;
        }
        .btn-secondary { background: #64748b; }
        .btn-success { background: #16a34a; }
        .btn-danger { background: #dc2626; }
        .stats {
            display: flex;
            gap: 16px;
            margin: 16px 0;
        }
        .stat {
            background: #f1f5f9;
            padding: 12px 16px;
            border-radius: 8px;
            text-align: center;
        }
        .stat-value { font-size: 24px; font-weight: 700; color: #2563eb; }
        .stat-label { font-size: 12px; color: #64748b; text-transform: uppercase; }
        table { width: 100%; border-collapse: collapse; margin: 16px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #e2e8f0; }
        th { background: #f8fafc; font-weight: 600; }
        .footer {
            margin-top: 32px;
            padding-top: 16px;
            border-top: 1px solid #e2e8f0;
            color: #94a3b8;
            font-size: 12px;
        }
    </style>
    """


def get_dashboard_url() -> str:
    """Get the dashboard URL."""
    settings = get_settings()
    return settings.dashboard_url or "http://localhost:3000"


def review_digest_template(
    pending_count: int,
    reviews: list[dict],
) -> str:
    """
    Generate the review digest email.

    Args:
        pending_count: Total pending reviews
        reviews: List of review items (limit to 10)

    Returns:
        HTML email content
    """
    dashboard_url = get_dashboard_url()

    review_cards = ""
    for review in reviews[:10]:
        review_cards += f"""
        <div class="card">
            <div class="card-title">{review['brand_name']}: {review['discount_summary']}</div>
            <div class="card-meta">
                Confidence: {review['confidence']:.0%} |
                Model: {review['model_used']}
            </div>
            <div style="margin-top: 12px;">
                <a href="{dashboard_url}/review/{review['id']}" class="btn">Review</a>
                <a href="{dashboard_url}/review/{review['id']}/approve" class="btn btn-success">Approve</a>
                <a href="{dashboard_url}/review/{review['id']}/reject" class="btn btn-danger">Reject</a>
            </div>
        </div>
        """

    remaining = pending_count - len(reviews)
    remaining_note = f"<p>...and {remaining} more</p>" if remaining > 0 else ""

    return f"""
    <!DOCTYPE html>
    <html>
    <head>{get_base_style()}</head>
    <body>
        <h1>Review Queue Digest</h1>

        <p>You have <strong>{pending_count}</strong> extraction(s) pending review.</p>

        {review_cards}
        {remaining_note}

        <p>
            <a href="{dashboard_url}/review" class="btn">View All Reviews</a>
        </p>

        <div class="footer">
            This is an automated message from SaleWatcher.
        </div>
    </body>
    </html>
    """


def weekly_summary_template(
    upcoming_count: int,
    predictions: list[dict],
    accuracy_stats: Optional[dict] = None,
) -> str:
    """
    Generate the weekly prediction summary email.

    Args:
        upcoming_count: Total upcoming predictions
        predictions: List of upcoming predictions
        accuracy_stats: Optional accuracy statistics

    Returns:
        HTML email content
    """
    dashboard_url = get_dashboard_url()

    # Stats section
    stats_html = ""
    if accuracy_stats:
        stats_html = f"""
        <div class="stats">
            <div class="stat">
                <div class="stat-value">{accuracy_stats.get('hit_rate', 0):.0%}</div>
                <div class="stat-label">Hit Rate</div>
            </div>
            <div class="stat">
                <div class="stat-value">{accuracy_stats.get('total_predictions', 0)}</div>
                <div class="stat-label">Total Predictions</div>
            </div>
            <div class="stat">
                <div class="stat-value">{accuracy_stats.get('brands_tracked', 0)}</div>
                <div class="stat-label">Brands Tracked</div>
            </div>
        </div>
        """

    # Predictions table
    rows = ""
    for pred in predictions[:15]:
        rows += f"""
        <tr>
            <td>{pred['brand_name']}</td>
            <td>{pred['discount_summary']}</td>
            <td>{pred['predicted_start']} - {pred['predicted_end']}</td>
            <td>{pred['confidence']:.0%}</td>
        </tr>
        """

    predictions_table = ""
    if predictions:
        predictions_table = f"""
        <h2>Upcoming Sales ({upcoming_count} total)</h2>
        <table>
            <thead>
                <tr>
                    <th>Brand</th>
                    <th>Discount</th>
                    <th>Expected Dates</th>
                    <th>Confidence</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        """
    else:
        predictions_table = "<p>No upcoming predictions for the next 14 days.</p>"

    return f"""
    <!DOCTYPE html>
    <html>
    <head>{get_base_style()}</head>
    <body>
        <h1>Weekly SaleWatcher Summary</h1>

        <p>Here's your weekly overview of predicted sales and system status.</p>

        {stats_html}
        {predictions_table}

        <p>
            <a href="{dashboard_url}/predictions" class="btn">View All Predictions</a>
            <a href="{dashboard_url}/accuracy" class="btn btn-secondary">Accuracy Dashboard</a>
        </p>

        <div class="footer">
            This is an automated weekly summary from SaleWatcher.
        </div>
    </body>
    </html>
    """


def accuracy_alert_template(
    brand_name: str,
    current_hit_rate: float,
    previous_hit_rate: float,
    recent_misses: list[dict],
) -> str:
    """
    Generate an accuracy alert email when a brand drops below threshold.

    Args:
        brand_name: Name of the affected brand
        current_hit_rate: Current hit rate
        previous_hit_rate: Previous hit rate
        recent_misses: Recent missed predictions

    Returns:
        HTML email content
    """
    dashboard_url = get_dashboard_url()

    miss_rows = ""
    for miss in recent_misses[:5]:
        miss_rows += f"""
        <tr>
            <td>{miss['predicted_start']}</td>
            <td>{miss['discount_summary']}</td>
            <td>{miss.get('reason', 'No matching sale found')}</td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>{get_base_style()}</head>
    <body>
        <h1>Accuracy Alert: {brand_name}</h1>

        <p>The prediction accuracy for <strong>{brand_name}</strong> has dropped significantly.</p>

        <div class="stats">
            <div class="stat">
                <div class="stat-value" style="color: #dc2626;">{current_hit_rate:.0%}</div>
                <div class="stat-label">Current Hit Rate</div>
            </div>
            <div class="stat">
                <div class="stat-value">{previous_hit_rate:.0%}</div>
                <div class="stat-label">Previous Hit Rate</div>
            </div>
        </div>

        <h2>Recent Misses</h2>
        <table>
            <thead>
                <tr>
                    <th>Expected Date</th>
                    <th>Predicted Discount</th>
                    <th>Reason</th>
                </tr>
            </thead>
            <tbody>
                {miss_rows}
            </tbody>
        </table>

        <p>Consider reviewing this brand's prediction settings or checking for pattern changes.</p>

        <p>
            <a href="{dashboard_url}/brands/{brand_name}" class="btn">View Brand Details</a>
        </p>

        <div class="footer">
            This alert was triggered because the hit rate dropped below the configured threshold.
        </div>
    </body>
    </html>
    """
