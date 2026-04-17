# Phase 1 Setup

This document describes the current runnable setup only. Later RAG capabilities such as
ingestion, querying, auth, persistence, workers, and readiness checks are intentionally out
of scope for this phase.

## What Exists

- FastAPI API service in `services/api`
- Modular source layout:
  - `app/` for application wiring, routers, and schemas
  - `services/` for application service logic
  - `core/` for environment configuration
- Environment configuration through `pydantic-settings`
- Basic health endpoint at `GET /api/v1/health`
- Dockerfile for the API service
- Docker Compose file for local API startup
- Unit and contract tests for setup behavior

## Local Run

```bash
pip install -e "services/api[dev]"
PYTHONPATH=services/api/src uvicorn app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/api/v1/health
```

## Docker Run

```bash
cp infra/docker/.env.example infra/docker/.env
docker compose -f infra/docker/docker-compose.yml up --build
```

Health check:

```bash
curl http://localhost:8000/api/v1/health
```

## Tests

```bash
pytest tests/unit tests/contract -v
```
