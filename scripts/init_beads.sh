#!/bin/bash

# SaleWatcher Beads Initialization Script
# Run this after `bd init` to create all project tasks

set -e

echo "🔧 Creating SaleWatcher beads..."
echo ""

# ============================================================================
# PHASE 0: Project Setup
# ============================================================================

echo "📦 Phase 0: Project Setup"

# Epic
bd create "Phase 0: Project Setup" -t feature -p 1 \
  --description="Initialize repository, environments, and CI/CD" --json > /dev/null

# Get the epic ID for dependencies
PHASE0_ID=$(bd list --json | jq -r '.[] | select(.title == "Phase 0: Project Setup") | .id')

# Tasks
bd create "Initialize Git repository and push to GitHub" -t task -p 0 \
  --description="Create repo, add .gitignore, initial commit, push to GitHub" --json > /dev/null

bd create "Set up backend project structure" -t task -p 1 \
  --description="Create Python project with FastAPI, requirements.txt, src/ layout" --json > /dev/null

bd create "Set up dashboard project structure" -t task -p 1 \
  --description="Create Next.js 14 project with App Router, Tailwind CSS" --json > /dev/null

bd create "Configure Railway backend deployment" -t task -p 1 \
  --description="Link repo, configure build, add PostgreSQL, set env vars" --json > /dev/null

bd create "Configure Vercel dashboard deployment" -t task -p 1 \
  --description="Link repo, set root directory, configure env vars" --json > /dev/null

bd create "Create .env.example files" -t task -p 2 \
  --description="Document all required environment variables for backend and dashboard" --json > /dev/null

echo "  ✓ Phase 0 tasks created"

# ============================================================================
# PHASE 1: Core Backend Infrastructure
# ============================================================================

echo "📦 Phase 1: Core Backend Infrastructure"

bd create "Phase 1: Core Backend Infrastructure" -t feature -p 1 \
  --description="Database models, migrations, FastAPI setup" --json > /dev/null

bd create "Create SQLAlchemy models for all entities" -t task -p 0 \
  --description="Brand, RawEmail, ExtractedSale, SaleWindow, Prediction, PredictionOutcome, BrandAccuracyStats, AdjustmentSuggestion" --json > /dev/null

bd create "Set up Alembic migrations" -t task -p 1 \
  --description="Initialize Alembic, create initial migration, test upgrade/downgrade" --json > /dev/null

bd create "Create database session management" -t task -p 1 \
  --description="Connection pooling, async session factory, dependency injection" --json > /dev/null

bd create "Implement CRUD operations for Brand" -t task -p 1 \
  --description="Create, read, update, deactivate brands with validation" --json > /dev/null

bd create "Create FastAPI application structure" -t task -p 1 \
  --description="Main app, routers, dependency injection, error handling" --json > /dev/null

bd create "Implement /api/brands endpoints" -t task -p 2 \
  --description="GET list, POST create, GET detail, PATCH update, DELETE deactivate" --json > /dev/null

bd create "Implement /api/health endpoint" -t task -p 2 \
  --description="Basic health check returning DB connection status" --json > /dev/null

bd create "Add Pydantic schemas for all entities" -t task -p 1 \
  --description="Request/response models with validation" --json > /dev/null

bd create "Configure logging and error handling" -t task -p 2 \
  --description="Structured JSON logging, global exception handler" --json > /dev/null

echo "  ✓ Phase 1 tasks created"

# ============================================================================
# PHASE 2: Scraper & Extractor
# ============================================================================

echo "📦 Phase 2: Scraper & Extractor"

bd create "Phase 2: Scraper and Extractor" -t feature -p 1 \
  --description="Milled.com scraping and Claude-based sale extraction" --json > /dev/null

# Scraper tasks
bd create "Implement Milled.com authentication" -t task -p 0 \
  --description="Playwright login flow with session persistence, handle auth failures" --json > /dev/null

bd create "Implement brand page navigation" -t task -p 1 \
  --description="Navigate to brand page, apply date filters, handle pagination" --json > /dev/null

bd create "Implement email content extraction" -t task -p 1 \
  --description="Extract subject, sent date, URL, full HTML content" --json > /dev/null

bd create "Implement scraper error handling" -t task -p 1 \
  --description="Retry logic, screenshot on failure, skip bad emails, alert on brand failure" --json > /dev/null

bd create "Create scraper entry point script" -t task -p 2 \
  --description="CLI script for manual runs and cron invocation" --json > /dev/null

bd create "Implement historical backfill command" -t task -p 2 \
  --description="Scrape full year of history for a brand" --json > /dev/null

