# Railway Deployment Checklist

## ✅ Files Created
- [x] `Dockerfile` - Container configuration
- [x] `.dockerignore` - Build optimization
- [x] `railway.json` - Cron schedule configuration
- [x] `requirements.txt` - Updated with python-dotenv

## ✅ Code Fixes Applied
- [x] Added `port` parameter to database connection in `src/db.py`

## 🔴 Critical Issue: Environment Variables

**The code expects individual environment variables, NOT `POSTGRES_URL`.**

### Required Environment Variables for Railway

You need to parse Vercel's `POSTGRES_URL` into 5 separate variables:

Vercel gives you:
```
postgresql://user:password@host:5432/database?sslmode=require
```

Set these in Railway:
```
POSTGRES_HOST=ep-xxx.us-east-1.postgres.vercel-storage.com
POSTGRES_PORT=5432
POSTGRES_USER=default
POSTGRES_PASSWORD=your_password_here
POSTGRES_DATABASE=verceldb
```

### How to Parse POSTGRES_URL

If Vercel gives you:
```
postgresql://default:AbCd1234@ep-example-123.us-east-1.postgres.vercel-storage.com:5432/verceldb?sslmode=require
```

Parse it as:
- **Host**: `ep-example-123.us-east-1.postgres.vercel-storage.com`
- **Port**: `5432`
- **User**: `default`
- **Password**: `AbCd1234`
- **Database**: `verceldb`

## ⚠️ Important Notes

### 1. Railway Cron Jobs - Important Update

**Railway changed their cron job approach**. The `railway.json` with `cronSchedule` may NOT work as expected.

**Two options**:

#### Option A: Use Railway's Cron Job Service Type (Recommended)
- Deploy as a separate "Cron Job" service type in Railway dashboard
- Don't use `railway.json` cron schedule
- Configure schedule in Railway UI

#### Option B: Use External Cron Service
- Deploy as regular service
- Use external cron service (e.g., cron-job.org) to trigger via webhook
- Add webhook endpoint to trigger scraper

**Recommendation**: Create the service in Railway dashboard as type "Cron Job" instead of relying on railway.json.

### 2. Database Initialization

**Before deploying**, initialize the database schema:

```bash
# Local initialization
cd /Users/jessica.jung/code/personal/Itch-creators
export POSTGRES_HOST=xxx
export POSTGRES_PORT=5432
export POSTGRES_USER=xxx
export POSTGRES_PASSWORD=xxx
export POSTGRES_DATABASE=xxx
python3 -m src init-db
```

### 3. Testing Before Deployment

**Highly recommended**:
```bash
# Test poll command
python3 -m src poll

# Test full pipeline (may take 10-30 minutes first time)
python3 -m src run
```

## 🚀 Deployment Steps (Updated)

### Step 1: Set Up Vercel Postgres

1. Go to https://vercel.com/dashboard
2. Click "Storage" → "Create Database" → "Postgres"
3. Name: `itch-creators-db`
4. Copy the connection details from ".env.local" tab
5. Parse POSTGRES_URL into individual components (see above)

### Step 2: Initialize Database Locally

```bash
# Create .env file with parsed variables
cd /Users/jessica.jung/code/personal/Itch-creators
cat > .env << EOF
POSTGRES_HOST=your_host_here
POSTGRES_PORT=5432
POSTGRES_USER=your_user_here
POSTGRES_PASSWORD=your_password_here
POSTGRES_DATABASE=your_database_here
EOF

# Initialize schema
python3 -m src init-db

# Test with a quick poll
python3 -m src poll
```

### Step 3: Push Code to GitHub

```bash
git add Dockerfile .dockerignore railway.json requirements.txt src/db.py DEPLOYMENT_CHECKLIST.md DEPLOYMENT_ISSUES.md
git commit -m "Add Railway deployment configuration and database port support"
git push origin main
```

### Step 4: Deploy to Railway (Manual Setup Recommended)

**Don't use railway.json for cron scheduling**. Instead:

1. Go to https://railway.app
2. Create account / Sign in with GitHub
3. Click "New Project" → "Deploy from GitHub repo"
4. Select `Itch-creators` repository
5. **Important**: Change service type to "Cron Job" (not Web Service)
6. Configure:
   - **Docker Build**: Railway will auto-detect Dockerfile ✓
   - **Cron Schedule**: `0 6 * * *` (enter in Railway UI)
   - **Start Command**: `python -m src run`
   - **Region**: Choose closest to Vercel Postgres region

