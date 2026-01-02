# Enhanced Logging Example

## Current vs Enhanced Logging Comparison

### Current Logging (Basic Print)

**Output:**
```
Backfilling creators...
Error backfilling testdev: HTTPError: 404
Error backfilling coolcreator: TimeoutException

Results:
  Creators processed: 8
  Games inserted: 200
  Errors: 2
```

**Problems:**
- ❌ No timestamps
- ❌ Can't tell when it started/finished
- ❌ Can't distinguish WARNING from ERROR
- ❌ No module context
- ❌ No execution time

---

### Enhanced Logging (With logger.py)

**Output:**
```
[2025-01-01 06:00:01] [INFO    ] [backfiller] Found 10 creators to backfill
[2025-01-01 06:00:01] [INFO    ] [backfiller] Backfilling creators - Started
[2025-01-01 06:00:02] [DEBUG   ] [backfiller] [1/10] Processing creator: testdev
[2025-01-01 06:00:02] [DEBUG   ] [http_client] Fetching URL: https://testdev.itch.io
[2025-01-01 06:00:03] [ERROR   ] [backfiller] ✗ Backfill failed for 'testdev': HTTPError: 404 Not Found
[2025-01-01 06:00:03] [DEBUG   ] [backfiller] [2/10] Processing creator: coolcreator
[2025-01-01 06:00:03] [DEBUG   ] [http_client] Fetching URL: https://coolcreator.itch.io
[2025-01-01 06:00:33] [WARNING ] [http_client] Timeout on https://coolcreator.itch.io (attempt 1/3)
[2025-01-01 06:00:35] [WARNING ] [http_client] Timeout on https://coolcreator.itch.io (attempt 2/3)
[2025-01-01 06:00:39] [WARNING ] [http_client] Timeout on https://coolcreator.itch.io (attempt 3/3)
[2025-01-01 06:00:39] [ERROR   ] [http_client] Failed to fetch https://coolcreator.itch.io after 3 attempts
[2025-01-01 06:00:39] [ERROR   ] [backfiller] ✗ Backfill failed for 'coolcreator': TimeoutException
[2025-01-01 06:00:40] [DEBUG   ] [backfiller] [3/10] Processing creator: amazingdev
[2025-01-01 06:00:41] [DEBUG   ] [http_client] Fetching URL: https://amazingdev.itch.io
[2025-01-01 06:00:42] [INFO    ] [backfiller] ✓ amazingdev: 15 games backfilled
...
[2025-01-01 06:03:25] [INFO    ] [backfiller] Backfilling creators - Completed in 204.32s
[2025-01-01 06:03:25] [INFO    ] [backfiller] Results:
[2025-01-01 06:03:25] [INFO    ] [backfiller]   creators_processed: 8
[2025-01-01 06:03:25] [INFO    ] [backfiller]   games_inserted: 200
[2025-01-01 06:03:25] [INFO    ] [backfiller]   errors: 2
```

**Benefits:**
- ✅ Timestamps show exactly when each operation occurred
- ✅ Log levels distinguish INFO/WARNING/ERROR/DEBUG
- ✅ Module names show which file generated the log
- ✅ Progress indicators show which creator being processed
- ✅ Retry attempts are visible
- ✅ Execution time tracked automatically
- ✅ Errors include context (which creator failed)

---

## How to Use Enhanced Logging

### Option 1: Quick Integration (Recommended)

Just update `src/backfiller.py` as an example:

```python
from . import db
from .http_client import fetch
from .logger import setup_logger, LogContext, log_error_with_context
from .models import Creator, Game
from .parsers import profile

# Set up logger for this module
logger = setup_logger(__name__)


def backfill_creator(creator: Creator) -> int:
    """Fetch a creator's profile and backfill their game history."""
    logger.debug(f"Backfilling creator: {creator.name}")

    # Fetch profile
    html = fetch(creator.profile_url)
    games = profile.parse_profile(html)

    logger.debug(f"Found {len(games)} games for {creator.name}")

    # Insert games
    inserted_count = 0
    for game_data in games:
        itch_id = _extract_game_id(game_data["url"])
        game = Game(...)
        game_id = db.insert_game(game)
        if game_id:
            inserted_count += 1

    db.mark_creator_backfilled(creator.id)
    logger.info(f"✓ {creator.name}: {inserted_count} games backfilled")

    return inserted_count


def backfill_all() -> dict[str, int]:
    """Process all unbackfilled creators."""
    stats = {
        "creators_processed": 0,
        "games_inserted": 0,
        "errors": 0,
    }

    creators = db.get_unbackfilled_creators()
    logger.info(f"Found {len(creators)} creators to backfill")

    # Use LogContext to track execution time
    with LogContext(logger, "Backfilling creators"):
        for i, creator in enumerate(creators, 1):
            logger.debug(f"[{i}/{len(creators)}] Processing creator: {creator.name}")
            try:
                games_count = backfill_creator(creator)
                stats["creators_processed"] += 1
                stats["games_inserted"] += games_count
            except Exception as e:
                stats["errors"] += 1
                log_error_with_context(logger, "Backfill", creator.name, e)

    # Log final stats
    logger.info("Results:")
    for key, value in stats.items():
        logger.info(f"  {key}: {value}")

    return stats
```

