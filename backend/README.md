# Domain Intelligence Backend

FastAPI backend skeleton for normalized auction listing reads and shared domain intelligence storage.

## Directory Structure

```text
backend/
  src/domain_intel/
    api/
    core/
    db/
    repositories/
    services/
    main.py
  migrations/
  tests/
  .env.example
  alembic.ini
  docker-compose.yml
```

## Local Startup

```bash
cd backend
cp .env.example .env
docker compose up -d postgres
alembic upgrade head
uvicorn domain_intel.main:app --reload --host 0.0.0.0 --port 8000
```

Useful endpoints:

```text
GET /health
GET /v1/health
GET /v1/auctions?source=dynadot&tld=.com&min_price=25&max_price=500
```

## Notes

- Marketplace parsing and scraping are intentionally outside this slice.
- Auction list filters read canonical `auctions`, `domains`, and `source_marketplaces` rows only.
- Money fields are returned only when both amount and currency are present in stored data.
