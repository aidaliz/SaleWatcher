# SKILLS.md — SaleWatcher

This document outlines the technical skills and domain knowledge required to build and maintain SaleWatcher.

## Core Technical Skills

### 1. Web Scraping with Playwright

**Required For**: Milled.com email extraction

**Key Capabilities**:
- Headless browser automation with Playwright (Python)
- Authentication flow handling (email/password login)
- Session persistence and cookie management
- Dynamic content waiting and element selection
- Rate limiting and polite scraping practices
- Error recovery and retry logic
- Screenshot/debugging for failed scrapes

**Specific Challenges**:
- Milled.com requires authenticated access
- Date range filtering via URL parameters or UI interaction
- Pagination through brand email archives
- Extracting email HTML content from rendered pages

### 2. LLM Integration (Anthropic Claude)

**Required For**: Sale detail extraction from email HTML

**Key Capabilities**:
- Anthropic Python SDK usage
- Prompt engineering for structured extraction
- JSON mode / structured output parsing
- Confidence scoring and self-assessment prompts
- Model selection (Haiku vs Sonnet) based on task complexity
- Token usage optimization
- Error handling for rate limits and API failures

**Specific Challenges**:
- Extracting discount percentages from varied language ("up to 50%", "BOGO", "extra 20% off clearance")
- Category classification from email content
- Identifying sale date ranges from promotional copy
- Distinguishing sitewide vs category-specific sales
- Handling stacked promotions

### 3. FastAPI Backend Development

**Required For**: API server, cron jobs, business logic

**Key Capabilities**:
- FastAPI application structure and routing
- Pydantic models for request/response validation
- Dependency injection patterns
- Async/await for I/O operations
- Background tasks and scheduling (APScheduler)
- Error handling and HTTP status codes
- OpenAPI documentation

### 4. PostgreSQL & SQLAlchemy

**Required For**: Data persistence

**Key Capabilities**:
- SQLAlchemy 2.0 ORM patterns
- Alembic migrations
- Relationship modeling (one-to-many, many-to-many)
- JSON column handling
- Query optimization and indexing
- Connection pooling
- Transaction management

**Schema Complexity**:
- Brands with configurable exclusions
- Raw emails linked to brands
- Extracted sales with confidence scores
- Sale windows (deduplicated)
- Predictions linked to historical windows
- Outcomes with auto/manual verification
- Adjustment suggestions

### 5. Next.js Dashboard Development

**Required For**: Review dashboard UI

**Key Capabilities**:
- Next.js 14 App Router
- Server Components vs Client Components
- Data fetching patterns (fetch in RSC, SWR/React Query for client)
- Tailwind CSS styling
- Form handling (approve/reject actions)
- Responsive design
- Loading and error states

**Dashboard Features**:
- Brand management (CRUD)
- Review queue with approve/reject
- Prediction browser with filters
- Accuracy reports and charts
- Adjustment suggestion review

### 6. Google Calendar API

**Required For**: Prediction calendar sync

**Key Capabilities**:
- Service account authentication
- Calendar event CRUD operations
- Event deduplication (prevent duplicates on re-sync)
- Timezone handling
- Batch operations for efficiency

### 7. Email Notifications (Resend)

**Required For**: Daily digests, prediction alerts

**Key Capabilities**:
- Resend SDK usage
- HTML email templates
- Action links (approve/reject from email)
- Delivery tracking

## Domain Knowledge

### 1. Retail Promotional Patterns

**Understanding Required**:
- Seasonal sale cycles (Back to School, Black Friday, etc.)
- Holiday-anchored vs fixed-date promotions
- Brand-specific patterns (Sephora VIB, Kohl's Cash, etc.)
- Discount structures (% off, BOGO, tiered, stackable)
- Exclusion patterns (luxury brands, new arrivals)

### 2. Amazon Online Arbitrage

**Context Required**:
- Why predicting sales matters for sourcing
- Lead time needed before sales (7 days chosen)
- Category relevance (excluding shoes/clothing)
- ROI considerations for different discount levels

### 3. Milled.com Structure

**Understanding Required**:
- How brand pages are organized
- Email archive navigation
- Date filtering capabilities
- Email content structure

## Infrastructure Skills

### 1. Railway Deployment

**Required For**: Backend hosting

**Key Capabilities**:
- Railway CLI and dashboard
- Environment variable management
- PostgreSQL provisioning
- Cron job configuration
- Log monitoring
- Cost management

### 2. Vercel Deployment

**Required For**: Dashboard hosting

**Key Capabilities**:
- Vercel CLI and dashboard
- Next.js deployment configuration
- Environment variables
- Build optimization

## Algorithm Design

### 1. Prediction Engine

**Logic Required**:
- Date matching with ±7 day window
- Holiday detection and date adjustment
- Pattern confidence scoring
- Multi-year trend analysis (future enhancement)

### 2. Deduplication

**Logic Required**:
- Grouping emails about same sale event
- Date range overlap detection
- Discount similarity matching
- Brand-specific heuristics

### 3. Accuracy Tracking

**Logic Required**:
- Auto-verification matching algorithm
- Per-brand reliability scoring
- Timing delta calculation
- Adjustment suggestion generation

## Testing Skills

### 1. Pytest

**Required For**: Backend testing

**Key Capabilities**:
- Fixtures and conftest patterns
- Async test support
- Mocking (pytest-mock, responses)
- Coverage reporting
- Integration test patterns with test database

### 2. Component Testing

**Required For**: Dashboard testing

**Key Capabilities**:
- React Testing Library
- Mock API responses
- User interaction simulation

## Security Awareness

### Required Considerations:
- Credential storage (environment variables only)
- No authentication needed (personal use) but understand implications
- API rate limiting concepts
- Data privacy for scraped content

## Learning Resources

### Playwright
- https://playwright.dev/python/docs/intro

### Anthropic Claude
- https://docs.anthropic.com/en/docs/intro-to-claude

### FastAPI
- https://fastapi.tiangolo.com/

### SQLAlchemy 2.0
- https://docs.sqlalchemy.org/en/20/

### Next.js App Router
- https://nextjs.org/docs/app

### Google Calendar API
- https://developers.google.com/calendar/api/quickstart/python

### Resend
- https://resend.com/docs/send-with-python

### Railway
- https://docs.railway.app/

### Vercel
- https://vercel.com/docs
