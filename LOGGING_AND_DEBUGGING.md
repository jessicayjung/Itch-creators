# Logging and Debugging Guide

## Current Logging State

### ✅ What's Currently Logged

The scraper uses **basic print statements** throughout the code. Here's what you'll see:

#### 1. **Main Pipeline (`src/main.py`)**
```
Polling RSS feeds...
Found 42 new releases
  Warning: Could not extract creator from URL: https://...
  New creator: cooldev
Results:
  New creators: 5
  New games: 42

Backfilling creators...
Results:
  Creators processed: 5
  Games inserted: 123
  Errors: 0

Enriching game ratings...
Results:
  Games processed: 123
  Errors: 2

Calculating creator scores...
Results:
  Creators scored: 5
```

#### 2. **Error Messages**
- `backfiller.py:80` - "Error backfilling {creator_name}: {exception}"
- `enricher.py:57` - "Error enriching {game_title} ({url}): {exception}"
- `feed_poller.py:41` - "Warning: Skipping malformed feed entry"
- `main.py:206` - "Error: {exception}" (to stderr, exits with code 1)

#### 3. **HTTP Client (`src/http_client.py`)**
- **Silent retries** - No logging when retrying 429 or 5xx errors
- Only raises exception after all retries fail

### ❌ What's NOT Logged

1. **No timestamps** - Can't tell when each step started/finished
2. **No log levels** - Can't distinguish INFO from WARNING from ERROR
3. **No structured logging** - Hard to parse programmatically
4. **Database queries** - No logging of SQL operations
5. **HTTP retry attempts** - Silent retries, can't see rate limiting issues
6. **Individual game/creator processing** - Only summary stats
7. **Environment variable values** - Can't verify config without exposing secrets
8. **Startup/shutdown** - No "scraper started" or "scraper finished" logs

---

## What Railway Captures

### Automatic Log Collection

Railway **automatically captures**:
- ✅ All `print()` output (stdout)
- ✅ All `print(..., file=sys.stderr)` output (stderr)
- ✅ Python exceptions and tracebacks
- ✅ Exit codes (0 = success, 1 = failure)
- ✅ Build logs (Docker build process)
- ✅ Deployment logs (when cron job triggers)
- ✅ Runtime logs (everything your Python script outputs)

### Railway Log Viewer

Access logs via:
1. Railway Dashboard → Your Service → **Logs** tab
2. Real-time log streaming (auto-updates)
3. Search and filter capabilities
4. Download logs for offline analysis

### Log Retention

- **Free Tier**: Last 1,000 log lines (rolling window)
- **Pro Tier**: Extended retention

---

## Debugging Different Failure Modes

### 1. **Deployment Fails to Build**

**Symptoms**: Service shows "Build Failed" status

**Where to Look**:
```
Railway Dashboard → Service → Deployments → [Failed Build] → View Logs
```

**Common Errors**:
```
ERROR: failed to solve: failed to compute cache key: ...
```
→ **Fix**: Dockerfile syntax error or missing files

```
ERROR: Could not find a version that satisfies the requirement...
```
→ **Fix**: Invalid package in requirements.txt

```
#8 ERROR: executor failed running [/bin/sh -c pip install...]: exit code: 1
```
→ **Fix**: Dependency installation failed (check for missing system packages)

**How to Debug**:
1. Check Dockerfile syntax
2. Test `docker build .` locally
3. Verify all files referenced by `COPY` exist
4. Check requirements.txt for typos

---

### 2. **Service Crashes on Startup**

**Symptoms**: Logs show Python error immediately after start

**Where to Look**:
```
Railway Logs → Filter by "Error" or "Traceback"
```

**Common Errors**:

#### Missing Environment Variables
```
Traceback (most recent call last):
  File "src/main.py", line 15, in cmd_poll
    conn = psycopg2.connect(
           ^^^^^^^^^^^^^^^^^^^^
TypeError: Missing required argument 'dbname'
```
→ **Fix**: Set `POSTGRES_DATABASE` in Railway dashboard

#### Database Connection Failed
```
psycopg2.OperationalError: could not connect to server: Connection refused
	Is the server running on host "xxx" and accepting TCP/IP connections on port 5432?
```
→ **Fix**: Check POSTGRES_HOST, POSTGRES_PORT, verify Vercel Postgres is running

