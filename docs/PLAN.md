# PLAN.md — SaleWatcher Implementation Plan

This document outlines the implementation plan for SaleWatcher, organized for use with beads (`bd`) task tracking.

## Phase Overview

```
Phase 0: Project Setup                    [Week 1, Days 1-2]
Phase 1: Core Backend Infrastructure      [Week 1, Days 3-5]
Phase 2: Scraper & Extractor              [Week 2]
Phase 3: Prediction Engine                [Week 3, Days 1-3]
Phase 4: Calendar & Notifications         [Week 3, Days 4-5]
Phase 5: Dashboard MVP                    [Week 4]
Phase 6: Feedback Loop                    [Week 5, Days 1-3]
Phase 7: Testing & Polish                 [Week 5, Days 4-5]
```

---

## Phase 0: Project Setup

**Goal**: Initialize repository, configure environments, set up CI/CD.

### Beads to Create

```bash
# Epic
bd create "Phase 0: Project Setup" -t feature -p 1 \
  --description="Initialize repository, environments, and CI/CD"

# Tasks
bd create "Initialize Git repository and push to GitHub" -t task -p 0 \
  --description="Create repo, add .gitignore, initial commit, push to GitHub"

bd create "Set up backend project structure" -t task -p 1 \
  --description="Create Python project with FastAPI, requirements.txt, src/ layout"

bd create "Set up dashboard project structure" -t task -p 1 \
  --description="Create Next.js 14 project with App Router, Tailwind CSS"

bd create "Configure Railway backend deployment" -t task -p 1 \
  --description="Link repo, configure build, add PostgreSQL, set env vars"

bd create "Configure Vercel dashboard deployment" -t task -p 1 \
  --description="Link repo, set root directory, configure env vars"

bd create "Set up beads for task tracking" -t task -p 0 \
  --description="bd init, configure project prefix, create initial issues"

bd create "Create .env.example files" -t task -p 2 \
  --description="Document all required environment variables for backend and dashboard"
```

### Dependencies
```bash
bd dep add "Set up backend project structure" "Initialize Git repository and push to GitHub"
bd dep add "Set up dashboard project structure" "Initialize Git repository and push to GitHub"
bd dep add "Configure Railway backend deployment" "Set up backend project structure"
bd dep add "Configure Vercel dashboard deployment" "Set up dashboard project structure"
```

---

## Phase 1: Core Backend Infrastructure

**Goal**: Database models, migrations, basic API structure.

### Beads to Create

```bash
# Epic
bd create "Phase 1: Core Backend Infrastructure" -t feature -p 1 \
  --description="Database models, migrations, FastAPI setup"

# Tasks
bd create "Create SQLAlchemy models for all entities" -t task -p 0 \
  --description="Brand, RawEmail, ExtractedSale, SaleWindow, Prediction, PredictionOutcome, BrandAccuracyStats, AdjustmentSuggestion"

bd create "Set up Alembic migrations" -t task -p 1 \
  --description="Initialize Alembic, create initial migration, test upgrade/downgrade"

bd create "Create database session management" -t task -p 1 \
  --description="Connection pooling, async session factory, dependency injection"

bd create "Implement CRUD operations for Brand" -t task -p 1 \
  --description="Create, read, update, deactivate brands with validation"

bd create "Create FastAPI application structure" -t task -p 1 \
  --description="Main app, routers, dependency injection, error handling"

bd create "Implement /api/brands endpoints" -t task -p 2 \
  --description="GET list, POST create, GET detail, PATCH update, DELETE deactivate"

bd create "Implement /api/health endpoint" -t task -p 2 \
  --description="Basic health check returning DB connection status"

bd create "Add Pydantic schemas for all entities" -t task -p 1 \
  --description="Request/response models with validation"

bd create "Configure logging and error handling" -t task -p 2 \
  --description="Structured JSON logging, global exception handler"
```

### Dependencies
```bash
bd dep add "Set up Alembic migrations" "Create SQLAlchemy models for all entities"
bd dep add "Create database session management" "Set up Alembic migrations"
bd dep add "Implement CRUD operations for Brand" "Create database session management"
bd dep add "Create FastAPI application structure" "Create database session management"
bd dep add "Implement /api/brands endpoints" "Create FastAPI application structure"
bd dep add "Implement /api/brands endpoints" "Implement CRUD operations for Brand"
bd dep add "Implement /api/brands endpoints" "Add Pydantic schemas for all entities"
bd dep add "Implement /api/health endpoint" "Create FastAPI application structure"
```

