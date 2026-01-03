# itch-creators

A system for tracking itch.io game creators, monitoring new releases, and ranking creators by publishing frequency and game quality.

**Production URL:** https://itch-creators.vercel.app

## Documentation

See `docs/implementation-plan.md` for architecture, module specifications, data models, and build order.

## Architecture Overview

Two separate codebases sharing a database:

```
┌─────────────────────────────────────────────────────────────┐
│                       Neon Postgres                         │
└─────────────────────────────────────────────────────────────┘
        ▲                                       ▲
        │ writes                                │ reads
        │                                       │
┌───────┴───────────┐                 ┌─────────┴─────────┐
│  Python Scraper   │                 │  Next.js Frontend │
│ (GitHub Actions)  │                 │     (Vercel)      │
└───────────────────┘                 └───────────────────┘
```

**Python Scraper** — Runs on a schedule via GitHub Actions, polls RSS feeds, scrapes creator profiles and game pages, writes to Postgres. Lives in root directory with `.github/workflows/scraper.yml`.

**Next.js Frontend** — Reads from Postgres, displays ranked creators. Deployed on Vercel. Lives in `/web` directory.

**Neon Postgres** — Shared database. Both services connect via `POSTGRES_URL` environment variable.

## Tech Stack

### Scraper (Python)
- **Language:** Python 3.11+
- **HTTP:** httpx
- **RSS Parsing:** feedparser
- **HTML Parsing:** BeautifulSoup4 with lxml
- **Database:** psycopg2 or asyncpg for Postgres
- **Testing:** pytest

### Frontend (Next.js)
- **Framework:** Next.js 14+ (App Router)
- **Database:** Vercel Postgres (@vercel/postgres)
- **Styling:** Tailwind CSS
- **Deployment:** Vercel

## Development Approach

**Build one module at a time.** Complete each module with tests before moving to the next. Don't scaffold multiple modules at once.

**Test against fixtures, not live sites.** Save sample HTML/XML to `tests/fixtures/`. Parsers should never hit itch.io during tests.

**Keep modules isolated.** Each module should have clear inputs and outputs. Don't let implementation details leak across boundaries.

**Wire it up last.** Only build orchestration and CLI entry points after individual modules are tested and working.

**Scraper first, frontend second.** Get data flowing into Postgres before building the display layer.

## Guardrails

**Follow the implementation plan.** Don't add modules, change architecture, or introduce dependencies not specified in `docs/IMPLEMENTATION-PLAN.md`. If something seems missing, ask first.

**No speculative files.** Only create files that are immediately needed for the current task. Don't scaffold ahead or create placeholder modules.

**Don't modify unrelated code.** When working on a module, don't refactor or "improve" other modules unless explicitly asked.

**Ask before adding dependencies.** If a task seems to require a library not in the tech stack, confirm before adding it.

**Stick to the data models.** Use the schemas defined in the implementation plan. Don't add fields or create new models without discussion.

**When uncertain, stop and ask.** If requirements are ambiguous or a task seems to conflict with the plan, clarify before proceeding.

**Always update tests when changing features.** When modifying code (models, functions, database schema, etc.), immediately update the corresponding test files to match. Tests should always pass before pushing to main. Check `tests/` directory for affected test files.

## Code Conventions

### Python (Scraper)
- Type hints on all function signatures
- Dataclasses for structured data
- One module per file in `src/`
- Tests mirror source structure in `tests/`
- No classes where functions suffice
- Async for HTTP calls, sync otherwise

### TypeScript (Frontend)
- Strict mode enabled
- Server components by default, client components only when needed
- Database queries in server components or API routes only

## Rate Limiting

Be respectful to itch.io:
- 2 second minimum delay between requests
- Descriptive User-Agent header
- Exponential backoff on 429s
- No parallel requests to the same domain

## Environment Variables

Both services need the database connection string:

```
# Neon Postgres connection (required)
POSTGRES_URL=postgresql://user:password@host/database?sslmode=require
```

### Setting up secrets

**GitHub Actions (Scraper):**
1. Go to repository Settings → Secrets and variables → Actions
2. Add `POSTGRES_URL` as a repository secret

**Vercel (Frontend):**
1. Go to project Settings → Environment Variables
2. Add `POSTGRES_URL` for Production environment

## Frontend Features

### Leaderboard Filters
- **All** — Show all creators with scores
- **2+ Games** — Creators with multiple games
- **10+ Ratings** — Well-established creators
- **Rising** — Creators with highly rated games (4.0+) published in 2025 or later

### Sorting Options
- **Score** — Bayesian score (default), with game count as tiebreaker
- **Games** — Number of games published
- **Ratings** — Total ratings received
- **Avg Rating** — Average rating across all games

### Pagination
- 50 creators per page
- Page jump input for direct navigation to specific pages
- Prev/Next buttons with page number indicators

### Leaderboard Columns
| Column | Description |
|--------|-------------|
| Rank | Position in current filter/sort |
| Creator | Name with link to detail page and itch.io profile |
| Latest Game | Most recent game title and publish date |
| Games | Total game count |
| Ratings | Total ratings received |
| Avg | Average rating across all games |
| Score | Bayesian score |

## Useful Commands

### Scraper (Local)
```bash
pytest                              # run tests
python -m src.main init-db          # initialize database schema
python -m src.main seed             # seed known prolific creators
python -m src.main poll             # fetch RSS feeds
python -m src.main discover --pages 5  # discover creators from browse pages
python -m src.main backfill         # scrape new creator histories
python -m src.main enrich --limit 2000  # scrape game ratings (with limit)
python -m src.main re-enrich --days 7 --limit 500  # update stale game data
python -m src.main score            # recalculate rankings
python -m src.main run              # run full pipeline
```

### Scraper (GitHub Actions)
```bash
# Trigger Daily Scrape manually:
gh workflow run "Daily Scrape"

# Watch a running workflow:
gh run watch <run-id>

# View recent runs:
gh run list --limit 10
```

### Frontend
```bash
cd web
npm run dev                 # local development
npm run build               # production build
vercel --prod               # deploy to production
vercel alias <deployment> itch-creators.vercel.app  # alias to custom domain
```

## GitHub Actions Workflows

### Daily Scrape (`.github/workflows/scrape.yml`)
Runs daily at 6:00 AM UTC or on manual trigger.

**Steps:**
1. `init-db` — Ensure schema exists
2. `seed` — Add known creators
3. `poll` — Fetch RSS feeds
4. `discover --pages 5` — Scrape browse pages for new creators
5. `backfill` — Fetch creator game histories
6. `enrich --limit 2000` — Fetch game ratings (limited to prevent timeout)
7. `re-enrich --days 7 --limit 500` — Update stale games
8. `score` — Recalculate rankings

**Timeout:** 120 minutes

### CI (`.github/workflows/ci.yml`)
Runs on push to main. Runs Python tests.