# Extractor tasks
bd create "Create Anthropic client wrapper" -t task -p 1 \
  --description="Async client, retry on rate limit, model selection" --json > /dev/null

bd create "Design extraction prompt" -t task -p 0 \
  --description="Prompt for structured sale extraction with confidence scoring" --json > /dev/null

bd create "Implement Haiku extraction" -t task -p 1 \
  --description="Primary extraction with Haiku 4.5, parse JSON response" --json > /dev/null

bd create "Implement Sonnet fallback" -t task -p 1 \
  --description="Re-process low-confidence extractions with Sonnet 4.5" --json > /dev/null

bd create "Implement extraction result parsing" -t task -p 1 \
  --description="Parse LLM JSON response, validate, map to ExtractedSale model" --json > /dev/null

bd create "Create extraction entry point" -t task -p 2 \
  --description="Process pending emails, update database with results" --json > /dev/null

bd create "Implement review queue logic" -t task -p 2 \
  --description="Route low-confidence extractions to review queue" --json > /dev/null

echo "  ✓ Phase 2 tasks created"

# ============================================================================
# PHASE 3: Prediction Engine
# ============================================================================

echo "📦 Phase 3: Prediction Engine"

bd create "Phase 3: Prediction Engine" -t feature -p 1 \
  --description="Deduplication, holiday detection, prediction generation" --json > /dev/null

bd create "Implement sale deduplication" -t task -p 0 \
  --description="Group related emails into sale windows based on dates and discount similarity" --json > /dev/null

bd create "Create holiday calendar utility" -t task -p 1 \
  --description="Functions to compute holiday dates for any year (Memorial Day, etc.)" --json > /dev/null

bd create "Implement holiday anchor detection" -t task -p 1 \
  --description="Detect if sale is within plus/minus 3 days of a holiday" --json > /dev/null

bd create "Implement prediction date calculation" -t task -p 1 \
  --description="Calculate predicted dates with holiday adjustment" --json > /dev/null

bd create "Implement prediction generation" -t task -p 0 \
  --description="Generate predictions from historical sale windows" --json > /dev/null

bd create "Create prediction confidence scoring" -t task -p 2 \
  --description="Score predictions based on historical consistency" --json > /dev/null

bd create "Implement /api/predictions endpoints" -t task -p 2 \
  --description="GET list, GET upcoming, GET detail" --json > /dev/null

bd create "Create predictor entry point script" -t task -p 2 \
  --description="CLI for manual prediction generation" --json > /dev/null

echo "  ✓ Phase 3 tasks created"

# ============================================================================
# PHASE 4: Calendar & Notifications
# ============================================================================

echo "📦 Phase 4: Calendar & Notifications"

bd create "Phase 4: Calendar and Notifications" -t feature -p 1 \
  --description="Google Calendar sync and Resend email notifications" --json > /dev/null

# Calendar tasks
bd create "Set up Google Calendar API client" -t task -p 1 \
  --description="Service account auth, calendar client wrapper" --json > /dev/null

bd create "Implement calendar event creation" -t task -p 1 \
  --description="Create events from predictions with proper formatting" --json > /dev/null

bd create "Implement calendar event updates" -t task -p 2 \
  --description="Update existing events when predictions change" --json > /dev/null

bd create "Implement calendar sync entry point" -t task -p 2 \
  --description="Sync all pending predictions to calendar" --json > /dev/null

# Notification tasks
bd create "Set up Resend email client" -t task -p 1 \
  --description="Resend SDK setup, email sending wrapper" --json > /dev/null

bd create "Create email templates" -t task -p 1 \
  --description="HTML templates for digest, summary, alerts" --json > /dev/null

bd create "Implement review digest email" -t task -p 1 \
  --description="Daily email with pending review items and action links" --json > /dev/null

bd create "Implement weekly prediction summary" -t task -p 2 \
  --description="Weekly email with upcoming predictions" --json > /dev/null

bd create "Create notifier entry point" -t task -p 2 \
  --description="CLI for sending notifications" --json > /dev/null

echo "  ✓ Phase 4 tasks created"

# ============================================================================
# PHASE 5: Dashboard MVP
# ============================================================================

echo "📦 Phase 5: Dashboard MVP"

bd create "Phase 5: Dashboard MVP" -t feature -p 1 \
  --description="Next.js dashboard with brand management, review queue, predictions" --json > /dev/null

# Setup tasks
bd create "Create API client for dashboard" -t task -p 1 \
  --description="Typed fetch wrapper for backend API" --json > /dev/null

