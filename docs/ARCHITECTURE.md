# ARCHITECTURE.md — SaleWatcher

## System Overview

SaleWatcher is a sales prediction system that analyzes historical retail promotional emails to predict future sales events. The system operates on two primary cycles:

1. **Weekly Pipeline**: Scrape → Extract → Deduplicate → Predict → Notify
2. **Daily Verification**: Verify Outcomes → Calculate Accuracy → Generate Suggestions

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              WEEKLY CRON (Sunday 2 AM)                       │
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐  │
│  │   Scraper    │───▶│  Extractor   │───▶│ Deduplicator │───▶│ Predictor │  │
│  │  (Milled)    │    │ (Haiku/Son.) │    │              │    │           │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └─────┬─────┘  │
│                                                                     │       │
└─────────────────────────────────────────────────────────────────────┼───────┘
                                                                      │
┌─────────────────────────────────────────────────────────────────────┼───────┐
│                           DAILY CRON (8 AM)                         │       │
│                                                                     │       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐           │       │
│  │ Auto-Verify  │───▶│  Calculate   │───▶│  Generate    │           │       │
│  │ Outcomes     │    │  Accuracy    │    │  Suggestions │           │       │
│  └──────────────┘    └──────────────┘    └──────────────┘           │       │
│                                                                     │       │
└─────────────────────────────────────────────────────────────────────┼───────┘
                                                                      │
                    ┌─────────────────────────────────────────────────┼───────┐
                    │                     ALWAYS ON                   ▼       │
                    │                                                         │
                    │  ┌──────────────┐    ┌──────────────┐    ┌───────────┐  │
                    │  │   Database   │◀───│   Calendar   │◀───│  Notifier │  │
                    │  │ (PostgreSQL) │    │   (Google)   │    │  (Resend) │  │
                    │  └──────┬───────┘    └──────────────┘    └───────────┘  │
                    │         │                                               │
                    │         ▼                                               │
                    │  ┌────────────────────────────────────────────────────┐ │
                    │  │              Review Dashboard (Next.js)            │ │
                    │  │   • Brand management    • Accuracy reports         │ │
                    │  │   • Review queue        • Adjustment suggestions   │ │
                    │  └────────────────────────────────────────────────────┘ │
                    │                                                         │
                    └─────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Scraper (Milled.com)

**Purpose**: Authenticate to Milled.com and download promotional emails for tracked brands.

**Technology**: Playwright (Python) with headless Chromium

**Flow**:
```
1. Launch headless browser
2. Navigate to Milled.com login page
3. Enter credentials, submit form
4. For each active brand:
   a. Navigate to brand page (milled.com/brand-slug)
   b. Apply date filter (last 7 days for weekly, or full year for backfill)
   c. Paginate through results
   d. For each email:
      - Extract subject, sent date, Milled URL
      - Click to open email detail
      - Extract full HTML content
      - Save to raw_emails table
5. Close browser
```

**Error Handling**:
- Retry failed page loads (3 attempts with exponential backoff)
- Screenshot on failure for debugging
- Skip individual emails on error, continue with others
- Alert on complete brand failure

**Rate Limiting**:
- 2-second delay between page navigations
- 500ms delay between email opens
- Respect Milled.com's robots.txt

### 2. Extractor (LLM-Powered)

**Purpose**: Parse email HTML to extract structured sale information.

**Technology**: Anthropic Claude API (Haiku 4.5 primary, Sonnet 4.5 fallback)

**Extraction Schema**:
```python
class ExtractedSale(BaseModel):
    discount_type: Literal["percent_off", "bogo", "fixed_price", "free_shipping", "other"]
    discount_value: float | None          # e.g., 25.0 for "25% off"
    discount_max: float | None            # For "up to X% off"
    is_sitewide: bool
    categories: list[str]                 # e.g., ["beauty", "home"]
    excluded_categories: list[str]        # e.g., ["clothing", "shoes"]
    conditions: list[str]                 # e.g., ["members only", "min $50 purchase"]
    sale_start: date | None
    sale_end: date | None
    confidence: float                     # 0.0 - 1.0
    raw_discount_text: str                # Original text for reference
```

