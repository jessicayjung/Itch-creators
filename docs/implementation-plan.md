# Implementation Plan

## Project Purpose

Monitor itch.io for new game releases, identify active creators, backfill their historical catalogs, and rank them by publishing frequency and game quality (measured by ratings volume using Bayesian averaging).

---

## System Architecture

### Overview

Hybrid approach: RSS feeds for discovery, targeted scraping for enrichment. Two codebases sharing a Postgres database.

```
RSS Feeds → New Games → Creator Discovery → Profile Backfill → Game Detail Enrichment → Scoring → Web Display
```

### Components

| Component | Language | Hosting | Purpose |
|-----------|----------|---------|---------|
| Scraper | Python | Railway/Render | Data ingestion, runs on schedule |
| Frontend | Next.js | Vercel | Display ranked creators |
| Database | Postgres | Vercel Postgres | Shared data store |

---

## Data Models

### Database Schema

```sql
CREATE TABLE creators (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    profile_url VARCHAR(512) NOT NULL,
    backfilled BOOLEAN DEFAULT FALSE,
    first_seen TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE games (
    id SERIAL PRIMARY KEY,
    itch_id VARCHAR(255) UNIQUE,
    title VARCHAR(512) NOT NULL,
    creator_id INTEGER REFERENCES creators(id),
    url VARCHAR(512) NOT NULL,
    publish_date DATE,
    rating DECIMAL(3,2),
    rating_count INTEGER DEFAULT 0,
    scraped_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE creator_scores (
    id SERIAL PRIMARY KEY,
    creator_id INTEGER REFERENCES creators(id) UNIQUE,
    game_count INTEGER DEFAULT 0,
    total_ratings INTEGER DEFAULT 0,
    avg_rating DECIMAL(3,2),
    bayesian_score DECIMAL(5,4),
    calculated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_games_creator ON games(creator_id);
CREATE INDEX idx_scores_bayesian ON creator_scores(bayesian_score DESC);
```

### Python Dataclasses

```python
@dataclass
class Game:
    id: int | None
    itch_id: str
    title: str
    creator_name: str
    url: str
    publish_date: date | None
    rating: float | None
    rating_count: int
    scraped_at: datetime | None

@dataclass
class Creator:
    id: int | None
    name: str
    profile_url: str
    backfilled: bool
    first_seen: datetime

@dataclass
class CreatorScore:
    creator_id: int
    game_count: int
    total_ratings: int
    avg_rating: float
    bayesian_score: float
```

---

## Scraper Modules

Build in this order. Complete each with tests before proceeding.

### 1. `src/db.py` — Database Connection

**Purpose:** Manage Postgres connections and provide CRUD operations.

**Functions:**
- `get_connection()` → connection context manager
- `create_tables()` → initialize schema
- `insert_creator(creator)` → returns id
- `insert_game(game)` → returns id
- `get_creator_by_name(name)` → Creator or None
- `get_unbackfilled_creators()` → list of Creators
- `get_unenriched_games()` → list of Games
- `update_game_ratings(game_id, rating, rating_count)`
- `mark_creator_backfilled(creator_id)`
- `upsert_creator_score(score)`

**Dependencies:** psycopg2 or asyncpg

---

### 2. `src/http_client.py` — Rate-Limited HTTP

**Purpose:** Handle all HTTP requests with rate limiting and retries.

**Functions:**
- `fetch(url)` → raw HTML string
- Enforces 2-second delay between requests
- Retries with exponential backoff on 429/5xx
- Sets descriptive User-Agent

**Dependencies:** httpx

---

### 3. `src/feed_poller.py` — RSS Parsing

**Purpose:** Fetch and parse itch.io RSS feeds.

**Functions:**
- `poll_feed(feed_url)` → list of dicts with title, creator, game_url, publish_date
- `get_new_releases()` → polls default feeds, returns new games

**Key URLs:**
- `https://itch.io/games.xml`
- `https://itch.io/games/newest.xml`

**Dependencies:** feedparser

---

