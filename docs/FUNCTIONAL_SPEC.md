# FUNCTIONAL_SPEC.md — SaleWatcher

This document specifies the complete functional requirements for SaleWatcher.

## 1. User Stories

### 1.1 Brand Management

**US-1.1**: As a user, I want to add a new brand to track so that I can receive predictions for that brand's sales.

**Acceptance Criteria**:
- Can add brand with name and Milled.com slug
- Can configure excluded categories per brand
- Brand appears in dashboard brand list
- System begins scraping brand on next weekly cycle

**US-1.2**: As a user, I want to edit a brand's settings so that I can adjust category exclusions.

**Acceptance Criteria**:
- Can edit brand name and excluded categories
- Can activate/deactivate brand
- Changes take effect on next scrape cycle

**US-1.3**: As a user, I want to see all tracked brands and their status.

**Acceptance Criteria**:
- Dashboard shows all brands with:
  - Name
  - Active/inactive status
  - Last scrape date
  - Email count
  - Reliability score

---

### 1.2 Email Scraping

**US-2.1**: As a user, I want the system to automatically scrape promotional emails weekly.

**Acceptance Criteria**:
- Scraper runs every Sunday at 2 AM (configurable)
- Downloads last 7 days of emails for each active brand
- Stores raw HTML and metadata in database
- Logs scrape success/failure per brand

**US-2.2**: As a user, I want to trigger a historical backfill for a brand.

**Acceptance Criteria**:
- Can trigger backfill via API or dashboard
- Backfill scrapes full year of history
- Progress is visible (emails processed / total)
- Does not duplicate existing emails

---

### 1.3 Sale Extraction

**US-3.1**: As a user, I want emails to be automatically analyzed for sale details.

**Acceptance Criteria**:
- Extraction runs after each scrape
- Uses Haiku 4.5 for initial extraction
- Low-confidence extractions reprocessed with Sonnet 4.5
- Extracted data includes:
  - Discount type and value
  - Categories included/excluded
  - Sale date range
  - Confidence score

**US-3.2**: As a user, I want to review borderline extractions before they affect predictions.

**Acceptance Criteria**:
- Extractions with confidence < 0.5 go to review queue
- Review queue shows:
  - Email subject and date
  - Extracted values
  - Confidence score
  - Original email preview
- Can approve (accept extraction) or reject (discard)

**US-3.3**: As a user, I want to receive a daily email digest of items needing review.

**Acceptance Criteria**:
- Email sent at 8 AM if review queue is non-empty
- Digest frequency is configurable (daily, weekly, never)
- Email includes direct approve/reject links
- Links work without dashboard login

---

### 1.4 Sale Deduplication

**US-4.1**: As a user, I want related emails to be grouped into single sale events.

**Acceptance Criteria**:
- Emails about same sale grouped into "sale window"
- Grouping logic considers:
  - Same brand
  - Overlapping dates (within 3 days)
  - Similar discount structure
- Sale windows have:
  - Combined date range
  - Summary discount description
  - Links to all source emails

---

### 1.5 Prediction Generation

**US-5.1**: As a user, I want predictions based on last year's sales patterns.

**Acceptance Criteria**:
- Predictions generated for each historical sale window
- Predicted dates use ±7 day window from last year
- Holiday-anchored sales adjust to current year holidays
- Only high-confidence predictions shown (clear historical precedent)

**US-5.2**: As a user, I want predictions to account for floating holidays.

**Acceptance Criteria**:
- System detects sales within 3 days of holiday
- Predictions adjust to current year's holiday date
- Supported holidays:
  - New Year's Day
  - MLK Day
  - Presidents' Day
  - Memorial Day
  - Independence Day
  - Labor Day
  - Columbus Day
  - Veterans Day
  - Thanksgiving
  - Black Friday
  - Cyber Monday
  - Christmas
  - Back to School (August 1)

---

### 1.6 Calendar Integration

**US-6.1**: As a user, I want predictions to appear on my Google Calendar.

