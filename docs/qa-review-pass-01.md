# QA Review – itch-creators (Pass 01)

Owner: Claude (handoff)
Scope: Full repo review with focus on frontend quality and scraper throughput without increased ban risk.

## Critical

### 1) Frontend missing data layer (build/runtime failure)
- Locations: `web/src/app/page.tsx`, `web/src/app/creator/[name]/page.tsx`
- Issue: Imports from `@/lib/db` and `@/lib/types`, but `web/src/lib/*` doesn’t exist. App will not compile.
- Options:
  - A) Add `web/src/lib/db.ts` + `web/src/lib/types.ts` with server-side queries.
    - Pros: Fastest path, aligns with current imports.
    - Cons: Must define schema and query shape carefully.
  - B) Inline queries in server components.
    - Pros: Few files, quick fix.
    - Cons: Less reusable, harder to test.
  - C) Add API route and fetch from components.
    - Pros: Clear separation, cacheable.
    - Cons: More moving parts, adds request latency.

### 2) Game identity collisions across creators
- Locations: `src/backfiller.py`, `src/main.py`, `src/db.py`
- Issue: `itch_id` uses only slug; different creators sharing slug conflict due to `games.itch_id` UNIQUE. Causes data loss.
- Options:
  - A) Use URL hash as `itch_id`.
    - Pros: Unique and stable; minimal schema change.
    - Cons: Harder to debug manually.
  - B) Unique index on `(creator_id, itch_id)` with slug stored separately.
    - Pros: Human-readable slug retained; prevents cross-creator collision.
    - Cons: Requires schema migration and query updates.
  - C) Use canonical `url` as unique key instead of `itch_id`.
    - Pros: Direct identity, avoids slug ambiguity.
    - Cons: Requires URL normalization and migration.

### 3) Typography override breaks intended font
- Locations: `web/src/app/layout.tsx`, `web/src/app/globals.css`
- Issue: `body` sets `font-family: Arial, Helvetica, sans-serif`, overriding Geist.
- Options:
  - A) Remove `font-family` from `body`.
    - Pros: Uses intended Geist fonts immediately.
    - Cons: None.
  - B) Set `font-family: var(--font-geist-sans)` in `web/src/app/globals.css`.
    - Pros: Explicitly uses loaded font.
    - Cons: Slight duplication of intent.
  - C) Remove Geist from layout and use Tailwind font utilities only.
    - Pros: Simplifies font chain.
    - Cons: Loses current typography setup.

## High

### 4) Relative URLs in profile pagination and game links
- Locations: `src/parsers/profile.py`, `src/backfiller.py`
- Issue: `next_page` and game URLs can be relative; `fetch` expects absolute URLs.
- Options:
  - A) Use `urllib.parse.urljoin(current_url, next_url)` and for game URLs.
    - Pros: Robust and standard.
    - Cons: Requires base URL passed to parser or handled in backfiller.
  - B) Parse `<base>` tag or use profile URL in parser.
    - Pros: More HTML-aware.
    - Cons: More logic and coupling.
  - C) Normalize URLs in `backfill_creator` before insert/fetch.
    - Pros: Keeps parser simple.
    - Cons: Must pass base URL through backfiller.

### 5) Enricher marks scraped even on parse failures
- Locations: `src/enricher.py`, `src/parsers/game.py`, `src/db.py`
- Issue: If parser misses rating but rating_count > 0, `ratings_hidden=False` and `scraped_at` is set, so no retry.
- Options:
  - A) Treat `rating None + rating_count > 0` as parse error and skip `scraped_at`.
    - Pros: Prevents permanent data loss.
    - Cons: Needs new error path.
  - B) Add `parse_failed` flag or retry counter.
    - Pros: Explicit state, observable.
    - Cons: Schema change.
  - C) If rating is None, set `ratings_hidden` with short retry window.
    - Pros: No schema change.
    - Cons: Extra retries for truly unrated games.

### 6) Per-game DB connections throttle throughput
- Locations: `src/db.py`, `src/backfiller.py`, `src/enricher.py`, `src/main.py`
- Issue: Every insert/update opens a new DB connection; slows pipeline at scale.
- Options:
  - A) Add psycopg2 connection pool and reuse connections.
    - Pros: Large throughput boost; minimal behavior change.
    - Cons: More lifecycle management.
  - B) Batch inserts/updates per creator.
    - Pros: Fewer round-trips; faster.
    - Cons: Refactor required.
  - C) Pass a shared connection through backfill/enrich loops.
    - Pros: Minimal code churn.
    - Cons: Must handle rollback/exception paths carefully.