### 4. `src/parsers/profile.py` — Creator Profile Parser

**Purpose:** Extract game list from creator profile pages.

**Functions:**
- `parse_profile(html)` → list of dicts with title, url, publish_date

**Target URL pattern:** `https://{username}.itch.io`

**Dependencies:** BeautifulSoup4

---

### 5. `src/parsers/game.py` — Game Page Parser

**Purpose:** Extract ratings from individual game pages.

**Functions:**
- `parse_game(html)` → dict with rating, rating_count (or None if hidden)

**Target URL pattern:** `https://{username}.itch.io/{game-slug}`

**Dependencies:** BeautifulSoup4

---

### 6. `src/backfiller.py` — Creator History Backfill

**Purpose:** Orchestrate fetching creator profiles and storing historical games.

**Functions:**
- `backfill_creator(creator)` → fetches profile, inserts games, marks backfilled
- `backfill_all()` → processes all unbackfilled creators

**Uses:** http_client, parsers/profile, db

---

### 7. `src/enricher.py` — Game Ratings Enrichment

**Purpose:** Orchestrate fetching game pages and updating ratings.

**Functions:**
- `enrich_game(game)` → fetches page, updates ratings in db
- `enrich_all()` → processes all unenriched games

**Uses:** http_client, parsers/game, db

---

### 8. `src/scorer.py` — Ranking Calculations

**Purpose:** Calculate creator scores using Bayesian averaging.

**Functions:**
- `calculate_bayesian_score(avg_rating, rating_count, global_avg, min_votes)` → float
- `score_creator(creator_id)` → CreatorScore
- `score_all()` → recalculates all scores

**Bayesian formula:**
```
weighted_score = (rating_count / (rating_count + min_votes)) * avg_rating
               + (min_votes / (rating_count + min_votes)) * global_avg
```

**Uses:** db

---

### 9. `src/main.py` — CLI Entry Point

**Purpose:** Tie modules together with CLI commands.

**Commands:**
- `poll` — run feed poller, insert new games and creators
- `backfill` — process unbackfilled creators
- `enrich` — fetch ratings for unenriched games
- `score` — recalculate all creator scores
- `run` — execute full pipeline (poll → backfill → enrich → score)

**Uses:** all modules

---

## Frontend Pages

Build after scraper is complete and data is flowing.

### 1. Home Page (`/`)

Display ranked list of creators with:
- Rank
- Creator name (links to itch.io profile)
- Game count
- Total ratings
- Bayesian score

Server component that queries Postgres directly.

### 2. Creator Detail Page (`/creator/[name]`)

Display single creator with:
- Profile info
- List of all their games with individual ratings
- Score breakdown

---

## Build Order

### Phase 1: Scraper Foundation
1. `src/db.py` + schema migration
2. `src/http_client.py`
3. `src/feed_poller.py`

### Phase 2: Parsers
4. `src/parsers/profile.py`
5. `src/parsers/game.py`

### Phase 3: Orchestration
6. `src/backfiller.py`
7. `src/enricher.py`
8. `src/scorer.py`
9. `src/main.py`

### Phase 4: Deployment
10. Deploy scraper to Railway/Render
11. Set up cron schedule (hourly or daily)

### Phase 5: Frontend
12. Next.js project setup with Vercel Postgres
13. Home page with ranked list
14. Creator detail page
15. Deploy to Vercel

---

## Testing Strategy

### Fixtures

Save sample HTML/XML in `tests/fixtures/`:
- `feed_sample.xml` — RSS feed response
- `profile_sample.html` — creator profile page
- `game_sample.html` — game page with ratings
- `game_no_ratings.html` — game page with hidden ratings

### Test Coverage

Each module should have tests for:
- Happy path
- Edge cases (missing data, malformed input)
- Error handling

Parsers test against fixtures only—never hit live sites in tests.

---

## What NOT To Build

- User accounts or authentication
- Real-time updates (scheduled polling is sufficient)
- Complex filtering UI (start with a single ranked list)
- Proxy rotation or anti-detection
- Full-text search
- Mobile app
