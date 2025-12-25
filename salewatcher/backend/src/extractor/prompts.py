"""Prompts for LLM-based sale extraction."""

EXTRACTION_SYSTEM_PROMPT = """You are an expert at analyzing retail promotional emails to extract sale information for Amazon Online Arbitrage sourcing.

Your task is to analyze email content and extract structured sale details. Be precise and conservative - only extract information you're confident about.

For confidence scoring:
- 1.0: Very clear sale with explicit discount, dates, and categories
- 0.8-0.9: Clear sale with most details explicit
- 0.6-0.7: Likely a sale but some details inferred
- 0.4-0.5: Possibly a sale, significant uncertainty
- 0.0-0.3: Probably not a sale or very unclear

Focus on sales that would be relevant for retail arbitrage (buying products on sale to resell on Amazon)."""


EXTRACTION_USER_PROMPT = """Analyze this promotional email and extract sale information.

Brand: {brand_name}
Email Subject: {subject}
Email Date: {sent_date}

Email Content:
{html_content}

---

Extract the following information as JSON:

{{
  "is_sale": boolean,           // Is this email about a sale/promotion?
  "discount_type": string,      // "percentage", "fixed_amount", "bogo", "free_shipping", "other", or null
  "discount_value": number,     // The discount amount (e.g., 25 for 25% off), or null
  "discount_summary": string,   // Brief description like "25% off sitewide" or "Buy 2 Get 1 Free"
  "categories": [string],       // Product categories on sale (e.g., ["Beauty", "Skincare"]), empty if all/unclear
  "sale_start": string,         // Start date in YYYY-MM-DD format, or null if unclear
  "sale_end": string,           // End date in YYYY-MM-DD format, or null if unclear
  "confidence": number          // Your confidence score 0.0-1.0
}}

Important:
- If this is NOT a sale email (just newsletter, lookbook, etc.), set is_sale=false and confidence=0.9
- Exclude categories that don't apply to arbitrage: clothing/apparel, shoes, groceries/food
- If multiple discounts, use the most significant one
- Be conservative with confidence scores

Respond ONLY with valid JSON, no other text."""


def get_extraction_prompt(
    brand_name: str,
    subject: str,
    sent_date: str,
    html_content: str,
    max_content_length: int = 15000,
) -> str:
    """Generate extraction prompt with email content."""
    # Truncate content if too long
    if len(html_content) > max_content_length:
        html_content = html_content[:max_content_length] + "\n... [content truncated]"

    return EXTRACTION_USER_PROMPT.format(
        brand_name=brand_name,
        subject=subject,
        sent_date=sent_date,
        html_content=html_content,
    )
