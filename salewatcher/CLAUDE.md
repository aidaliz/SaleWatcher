# CLAUDE.md — SaleWatcher

This file provides context and instructions for Claude Code when working on SaleWatcher.

## Project Overview

SaleWatcher is a sales prediction system for Amazon Online Arbitrage. It:
1. Scrapes promotional emails from Milled.com for target retail brands
2. Uses LLMs to extract sale details (discount %, categories, dates)
3. Identifies seasonal patterns from 1 year of historical data
4. Predicts when similar sales will occur this year
5. Syncs predictions to Google Calendar with 7-day advance notice
6. Tracks prediction accuracy and learns from outcomes

## Issue Tracking

**IMPORTANT: This project uses `bd` (beads) for ALL issue tracking.**

Do NOT use markdown TODOs, task lists, or other tracking methods. All work items must be tracked in beads.

### Common Commands

```bash
# View ready work
bd ready
bd ready --json

# Create issues
bd create "Issue title" --description="Details" -t task -p 1 --json
bd create "Bug description" -t bug -p 0 --json
bd create "Feature name" -t feature -p 2 --json

# Update and close
bd update <id> --status in_progress
bd update <id> --notes "Progress update"
bd close <id>

# Dependencies
bd dep add <child-id> <parent-id>  # child depends on parent
bd blocked                         # show blocked issues
```

### Priority Levels
- **P0**: Critical/blocking — must be done immediately
- **P1**: High — important for current milestone
- **P2**: Medium — should be done soon
- **P3**: Low — nice to have
- **P4**: Backlog — future consideration

### Issue Types
- **bug**: Something broken
- **feature**: New capability
- **task**: Implementation work, refactoring, docs

## Tech Stack

### Backend (Python)
- **Framework**: FastAPI with Pydantic for validation
- **Database**: PostgreSQL with SQLAlchemy ORM + Alembic migrations
- **Scraping**: Playwright (headless Chromium) for Milled.com
- **LLM**: Anthropic SDK — Haiku 4.5 primary, Sonnet 4.5 fallback
- **Scheduling**: APScheduler for cron jobs
- **HTTP Client**: httpx for async requests
- **Email**: Resend SDK

### Dashboard (TypeScript/React)
- **Framework**: Next.js 14 with App Router
- **Styling**: Tailwind CSS
- **State**: React hooks (no external state management needed)
- **API Client**: fetch with typed responses

### Infrastructure
- **Backend Hosting**: Railway (includes PostgreSQL)
- **Dashboard Hosting**: Vercel
- **Calendar**: Google Calendar API (service account)

## Code Standards

### Python
```python
# Use type hints everywhere
def extract_sale(email_html: str, brand: Brand) -> ExtractedSale:
    ...

# Pydantic for all data models
class ExtractedSale(BaseModel):
    discount_type: DiscountType
    discount_value: float
    categories: list[str]
    confidence: float

# Async for I/O operations
async def scrape_brand(brand: Brand) -> list[RawEmail]:
    async with async_playwright() as p:
        ...

# Use tenacity for retries
@retry(stop=stop_after_attempt(3), wait=wait_exponential())
async def call_llm(prompt: str) -> str:
    ...
```

### TypeScript/React
```typescript
// Use TypeScript strictly
interface Prediction {
  id: string;
  brandId: string;
  predictedStart: Date;
  discountSummary: string;
}

// Server Components by default, Client Components when needed
'use client'  // Only for interactive components

// Fetch in Server Components
async function PredictionList() {
  const predictions = await fetchPredictions();
  return <div>...</div>;
}
```

### Database
```sql
-- Use snake_case for all identifiers
-- Include created_at/updated_at on all tables
-- Use UUIDs for primary keys
-- Add indexes for frequently queried columns
```

## Key Architectural Decisions