### Step 5: Set Environment Variables in Railway

In Railway dashboard → Your service → Variables:

```
POSTGRES_HOST=ep-xxx.vercel-storage.com
POSTGRES_PORT=5432
POSTGRES_USER=default
POSTGRES_PASSWORD=xxx
POSTGRES_DATABASE=verceldb
```

**Tip**: Copy these from your local `.env` file

### Step 6: Test Manual Trigger

1. In Railway dashboard, find your cron job service
2. Click "..." menu → "Run Now" (or similar)
3. Watch logs in real-time
4. Verify no errors
5. Check Vercel Postgres for new data

### Step 7: Verify Scheduled Run

1. Wait for next scheduled run (6 AM UTC)
2. Check Railway logs
3. Query Vercel Postgres:
```sql
SELECT COUNT(*) FROM creators;
SELECT COUNT(*) FROM games;
SELECT * FROM creators ORDER BY updated_at DESC LIMIT 10;
```

## 🐛 Common Issues & Solutions

### Issue: "Missing database configuration" error

**Solution**: Verify all 5 env vars are set in Railway dashboard (not railway.json)

### Issue: "Connection timeout" or "Could not connect"

**Solution**:
- Check Vercel Postgres is not sleeping (free tier)
- Verify host/port/credentials are correct
- Try using non-pooling connection URL from Vercel

### Issue: Cron job doesn't run on schedule

**Solution**:
- Railway cron jobs must be service type "Cron Job"
- Verify schedule format: `0 6 * * *` (standard 5-field cron)
- Check Railway logs for scheduler errors

### Issue: Docker build fails

**Solution**:
```bash
# Check Dockerfile syntax
docker build -t test-itch-scraper .

# If no Docker locally, check Railway build logs
# Common issue: Missing dependencies in requirements.txt
```

### Issue: "ModuleNotFoundError" in Railway

**Solution**: Verify `COPY src/ ./src/` in Dockerfile is correct and src/ directory exists

## 📊 Expected Behavior

### First Run
- **Duration**: 10-30 minutes (depends on RSS feed size)
- **Data**: Hundreds of new creators and games
- **Memory**: <512 MB
- **Disk**: Minimal (stateless)

### Subsequent Runs
- **Duration**: 2-10 minutes (only new data)
- **Data**: Dozens of new games/creators per day
- **Memory**: <256 MB

## 💰 Cost Estimate

### Free Tier Testing
- **Railway**: $5 free credit (lasts ~5 months at $1/month)
- **Vercel Postgres**: Free tier (256 MB storage)
- **Total**: $0 for testing

### After Free Credit
- **Railway Cron**: ~$1-2/month (daily runs)
- **Vercel Postgres**: $0 (stays in free tier unless you exceed 256 MB)
- **Total**: ~$1-2/month

## 🎯 Success Criteria

- [ ] Dockerfile builds successfully
- [ ] All env vars set correctly in Railway
- [ ] Manual trigger completes without errors
- [ ] Database shows new creators/games after run
- [ ] Scheduled cron executes at 6 AM UTC
- [ ] Logs show all 4 pipeline stages complete (poll → backfill → enrich → score)
- [ ] No connection errors in logs
- [ ] Data freshness: `updated_at` timestamps are recent

## 📝 Next Steps After Successful Deployment

1. Monitor for 1 week to ensure stability
2. Review execution times and optimize if needed
3. Check data quality in Vercel Postgres
4. Adjust cron schedule if needed (more/less frequent)
5. Proceed to Phase 5: Build Next.js frontend

## 🔗 Useful Links

- [Railway Dashboard](https://railway.app/dashboard)
- [Railway Cron Jobs Docs](https://docs.railway.app/reference/cron-jobs)
- [Vercel Postgres Dashboard](https://vercel.com/dashboard/stores)
- [Railway Environment Variables](https://docs.railway.app/develop/variables)

## 📞 Support

If you encounter issues:
1. Check `DEPLOYMENT_ISSUES.md` for detailed edge case analysis
2. Review Railway logs for specific error messages
3. Test database connection locally first
4. Verify environment variables are set correctly

---

**Ready to deploy?** Follow Steps 1-7 above carefully and verify each step before proceeding to the next.