**Two-Stage Extraction**:
```
Stage 1: Haiku 4.5
├── Process all emails
├── Self-report confidence score
├── If confidence >= 0.7 → Accept result
└── If confidence < 0.7 → Queue for Stage 2

Stage 2: Sonnet 4.5
├── Re-process low-confidence emails
├── Higher accuracy for edge cases
├── If confidence >= 0.5 → Accept result
└── If confidence < 0.5 → Queue for human review
```

**Prompt Design**:
```
You are analyzing a retail promotional email. Extract sale details as JSON.

Email HTML:
{html_content}

Brand: {brand_name}
Brand typically sells: {brand_categories}
Exclude these categories from your analysis: {excluded_categories}

Return a JSON object with:
- discount_type: "percent_off" | "bogo" | "fixed_price" | "free_shipping" | "other"
- discount_value: number or null
- discount_max: number or null (for "up to X%" promotions)
- is_sitewide: boolean
- categories: array of category strings this sale applies to
- excluded_categories: array of categories explicitly excluded
- conditions: array of strings describing requirements
- sale_start: "YYYY-MM-DD" or null
- sale_end: "YYYY-MM-DD" or null
- confidence: 0.0-1.0 (how confident you are in this extraction)
- raw_discount_text: the exact text describing the discount

Be conservative with confidence. Use < 0.7 if:
- Discount structure is ambiguous
- Category scope is unclear
- Dates are not explicitly stated
- Multiple conflicting offers exist
```

### 3. Deduplicator

**Purpose**: Group related emails into unified "sale windows."

**Logic**:
```python
def deduplicate_sales(extracted_sales: list[ExtractedSale]) -> list[SaleWindow]:
    """
    Group sales that represent the same promotional event.
    
    Matching criteria:
    1. Same brand
    2. Overlapping or adjacent date ranges (within 3 days)
    3. Similar discount structure (same type, value within 5%)
    """
    windows = []
    for sale in sorted(extracted_sales, key=lambda s: s.sale_start):
        matched = False
        for window in windows:
            if is_same_event(sale, window):
                window.merge(sale)
                matched = True
                break
        if not matched:
            windows.append(SaleWindow.from_sale(sale))
    return windows
```

**Sale Window Schema**:
```python
class SaleWindow(BaseModel):
    id: UUID
    brand_id: UUID
    name: str                              # Generated: "Sephora 20% Off Spring Sale"
    discount_summary: str                  # "20-25% off sitewide"
    start_date: date
    end_date: date
    linked_email_ids: list[UUID]           # All emails about this sale
    holiday_anchor: str | None             # "memorial_day", "black_friday", etc.
    categories: list[str]
    year: int
```

### 4. Predictor

**Purpose**: Analyze historical sale windows to predict future occurrences.

**Prediction Algorithm**:
```python
def generate_predictions(
    historical_windows: list[SaleWindow],
    target_year: int
) -> list[Prediction]:
    """
    For each historical sale window, predict when it will recur.
    """
    predictions = []
    
    for window in historical_windows:
        if window.year != target_year - 1:
            continue  # Only use last year's data
            
        predicted_start, predicted_end = calculate_predicted_dates(
            window.start_date,
            window.end_date,
            window.holiday_anchor,
            target_year
        )
        
        prediction = Prediction(
            brand_id=window.brand_id,
            source_window_id=window.id,
            predicted_start=predicted_start,
            predicted_end=predicted_end,
            discount_summary=window.discount_summary,
            milled_reference_url=get_reference_url(window),
            confidence=calculate_confidence(window),
            calendar_alert_date=predicted_start - timedelta(days=7)
        )
        predictions.append(prediction)
    
    return predictions
```

**Date Calculation**:
```python
def calculate_predicted_dates(
    historical_start: date,
    historical_end: date,
    holiday_anchor: str | None,
    target_year: int
) -> tuple[date, date]:
    """
    Calculate predicted dates, adjusting for holiday anchoring.
    """
    if holiday_anchor:
        # Get holiday date for target year
        historical_holiday = get_holiday_date(holiday_anchor, historical_start.year)
        target_holiday = get_holiday_date(holiday_anchor, target_year)
        
        # Calculate offset from holiday
        offset = historical_start - historical_holiday
        duration = historical_end - historical_start
        
        predicted_start = target_holiday + offset
        predicted_end = predicted_start + duration
    else:
        # Simple year replacement with same month/day
        predicted_start = historical_start.replace(year=target_year)
        predicted_end = historical_end.replace(year=target_year)
    
    return predicted_start, predicted_end
```