### LLM Extraction Strategy
1. **Haiku First**: Process all emails with Haiku 4.5 (fast, cheap)
2. **Confidence Scoring**: Haiku self-reports confidence 0.0-1.0
3. **Sonnet Fallback**: Re-process low-confidence (<0.7) with Sonnet 4.5
4. **Review Queue**: Very low confidence (<0.5) goes to human review

### Prediction Logic
1. **±7 Day Window**: Match sales occurring within 7 days of last year's date
2. **Holiday Anchoring**: Detect holiday-proximate sales, adjust to current year holiday
3. **High Confidence Only**: Only predict sales with clear historical precedent
4. **Deduplication**: Group related emails into single "sale window"

### Verification Flow
1. **Auto-Verify**: Check if actual sale occurred during prediction window
2. **Manual Override**: User can correct auto-verification
3. **Accuracy Tracking**: Per-brand reliability scores
4. **Adjustment Suggestions**: System proposes calibration when patterns shift

## File Naming Conventions

```
backend/src/
├── api/
│   ├── main.py              # FastAPI app initialization
│   ├── routes/
│   │   ├── brands.py        # /api/brands endpoints
│   │   ├── predictions.py   # /api/predictions endpoints
│   │   └── review.py        # /api/review endpoints
│   └── deps.py              # Dependency injection
├── scraper/
│   ├── milled.py            # Milled.com scraper
│   └── auth.py              # Session management
├── extractor/
│   ├── llm.py               # Claude API calls
│   ├── prompts.py           # Extraction prompts
│   └── parser.py            # Response parsing
├── db/
│   ├── models.py            # SQLAlchemy models
│   ├── session.py           # Database connection
│   └── crud/                # CRUD operations per entity
```

## Testing Strategy

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific module
pytest tests/test_extractor.py

# Run marked tests
pytest -m "not slow"
```

### Test Categories
- **Unit tests**: Pure logic (extractors, parsers, predictors)
- **Integration tests**: Database operations, API endpoints
- **E2E tests**: Full pipeline with mocked external services

## Environment Setup

### Required Environment Variables
```env
# Required
DATABASE_URL=postgresql://...
MILLED_EMAIL=...
MILLED_PASSWORD=...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_CREDENTIALS_JSON={...}
GOOGLE_CALENDAR_ID=...

# Optional
RESEND_API_KEY=re_...          # For email notifications
NOTIFICATION_EMAIL=...          # Where to send digests
DASHBOARD_URL=...               # For email links
LOG_LEVEL=INFO                  # DEBUG, INFO, WARNING, ERROR
```

### Local Development
```bash
# Copy example env
cp .env.example .env

# Edit with your credentials
$EDITOR .env

# Source for local dev
source .env
```

## Common Tasks

### Adding a New Brand
1. Add brand to database via dashboard or API
2. Verify Milled.com slug is correct
3. Configure category exclusions if needed
4. Run historical backfill: `python scripts/backfill.py --brand "Brand Name"`

### Debugging Extraction Issues
1. Check `raw_emails` table for the email HTML
2. Test extraction in isolation: `python -m src.extractor.llm --email-id <id>`
3. Compare Haiku vs Sonnet output if confidence is low

### Manual Prediction Verification
1. Open dashboard → Accuracy tab
2. Find prediction in "Recent Outcomes"
3. Click Override if auto-verification is incorrect
4. Add optional reason for audit trail

## Deployment

### Railway (Backend)
```bash
# Railway CLI
railway login
railway link
railway up

# Or push to connected GitHub branch
git push origin main
```

### Vercel (Dashboard)
```bash
# Vercel CLI
vercel

# Or push to connected GitHub branch
git push origin main
```

## Monitoring

### Key Metrics
- Scrape success rate per brand
- Extraction confidence distribution
- Prediction accuracy (hit rate)
- API response times
- Error rates by component

### Logs
- Railway dashboard for backend logs
- Vercel dashboard for dashboard logs
- Structured JSON logging for production

## Security Notes

- Milled.com credentials stored only in environment variables
- Google service account key never committed
- API has no authentication (personal use only)
- Database access restricted to Railway internal network
