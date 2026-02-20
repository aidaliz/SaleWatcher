"""Anthropic Claude client wrapper for sale extraction."""

import json
from typing import Literal, Optional

from anthropic import AsyncAnthropic, RateLimitError, APIError
from pydantic import BaseModel
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.config.settings import get_settings


class ExtractionResult(BaseModel):
    """Structured result from LLM extraction."""
    discount_type: Literal["percent_off", "bogo", "fixed_price", "free_shipping", "other"]
    discount_value: Optional[float] = None
    discount_max: Optional[float] = None
    is_sitewide: bool = False
    categories: list[str] = []
    excluded_categories: list[str] = []
    conditions: list[str] = []
    sale_start: Optional[str] = None  # YYYY-MM-DD format
    sale_end: Optional[str] = None
    confidence: float
    raw_discount_text: str


class ClaudeClient:
    """Async client wrapper for Anthropic Claude API."""

    def __init__(self):
        self.settings = get_settings()
        self.client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=30),
        retry=retry_if_exception_type(RateLimitError),
    )
    async def complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> str:
        """
        Send a completion request to Claude.

        Args:
            prompt: The user prompt
            model: Model to use (default: Haiku)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            The model's response text
        """
        if model is None:
            model = self.settings.llm_haiku_model

        response = await self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "user", "content": prompt}
            ],
        )

        return response.content[0].text

    async def extract_with_haiku(self, prompt: str) -> str:
        """Extract using Haiku model (fast, cheap)."""
        return await self.complete(prompt, model=self.settings.llm_haiku_model)

    async def extract_with_sonnet(self, prompt: str) -> str:
        """Extract using Sonnet model (more accurate, for edge cases)."""
        return await self.complete(prompt, model=self.settings.llm_sonnet_model)

    async def extract_sale(
        self,
        email_html: str,
        brand_name: str,
        brand_categories: Optional[list[str]] = None,
        excluded_categories: Optional[list[str]] = None,
        use_sonnet: bool = False,
    ) -> tuple[ExtractionResult, str]:
        """
        Extract sale details from email HTML.

        Args:
            email_html: The raw HTML of the promotional email
            brand_name: Name of the brand
            brand_categories: Categories the brand typically sells
            excluded_categories: Categories to ignore in extraction
            use_sonnet: Whether to use Sonnet instead of Haiku

        Returns:
            Tuple of (ExtractionResult, model_used)
        """
        from src.extractor.prompts import build_extraction_prompt

        prompt = build_extraction_prompt(
            email_html=email_html,
            brand_name=brand_name,
            brand_categories=brand_categories or [],
            excluded_categories=excluded_categories or [],
        )

        if use_sonnet:
            response = await self.extract_with_sonnet(prompt)
            model_used = self.settings.llm_sonnet_model
        else:
            response = await self.extract_with_haiku(prompt)
            model_used = self.settings.llm_haiku_model

        # Parse JSON response
        result = self._parse_extraction_response(response)
        return result, model_used

    def _parse_extraction_response(self, response: str) -> ExtractionResult:
        """Parse the LLM response into an ExtractionResult."""
        # Try to extract JSON from the response
        try:
            # Look for JSON block in response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                return ExtractionResult(**data)
        except (json.JSONDecodeError, ValueError) as e:
            # If parsing fails, return a low-confidence result
            return ExtractionResult(
                discount_type="other",
                confidence=0.0,
                raw_discount_text=f"Parse error: {e}",
            )


# Singleton instance
_client: Optional[ClaudeClient] = None


def get_claude_client() -> ClaudeClient:
    """Get or create the Claude client singleton."""
    global _client
    if _client is None:
        _client = ClaudeClient()
    return _client