**Supported Holidays**:
```python
HOLIDAYS = {
    "new_years": lambda year: date(year, 1, 1),
    "mlk_day": lambda year: nth_weekday(year, 1, 0, 3),      # 3rd Monday of January
    "presidents_day": lambda year: nth_weekday(year, 2, 0, 3), # 3rd Monday of February
    "memorial_day": lambda year: last_weekday(year, 5, 0),   # Last Monday of May
    "independence_day": lambda year: date(year, 7, 4),
    "labor_day": lambda year: nth_weekday(year, 9, 0, 1),    # 1st Monday of September
    "columbus_day": lambda year: nth_weekday(year, 10, 0, 2), # 2nd Monday of October
    "veterans_day": lambda year: date(year, 11, 11),
    "thanksgiving": lambda year: nth_weekday(year, 11, 3, 4), # 4th Thursday of November
    "black_friday": lambda year: nth_weekday(year, 11, 3, 4) + timedelta(days=1),
    "cyber_monday": lambda year: nth_weekday(year, 11, 3, 4) + timedelta(days=4),
    "christmas": lambda year: date(year, 12, 25),
    "back_to_school": lambda year: date(year, 8, 1),  # Approximate
}
```

### 5. Verifier (Outcome Tracking)

**Purpose**: Automatically verify if predictions were accurate; allow manual override.

**Auto-Verification Logic**:
```python
async def verify_predictions():
    """
    Run daily to check if predicted sales actually occurred.
    """
    # Get predictions whose windows have ended
    ended_predictions = await get_predictions_past_window()
    
    for prediction in ended_predictions:
        # Check if we scraped a matching sale during the window
        matching_sales = await find_sales_in_window(
            brand_id=prediction.brand_id,
            start_date=prediction.predicted_start - timedelta(days=7),
            end_date=prediction.predicted_end + timedelta(days=7),
            min_discount=15.0  # Allow some tolerance
        )
        
        if matching_sales:
            outcome = PredictionOutcome(
                prediction_id=prediction.id,
                auto_result="hit",
                actual_start=min(s.start_date for s in matching_sales),
                actual_end=max(s.end_date for s in matching_sales),
                actual_discount=matching_sales[0].discount_value,
                timing_delta_days=calculate_timing_delta(prediction, matching_sales),
                matched_email_ids=[s.source_email_id for s in matching_sales]
            )
        else:
            outcome = PredictionOutcome(
                prediction_id=prediction.id,
                auto_result="miss",
                timing_delta_days=None
            )
        
        await save_outcome(outcome)
```

**Manual Override**:
```python
class PredictionOutcome(BaseModel):
    id: UUID
    prediction_id: UUID
    
    # Auto-verification
    auto_result: Literal["hit", "miss", "pending"]
    auto_verified_at: datetime | None
    matched_email_ids: list[UUID]
    
    # Manual override
    manual_override: bool = False
    manual_result: Literal["hit", "miss"] | None
    override_reason: str | None
    overridden_at: datetime | None
    
    # Actual values (if hit)
    actual_start: date | None
    actual_end: date | None
    actual_discount: float | None
    timing_delta_days: int | None
    discount_delta_percent: float | None
    
    @property
    def final_result(self) -> str:
        if self.manual_override:
            return self.manual_result
        return self.auto_result
```

### 6. Accuracy Calculator

**Purpose**: Compute per-brand reliability scores and detect patterns.

**Metrics**:
```python
class BrandAccuracyStats(BaseModel):
    brand_id: UUID
    
    # Counts
    total_predictions: int
    correct_predictions: int  # final_result == "hit"
    
    # Rates
    hit_rate: float          # correct / total
    
    # Timing accuracy (for hits only)
    avg_timing_delta_days: float
    timing_delta_std: float
    
    # Discount accuracy (for hits only)
    avg_discount_delta_percent: float
    
    # Reliability tier
    reliability_score: int    # 0-100
    reliability_tier: Literal["excellent", "good", "fair", "poor"]
    
    last_calculated_at: datetime
```

