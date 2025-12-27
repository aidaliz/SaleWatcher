"""Prompts for LLM-based sale extraction."""


EXTRACTION_PROMPT = """You are analyzing a retail promotional email to extract sale details.
Your task is to identify discount information and return it as structured JSON.

## Email HTML Content:
{email_html}

## Context:
- Brand: {brand_name}
- Categories this brand typically sells: {brand_categories}
- Categories to EXCLUDE from analysis: {excluded_categories}

## Instructions:
1. Analyze the email for promotional/sale information
2. Extract the main discount offer (ignore minor add-ons)
3. Be conservative with your confidence score

## Output Format:
Return ONLY a JSON object with these fields:

{{
  "discount_type": "percent_off" | "bogo" | "fixed_price" | "free_shipping" | "other",
  "discount_value": <number or null>,
  "discount_max": <number or null for "up to X%" promotions>,
  "is_sitewide": <boolean>,
  "categories": ["category1", "category2"],
  "excluded_categories": ["excluded1"],
  "conditions": ["condition1", "condition2"],
  "sale_start": "YYYY-MM-DD" or null,
  "sale_end": "YYYY-MM-DD" or null,
  "confidence": <0.0 to 1.0>,
  "raw_discount_text": "<exact text describing the discount>"
}}

## Confidence Guidelines:
- 0.9-1.0: Clear, unambiguous discount with explicit dates
- 0.7-0.9: Clear discount, dates inferred or partially stated
- 0.5-0.7: Discount present but details ambiguous
- 0.3-0.5: Multiple conflicting offers or unclear scope
- 0.0-0.3: Cannot reliably extract discount information

## Examples:

Email: "SALE! 25% OFF EVERYTHING - This weekend only!"
Response: {{"discount_type": "percent_off", "discount_value": 25.0, "is_sitewide": true, "confidence": 0.85, "raw_discount_text": "25% OFF EVERYTHING"}}

Email: "Buy 2 Get 1 Free on all beauty products"
Response: {{"discount_type": "bogo", "categories": ["beauty"], "is_sitewide": false, "confidence": 0.9, "raw_discount_text": "Buy 2 Get 1 Free on all beauty products"}}

Now analyze the email and return ONLY the JSON object, no other text:"""


def build_extraction_prompt(
    email_html: str,
    brand_name: str,
    brand_categories: list[str],
    excluded_categories: list[str],
) -> str:
    """Build the extraction prompt with context."""
    # Truncate HTML if too long (keep first 50k chars)
    max_html_length = 50000
    if len(email_html) > max_html_length:
        email_html = email_html[:max_html_length] + "\n... [truncated]"

    return EXTRACTION_PROMPT.format(
        email_html=email_html,
        brand_name=brand_name,
        brand_categories=", ".join(brand_categories) if brand_categories else "general retail",
        excluded_categories=", ".join(excluded_categories) if excluded_categories else "none",
    )