bd create "Set up dashboard layout and navigation" -t task -p 1 \
  --description="App layout, sidebar, navigation components" --json > /dev/null

# Page tasks
bd create "Implement home/overview page" -t task -p 2 \
  --description="Quick stats, upcoming predictions, review queue count" --json > /dev/null

bd create "Implement brands list page" -t task -p 1 \
  --description="List brands with status, add brand button" --json > /dev/null

bd create "Implement add brand form" -t task -p 2 \
  --description="Form to add new brand with slug and exclusions" --json > /dev/null

bd create "Implement brand detail page" -t task -p 2 \
  --description="Brand info, email history, predictions, accuracy" --json > /dev/null

bd create "Implement review queue page" -t task -p 1 \
  --description="List pending reviews with approve/reject actions" --json > /dev/null

bd create "Implement predictions page" -t task -p 1 \
  --description="List predictions with filters and status" --json > /dev/null

bd create "Implement accuracy page" -t task -p 2 \
  --description="Overall stats, per-brand table, recent outcomes" --json > /dev/null

echo "  ✓ Phase 5 tasks created"

# ============================================================================
# PHASE 6: Feedback Loop
# ============================================================================

echo "📦 Phase 6: Feedback Loop"

bd create "Phase 6: Feedback Loop" -t feature -p 1 \
  --description="Outcome verification, accuracy tracking, adjustment suggestions" --json > /dev/null

bd create "Implement auto-verification logic" -t task -p 0 \
  --description="Check if predicted sales occurred, mark HIT/MISS" --json > /dev/null

bd create "Implement manual override API" -t task -p 1 \
  --description="POST endpoint to override auto-verification" --json > /dev/null

bd create "Implement accuracy calculation" -t task -p 1 \
  --description="Calculate per-brand stats, reliability scores" --json > /dev/null

bd create "Implement suggestion generation" -t task -p 2 \
  --description="Detect timing shifts, pattern changes, generate suggestions" --json > /dev/null

bd create "Implement /api/accuracy endpoints" -t task -p 2 \
  --description="GET stats, GET per-brand, GET suggestions" --json > /dev/null

bd create "Implement /api/suggestions endpoints" -t task -p 2 \
  --description="POST approve, POST dismiss" --json > /dev/null

bd create "Add outcome override to dashboard" -t task -p 2 \
  --description="Override button on accuracy page outcomes list" --json > /dev/null

bd create "Add suggestions section to dashboard" -t task -p 2 \
  --description="Display pending suggestions with approve/dismiss" --json > /dev/null

bd create "Implement accuracy alert emails" -t task -p 3 \
  --description="Send alert when brand drops below threshold" --json > /dev/null

echo "  ✓ Phase 6 tasks created"

# ============================================================================
# PHASE 7: Testing & Polish
# ============================================================================

echo "📦 Phase 7: Testing & Polish"

bd create "Phase 7: Testing and Polish" -t feature -p 2 \
  --description="Test coverage, bug fixes, documentation, final polish" --json > /dev/null

bd create "Write unit tests for extractor" -t task -p 1 \
  --description="Test extraction parsing, confidence scoring" --json > /dev/null

bd create "Write unit tests for predictor" -t task -p 1 \
  --description="Test date calculation, holiday anchoring" --json > /dev/null

bd create "Write integration tests for API" -t task -p 2 \
  --description="Test endpoints with test database" --json > /dev/null

bd create "Write E2E test for full pipeline" -t task -p 2 \
  --description="Scrape (mocked) to Extract to Predict to Verify" --json > /dev/null

bd create "Set up cron jobs on Railway" -t task -p 1 \
  --description="Configure weekly scrape, daily verification, daily digest" --json > /dev/null

bd create "Perform initial backfill for all brands" -t task -p 1 \
  --description="Run historical scrape for 1 year of data" --json > /dev/null

bd create "Create user documentation" -t task -p 3 \
  --description="How to use dashboard, add brands, interpret predictions" --json > /dev/null

bd create "Final bug fixes and polish" -t task -p 2 \
  --description="Address issues discovered during testing" --json > /dev/null

echo "  ✓ Phase 7 tasks created"

# ============================================================================
# Summary
# ============================================================================

echo ""
echo "✅ All beads created successfully!"
echo ""
echo "Run 'bd list' to see all tasks"
echo "Run 'bd ready' to see tasks ready to work on"
echo "Run 'bd list -p 0' to see critical priority tasks"
echo ""
echo "Start with: bd ready"
