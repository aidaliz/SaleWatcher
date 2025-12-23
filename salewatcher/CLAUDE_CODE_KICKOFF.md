# Claude Code Kickoff Prompt for SaleWatcher

Copy and paste this prompt into Claude Code to initialize the project.

---

## PROMPT START

I'm starting a new project called **SaleWatcher** — a sales prediction system for Amazon Online Arbitrage. Before we begin coding, let's set up the project properly.

### Project Overview

SaleWatcher:
1. Scrapes promotional emails from Milled.com for retail brands
2. Uses Claude LLMs to extract sale details (discount %, categories, dates)
3. Identifies seasonal patterns from 1 year of historical data
4. Predicts when similar sales will recur this year
5. Syncs predictions to Google Calendar (7-day advance notice)
6. Tracks prediction accuracy and learns from outcomes

### Your First Tasks

Please do the following in order:

1. **Read the documentation** — Start by reading these files to understand the project:
   - `README.md` — Project overview
   - `CLAUDE.md` — Instructions for you (Claude Code)
   - `SKILLS.md` — Required technical capabilities
   - `docs/ARCHITECTURE.md` — System design
   - `docs/FUNCTIONAL_SPEC.md` — Feature specifications
   - `docs/PLAN.md` — Implementation plan with task breakdown

2. **Initialize beads** — Set up beads for task tracking:
   ```bash
   bd init
   ```
   Use project prefix `sw-` (for SaleWatcher).

3. **Create Phase 0 tasks** — Based on `docs/PLAN.md`, create the beads for Phase 0 (Project Setup). Start with the epic, then create child tasks with proper dependencies.

4. **Begin Phase 0** — Work through the Phase 0 tasks:
   - Create the backend project structure (Python/FastAPI)
   - Create the dashboard project structure (Next.js 14)
   - Set up `.env.example` files
   - Configure for Railway and Vercel deployment

### Key Constraints

- Use beads (`bd`) for ALL task tracking — no markdown TODOs
- Backend: Python 3.11+, FastAPI, SQLAlchemy 2.0, Playwright, Anthropic SDK
- Dashboard: Next.js 14 (App Router), Tailwind CSS, TypeScript
- Database: PostgreSQL
- Follow the architecture in `docs/ARCHITECTURE.md`
- Keep costs under $50/month (Railway + Vercel free tier + ~$15 Claude API)

### Working Style

- Create beads before starting work
- Update bead notes as you progress
- Close beads when complete
- Ask me for clarification on any ambiguities
- Commit frequently with descriptive messages

Let's begin! Start by reading the documentation files.

---

## PROMPT END