### Option 2: Keep Current Logging

If you prefer to keep the current simple print statements, that's fine! They work and Railway will capture them. Enhanced logging is optional.

---

## Testing Enhanced Logging Locally

### 1. Default (INFO level)
```bash
cd /Users/jessica.jung/code/personal/Itch-creators
python3 -m src poll
```

**Output:**
```
[2025-01-01 12:30:45] [INFO    ] [main] Polling RSS feeds...
[2025-01-01 12:30:47] [INFO    ] [feed_poller] Found 42 new releases
...
```

### 2. Debug Mode (See Everything)
```bash
export LOG_LEVEL=DEBUG
python3 -m src poll
```

**Output:**
```
[2025-01-01 12:30:45] [INFO    ] [main] Polling RSS feeds...
[2025-01-01 12:30:45] [DEBUG   ] [http_client] Fetching URL: https://itch.io/games.xml
[2025-01-01 12:30:47] [DEBUG   ] [feed_poller] Parsing RSS feed with 100 entries
[2025-01-01 12:30:47] [DEBUG   ] [feed_poller] Extracted creator 'testdev' from https://testdev.itch.io/game
...
```

### 3. Errors Only
```bash
export LOG_LEVEL=ERROR
python3 -m src poll
```

**Output:**
```
[2025-01-01 12:30:52] [ERROR   ] [backfiller] ✗ Backfill failed for 'testdev': HTTPError: 404
```

---

## Railway Environment Variable

To enable debug logging in Railway:

1. Railway Dashboard → Your Service → Variables
2. Add: `LOG_LEVEL` = `DEBUG`
3. Redeploy

Now you'll see detailed debug logs in Railway!

---

## Integration Plan

### Phase 1: Test Locally (5 minutes)
1. `src/logger.py` is already created ✅
2. Test it:
   ```bash
   cd /Users/jessica.jung/code/personal/Itch-creators
   python3 -c "from src.logger import setup_logger; logger = setup_logger(); logger.info('Test')"
   ```
3. Expected output: `[2025-01-01 12:30:45] [INFO    ] [root] Test`

### Phase 2: Update One Module (10 minutes)
1. Choose `src/backfiller.py` as test case
2. Add `from .logger import setup_logger` at top
3. Replace `print()` with `logger.info()`
4. Test: `python3 -m src backfill`

### Phase 3: Update All Modules (30 minutes)
1. `src/main.py` - Replace all prints
2. `src/http_client.py` - Add retry logging
3. `src/enricher.py` - Add progress logging
4. `src/feed_poller.py` - Add parsing details
5. `src/db.py` - Add connection logging (optional)

### Phase 4: Deploy to Railway (5 minutes)
1. Git commit: `git add src/logger.py src/...`
2. Git push
3. Railway auto-deploys
4. Check logs - should now have timestamps!

---

## Decision: Do You Want Enhanced Logging?

### ✅ YES - I want better logging

**I'll update the modules now with:**
- Timestamps on all logs
- Log levels (INFO, WARNING, ERROR, DEBUG)
- Module context
- Execution time tracking
- Better error messages

**Time to implement:** ~30 minutes
**Benefit:** Much easier debugging in production

### 🤷 MAYBE LATER - Current logging is fine for now

**Keep current print statements:**
- Still works fine
- Railway captures everything
- Can add enhanced logging later if needed

**Benefit:** Deploy faster, iterate later

### ❌ NO - Keep it simple

**Leave as-is:**
- Basic prints are sufficient
- Less code to maintain
- Can always check Railway logs

---

## What I Recommend

**For testing/prototyping**: Current logging is fine. Railway will show you everything you need.

**For production**: Add enhanced logging before deploying. When things break at 3 AM, you'll want timestamps and detailed error context!

**Compromise**: I can add enhanced logging to just the **critical modules** (http_client, db) where errors are most likely, and leave the rest as-is.

---

Let me know:
1. Do you want enhanced logging now?
2. Should I update all modules or just critical ones?
3. Or should we keep current logging and deploy as-is?
