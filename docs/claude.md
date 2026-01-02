# itch-creators

A system for tracking itch.io game creators, monitoring new releases, and ranking creators by publishing frequency and game quality.

## Documentation

See `docs/IMPLEMENTATION-PLAN.md` for architecture, module specifications, data models, and build order.

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

## Useful Commands

### Scraper (Local)
```bash
pytest                      # run tests
python -m src.main poll     # fetch RSS feeds
python -m src.main backfill # scrape new creator histories
python -m src.main enrich   # scrape game ratings
python -m src.main score    # recalculate rankings
python -m src.main run      # run full pipeline
```

### Scraper (GitHub Actions)
```bash
# Trigger manually from GitHub UI:
# Actions → Scraper Pipeline → Run workflow

# Or use GitHub CLI:
gh workflow run scraper.yml
gh workflow run scraper.yml -f command=poll  # run specific command
```

### Frontend
```bash
cd web
npm run dev                 # local development
npm run build               # production build
vercel                      # deploy
```