#### Import Error
```
ModuleNotFoundError: No module named 'src.models'
```
→ **Fix**: Check COPY paths in Dockerfile, verify directory structure

**How to Debug**:
1. Check Railway "Variables" tab - ensure all 5 env vars are set
2. Test database connection from Railway shell:
   ```bash
   railway shell
   python3 -c "import psycopg2; psycopg2.connect(...)"
   ```
3. Check file structure: `railway shell` → `ls -la src/`

---

### 3. **Scraper Runs But Finds No Data**

**Symptoms**: Logs show "Found 0 new releases" or no errors but database is empty

**Where to Look**:
```
Railway Logs → Search for "Found X new releases"
```

**Common Causes**:

#### RSS Feed Changed Format
```
Polling RSS feeds...
Found 0 new releases
```
→ **Check**: Visit https://itch.io/games.xml manually, verify it's working

#### Parsing Errors (Silent)
```
Warning: Skipping malformed feed entry (missing link or title)
Warning: Skipping malformed feed entry (missing link or title)
...
Found 0 new releases
```
→ **Fix**: RSS feed format may have changed, update parsers

#### Database Not Initialized
```
Backfilling creators...
Results:
  Creators processed: 0
  Games inserted: 0
  Errors: 0
```
→ **Fix**: Run `init-db` command first

**How to Debug**:
1. Check feed_poller warnings for skipped entries
2. Test RSS feed manually: `curl https://itch.io/games.xml`
3. Verify database has tables: Query Vercel Postgres
4. Check if games were inserted: `SELECT COUNT(*) FROM games`

---

### 4. **HTTP Errors / Rate Limiting**

**Symptoms**: "Error backfilling" or "Error enriching" messages

**Where to Look**:
```
Railway Logs → Search for "Error enriching" or "Error backfilling"
```

**Common Errors**:

#### Rate Limited (429)
```
Error enriching Cool Game (https://xxx.itch.io/cool-game): HTTPError: 429 Too Many Requests
```
→ **Cause**: http_client retried 3 times but all failed
→ **Fix**: Increase `_min_delay_seconds` or reduce concurrency

#### Server Error (503)
```
Error enriching Cool Game (https://xxx.itch.io/cool-game): HTTPError: 503 Service Unavailable
```
→ **Cause**: itch.io is down or slow
→ **Fix**: Retry later, this is expected to happen occasionally

#### Timeout
```
Error enriching Cool Game (https://xxx.itch.io/cool-game): TimeoutException: Request timeout after 30s
```
→ **Cause**: Network slow or itch.io not responding
→ **Fix**: Increase timeout in http_client.py or retry later

**How to Debug**:
1. Check error count in results: "Errors: 5" (out of how many?)
2. Test URL manually: Visit the failing game URL in browser
3. Check itch.io status: https://itch.io (is the site up?)
4. Monitor Railway logs for patterns (many 429s = rate limit issue)

---

### 5. **Database Errors**

**Symptoms**: Entire pipeline crashes with database error

**Where to Look**:
```
Railway Logs → Last lines before crash
```

**Common Errors**:

#### Connection Lost
```
psycopg2.InterfaceError: connection already closed
```
→ **Cause**: Database connection timeout
→ **Fix**: Vercel Postgres may have terminated idle connection

#### Constraint Violation
```
psycopg2.IntegrityError: duplicate key value violates unique constraint "games_itch_id_key"
```
→ **Cause**: Trying to insert game that already exists
→ **Note**: This is handled by `ON CONFLICT DO UPDATE` so shouldn't happen

#### Permission Denied
```
psycopg2.ProgrammingError: permission denied for table games
```
→ **Cause**: Database user doesn't have INSERT/UPDATE permissions
→ **Fix**: Check Vercel Postgres user permissions

**How to Debug**:
1. Check full error traceback in Railway logs
2. Test database connection locally with same credentials
3. Query Vercel Postgres to verify tables exist: `\dt` or `SELECT * FROM creators LIMIT 1`
4. Check Vercel Postgres dashboard for connection limits

---

### 6. **Silent Failures (Errors But No Crash)**

**Symptoms**: Pipeline completes but "Errors: 10" in results

**Where to Look**:
```
Railway Logs → Search for "Error enriching" or "Error backfilling"
```