**Reliability Tiers**:
```python
def calculate_reliability_tier(stats: BrandAccuracyStats) -> str:
    score = (
        stats.hit_rate * 60 +                    # Hit rate is most important
        max(0, 20 - stats.avg_timing_delta_days) +  # Timing accuracy
        max(0, 20 - stats.avg_discount_delta_percent)  # Discount accuracy
    )
    
    if score >= 85:
        return "excellent"
    elif score >= 70:
        return "good"
    elif score >= 55:
        return "fair"
    else:
        return "poor"
```

### 7. Suggestion Generator

**Purpose**: Propose adjustments when prediction patterns shift.

**Suggestion Types**:
```python
class AdjustmentSuggestion(BaseModel):
    id: UUID
    brand_id: UUID
    suggestion_type: Literal["timing_shift", "pattern_change", "confidence_adjust"]
    description: str
    recommended_action: str
    supporting_data: dict          # Evidence for the suggestion
    status: Literal["pending", "approved", "dismissed"]
    created_at: datetime
```

**Detection Logic**:
```python
async def generate_suggestions(brand_id: UUID):
    outcomes = await get_recent_outcomes(brand_id, days=90)
    
    # Detect consistent timing shift
    timing_deltas = [o.timing_delta_days for o in outcomes if o.final_result == "hit"]
    if len(timing_deltas) >= 3:
        avg_delta = mean(timing_deltas)
        if abs(avg_delta) >= 2:
            await create_suggestion(
                brand_id=brand_id,
                type="timing_shift",
                description=f"Last {len(timing_deltas)} predictions averaged {avg_delta:.1f} days {'late' if avg_delta > 0 else 'early'}",
                action=f"Shift prediction window by {int(avg_delta)} days"
            )
    
    # Detect pattern change (holiday no longer anchored)
    # ... similar logic
```

### 8. Calendar Sync

**Purpose**: Create Google Calendar events for upcoming predictions.

**Technology**: Google Calendar API with service account

**Flow**:
```python
async def sync_predictions_to_calendar():
    """
    Create calendar events for predictions in the next 30 days.
    Events appear 7 days before predicted sale start.
    """
    predictions = await get_upcoming_predictions(days=30)
    
    for prediction in predictions:
        if prediction.calendar_event_id:
            # Update existing event
            await update_calendar_event(prediction)
        else:
            # Create new event
            event = {
                "summary": f"🛒 {prediction.brand_name}: {prediction.discount_summary}",
                "description": f"""
Predicted Sale Window: {prediction.predicted_start} - {prediction.predicted_end}

Based on last year's sale: {prediction.milled_reference_url}

Discount: {prediction.discount_summary}
Confidence: {prediction.reliability_tier}
                """.strip(),
                "start": {"date": str(prediction.calendar_alert_date)},
                "end": {"date": str(prediction.calendar_alert_date + timedelta(days=1))},
                "reminders": {"useDefault": True}
            }
            
            result = await calendar_service.events().insert(
                calendarId=CALENDAR_ID,
                body=event
            ).execute()
            
            prediction.calendar_event_id = result["id"]
            await save_prediction(prediction)
```

### 9. Notifier

**Purpose**: Send email digests and alerts.

**Technology**: Resend API

**Email Types**:

1. **Daily Review Digest** (configurable frequency):
```
Subject: SaleWatcher: 5 items need review

Hi,

You have 5 borderline extractions that need your approval:

1. Sephora - "20% off" (confidence: 0.62)
   [Approve] [Reject] [View Details]

2. Target - "Buy 2 Get 1 Free" (confidence: 0.58)
   [Approve] [Reject] [View Details]

...

Review in dashboard: {dashboard_url}/review
```

2. **Weekly Prediction Summary**:
```
Subject: SaleWatcher: 8 sales predicted for next week

Hi,

Here are your upcoming predicted sales:

March 15-19: Sephora Spring Sale (20-25% off)
March 17: Kohl's Yes Pass Event (30% off)
...

View all predictions: {dashboard_url}/predictions
```

