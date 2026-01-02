# Bug Fixes (Medium+ Priority)

This list consolidates all identified medium+ severity issues from the code review.

## 1) DB connection fails when only POSTGRES_URL is set (High)
**Where**: `src/db.py`

**Problem**: The DB connector ignores `POSTGRES_URL` and only reads individual env vars. In Railway/Vercel setups, only `POSTGRES_URL` is often provided, so the app fails at startup.

**Impact**: Service cannot start or connect to the database.

**Fix options**:
- **A**: Add support for `POSTGRES_URL` in `src/db.py` (like `scraper/src/db.py`).
- **B**: Parse `POSTGRES_URL` into individual vars before connecting.
- **C**: Accept both: `POSTGRES_URL` first, fallback to individual vars.

## 2) Unknown itch_id collapses to a single unique value (High)
**Where**: `src/backfiller.py`, `src/main.py`, `src/db.py`

**Problem**: `_extract_game_id` returns the literal string `"unknown"` when it can’t parse a slug. Because `games.itch_id` is `UNIQUE`, all such games conflict and are dropped after the first insert.

**Impact**: Data loss; many games never stored.

**Fix options**:
- **A**: Return `None` for unknown IDs and allow multiple NULLs in `games.itch_id`.
- **B**: Use a stable hash of the URL as the fallback `itch_id`.
- **C**: Add a separate `url_hash` column and unique index on that instead.

## 3) Profile URL extraction fails for schemeless URLs (Medium)
**Where**: `src/main.py`

**Problem**: `_extract_profile_url` returns the full game URL when the URL lacks a scheme. Backfill then parses a game page as a profile and marks the creator as backfilled.

**Impact**: Creators become permanently backfilled with zero games.

**Fix options**:
- **A**: Normalize URLs with `urllib.parse` and add a default scheme before parsing.
- **B**: Validate extracted profile URLs and skip backfill until a valid host is found.
- **C**: Store invalid URLs and retry after normalization in a later pass.

## 4) Enrich marks scraped_at even when ratings are hidden (Medium)
**Where**: `src/enricher.py`, `src/db.py`

**Problem**: `scraped_at` is set even when no ratings are present, so the game is never re-enriched if ratings appear later.

**Impact**: Ratings remain permanently missing for games that later receive visible ratings.

**Fix options**:
- **A**: Only set `scraped_at` when `rating` is not `None`.
- **B**: Store a `ratings_hidden` flag and retry after a cooldown window.
- **C**: Add a periodic re-enrich job for games with `rating IS NULL`.

## 5) Scoring uses unweighted average of per-game ratings (High)
**Where**: `src/scorer.py`

**Problem**: Average rating is computed as a simple average of game ratings, not weighted by `rating_count`. This inflates creators with a single high-rated, low-vote game.

**Impact**: Rankings are materially skewed and inconsistent with vote volume.

**Fix options**:
- **A**: Compute weighted average in SQL with `SUM(rating * rating_count) / NULLIF(SUM(rating_count), 0)`.
- **B**: Fetch per-game rows and compute weighted average in Python.
- **C**: Store a `weighted_rating_sum` per game at enrich time and aggregate it.

## 6) Backfill doesn’t paginate creator profiles (Medium)
**Where**: `src/parsers/profile.py`, `src/backfiller.py`

**Problem**: Only the first profile page is parsed. Creators with paginated profiles silently lose older games but are marked as backfilled.

**Impact**: Incomplete historical data with no retry path.

**Fix options**:
- **A**: Detect pagination links and loop through all pages in backfill.
- **B**: Use creator RSS/API endpoints (if available) and use profile parsing only as fallback.
- **C**: Add a re-backfill policy if total games are below a threshold.

## 7) Scorer tests mock the wrong SQL shape (Medium)
**Where**: `tests/test_scorer.py`

**Problem**: The test mocks return tuples with 3 fields, but production SQL returns 4 fields. This can mask regressions or cause incorrect assertions.

**Impact**: Test suite doesn’t validate real behavior.

**Fix options**:
- **A**: Update mocks to return `(total_games, rated_games, total_ratings, avg_rating)`.
- **B**: Change SQL to return only 3 fields and adjust logic accordingly.
- **C**: Use `RealDictCursor` and make tests assert by keys to avoid tuple-shape drift.