**Example**:
```
Error backfilling testdev: HTTPError: 404 Not Found
Error backfilling coolcreator: TimeoutException: ...
Error enriching My Game (https://xxx.itch.io/game): ...
Results:
  Creators processed: 8
  Games inserted: 200
  Errors: 3
```

**What Happened**:
- 3 creators/games failed but didn't crash the pipeline
- Errors are caught and logged, processing continues
- **Good**: Pipeline is resilient
- **Bad**: Silent data loss (some games not enriched)

**How to Debug**:
1. Count errors: If "Errors: 3" out of 200 processed = 1.5% failure rate (acceptable)
2. If "Errors: 150" out of 200 = 75% failure rate (itch.io might be blocking you)
3. Look at specific error messages to identify patterns
4. Check if same creators/games fail repeatedly

---

## How to Add Better Logging

### Quick Fix: Add Timestamps

Replace basic prints with timestamped prints:

```python
# Add to top of src/main.py
from datetime import datetime

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

# Usage:
log("Polling RSS feeds...", "INFO")
log(f"Found {len(entries)} new releases", "INFO")
log(f"Error backfilling {creator.name}: {e}", "ERROR")
```

### Better: Use Python logging Module

Create `src/logger.py`:

```python
import logging
import sys

def setup_logger(name="itch-scraper", level=logging.INFO):
    """Configure structured logging."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Console handler (for Railway)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Format: [2025-01-01 12:30:45] [INFO] [backfiller] Message here
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger

# Usage in other modules:
from .logger import setup_logger
logger = setup_logger(__name__)

logger.info("Polling RSS feeds...")
logger.warning(f"Could not extract creator from URL: {url}")
logger.error(f"Error backfilling {creator.name}: {e}")
logger.debug(f"Fetching URL: {url}")
```

**Benefits**:
- ✅ Timestamps on every log line
- ✅ Log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- ✅ Module names (know which file logged it)
- ✅ Can filter by level
- ✅ Can redirect to files, external services, etc.

---

## Enhanced Logging for Key Modules

### 1. Database Connection Logging

Add to `src/db.py`:

```python
import logging
logger = logging.getLogger(__name__)

@contextmanager
def get_connection():
    """Context manager for database connections."""
    logger.debug(f"Connecting to database at {os.getenv('POSTGRES_HOST')}")
    try:
        conn = psycopg2.connect(...)
        logger.debug("Database connection established")
        yield conn
        conn.commit()
        logger.debug("Transaction committed successfully")
    except psycopg2.OperationalError as e:
        logger.error(f"Database connection failed: {e}")
        conn.rollback()
        raise
    except Exception as e:
        logger.error(f"Database error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
        logger.debug("Database connection closed")
```

### 2. HTTP Client Logging

Add to `src/http_client.py`:

```python
import logging
logger = logging.getLogger(__name__)

def fetch(url: str, max_retries: int = 3) -> str:
    logger.debug(f"Fetching URL: {url}")

    for attempt in range(max_retries):
        try:
            # ... existing code ...

            if response.status_code == 429:
                wait_time = (2 ** attempt) * 2
                logger.warning(f"Rate limited (429) on {url}, retrying in {wait_time}s (attempt {attempt+1}/{max_retries})")
                time.sleep(wait_time)
                continue

            if 500 <= response.status_code < 600:
                logger.warning(f"Server error {response.status_code} on {url}, retrying in {wait_time}s")
                time.sleep(wait_time)
                continue

        except httpx.TimeoutException:
            logger.warning(f"Timeout on {url} (attempt {attempt+1}/{max_retries})")
            # ... existing code ...

    logger.error(f"Failed to fetch {url} after {max_retries} attempts")
    raise httpx.HTTPError(f"Failed to fetch {url}")
```

### 3. Backfiller/Enricher Logging

Add to `src/backfiller.py` and `src/enricher.py`:

