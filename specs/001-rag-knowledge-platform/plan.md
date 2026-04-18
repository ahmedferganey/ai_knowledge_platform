# Implementation Plan: AI Knowledge Assistant Platform (RAG System)

**Branch**: `001-rag-knowledge-platform` | **Date**: 2026-04-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-rag-knowledge-platform/spec.md`

---

## Summary

Build a production-grade Retrieval-Augmented Generation platform: users upload documents
(PDF, DOCX, CSV) → async ingestion pipeline parses, chunks, embeds, and indexes content per
user → natural language queries retrieve top-K semantically relevant segments → LLM synthesises
grounded answers with source attribution. External OIDC/OAuth2 authentication, per-user
FAISS isolation, Redis response caching, Celery async workers, and full OpenTelemetry
observability. Provider abstractions for LLM, embedding, and vector store enable future
backend swaps without code changes.

---

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI 0.111+, Pydantic v2, SQLAlchemy 2 (async) + asyncpg,
  Alembic, Celery[redis], sentence-transformers (`all-MiniLM-L6-v2`), faiss-cpu,
  openai, anthropic, python-jose[cryptography], slowapi, prometheus-fastapi-instrumentator,
  opentelemetry-sdk, structlog
**Storage**: PostgreSQL 15 (metadata), Redis 7 (cache + Celery broker), FAISS on PV (vectors)
**Testing**: pytest, pytest-asyncio, httpx (contract tests), Locust (load tests)
**Target Platform**: Linux container, Kubernetes 1.28+
**Project Type**: Multi-service web application (REST API + Celery worker)
**Performance Goals**: <5s p95 uncached query, <2s p95 cached query, 100 concurrent users
**Constraints**: External IdP (OIDC/OAuth2, RS256), per-user FAISS index isolation,
  query plaintext never logged, JWKS keys cached 10 min TTL,
  max 1 000 chunks per document (operator-configurable)
**Scale/Scope**: 100 concurrent users, documents ≤ 10 MB, per-user 1 GB storage quota

---

## Constitution Check

*Authority: `.specify/memory/constitution.md` v1.0.0*

- [X] All new endpoints define a versioned API contract before implementation.
      → 5 contracts defined in `contracts/` (health, ingest, ingest-status, query, query-status)
- [X] New domain code does not import internals of another domain.
      → Provider ABCs enforce boundary: LLMProvider, EmbeddingProvider, VectorStoreProvider
- [X] JWT auth applied to all non-health routes.
      → FR-016/FR-017; `/health` and `/ready` explicitly exempt; all others require Bearer token
- [X] Structured logging, metrics, and trace propagation added.
      → structlog + Prometheus metrics endpoint + OpenTelemetry OTLP export (FR-022–FR-025)
- [X] Rate limiting configured for any new public endpoint.
      → slowapi Redis-backed rate limiting on /query and /ingest (FR-019)
- [X] Pydantic v2 models used for all request/response validation.
      → All request/response schemas use `BaseModel` from pydantic v2
- [X] Tests written (contract + unit) and failing before implementation (TDD Red phase).
      → TDD enforced in tasks.md; test tasks precede implementation tasks in every phase
- [X] `tenant_id` included in any new data model.
      → All 5 PostgreSQL entities include `tenant_id UUID NULLABLE`
- [X] Provider interface used for any LLM, embedding, or vector store access.
      → `shared/src/providers/` contains all three ABCs; no direct SDK imports in domain code
- [X] Docker image builds and readiness/liveness probes work before merge.
      → Multi-stage Dockerfiles exist; `/api/v1/health` (liveness) + `/api/v1/ready` (readiness)

**All 10 gates: PASS ✅**

---

## Project Structure

### Documentation (this feature)

```text
specs/001-rag-knowledge-platform/
├── plan.md              ← This file
├── research.md          ← Phase 0: all technical decisions
├── data-model.md        ← Phase 1: PostgreSQL entities, FAISS schema, Redis cache
├── quickstart.md        ← Phase 1: integration test scenarios
├── contracts/           ← Phase 1: versioned API contracts
│   ├── health.md
│   ├── ingest.md
│   ├── ingest-status.md
│   ├── query.md
│   └── query-status.md  ← NEW: async query polling endpoint
└── tasks.md             ← Phase 2: 98 tasks across 8 phases
```

### Source Code (repository root)

```text
services/
├── api/                        FastAPI HTTP service
│   ├── src/
│   │   ├── app/
│   │   │   ├── main.py         FastAPI app factory + lifespan
│   │   │   ├── routers/        Route handlers (health, ingest, query, …)
│   │   │   ├── schemas/        Pydantic v2 request/response models
│   │   │   └── middleware/     Auth, rate limiting, correlation ID
│   │   ├── services/           Domain service layer (pure business logic)
│   │   └── core/               Config singleton, DI wiring
│   ├── Dockerfile              Multi-stage, non-root appuser
│   └── pyproject.toml
│
└── worker/                     Celery ingestion worker
    ├── src/
    │   ├── main.py             Celery app entry-point
    │   ├── config.py           WorkerSettings
    │   ├── tasks/              Celery task definitions
    │   └── processors/         parse → chunk → embed → index pipeline stages
    ├── Dockerfile
    └── pyproject.toml