3. **Accuracy Alert** (when brand drops below threshold):
```
Subject: SaleWatcher: GameStop accuracy dropped to 52%

Hi,

GameStop's prediction accuracy has dropped below 60%.

Last 5 predictions: 2 hits, 3 misses

Consider:
- Reviewing recent predictions for issues
- Adjusting timing window for this brand
- Checking if brand has changed promotional patterns

View details: {dashboard_url}/accuracy?brand=gamestop
```

## Database Schema

```sql
-- Brands to track
CREATE TABLE brands (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    milled_slug VARCHAR(255) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT true,
    excluded_categories TEXT[] DEFAULT '{}',
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

-- Raw scraped emails
CREATE TABLE raw_emails (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID REFERENCES brands(id),
    milled_url VARCHAR(1024) NOT NULL UNIQUE,
    subject VARCHAR(512),
    sent_at DATE NOT NULL,
    html_content TEXT,
    scraped_at TIMESTAMP DEFAULT now()
);

-- LLM-extracted sale details
CREATE TABLE extracted_sales (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_id UUID REFERENCES raw_emails(id),
    discount_type VARCHAR(50) NOT NULL,
    discount_value FLOAT,
    discount_max FLOAT,
    is_sitewide BOOLEAN DEFAULT false,
    categories TEXT[] DEFAULT '{}',
    excluded_categories TEXT[] DEFAULT '{}',
    conditions TEXT[] DEFAULT '{}',
    sale_start DATE,
    sale_end DATE,
    confidence FLOAT NOT NULL,
    raw_discount_text TEXT,
    model_used VARCHAR(50),  -- 'haiku-4.5' or 'sonnet-4.5'
    review_status VARCHAR(20) DEFAULT 'pending',  -- pending, approved, rejected
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT now()
);

-- Deduplicated sale windows
CREATE TABLE sale_windows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID REFERENCES brands(id),
    name VARCHAR(255) NOT NULL,
    discount_summary VARCHAR(255),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    linked_email_ids UUID[] DEFAULT '{}',
    holiday_anchor VARCHAR(50),
    categories TEXT[] DEFAULT '{}',
    year INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);

-- Predictions for future sales
CREATE TABLE predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID REFERENCES brands(id),
    source_window_id UUID REFERENCES sale_windows(id),
    predicted_start DATE NOT NULL,
    predicted_end DATE NOT NULL,
    discount_summary VARCHAR(255),
    milled_reference_url VARCHAR(1024),
    confidence FLOAT NOT NULL,
    calendar_event_id VARCHAR(255),
    notified_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT now()
);

-- Prediction outcome verification
CREATE TABLE prediction_outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id UUID REFERENCES predictions(id) UNIQUE,
    auto_result VARCHAR(20),  -- hit, miss, pending
    auto_verified_at TIMESTAMP,
    matched_email_ids UUID[] DEFAULT '{}',
    manual_override BOOLEAN DEFAULT false,
    manual_result VARCHAR(20),
    override_reason TEXT,
    overridden_at TIMESTAMP,
    actual_start DATE,
    actual_end DATE,
    actual_discount FLOAT,
    timing_delta_days INTEGER,
    discount_delta_percent FLOAT,
    created_at TIMESTAMP DEFAULT now()
);

-- Brand accuracy statistics (materialized)
CREATE TABLE brand_accuracy_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID REFERENCES brands(id) UNIQUE,
    total_predictions INTEGER DEFAULT 0,
    correct_predictions INTEGER DEFAULT 0,
    hit_rate FLOAT DEFAULT 0,
    avg_timing_delta_days FLOAT,
    timing_delta_std FLOAT,
    avg_discount_delta_percent FLOAT,
    reliability_score INTEGER DEFAULT 0,
    reliability_tier VARCHAR(20),
    last_calculated_at TIMESTAMP DEFAULT now()
);

-- Adjustment suggestions
CREATE TABLE adjustment_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID REFERENCES brands(id),
    suggestion_type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    supporting_data JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'pending',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT now()
);

-- Indexes
CREATE INDEX idx_raw_emails_brand_date ON raw_emails(brand_id, sent_at DESC);
CREATE INDEX idx_extracted_sales_review ON extracted_sales(review_status, confidence);
CREATE INDEX idx_sale_windows_brand_year ON sale_windows(brand_id, year);
CREATE INDEX idx_predictions_dates ON predictions(predicted_start, predicted_end);
CREATE INDEX idx_outcomes_result ON prediction_outcomes(auto_result, manual_override);
```