```python
import logging
logger = logging.getLogger(__name__)

def backfill_all():
    creators = db.get_unbackfilled_creators()
    logger.info(f"Found {len(creators)} creators to backfill")

    for i, creator in enumerate(creators, 1):
        logger.debug(f"[{i}/{len(creators)}] Processing creator: {creator.name}")
        try:
            games_count = backfill_creator(creator)
            logger.info(f"✓ {creator.name}: {games_count} games backfilled")
            stats["creators_processed"] += 1
            stats["games_inserted"] += games_count
        except Exception as e:
            logger.error(f"✗ {creator.name}: {e}")
            stats["errors"] += 1

    logger.info(f"Backfill complete: {stats}")
    return stats
```

---

## Recommended Logging Enhancement Plan

### Phase 1: Minimal Changes (15 minutes)
1. ✅ Add timestamp wrapper to existing prints (see "Quick Fix" above)
2. ✅ Add structured output for Railway parsing
3. ✅ Add module context to error messages

### Phase 2: Proper Logging (30 minutes)
1. ⚠️ Create `src/logger.py` with standard Python logging
2. ⚠️ Replace all print() with logger.info()
3. ⚠️ Add logger.error() with context
4. ⚠️ Add logger.warning() for retries
5. ⚠️ Add logger.debug() for detailed tracing

### Phase 3: Advanced Observability (60 minutes)
1. ⬜ Add structured JSON logging for machine parsing
2. ⬜ Add correlation IDs to track pipeline runs
3. ⬜ Add metrics (execution time, success rates)
4. ⬜ Integrate with external logging service (Sentry, LogDNA, etc.)

**Recommendation for Now**: Phase 1 (quick timestamp fix)
**For Production**: Phase 2 (proper logging module)

---

## Debugging Checklist

When something goes wrong, check in this order:

### 1. Build Failures
- [ ] Check Railway Deployment logs
- [ ] Verify Dockerfile syntax
- [ ] Test `docker build .` locally
- [ ] Check requirements.txt for typos

### 2. Startup Failures
- [ ] Check Railway Variables tab (all 5 env vars set?)
- [ ] Check Railway Logs for Python traceback
- [ ] Test database connection locally
- [ ] Verify src/ directory structure in container

### 3. Runtime Failures
- [ ] Search Railway logs for "Error" keyword
- [ ] Check error counts in results summary
- [ ] Verify itch.io is accessible
- [ ] Query Vercel Postgres to verify data

### 4. Silent Failures (No Data)
- [ ] Check "Found X new releases" count
- [ ] Verify RSS feed: `curl https://itch.io/games.xml`
- [ ] Check database tables exist: `SELECT * FROM creators LIMIT 1`
- [ ] Look for "Warning: Skipping malformed entry" messages

### 5. Performance Issues
- [ ] Check execution time in Railway logs
- [ ] Count number of HTTP requests (should have 2s delay between)
- [ ] Monitor for repeated 429 errors (rate limiting)
- [ ] Check if Vercel Postgres has connection limit issues

---

## Railway Debugging Commands

### Access Railway Shell
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to project
railway link

# Open shell in container
railway shell

# Then inside shell:
python3 -m src poll
python3 -c "import os; print(os.getenv('POSTGRES_HOST'))"
ls -la src/
```

### View Recent Logs
```bash
# Via CLI
railway logs

# Via Dashboard
https://railway.app/project/[your-project]/service/[your-service]/logs
```

### Manual Trigger
```bash
# Via CLI
railway run python -m src run

# Via Dashboard
Railway → Service → Deployments → ... → "Redeploy"
```

---

## Quick Debugging Reference

| Symptom | Where to Look | Common Cause |
|---------|--------------|--------------|
| Build fails | Deployment logs | Dockerfile syntax or missing dependency |
| Crashes on start | Runtime logs (first 10 lines) | Missing env vars or DB connection failure |
| "Found 0 releases" | Logs → search "Found" | RSS feed changed or parsing error |
| "Errors: 50" | Logs → search "Error enriching" | Rate limiting or itch.io down |
| No data in DB | Vercel Postgres query | Didn't run init-db or pipeline failed silently |
| Slow execution | Logs → check timestamps | Too many games to process or rate limiting |

---

## Next Steps

Want to improve logging? I can:

1. **Create a logging module** with proper timestamps and levels
2. **Add it to all modules** (backfiller, enricher, http_client, etc.)
3. **Test it locally** to ensure it works
4. **Deploy with enhanced logging** to Railway

This would give you much better visibility into what's happening and make debugging production issues much easier.

Would you like me to implement enhanced logging now?