---

## Phase 2: Scraper & Extractor

**Goal**: Milled.com scraping and LLM-based extraction.

### Beads to Create

```bash
# Epic
bd create "Phase 2: Scraper & Extractor" -t feature -p 1 \
  --description="Milled.com scraping and Claude-based sale extraction"

# Scraper tasks
bd create "Implement Milled.com authentication" -t task -p 0 \
  --description="Playwright login flow with session persistence, handle auth failures"

bd create "Implement brand page navigation" -t task -p 1 \
  --description="Navigate to brand page, apply date filters, handle pagination"

bd create "Implement email content extraction" -t task -p 1 \
  --description="Extract subject, sent date, URL, full HTML content"

bd create "Implement scraper error handling" -t task -p 1 \
  --description="Retry logic, screenshot on failure, skip bad emails, alert on brand failure"

bd create "Create scraper entry point script" -t task -p 2 \
  --description="CLI script for manual runs and cron invocation"

bd create "Implement historical backfill command" -t task -p 2 \
  --description="Scrape full year of history for a brand"

# Extractor tasks
bd create "Create Anthropic client wrapper" -t task -p 1 \
  --description="Async client, retry on rate limit, model selection"

bd create "Design extraction prompt" -t task -p 0 \
  --description="Prompt for structured sale extraction with confidence scoring"

bd create "Implement Haiku extraction" -t task -p 1 \
  --description="Primary extraction with Haiku 4.5, parse JSON response"

bd create "Implement Sonnet fallback" -t task -p 1 \
  --description="Re-process low-confidence extractions with Sonnet 4.5"

bd create "Implement extraction result parsing" -t task -p 1 \
  --description="Parse LLM JSON response, validate, map to ExtractedSale model"

bd create "Create extraction entry point" -t task -p 2 \
  --description="Process pending emails, update database with results"

bd create "Implement review queue logic" -t task -p 2 \
  --description="Route low-confidence extractions to review queue"
```

### Dependencies
```bash
bd dep add "Implement brand page navigation" "Implement Milled.com authentication"
bd dep add "Implement email content extraction" "Implement brand page navigation"
bd dep add "Implement scraper error handling" "Implement email content extraction"
bd dep add "Create scraper entry point script" "Implement scraper error handling"
bd dep add "Implement historical backfill command" "Create scraper entry point script"

bd dep add "Implement Haiku extraction" "Create Anthropic client wrapper"
bd dep add "Implement Haiku extraction" "Design extraction prompt"
bd dep add "Implement Sonnet fallback" "Implement Haiku extraction"
bd dep add "Implement extraction result parsing" "Implement Haiku extraction"
bd dep add "Create extraction entry point" "Implement extraction result parsing"
bd dep add "Create extraction entry point" "Implement Sonnet fallback"
bd dep add "Implement review queue logic" "Create extraction entry point"
```

---

## Phase 3: Prediction Engine

**Goal**: Deduplication, pattern detection, prediction generation.

### Beads to Create

```bash
# Epic
bd create "Phase 3: Prediction Engine" -t feature -p 1 \
  --description="Deduplication, holiday detection, prediction generation"

# Tasks
bd create "Implement sale deduplication" -t task -p 0 \
  --description="Group related emails into sale windows based on dates and discount similarity"

bd create "Create holiday calendar utility" -t task -p 1 \
  --description="Functions to compute holiday dates for any year (Memorial Day, etc.)"

bd create "Implement holiday anchor detection" -t task -p 1 \
  --description="Detect if sale is within ±3 days of a holiday"

bd create "Implement prediction date calculation" -t task -p 1 \
  --description="Calculate predicted dates with holiday adjustment"

bd create "Implement prediction generation" -t task -p 0 \
  --description="Generate predictions from historical sale windows"

bd create "Create prediction confidence scoring" -t task -p 2 \
  --description="Score predictions based on historical consistency"

bd create "Implement /api/predictions endpoints" -t task -p 2 \
  --description="GET list, GET upcoming, GET detail"

bd create "Create predictor entry point script" -t task -p 2 \
  --description="CLI for manual prediction generation"
```

