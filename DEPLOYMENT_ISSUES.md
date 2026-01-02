# Deployment Testing & Edge Case Analysis

## Critical Issues Found

### 🔴 CRITICAL: Environment Variable Handling

**Problem**: The root `/src/db.py` expects individual environment variables but deployment plan recommends using `POSTGRES_URL`.

**Current Code** (`src/db.py` lines 15-20):
```python
conn = psycopg2.connect(
    dbname=os.getenv("POSTGRES_DATABASE"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
    host=os.getenv("POSTGRES_HOST"),
)
```

**Issues**:
1. No support for `POSTGRES_URL` connection string (Vercel's preferred format)
2. No `load_dotenv()` call (won't load .env locally, but OK for Railway)
3. No validation - will fail silently if env vars missing
4. Missing `port` parameter (defaults to 5432, may fail if Vercel uses different port)

**Impact**:
- **Medium-High** - Will work if all 4 individual env vars are set
- **High** - Will fail if only POSTGRES_URL is provided
- **Low** - Railway injects env vars directly, so no .env needed

**Solutions**:
1. **Option A**: Set individual env vars in Railway (parse from Vercel's POSTGRES_URL)
2. **Option B**: Update src/db.py to support POSTGRES_URL (like scraper/src/db.py does)
3. **Option C**: Add port parameter explicitly

**Recommendation**: Option A for quick deployment, Option B for production robustness

---

### 🟡 WARNING: Missing Port Configuration

**Problem**: Database connection doesn't specify port, assumes default 5432.

**Risk**: Vercel Postgres might use a non-standard port

**Solution**: Check Vercel connection string for port, add explicitly:
```python
conn = psycopg2.connect(
    dbname=os.getenv("POSTGRES_DATABASE"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
    host=os.getenv("POSTGRES_HOST"),
    port=os.getenv("POSTGRES_PORT", "5432"),  # Add this
)
```

---

### 🟡 WARNING: Railway Cron Schedule Format

**Problem**: Railway cron format may differ from standard cron

**Current**: `"cronSchedule": "0 6 * * *"` (6 AM UTC daily)

**Verification Needed**:
- Railway supports standard 5-field cron format ✓ (per docs)
- Schedule runs in UTC ✓
- No syntax errors ✓

**Edge Cases**:
- What if cron job runs longer than 24 hours? (Railway has timeouts)
- What if previous run hasn't finished? (Railway queues by default)

**Solution**: Add timeout monitoring, verify Railway settings

---

## Edge Case Analysis

### 1. Database Connection Failures

**Scenarios**:
- ❌ Vercel Postgres is down
- ❌ Network timeout between Railway and Vercel
- ❌ Invalid credentials
- ❌ Connection pool exhausted
- ❌ SSL/TLS certificate issues

**Current Handling**:
```python
except Exception:
    conn.rollback()
    raise
```

**Issues**:
- Generic exception handling
- No retry logic
- No connection timeout configured
- Fails fast (good for cron, but no notification)

**Improvements Needed**:
- Add specific exception handling for `psycopg2.OperationalError`
- Add connection timeout parameter
- Log errors before re-raising
- Consider retry with exponential backoff

---

### 2. Empty Environment Variables

**Scenarios**:
- ❌ Env var not set in Railway dashboard
- ❌ Typo in env var name
- ❌ Env var value is empty string

**Current Handling**:
```python
dbname=os.getenv("POSTGRES_DATABASE")  # Returns None if not set
```

**Result**: psycopg2 will raise `psycopg2.OperationalError` but error message may be unclear

**Test**:
```bash
# What happens if we run without env vars?
docker run itch-scraper python -m src run
# Expected: Error about missing database config
```

---

### 3. Scraper Runtime Exceeds 24 Hours

**Scenario**:
- Thousands of new creators to backfill
- itch.io slow to respond
- Rate limiting causes delays

**Current Protection**:
- 2-second delay between requests in http_client.py
- Exponential backoff on 429 errors

**Risk**: Railway may have execution time limits for cron jobs

**Calculation**:
- 1000 games to scrape
- 2 seconds per request
- = 33 minutes (within Railway limits)

**Unlikely to hit limits unless**:
- 10,000+ games (rare for itch.io RSS feed)
- Network is extremely slow
- Rate limiting kicks in heavily

---

### 4. Itch.io Rate Limiting / Downtime

**Scenarios**:
- ❌ itch.io returns 429 (Too Many Requests)
- ❌ itch.io is completely down (503)
- ❌ DNS resolution fails
- ❌ SSL certificate expired

**Current Handling** (`http_client.py`):
- Retries with exponential backoff on 429/5xx
- Max retries: Check implementation

**Edge Cases**:
- What if ALL requests fail?
- What if itch.io blocks Railway's IP range?
- What if robots.txt changes?

**Solution**:
- Graceful degradation (skip failed games, continue pipeline)
- Log failures for manual review
- Alert on high failure rates

---

### 5. Malformed HTML from itch.io

**Scenarios**:
- ❌ itch.io changes HTML structure (parsers break)
- ❌ Game page has unexpected format
- ❌ Special characters in game titles cause parsing errors
- ❌ Missing or malformed rating data

**Current Handling** (`parsers/game.py`, `parsers/profile.py`):
- BeautifulSoup is fault-tolerant
- Returns None/empty for missing data
- Check if proper validation exists

**Test Cases Needed**:
- Game with no ratings
- Game with HTML entities in title
- Game with missing publish date
- Creator with empty profile

---

### 6. Docker Build Issues

**Potential Problems**:

#### Missing System Dependencies
```dockerfile
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    libxml2-dev \
    libxslt-dev \
```

**Verification**:
- ✓ gcc - needed for psycopg2-binary compilation fallback
- ✓ postgresql-client - not strictly needed but useful for debugging
- ✓ libpq-dev - required for psycopg2
- ✓ libxml2-dev, libxslt-dev - required for lxml

**Risk**: LOW - All dependencies correct

#### Wrong Python Version
```dockerfile
FROM python:3.11-slim
```

**Risk**: LOW - Matches development (3.13) close enough
**Note**: Local is 3.13, Docker is 3.11 - could cause compatibility issues?

**Check**: Are there any Python 3.13-specific features used?

#### Missing Files in COPY
```dockerfile
COPY src/ ./src/
```

**Risk**: MEDIUM - What if tests or other files are needed?

**Verification**:
```bash
# Check what src/ contains
ls -la src/
# Ensure all imports work
```

---

### 7. Timezone Issues

**Problem**: Railway cron runs in UTC, but data may have timezone expectations

**Current**:
- Cron: `0 6 * * *` = 6 AM UTC = 10 PM PST / 11 PM PDT (previous day)
- Code uses `datetime.now()` for timestamps

**Edge Cases**:
- Publish dates from RSS might be in different timezone
- Database timestamps default to `NOW()` which is server timezone
- User expects data "updated today" but cron ran at 11 PM yesterday

**Solution**: Document timezone in deployment guide

---

### 8. First Run vs Subsequent Runs

**First Run**:
- Database might be empty
- Might backfill thousands of creators
- Could take much longer

**Subsequent Runs**:
- Only new data since last run
- Much faster (minutes vs hours)

**Edge Case**: What if database is wiped between runs?
- Should re-create tables (init-db)
- Should start fresh backfill

**Current Protection**:
- `CREATE TABLE IF NOT EXISTS` in db.py ✓

---

### 9. Concurrent Cron Executions

**Scenario**: Previous cron job still running when new one starts

**Railway Behavior**:
- Default: Queues new job, waits for previous to complete
- Risk: Job queue builds up if each run takes >24 hours

**Solution**:
- Ensure runs complete within reasonable time (<30 min)
- Monitor execution times
- Add maximum execution time tracking

---

### 10. Disk Space in Container

**Risk**: Logs or temp files fill up container disk

**Current**:
- No file writes except database (external)
- Python logs to stdout (captured by Railway)

**Risk**: LOW - Stateless container design

---

## Recommended Testing Plan

### Pre-Deployment Tests

1. **Parse Vercel POSTGRES_URL**:
```bash
echo $POSTGRES_URL
# Extract: host, port, user, password, database
```

2. **Test Database Connection Locally**:
```bash
export POSTGRES_HOST=xxx
export POSTGRES_USER=xxx
export POSTGRES_PASSWORD=xxx
export POSTGRES_DATABASE=xxx
python3 -m src init-db
python3 -m src poll
```

3. **Test Without Environment Variables**:
```bash
unset POSTGRES_HOST
python3 -m src poll
# Expected: Clean error message
```

4. **Test Docker Build**:
```bash
docker build -t itch-scraper .
# Expected: Successful build
```

5. **Test Docker Run**:
```bash
docker run --env-file .env itch-scraper python -m src poll
# Expected: Successful execution
```

### Post-Deployment Tests

1. **Manual Trigger in Railway**:
   - Verify all commands work: poll, backfill, enrich, score, run
   - Check logs for errors

2. **Database Verification**:
   - Query creators, games, scores tables
   - Verify data types and constraints

3. **Monitor First Scheduled Run**:
   - Wait for 6 AM UTC cron
   - Check execution logs
   - Verify data updated

4. **Test Failure Scenarios**:
   - Temporarily break env var
   - Verify Railway captures error
   - Fix and verify recovery

---

## Required Fixes Before Deployment

### High Priority
1. ✅ Add port to database connection OR verify Vercel uses 5432
2. ✅ Document individual env vars needed (not just POSTGRES_URL)
3. ⚠️ Add error handling for missing env vars
4. ⚠️ Test Docker build locally if possible

### Medium Priority
1. ⚠️ Add connection timeout to database
2. ⚠️ Improve error messages
3. ⚠️ Add logging for debugging

### Low Priority
1. ⬜ Add retry logic for database connections
2. ⬜ Monitor execution times
3. ⬜ Set up alerting for failures

---

## Updated Deployment Instructions

### Vercel Postgres Setup

When you get credentials from Vercel, you'll receive `POSTGRES_URL` like:
```
postgresql://user:password@host:5432/database?sslmode=require
```

**Parse it into individual components for Railway**:
- Host: Extract from URL (e.g., `ep-xxx.us-east-1.postgres.vercel-storage.com`)
- Port: Usually `5432` (check URL)
- User: Extract from URL
- Password: Extract from URL
- Database: Extract from URL

**In Railway, set these env vars**:
```
POSTGRES_HOST=ep-xxx.us-east-1.postgres.vercel-storage.com
POSTGRES_PORT=5432
POSTGRES_USER=default
POSTGRES_PASSWORD=xxx
POSTGRES_DATABASE=verceldb
```

**Add PORT to db.py** (recommended):
```python
conn = psycopg2.connect(
    dbname=os.getenv("POSTGRES_DATABASE"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
    host=os.getenv("POSTGRES_HOST"),
    port=os.getenv("POSTGRES_PORT", "5432"),
)
```

---

## Success Criteria

Before considering deployment successful:

- [  ] Docker builds without errors
- [ ] Local test run completes successfully
- [ ] All 5 env vars set correctly in Railway
- [ ] Manual trigger in Railway succeeds
- [ ] Database contains data after first run
- [ ] Scheduled cron executes at correct time
- [ ] No errors in Railway logs
- [ ] Data freshness verified in Vercel Postgres

---

## Rollback Procedure

If deployment fails:

1. Check Railway logs for specific error
2. Verify env vars are set correctly
3. Test database connection from Railway shell
4. Fix issue in code if needed
5. Redeploy

**Nuclear option**: Delete Railway service, fix issues, redeploy fresh
