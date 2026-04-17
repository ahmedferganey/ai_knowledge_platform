# Quickstart: AI Knowledge Assistant Platform

**Branch**: `001-rag-knowledge-platform`
**Date**: 2026-04-17

This guide gets a fully functional local development environment running in under 10 minutes.

---

## Prerequisites

| Tool | Minimum Version | Check |
|------|----------------|-------|
| Docker | 24.0+ | `docker --version` |
| Docker Compose | 2.20+ | `docker compose version` |
| Python | 3.11+ | `python --version` |
| make | any | `make --version` |

---

## 1. Clone and Configure

```bash
git clone <repo-url> ai_knowledge_platform
cd ai_knowledge_platform
```

Copy the example environment file and fill in required values:

```bash
cp infra/docker/.env.example infra/docker/.env
```

Open `infra/docker/.env` and set:

```dotenv
# Required: LLM provider
LLM_PROVIDER=openai                          # or: claude
OPENAI_API_KEY=sk-...                        # required if LLM_PROVIDER=openai
ANTHROPIC_API_KEY=sk-ant-...                 # required if LLM_PROVIDER=claude

# Required: External IdP (for local dev you can use a mock JWKS server — see note below)
AUTH_JWKS_URL=http://mock-idp:8080/jwks.json
AUTH_TOKEN_ISSUER=http://mock-idp:8080

# Pre-filled for local dev (do not use in production)
DATABASE_URL=postgresql+asyncpg://rag:rag@postgres:5432/rag
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
FAISS_DATA_PATH=/data/faiss

# Tunable defaults
CHUNK_SIZE=512
CHUNK_OVERLAP=64
CACHE_TTL_SECONDS=3600
QUERY_RATE_LIMIT_PER_MINUTE=20
UPLOAD_RATE_LIMIT_PER_MINUTE=10
MAX_FILE_SIZE_BYTES=10485760
```

> **Local dev auth note**: The `docker-compose.yml` includes a lightweight mock OIDC server
> (`mock-idp` service). It issues JWTs with configurable `sub`, `email`, and `role` claims.
> See `infra/docker/mock-idp/README.md` for token generation commands.

---

## 2. Start All Services

```bash
docker compose -f infra/docker/docker-compose.yml up --build
```

This starts:
- `api` — FastAPI app on `http://localhost:8000`
- `worker` — Celery ingestion worker
- `postgres` — PostgreSQL 15 on port 5432
- `redis` — Redis 7 on port 6379
- `jaeger` — Jaeger UI on `http://localhost:16686`
- `mock-idp` — Mock OIDC server on `http://localhost:8080`

Wait for all services to report healthy:

```bash
docker compose -f infra/docker/docker-compose.yml ps
# All services should show "Up (healthy)"
```

---

## 3. Verify Health

```bash
curl http://localhost:8000/api/v1/health
# Expected: {"status":"healthy","service":"api",...}

curl http://localhost:8000/api/v1/ready
# Expected: {"status":"ready","checks":{"database":"ok","cache":"ok","vector_store":"ok"}}
```

---

## 4. Get a Development Token

```bash
# Generate a contributor token via the mock IdP
curl -s http://localhost:8080/token \
  -d '{"sub":"user-001","email":"dev@example.com","role":"contributor"}' \
  -H "Content-Type: application/json" | jq -r '.access_token'
```

Store it for subsequent requests:

```bash
TOKEN="<paste token here>"
```

---

## 5. Upload a Document

```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/your/document.pdf" \
  -F "description=My test document"
```

Expected response (`202 Accepted`):

```json
{
  "job_id": "7c9e6679-...",
  "document_id": "a1b2c3d4-...",
  "status": "pending",
  "message": "Document accepted for processing..."
}
```

---

## 6. Poll Until Processing Completes

```bash
JOB_ID="7c9e6679-..."  # from step 5

# Poll every 5 seconds
while true; do
  STATUS=$(curl -s http://localhost:8000/api/v1/ingest/$JOB_ID \
    -H "Authorization: Bearer $TOKEN" | jq -r '.status')
  echo "Status: $STATUS"
  [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ] && break
  sleep 5
done
```

---

## 7. Query Your Document

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the main topic of the document?", "top_k": 3}'
```

Expected response:

```json
{
  "query_id": "...",
  "answer": "The document covers...",
  "degraded": false,
  "cache_hit": false,
  "sources": [...],
  "latency_ms": 2341
}
```

Submit the same query again to verify caching (`cache_hit: true`, faster response).

---

## 8. Explore Observability

| Tool | URL | What you see |
|------|-----|--------------|
| Jaeger traces | `http://localhost:16686` | End-to-end request traces |
| Prometheus metrics | `http://localhost:8000/metrics` | Raw Prometheus exposition |
| API docs (OpenAPI) | `http://localhost:8000/docs` | Interactive Swagger UI |
| Redoc | `http://localhost:8000/redoc` | Alternative API docs |

---

## 9. Run the Test Suite

```bash
# Install dev dependencies (once)
pip install -e "shared/[dev]"

# Unit tests (no I/O, fast)
pytest tests/unit/ -v

# Contract tests (against live docker compose stack)
pytest tests/contract/ -v --base-url http://localhost:8000

# Integration tests (requires running stack)
pytest tests/integration/ -v

# Load test (requires running stack, adjust --users as needed)
locust -f tests/load/locustfile.py \
  --host http://localhost:8000 \
  --users 50 --spawn-rate 5 --run-time 60s --headless
```

---

## Stopping and Cleaning Up

```bash
# Stop all services
docker compose -f infra/docker/docker-compose.yml down

# Stop and remove all volumes (wipes DB, Redis, and FAISS data)
docker compose -f infra/docker/docker-compose.yml down -v
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `401 Unauthorized` on every request | Token expired or wrong issuer | Regenerate token (step 4) |
| Job stuck in `pending` | Celery worker not running | Check `docker compose ps worker` |
| `vector_store: error` in `/ready` | FAISS data directory not mounted | Check PV mount in compose |
| LLM calls failing | Invalid API key | Check `OPENAI_API_KEY` in `.env` |
| `409 duplicate_document` | Same file uploaded before | Use a different file or check existing docs |