**Acceptance Criteria**:
- Calendar events created 7 days before predicted sale start
- Event includes:
  - Brand name
  - Discount summary
  - Link to reference email from last year
  - Confidence indicator
- Events sync automatically after prediction generation

**US-6.2**: As a user, I want calendar events updated if predictions change.

**Acceptance Criteria**:
- Changed predictions update existing calendar events
- Deleted predictions remove calendar events
- No duplicate events for same prediction

---

### 1.7 Outcome Verification

**US-7.1**: As a user, I want the system to automatically verify if predictions were accurate.

**Acceptance Criteria**:
- Verification runs daily after prediction window ends
- Checks if matching sale was scraped during window
- Marks prediction as HIT or MISS
- Records actual dates and discount if found

**US-7.2**: As a user, I want to override automatic verification when incorrect.

**Acceptance Criteria**:
- Dashboard shows recent outcomes with auto-verification result
- Can override HIT to MISS or vice versa
- Can add optional reason for override
- Override is recorded with timestamp

---

### 1.8 Accuracy Tracking

**US-8.1**: As a user, I want to see prediction accuracy per brand.

**Acceptance Criteria**:
- Dashboard accuracy page shows:
  - Overall hit rate
  - Average timing delta (days off)
  - Per-brand breakdown table
  - Reliability tier per brand (Excellent/Good/Fair/Poor)

**US-8.2**: As a user, I want to see historical accuracy trends.

**Acceptance Criteria**:
- Chart showing hit rate over time
- Filterable by brand
- Filterable by date range

---

### 1.9 Adjustment Suggestions

**US-9.1**: As a user, I want suggestions when prediction patterns shift.

**Acceptance Criteria**:
- System detects consistent timing shifts (3+ predictions off by same amount)
- System detects pattern changes (e.g., sale no longer holiday-anchored)
- Suggestions shown in dashboard with:
  - Description of detected pattern
  - Recommended adjustment
  - Supporting evidence

**US-9.2**: As a user, I want to approve or dismiss adjustment suggestions.

**Acceptance Criteria**:
- Can approve suggestion (system applies adjustment)
- Can dismiss suggestion (system ignores)
- Dismissed suggestions don't reappear

---

### 1.10 Email Notifications

**US-10.1**: As a user, I want weekly email summaries of upcoming predictions.

**Acceptance Criteria**:
- Email sent every Monday at 8 AM
- Lists predictions for next 14 days
- Grouped by brand
- Links to dashboard for full view

**US-10.2**: As a user, I want alerts when brand accuracy drops.

**Acceptance Criteria**:
- Alert triggered when brand drops below 60% hit rate
- Email includes:
  - Brand name
  - Current accuracy
  - Recent prediction history
  - Link to brand details

---

## 2. Dashboard Screens

### 2.1 Home / Overview

**Purpose**: Quick status check

**Content**:
- Upcoming predictions (next 7 days)
- Review queue count (if > 0)
- Recent outcomes summary
- Quick stats (total predictions, hit rate)

### 2.2 Brands

**Purpose**: Manage tracked brands

**Features**:
- List all brands with status indicators
- Add new brand form
- Edit brand (name, slug, exclusions)
- Deactivate/reactivate brand
- View brand detail page with:
  - Email history
  - Predictions history
  - Accuracy stats

### 2.3 Review Queue

**Purpose**: Approve/reject borderline extractions

**Features**:
- List pending reviews sorted by date
- Each item shows:
  - Email subject and brand
  - Extracted values
  - Confidence score
  - Preview of email
- Approve/reject buttons
- View original email link

### 2.4 Predictions

**Purpose**: Browse all predictions

**Features**:
- Filter by:
  - Brand
  - Date range
  - Status (upcoming, past, verified)
- Sort by predicted date
- Each prediction shows:
  - Brand
  - Predicted dates
  - Discount summary
  - Confidence tier
  - Outcome (if past)

### 2.5 Accuracy

**Purpose**: View prediction performance