shared/                         Shared library (installable package)
├── src/
│   ├── config/settings.py      Pydantic BaseSettings (all env vars)
│   ├── db/
│   │   ├── base.py             SQLAlchemy DeclarativeBase
│   │   └── session.py          AsyncEngine + AsyncSessionFactory
│   ├── models/                 SQLAlchemy 2 ORM mapped classes
│   │   ├── user.py
│   │   ├── document.py
│   │   ├── chunk.py
│   │   ├── ingestion_job.py
│   │   └── query_log.py
│   └── providers/              Provider ABCs (never import concrete impls directly)
│       ├── embedding.py        EmbeddingProvider ABC
│       ├── llm.py              LLMProvider ABC + ProviderUnavailableError
│       └── vector_store.py     VectorStoreProvider ABC + ChunkResult
├── alembic/                    DB migrations
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
│       └── 0001_initial_schema.py
└── pyproject.toml

infra/
├── docker/
│   ├── docker-compose.yml      Local dev (postgres, redis, api, worker, jaeger)
│   └── .env.example            All operator-configurable env vars
└── k8s/                        Kubernetes manifests (Deployments, Services, HPA, …)

tests/
├── contract/                   API schema conformance (httpx + TestClient)
├── integration/                Inter-service + DB + cache (requires running stack)
├── unit/                       Pure logic, no I/O
└── load/                       Locust scenarios

.github/workflows/
└── ci.yml                      ruff → mypy → pytest → docker build → GHCR push
```

---

## Implementation Phases

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 1: Setup | Repo structure, packages, CI, Docker skeleton | ✅ Complete |
| Phase 2: Foundation | Shared lib, DB models, provider ABCs, Alembic, health endpoints | ✅ Complete |
| Phase 3: Ingestion (US2) | Document upload, Celery parsing pipeline, chunk DB persistence | ⬜ Pending |
| Phase 4: Query + Embeddings (US1) | FAISS indexing, semantic retrieval, LLM synthesis | ⬜ Pending |
| Phase 5: Source Attribution (US3) | Sources array, traceability in response | ⬜ Pending |
| Phase 6: Auth + Rate Limiting (US4) | JWT middleware, RBAC, JWKS cache, slowapi | ⬜ Pending |
| Phase 7: Observability (US5) | Prometheus metrics, structlog events, OTLP tracing | ⬜ Pending |
| Phase 8: K8s + Load Tests | Kubernetes manifests, Locust scenarios, HPA | ⬜ Pending |

---

## Key Design Decisions (summary — details in research.md)

| Area | Decision |
|------|---------|
| Async tasks | Celery + Redis broker (not FastAPI BackgroundTasks) |
| DB | PostgreSQL 15 + SQLAlchemy 2 async + asyncpg + Alembic |
| Embedding | `all-MiniLM-L6-v2` (sentence-transformers, CPU, 384-dim) |
| Vector isolation | One FAISS `IndexFlatIP` per user at `/data/faiss/{user_id}/` |
| LLM | GPT-4o primary, Claude Sonnet secondary, via `LLMProvider` ABC |
| Auth | `python-jose` RS256, JWKS cached 10 min TTL, fail-closed on expiry |
| Rate limiting | `slowapi` Redis-backed, per-user, 20 q/min default |
| Chunking | Recursive splitter, 512 tokens, 64 overlap, max 1 000 chunks/doc |
| PDF parsing | `pdfplumber` (layout-aware) |
| CI/CD | GitHub Actions → GHCR, SHA-tagged images, K8s rollout |
| Async query path | Polling job ID (202 + query_job_id → GET /query/{id}) |
| PII in logs | Query hash only (SHA-256); query plaintext never logged |
| IdP unavailability | Serve from JWKS cache; fail closed after 10 min TTL expiry |
| Large docs | Hard ceiling 1 000 chunks; fail job with error, no partial indexing |
| Admin role | Defined in DB + RBAC from v1; management API endpoints deferred to v2 |

---

## Complexity Tracking

No Constitution Check violations. All gates pass without deviation.
