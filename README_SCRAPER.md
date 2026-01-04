# Itch Creators - Python Scraper

Data collection service for tracking itch.io game creators and their publishing history.

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure database:**

   Create a `.env` file with your Vercel Postgres credentials:
   ```bash
   POSTGRES_URL=your_postgres_url
   POSTGRES_USER=your_user
   POSTGRES_PASSWORD=your_password
   POSTGRES_HOST=your_host
   POSTGRES_DATABASE=your_database
   ```

3. **Initialize database:**
   ```bash
   python -m src init-db
   ```

## Usage

### Poll for new releases
Fetch new games from RSS feeds:
```bash
python -m src poll
```

### Backfill creator histories
Scrape all games from newly discovered creators:
```bash
python -m src backfill
```

### Enrich game ratings
Fetch rating information for games:
```bash
python -m src enrich
```
This step also backfills missing game metadata (title, publish date, description).

### Calculate scores
Recalculate creator rankings using Bayesian averaging:
```bash
python -m src score
```

### Run full pipeline
Execute all steps in sequence:
```bash
python -m src run
```
This includes discovery and re-enrichment steps.

## Development

### Run tests
```bash
pytest
```

### Run tests with coverage
```bash
pytest --cov=src --cov-report=html
```

### Run specific test file
```bash
pytest tests/test_db.py
```

## Architecture

See `docs/claude.md` and `docs/implementation-plan.md` for detailed architecture and implementation specifications.