## API Endpoints

### Brands
```
GET    /api/brands                    # List all brands
POST   /api/brands                    # Create brand
GET    /api/brands/{id}               # Get brand details
PATCH  /api/brands/{id}               # Update brand
DELETE /api/brands/{id}               # Deactivate brand
GET    /api/brands/{id}/emails        # List brand's emails
GET    /api/brands/{id}/predictions   # List brand's predictions
```

### Review Queue
```
GET    /api/review                    # List pending reviews
GET    /api/review/{id}               # Get review details
POST   /api/review/{id}/approve       # Approve extraction
POST   /api/review/{id}/reject        # Reject extraction
```

### Predictions
```
GET    /api/predictions               # List all predictions
GET    /api/predictions/upcoming      # Upcoming predictions
GET    /api/predictions/{id}          # Get prediction details
GET    /api/predictions/{id}/outcome  # Get outcome if exists
POST   /api/predictions/{id}/override # Override outcome
```

### Accuracy
```
GET    /api/accuracy                  # Overall accuracy stats
GET    /api/accuracy/brands           # Per-brand breakdown
GET    /api/accuracy/brands/{id}      # Single brand stats
GET    /api/suggestions               # List pending suggestions
POST   /api/suggestions/{id}/approve  # Approve suggestion
POST   /api/suggestions/{id}/dismiss  # Dismiss suggestion
```

### System
```
POST   /api/scrape/trigger            # Manually trigger scrape
POST   /api/backfill/{brand_id}       # Backfill brand history
GET    /api/health                    # Health check
```

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          RAILWAY                                │
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │   API Service   │◀──▶│   PostgreSQL    │                    │
│  │   (FastAPI)     │    │   (Railway)     │                    │
│  └────────┬────────┘    └─────────────────┘                    │
│           │                                                     │
│  ┌────────┴────────┐                                           │
│  │  Cron Service   │                                           │
│  │  (Weekly +      │                                           │
│  │   Daily jobs)   │                                           │
│  └─────────────────┘                                           │
│                                                                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ HTTPS API calls
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                          VERCEL                                 │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   Dashboard (Next.js)                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ Browser
                                ▼
                        ┌───────────────┐
                        │     User      │
                        └───────────────┘

External Services:
- Milled.com (scraping target)
- Anthropic API (LLM extraction)
- Google Calendar API (event sync)
- Resend (email notifications)
```

## Error Handling & Resilience

### Retry Policies
```python
# Scraping
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=30),
    retry=retry_if_exception_type((TimeoutError, NetworkError))
)
async def scrape_page(url: str): ...

# LLM calls
@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(5),
    retry=retry_if_exception_type(RateLimitError)
)
async def extract_sale(html: str): ...

# External APIs
@retry(
    stop=stop_after_attempt(2),
    wait=wait_fixed(2)
)
async def sync_calendar_event(event: dict): ...
```

### Failure Modes
| Component | Failure | Recovery |
|-----------|---------|----------|
| Scraper | Auth fails | Alert, retry next cycle |
| Scraper | Single page fails | Skip, log, continue |
| Extractor | LLM timeout | Retry with backoff |
| Extractor | Rate limit | Wait, retry |
| Calendar | API error | Log, retry next sync |
| Email | Delivery fails | Log, no retry (non-critical) |
| Database | Connection lost | Connection pool recovery |

## Security Considerations

1. **Credential Storage**: All secrets in environment variables, never in code
2. **No Authentication**: Dashboard has no auth (personal use); if deploying publicly, add basic auth
3. **Rate Limiting**: Respect Milled.com's rate limits to avoid blocking
4. **API Keys**: Rotate periodically, use least-privilege service accounts
5. **Data Privacy**: Scraped emails may contain personal data; don't expose raw HTML via API
