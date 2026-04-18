# ai_knowledge_platform Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-17

## Active Technologies
- Python 3.11+ + FastAPI 0.111+, Pydantic v2, SQLAlchemy 2 (async) + asyncpg, (001-rag-knowledge-platform)
- PostgreSQL 15 (metadata), Redis 7 (cache + Celery broker), FAISS on PV (vectors) (001-rag-knowledge-platform)

- Python 3.11+ + FastAPI 0.111+, Pydantic v2, SQLAlchemy 2 (async), asyncpg, (001-rag-knowledge-platform)

## Project Structure

```text
services/api/          FastAPI HTTP service (routers, middleware, schemas)
services/worker/       Celery ingestion worker (tasks, processors)
shared/                Shared models, provider interfaces, implementations, DB
infra/docker/          Local dev docker-compose + .env.example
infra/k8s/             Kubernetes manifests (api, worker, postgres, redis, monitoring)
tests/                 contract/, integration/, unit/, load/
specs/                 Feature specs, plans, data models, contracts
```

## Commands

```bash
# Local dev
docker compose -f infra/docker/docker-compose.yml up --build

# Run tests
pytest tests/unit/ -v
pytest tests/contract/ -v --base-url http://localhost:8000
pytest tests/integration/ -v

# Lint and type check
ruff check .
mypy services/ shared/ --strict

# Database migrations
alembic -c shared/src/db/alembic.ini upgrade head

# Load test
locust -f tests/load/locustfile.py --host http://localhost:8000 --headless -u 50 -r 5 -t 60s
```

## Code Style

- Python 3.11+ with full type annotations (mypy strict mode)
- ruff for linting and import sorting; black-compatible line length (88)
- All request/response models use Pydantic v2
- Async-first: all route handlers and service functions are `async def`
- Provider interfaces (ABC) for LLM, embedding, vector store — never import concrete impls directly
- `tenant_id` field on all database models (nullable in v1)
- structlog for all logging — never use `print()` or stdlib `logging` directly

## Recent Changes
- 001-rag-knowledge-platform: Added Python 3.11+ + FastAPI 0.111+, Pydantic v2, SQLAlchemy 2 (async) + asyncpg,

- 001-rag-knowledge-platform: Added Python 3.11+ + FastAPI 0.111+, Pydantic v2, SQLAlchemy 2 (async), asyncpg,

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
