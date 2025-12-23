# SaleWatcher

**Predict retail sales from historical Milled.com newsletter data for Amazon Online Arbitrage sourcing.**

SaleWatcher scrapes historical promotional emails from Milled.com, uses LLMs to extract sale details, identifies patterns, and predicts when future sales will occur — giving you a competitive edge in sourcing inventory before sales go live.

## Problem Statement

As an Amazon Online Arbitrage reseller, knowing when retailers will run promotions is critical for:
- Preparing capital and inventory space
- Monitoring specific products before sales hit
- Being first to source profitable deals

Retailers follow predictable seasonal patterns. SaleWatcher analyzes 1 year of historical newsletter data to predict when sales will recur.

## Key Features

- **Automated Milled.com Scraping** — Weekly extraction of promotional emails from 10+ retail brands
- **LLM-Powered Extraction** — Claude Haiku 4.5 parses discount percentages, categories, and sale types with Sonnet 4.5 fallback for edge cases
- **Smart Deduplication** — Groups related emails into unified "sale windows"
- **Holiday Anchoring** — Adjusts predictions for floating holidays (Memorial Day, Labor Day, etc.)
- **Prediction Accuracy Feedback** — Auto-verifies predictions with manual override, learns from outcomes
- **Google Calendar Integration** — Events appear 7 days before predicted sales
- **Review Dashboard** — Approve borderline extractions, manage brands, view accuracy reports

## Target Brands (Initial)

| Brand | Category Focus |
|-------|----------------|
| Target | All except shoes/clothing |
| Walmart | All except shoes/clothing |
| Kohl's | All except shoes/clothing |
| Sephora | Beauty |
| Bath & Body Works | Beauty/Home |
| Huda Beauty | Beauty |
| Summer Fridays | Beauty |
| REVOLVE | Beauty (exclude clothing) |
| Skullcandy | Electronics |
| GameStop | Gaming/Electronics |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend API | Python 3.11+ / FastAPI |
| Scraping | Playwright (headless Chromium) |
| LLM | Claude Haiku 4.5 + Sonnet 4.5 fallback |
| Database | PostgreSQL |
| Dashboard | Next.js 14 / React / Tailwind CSS |
| Calendar | Google Calendar API |
| Email | Resend |
| Backend Hosting | Railway |
| Dashboard Hosting | Vercel |

## Project Structure

```
salewatcher/
├── backend/
│   ├── src/
│   │   ├── api/              # FastAPI routes & endpoints
│   │   ├── scraper/          # Milled.com authentication & scraping
│   │   ├── extractor/        # LLM-based sale extraction
│   │   ├── deduplicator/     # Sale window grouping
│   │   ├── predictor/        # Pattern analysis & prediction engine
│   │   ├── verifier/         # Outcome verification & accuracy tracking
│   │   ├── notifier/         # Email notifications (Resend)
│   │   ├── calendar/         # Google Calendar sync
│   │   ├── db/               # SQLAlchemy models & migrations
│   │   └── config/           # Settings & environment
│   ├── scripts/              # Cron job entry points
│   ├── tests/                # Pytest test suite
│   ├── alembic/              # Database migrations
│   └── requirements.txt
├── dashboard/
│   ├── src/
│   │   ├── app/              # Next.js App Router pages
│   │   ├── components/       # React components
│   │   └── lib/              # API client, utilities
│   └── package.json
├── docs/
│   ├── ARCHITECTURE.md       # System design details
│   ├── FUNCTIONAL_SPEC.md    # Feature specifications
│   └── PLAN.md               # Implementation roadmap
├── CLAUDE.md                 # Instructions for Claude Code
├── SKILLS.md                 # Required capabilities
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Milled.com subscription (paid)
- Anthropic API key
- Google Cloud project with Calendar API
- Resend account

### Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:pass@host:5432/salewatcher

# Milled.com
MILLED_EMAIL=your@email.com
MILLED_PASSWORD=your_password

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Google Calendar
GOOGLE_CREDENTIALS_JSON={"type":"service_account",...}
GOOGLE_CALENDAR_ID=your-calendar@group.calendar.google.com

# Resend
RESEND_API_KEY=re_...
NOTIFICATION_EMAIL=your@email.com

# Dashboard
DASHBOARD_URL=https://your-dashboard.vercel.app
```

### Local Development

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
alembic upgrade head
uvicorn src.api.main:app --reload

# Dashboard
cd dashboard
npm install
npm run dev
```

## Estimated Costs

| Service | Monthly Cost |
|---------|-------------|
| Railway (backend + DB) | ~$10-15 |
| Vercel (dashboard) | Free tier |
| Claude API | ~$5-10 |
| Resend | Free tier |
| **Total** | **~$15-25** |

## License

MIT