### Dependencies
```bash
bd dep add "Implement holiday anchor detection" "Create holiday calendar utility"
bd dep add "Implement prediction date calculation" "Implement holiday anchor detection"
bd dep add "Implement prediction generation" "Implement sale deduplication"
bd dep add "Implement prediction generation" "Implement prediction date calculation"
bd dep add "Create prediction confidence scoring" "Implement prediction generation"
bd dep add "Implement /api/predictions endpoints" "Implement prediction generation"
bd dep add "Create predictor entry point script" "Implement prediction generation"
```

---

## Phase 4: Calendar & Notifications

**Goal**: Google Calendar sync and email notifications.

### Beads to Create

```bash
# Epic
bd create "Phase 4: Calendar & Notifications" -t feature -p 1 \
  --description="Google Calendar sync and Resend email notifications"

# Calendar tasks
bd create "Set up Google Calendar API client" -t task -p 1 \
  --description="Service account auth, calendar client wrapper"

bd create "Implement calendar event creation" -t task -p 1 \
  --description="Create events from predictions with proper formatting"

bd create "Implement calendar event updates" -t task -p 2 \
  --description="Update existing events when predictions change"

bd create "Implement calendar sync entry point" -t task -p 2 \
  --description="Sync all pending predictions to calendar"

# Notification tasks
bd create "Set up Resend email client" -t task -p 1 \
  --description="Resend SDK setup, email sending wrapper"

bd create "Create email templates" -t task -p 1 \
  --description="HTML templates for digest, summary, alerts"

bd create "Implement review digest email" -t task -p 1 \
  --description="Daily email with pending review items and action links"

bd create "Implement weekly prediction summary" -t task -p 2 \
  --description="Weekly email with upcoming predictions"

bd create "Create notifier entry point" -t task -p 2 \
  --description="CLI for sending notifications"
```

### Dependencies
```bash
bd dep add "Implement calendar event creation" "Set up Google Calendar API client"
bd dep add "Implement calendar event updates" "Implement calendar event creation"
bd dep add "Implement calendar sync entry point" "Implement calendar event updates"

bd dep add "Create email templates" "Set up Resend email client"
bd dep add "Implement review digest email" "Create email templates"
bd dep add "Implement weekly prediction summary" "Create email templates"
bd dep add "Create notifier entry point" "Implement review digest email"
bd dep add "Create notifier entry point" "Implement weekly prediction summary"
```

---

## Phase 5: Dashboard MVP

**Goal**: Next.js dashboard with core screens.

### Beads to Create

```bash
# Epic
bd create "Phase 5: Dashboard MVP" -t feature -p 1 \
  --description="Next.js dashboard with brand management, review queue, predictions"

# Setup tasks
bd create "Create API client for dashboard" -t task -p 1 \
  --description="Typed fetch wrapper for backend API"

bd create "Set up dashboard layout and navigation" -t task -p 1 \
  --description="App layout, sidebar, navigation components"

# Page tasks
bd create "Implement home/overview page" -t task -p 2 \
  --description="Quick stats, upcoming predictions, review queue count"

bd create "Implement brands list page" -t task -p 1 \
  --description="List brands with status, add brand button"

bd create "Implement add brand form" -t task -p 2 \
  --description="Form to add new brand with slug and exclusions"

bd create "Implement brand detail page" -t task -p 2 \
  --description="Brand info, email history, predictions, accuracy"

bd create "Implement review queue page" -t task -p 1 \
  --description="List pending reviews with approve/reject actions"

bd create "Implement predictions page" -t task -p 1 \
  --description="List predictions with filters and status"

bd create "Implement accuracy page" -t task -p 2 \
  --description="Overall stats, per-brand table, recent outcomes"
```

### Dependencies
```bash
bd dep add "Set up dashboard layout and navigation" "Create API client for dashboard"
bd dep add "Implement home/overview page" "Set up dashboard layout and navigation"
bd dep add "Implement brands list page" "Set up dashboard layout and navigation"
bd dep add "Implement add brand form" "Implement brands list page"
bd dep add "Implement brand detail page" "Implement brands list page"
bd dep add "Implement review queue page" "Set up dashboard layout and navigation"
bd dep add "Implement predictions page" "Set up dashboard layout and navigation"
bd dep add "Implement accuracy page" "Set up dashboard layout and navigation"
```

---

## Phase 6: Feedback Loop

**Goal**: Outcome verification, accuracy tracking, suggestions.

### Beads to Create

