"""Send sale prediction webhooks to OA Leads Alert."""

import hashlib
import hmac
import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _sign_payload(body: bytes, secret: str) -> str:
    """Sign a payload with HMAC-SHA256."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def post_prediction_webhook(
    prediction_data: dict[str, Any],
    webhook_url: str,
    webhook_secret: str = "",
) -> bool:
    """
    POST a sale prediction payload to OA Leads Alert webhook.

    Args:
        prediction_data: Dict with keys: retailer_domain, discount_pct,
            discount_type, predicted_start, predicted_end, confidence, brand_name
        webhook_url: Full URL of the /webhooks/sale-prediction endpoint
        webhook_secret: Optional HMAC signing secret

    Returns:
        True if delivered successfully, False otherwise.
    """
    body = json.dumps(prediction_data, default=str).encode()
    headers = {"Content-Type": "application/json"}

    if webhook_secret:
        sig = _sign_payload(body, webhook_secret)
        headers["X-Webhook-Signature"] = sig

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(webhook_url, content=body, headers=headers)
            response.raise_for_status()
            logger.info(
                "Sale prediction webhook delivered",
                url=webhook_url,
                status=response.status_code,
                retailer=prediction_data.get("retailer_domain"),
            )
            return True
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Webhook delivery failed — HTTP error",
            url=webhook_url,
            status=exc.response.status_code,
            body=exc.response.text[:200],
        )
        return False
    except httpx.RequestError as exc:
        logger.error(
            "Webhook delivery failed — request error",
            url=webhook_url,
            error=str(exc),
        )
        return False