**Features**:
- Overall stats at top
- Per-brand table with:
  - Hit rate
  - Avg timing delta
  - Reliability tier
  - Trend indicator (improving/declining)
- Recent outcomes list with override option
- Adjustment suggestions section

### 2.6 Settings

**Purpose**: Configure system behavior

**Features**:
- Notification preferences:
  - Review digest frequency
  - Weekly summary on/off
  - Accuracy alerts threshold
- Calendar settings:
  - Days before prediction for alert
- Scraping settings:
  - Scrape schedule (day/time)

---

## 3. Data Specifications

### 3.1 Brand

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | Auto | Unique identifier |
| name | string | Yes | Display name |
| milled_slug | string | Yes | URL slug on Milled.com |
| is_active | boolean | Yes | Whether to scrape |
| excluded_categories | string[] | No | Categories to ignore |
| created_at | datetime | Auto | |
| updated_at | datetime | Auto | |

### 3.2 Raw Email

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | Auto | |
| brand_id | UUID | Yes | Foreign key to brand |
| milled_url | string | Yes | Unique URL on Milled |
| subject | string | Yes | Email subject line |
| sent_at | date | Yes | Date email was sent |
| html_content | text | Yes | Full email HTML |
| scraped_at | datetime | Auto | When we scraped it |

### 3.3 Extracted Sale

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | Auto | |
| email_id | UUID | Yes | Foreign key to email |
| discount_type | enum | Yes | percent_off, bogo, fixed_price, free_shipping, other |
| discount_value | float | No | e.g., 25.0 for "25% off" |
| discount_max | float | No | For "up to X%" |
| is_sitewide | boolean | Yes | |
| categories | string[] | No | Applicable categories |
| excluded_categories | string[] | No | Excluded categories |
| conditions | string[] | No | Requirements/restrictions |
| sale_start | date | No | |
| sale_end | date | No | |
| confidence | float | Yes | 0.0 - 1.0 |
| raw_discount_text | string | No | Original text |
| model_used | string | Yes | haiku-4.5 or sonnet-4.5 |
| review_status | enum | Yes | pending, approved, rejected |
| reviewed_at | datetime | No | |

### 3.4 Sale Window

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | Auto | |
| brand_id | UUID | Yes | |
| name | string | Yes | Generated description |
| discount_summary | string | Yes | e.g., "20-25% off sitewide" |
| start_date | date | Yes | |
| end_date | date | Yes | |
| linked_email_ids | UUID[] | Yes | Related emails |
| holiday_anchor | string | No | e.g., "memorial_day" |
| categories | string[] | No | |
| year | integer | Yes | |

### 3.5 Prediction

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | Auto | |
| brand_id | UUID | Yes | |
| source_window_id | UUID | Yes | Last year's sale window |
| predicted_start | date | Yes | |
| predicted_end | date | Yes | |
| discount_summary | string | Yes | |
| milled_reference_url | string | Yes | Link to last year's email |
| confidence | float | Yes | |
| calendar_event_id | string | No | Google Calendar event ID |
| notified_at | datetime | No | When user was notified |

### 3.6 Prediction Outcome

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | Auto | |
| prediction_id | UUID | Yes | |
| auto_result | enum | Yes | hit, miss, pending |
| auto_verified_at | datetime | No | |
| matched_email_ids | UUID[] | No | Emails that matched |
| manual_override | boolean | Yes | Default false |
| manual_result | enum | No | hit, miss |
| override_reason | string | No | |
| overridden_at | datetime | No | |
| actual_start | date | No | |
| actual_end | date | No | |
| actual_discount | float | No | |
| timing_delta_days | integer | No | Days off from prediction |
| discount_delta_percent | float | No | % off from prediction |

