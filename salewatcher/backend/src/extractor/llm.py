"""LLM-based sale extraction using Claude."""
import json
import logging
import re
from datetime import datetime
from typing import Optional

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings
from src.db.models import DiscountType, ExtractedSale, ExtractionStatus, RawEmail
from src.extractor.prompts import EXTRACTION_SYSTEM_PROMPT, get_extraction_prompt

logger = logging.getLogger(__name__)


class SaleExtractor:
    """Extracts sale information from emails using Claude."""

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.haiku_model = settings.llm_haiku_model
        self.sonnet_model = settings.llm_sonnet_model
        self.confidence_threshold = settings.llm_confidence_threshold
        self.review_threshold = settings.llm_review_threshold

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _call_llm(self, prompt: str, model: str) -> str:
        """Call Claude API with retry logic."""
        response = await self.client.messages.create(
            model=model,
            max_tokens=1024,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def _parse_response(self, response_text: str) -> dict:
        """Parse JSON response from LLM."""
        # Try to find JSON in response
        response_text = response_text.strip()

        # Handle markdown code blocks
        if "```json" in response_text:
            match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
            if match:
                response_text = match.group(1)
        elif "```" in response_text:
            match = re.search(r"```\s*(.*?)\s*```", response_text, re.DOTALL)
            if match:
                response_text = match.group(1)

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response was: {response_text[:500]}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")

    def _map_discount_type(self, type_str: Optional[str]) -> Optional[DiscountType]:
        """Map string discount type to enum."""
        if not type_str:
            return None

        mapping = {
            "percentage": DiscountType.PERCENTAGE,
            "fixed_amount": DiscountType.FIXED_AMOUNT,
            "bogo": DiscountType.BOGO,
            "free_shipping": DiscountType.FREE_SHIPPING,
            "other": DiscountType.OTHER,
        }
        return mapping.get(type_str.lower())

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return None

    async def extract(
        self,
        raw_email: RawEmail,
        brand_name: str,
        use_sonnet: bool = False,
    ) -> ExtractedSale:
        """
        Extract sale information from an email.

        Args:
            raw_email: The raw email to process
            brand_name: Name of the brand
            use_sonnet: Force use of Sonnet model

        Returns:
            ExtractedSale with extraction results
        """
        model = self.sonnet_model if use_sonnet else self.haiku_model
        logger.info(f"Extracting sale info with {model}: {raw_email.subject[:50]}...")

        # Generate prompt
        prompt = get_extraction_prompt(
            brand_name=brand_name,
            subject=raw_email.subject,
            sent_date=raw_email.sent_at.strftime("%Y-%m-%d"),
            html_content=raw_email.html_content,
        )

        # Call LLM
        response_text = await self._call_llm(prompt, model)

        # Parse response
        data = self._parse_response(response_text)

        # Determine status based on confidence
        confidence = float(data.get("confidence", 0.5))

        if confidence >= self.confidence_threshold:
            status = ExtractionStatus.PROCESSED
        elif confidence >= self.review_threshold:
            status = ExtractionStatus.NEEDS_REVIEW
        else:
            status = ExtractionStatus.NEEDS_REVIEW

        # Create ExtractedSale
        extracted = ExtractedSale(
            raw_email_id=raw_email.id,
            is_sale=bool(data.get("is_sale", False)),
            discount_type=self._map_discount_type(data.get("discount_type")),
            discount_value=data.get("discount_value"),
            discount_summary=data.get("discount_summary"),
            categories=data.get("categories", []),
            sale_start=self._parse_date(data.get("sale_start")),
            sale_end=self._parse_date(data.get("sale_end")),
            confidence=confidence,
            model_used=model,
            status=status,
        )

        return extracted

    async def extract_with_fallback(
        self,
        raw_email: RawEmail,
        brand_name: str,
    ) -> ExtractedSale:
        """
        Extract using Haiku first, fall back to Sonnet for low confidence.

        Args:
            raw_email: The raw email to process
            brand_name: Name of the brand

        Returns:
            ExtractedSale with extraction results
        """
        # First try with Haiku
        extracted = await self.extract(raw_email, brand_name, use_sonnet=False)

        # If low confidence, retry with Sonnet
        if extracted.confidence < self.confidence_threshold:
            logger.info(f"Low confidence ({extracted.confidence}), retrying with Sonnet...")
            extracted = await self.extract(raw_email, brand_name, use_sonnet=True)

        return extracted