## Medium

### 7) Throughput improvements that keep ban risk low
- Locations: `src/http_client.py`, `src/enricher.py`, `src/backfiller.py`
- Issue: Single-threaded, no connection reuse, no adaptive backoff with jitter, no batching.
- Options:
  - A) Use shared `httpx.Client` with keep-alive and HTTP/2, keep 2s delay.
    - Pros: Safer (same rate), faster handshakes.
    - Cons: Requires refactor of fetch lifecycle.
  - B) Honor `Retry-After` and add jittered exponential backoff.
    - Pros: Lower ban risk; more polite.
    - Cons: More logic.
  - C) Add `max_games_per_run` with checkpoint.
    - Pros: Predictable runtime and load.
    - Cons: Needs scheduling/queue logic.

### 8) Backfill marks creators complete even if parsing yields zero games
- Locations: `src/backfiller.py`
- Issue: If parser breaks or profile HTML changes, creators are marked backfilled anyway.
- Options:
  - A) Only mark backfilled when at least one page parsed successfully.
    - Pros: Prevents silent data loss.
    - Cons: Might leave empty creators pending.
  - B) Add `backfill_status` (pending/partial/failed).
    - Pros: Recoverable state, clearer.
    - Cons: Schema change.
  - C) Require a minimum game count before marking complete.
    - Pros: Simple guardrail.
    - Cons: Heuristic may misclassify small creators.

### 9) Pagination loop protection is minimal
- Locations: `src/backfiller.py`
- Issue: `_MAX_PAGES_PER_CREATOR` is a blunt cap; no cycle detection.
- Options:
  - A) Track visited URLs and stop on repeat.
    - Pros: Prevents loops; safe.
    - Cons: Small memory overhead.
  - B) Stop if parsed games are identical to previous page.
    - Pros: Detects weird pagination.
    - Cons: Requires comparison logic.
  - C) Use pagination metadata if available.
    - Pros: Cleaner and future-proof.
    - Cons: Might not exist.

### 10) Duplicate scraper codebase increases divergence risk
- Locations: `scraper/` vs root `src/`
- Issue: Two similar implementations with different schema behavior.
- Options:
  - A) Remove `scraper/` and consolidate to root `src/`.
    - Pros: Single source of truth.
    - Cons: Must verify no deploys depend on it.
  - B) Document which is active and deprecate the other.
    - Pros: Low risk, transparent.
    - Cons: Still two code paths.
  - C) Keep both but sync changes.
    - Pros: Avoids breaking old deploys.
    - Cons: Ongoing maintenance burden.

## Low

### 11) Mobile overflow for tables
- Locations: `web/src/app/page.tsx`, `web/src/app/creator/[name]/page.tsx`
- Issue: Tables overflow on small screens; no horizontal scroll wrapper.
- Options:
  - A) Wrap tables with `overflow-x-auto`.
    - Pros: Quick fix.
    - Cons: Still dense on mobile.
  - B) Switch to card layout on small screens.
    - Pros: Best UX.
    - Cons: More markup and styling.
  - C) Hide low-priority columns on small screens.
    - Pros: Cleaner on mobile.
    - Cons: Less info visible.

### 12) `line-clamp-2` may be inactive
- Locations: `web/src/app/creator/[name]/page.tsx`
- Issue: Tailwind line-clamp may not be configured; descriptions can grow long.
- Options:
  - A) Add `@tailwindcss/line-clamp` plugin.
    - Pros: Works as intended.
    - Cons: Adds dependency/config.
  - B) Add custom CSS `line-clamp` utility in globals.
    - Pros: No dependency.
    - Cons: Manual CSS upkeep.
  - C) Truncate description in render logic.
    - Pros: Simple.
    - Cons: Less elegant; fixed truncation.

## Frontend enhancements (non-blocking but high impact)
- Add a hero/summary area highlighting top creator and recent movers.
- Add “rising” or “high engagement” badge using `comment_count`.
- Tighten typography hierarchy for table headers and totals.
- Improve empty state copy with suggested filters.

## Scraper throughput strategy (safe, low ban risk)
- Keep 2s minimum delay, but:
  - Use shared `httpx.Client` with keep-alive/HTTP2.
  - Honor `Retry-After` and use jittered backoff.
  - Batch DB writes per creator/enrich run.
  - Add max-per-run with checkpoint to keep cron runtimes bounded.