### 3.7 Brand Accuracy Stats

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | Auto | |
| brand_id | UUID | Yes | Unique |
| total_predictions | integer | Yes | |
| correct_predictions | integer | Yes | |
| hit_rate | float | Yes | |
| avg_timing_delta_days | float | No | |
| timing_delta_std | float | No | |
| avg_discount_delta_percent | float | No | |
| reliability_score | integer | Yes | 0-100 |
| reliability_tier | enum | Yes | excellent, good, fair, poor |
| last_calculated_at | datetime | Yes | |

### 3.8 Adjustment Suggestion

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | Auto | |
| brand_id | UUID | Yes | |
| suggestion_type | enum | Yes | timing_shift, pattern_change, confidence_adjust |
| description | string | Yes | Human-readable description |
| recommended_action | string | Yes | What to do |
| supporting_data | JSON | Yes | Evidence |
| status | enum | Yes | pending, approved, dismissed |
| resolved_at | datetime | No | |

---

## 4. Business Rules

### 4.1 Discount Threshold
- Only track sales with 20%+ discount
- "Up to X%" promotions: use X as the value
- BOGO: treat as 50% off
- Exclude promotions that only apply to shoes/clothing (per default)

### 4.2 Prediction Confidence
- **High confidence**: Same sale occurred at same time last year, clear pattern
- **Medium confidence**: Similar sale occurred, slight timing variation
- **Low confidence**: Inferred from partial data

Only high-confidence predictions are shown to user.

### 4.3 Review Queue Thresholds
- Confidence < 0.5 → Goes to review queue
- Confidence 0.5-0.7 → Reprocessed with Sonnet, may go to queue
- Confidence > 0.7 → Auto-approved

### 4.4 Holiday Detection
- Sale is holiday-anchored if start date is within ±3 days of holiday
- Holiday list is fixed (see US-5.2)

### 4.5 Deduplication Rules
- Same brand, same week, similar discount = same sale window
- "Similar discount" = same type AND value within 5%

### 4.6 Outcome Verification
- Check window: prediction dates ±7 days
- Match criteria: same brand, 15%+ discount (allows some tolerance)
- Auto-verify runs 1 day after prediction end date

### 4.7 Reliability Scoring
```
Score = (hit_rate × 60) + (20 - avg_timing_delta) + (20 - avg_discount_delta)

Tier:
- 85+: Excellent
- 70-84: Good
- 55-69: Fair
- <55: Poor
```

### 4.8 Adjustment Suggestion Triggers
- **Timing shift**: 3+ consecutive predictions off by ≥2 days in same direction
- **Pattern change**: 3+ missed predictions for a sale that was consistent
- **Confidence adjust**: Brand accuracy drops 15%+ from historical baseline

---

## 5. Non-Functional Requirements

### 5.1 Performance
- Scrape complete in under 30 minutes for 10 brands
- Dashboard pages load in under 2 seconds
- API endpoints respond in under 500ms

### 5.2 Reliability
- Weekly scrape succeeds 95%+ of the time
- Failed scrapes automatically retry next cycle
- Email notifications have 99%+ delivery rate

### 5.3 Scalability
- Support up to 50 brands
- Support up to 10,000 emails per brand
- 1 year of predictions (365 potential events × 50 brands)

### 5.4 Cost
- Total monthly cost under $50
- LLM costs optimized via Haiku-first strategy

### 5.5 Maintainability
- Scraper selectors documented and easy to update
- LLM prompts versioned and configurable
- Database migrations managed via Alembic

---

## 6. Initial Brand Configuration

| Brand | Milled Slug | Excluded Categories |
|-------|-------------|---------------------|
| Target | target | shoes, clothing, apparel |
| Walmart | walmart | shoes, clothing, apparel |
| Kohl's | kohls | shoes, clothing, apparel |
| Sephora | sephora | — |
| Bath & Body Works | bath-body-works | — |
| Huda Beauty | hudabeauty | — |
| Summer Fridays | summerfridays | — |
| REVOLVE | revolve | clothing, shoes, apparel |
| Skullcandy | skullcandy | — |
| GameStop | gamestop | — |

**Note**: Milled slugs need to be verified against actual Milled.com URLs.