```bash
# Epic
bd create "Phase 6: Feedback Loop" -t feature -p 1 \
  --description="Outcome verification, accuracy tracking, adjustment suggestions"

# Tasks
bd create "Implement auto-verification logic" -t task -p 0 \
  --description="Check if predicted sales occurred, mark HIT/MISS"

bd create "Implement manual override API" -t task -p 1 \
  --description="POST endpoint to override auto-verification"

bd create "Implement accuracy calculation" -t task -p 1 \
  --description="Calculate per-brand stats, reliability scores"

bd create "Implement suggestion generation" -t task -p 2 \
  --description="Detect timing shifts, pattern changes, generate suggestions"

bd create "Implement /api/accuracy endpoints" -t task -p 2 \
  --description="GET stats, GET per-brand, GET suggestions"

bd create "Implement /api/suggestions endpoints" -t task -p 2 \
  --description="POST approve, POST dismiss"

bd create "Add outcome override to dashboard" -t task -p 2 \
  --description="Override button on accuracy page outcomes list"

bd create "Add suggestions section to dashboard" -t task -p 2 \
  --description="Display pending suggestions with approve/dismiss"

bd create "Implement accuracy alert emails" -t task -p 3 \
  --description="Send alert when brand drops below threshold"
```

### Dependencies
```bash
bd dep add "Implement manual override API" "Implement auto-verification logic"
bd dep add "Implement accuracy calculation" "Implement auto-verification logic"
bd dep add "Implement suggestion generation" "Implement accuracy calculation"
bd dep add "Implement /api/accuracy endpoints" "Implement accuracy calculation"
bd dep add "Implement /api/suggestions endpoints" "Implement suggestion generation"
bd dep add "Add outcome override to dashboard" "Implement manual override API"
bd dep add "Add suggestions section to dashboard" "Implement /api/suggestions endpoints"
bd dep add "Implement accuracy alert emails" "Implement accuracy calculation"
```

---

## Phase 7: Testing & Polish

**Goal**: Test coverage, bug fixes, documentation.

### Beads to Create

```bash
# Epic
bd create "Phase 7: Testing & Polish" -t feature -p 2 \
  --description="Test coverage, bug fixes, documentation, final polish"

# Tasks
bd create "Write unit tests for extractor" -t task -p 1 \
  --description="Test extraction parsing, confidence scoring"

bd create "Write unit tests for predictor" -t task -p 1 \
  --description="Test date calculation, holiday anchoring"

bd create "Write integration tests for API" -t task -p 2 \
  --description="Test endpoints with test database"

bd create "Write E2E test for full pipeline" -t task -p 2 \
  --description="Scrape (mocked) → Extract → Predict → Verify"

bd create "Set up cron jobs on Railway" -t task -p 1 \
  --description="Configure weekly scrape, daily verification, daily digest"

bd create "Perform initial backfill for all brands" -t task -p 1 \
  --description="Run historical scrape for 1 year of data"

bd create "Create user documentation" -t task -p 3 \
  --description="How to use dashboard, add brands, interpret predictions"

bd create "Final bug fixes and polish" -t task -p 2 \
  --description="Address issues discovered during testing"
```

---

## Milestone Summary

| Milestone | Target | Key Deliverables |
|-----------|--------|------------------|
| **M1: Backend Live** | End of Week 1 | API deployed, DB schema, brands CRUD |
| **M2: Scraping Works** | End of Week 2 | Milled scraper, LLM extraction, backfill |
| **M3: Predictions Live** | Mid Week 3 | Predictions generated, calendar sync |
| **M4: Dashboard MVP** | End of Week 4 | All core screens functional |
| **M5: Feedback Loop** | Mid Week 5 | Verification, accuracy, suggestions |
| **M6: Production Ready** | End of Week 5 | Tests passing, cron running, docs complete |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Milled.com blocks scraping | Use realistic delays, rotate user-agents, monitor for blocks |
| LLM extraction unreliable | Extensive prompt iteration, Sonnet fallback, manual review queue |
| Calendar API quota | Batch updates, cache event IDs, handle quota errors |
| Cost overrun | Monitor LLM usage, use Haiku aggressively, set budget alerts |
| Scope creep | Strict adherence to beads, defer nice-to-haves to backlog |

---

## Definition of Done

A task is complete when:
1. Code is written and works locally
2. Unit tests pass (if applicable)
3. Code is committed with descriptive message
4. PR merged to main (or direct push if solo)
5. Deployed to Railway/Vercel (if affects production)
6. Bead updated with completion notes
