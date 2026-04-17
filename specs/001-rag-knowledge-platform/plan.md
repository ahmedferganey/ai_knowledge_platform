# Implementation Plan: AI Knowledge Assistant Platform (RAG System)

**Branch**: `001-rag-knowledge-platform` | **Date**: 2026-04-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-rag-knowledge-platform/spec.md`

## Summary

Build a production-grade Retrieval-Augmented Generation (RAG) platform that accepts document
uploads (PDF, DOCX, CSV), generates embeddings, stores them via a pluggable vector store
(FAISS v1), and answers natural language queries using a configurable LLM provider (OpenAI
primary, Claude secondary). The system exposes a versioned FastAPI async REST API, enforces
per-user document isolation via external OIDC/OAuth2 token validation, and degrades gracefully
when the LLM is unavailable by returning retrieved segments with `degraded: true`.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI 0.111+, Pydantic v2, SQLAlchemy 2 (async), asyncpg,
  sentence-transformers, faiss-cpu, openai, anthropic, python-jose[cryptography],
  structlog, prometheus-fastapi-instrumentator, opentelemetry-sdk, opentelemetry-exporter-otlp,
  celery[redis], redis, pdfplumber, python-docx, slowapi, pytest, pytest-asyncio, httpx, locust
**Storage**: PostgreSQL 15 (metadata, job state, user profiles) · Redis 7 (cache + task broker)
  · FAISS index files on persistent volume (per-user, serialized)
**Testing**: pytest + pytest-asyncio (unit/integration/contract) · Locust (load)
**Target Platform**: Linux container (Docker) · Kubernetes 1.28+
**Project Type**: Async web-service (multi-service: API + background worker + shared library)
**Performance Goals**: <5s p95 uncached query · <2s p95 cached query · 100 concurrent users
**Constraints**: External IdP only (no self-issued tokens) · Per-user FAISS index (isolation)
  · FAISS index serialized to PVC (survives pod restart) · Provider interfaces mandatory
**Scale/Scope**: 100 concurrent query users · Documents ≤10 MB · Chunks configurable
  · Single deployment (no multi-tenancy active in v1, tenant_id fields present)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*
*Authority: `.specify/memory/constitution.md` v1.0.0*

- [x] All new endpoints define a versioned API contract before implementation.
      → Contracts in `contracts/`: query.md, ingest.md, ingest-status.md, health.md
- [x] New domain code does not import internals of another domain.
      → `shared/` package exposes provider interfaces; services import only those interfaces.
- [x] JWT auth applied to all non-health routes.
      → Auth middleware validates bearer tokens from external IdP on all routes except `/api/v1/health`.
- [x] Structured logging, metrics, and trace propagation added.
      → structlog JSON + prometheus-fastapi-instrumentator + OpenTelemetry OTLP in every service.
- [x] Rate limiting configured for any new public endpoint.
      → slowapi (Redis-backed) applied to `/api/v1/query` and `/api/v1/ingest`.
- [x] Pydantic v2 models used for all request/response validation.
      → All routers use Pydantic v2 schemas in `services/api/src/schemas/`.
- [x] Tests written (contract + unit) and failing before implementation (TDD Red phase).
      → Tests in `tests/contract/`, `tests/unit/`, `tests/integration/`, `tests/load/`.
- [x] `tenant_id` included in any new data model.
      → All DB models include `tenant_id UUID` (nullable in v1, enforced in future multi-tenant).
- [x] Provider interface used for any LLM, embedding, or vector store access.
      → `LLMProvider`, `EmbeddingProvider`, `VectorStoreProvider` ABCs in `shared/src/providers/`.
- [x] Docker image builds and readiness/liveness probes work before merge.
      → `/api/v1/health` (liveness) · `/api/v1/ready` (readiness) · multi-stage Dockerfiles.

**Constitution Check: ALL GATES PASS. Proceeding to Phase 0.**

## Project Structure

### Documentation (this feature)

```text
specs/001-rag-knowledge-platform/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   ├── query.md
│   ├── ingest.md
│   ├── ingest-status.md
│   └── health.md
└── tasks.md             ← /speckit-tasks output (not yet created)
```

### Source Code (repository root)

```text
ai_knowledge_platform/
├── services/
│   ├── api/                         # FastAPI HTTP service
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── src/
│   │       ├── main.py              # App factory, lifespan, middleware wiring
│   │       ├── config.py            # Pydantic Settings (env-driven)
│   │       ├── dependencies.py      # FastAPI dependency injection
│   │       ├── routers/
│   │       │   ├── query.py         # POST /api/v1/query
│   │       │   ├── ingest.py        # POST /api/v1/ingest, GET /api/v1/ingest/{job_id}
│   │       │   └── health.py        # GET /api/v1/health, GET /api/v1/ready
│   │       ├── middleware/
│   │       │   ├── auth.py          # Bearer token validation (OIDC/OAuth2)
│   │       │   ├── rate_limit.py    # slowapi Redis-backed limiter
│   │       │   └── tracing.py       # OpenTelemetry trace context injection
│   │       └── schemas/             # Pydantic v2 request/response models
│   │           ├── query.py
│   │           ├── ingest.py
│   │           └── health.py
│   │
│   └── worker/                      # Celery background worker
│       ├── Dockerfile
│       ├── pyproject.toml
│       └── src/
│           ├── main.py              # Celery app + signal handlers
│           ├── config.py            # Worker-specific Pydantic Settings
│           ├── tasks/
│           │   └── ingestion.py     # ingest_document Celery task
│           └── processors/
│               ├── parser.py        # PDF/DOCX/CSV → raw text
│               ├── chunker.py       # text → chunks (configurable size/overlap)
│               └── indexer.py       # chunks → embeddings → FAISS + DB
│
├── shared/                          # Shared Python package (both services import this)
│   ├── pyproject.toml
│   └── src/
│       ├── models/                  # SQLAlchemy 2 ORM + Pydantic domain models
│       │   ├── user.py
│       │   ├── document.py
│       │   ├── chunk.py
│       │   ├── ingestion_job.py
│       │   └── query_log.py
│       ├── providers/               # Abstract provider interfaces (ABCs)
│       │   ├── vector_store.py      # VectorStoreProvider ABC
│       │   ├── embedding.py         # EmbeddingProvider ABC
│       │   └── llm.py              # LLMProvider ABC
│       ├── impl/                    # Concrete provider implementations
│       │   ├── faiss_store.py       # FAISS + PV serialization
│       │   ├── sentence_transformer.py  # SentenceTransformer embedding
│       │   ├── openai_llm.py        # OpenAI GPT-4o
│       │   └── claude_llm.py        # Anthropic Claude
│       ├── cache/
│       │   └── redis_cache.py       # Response cache client
│       ├── db/
│       │   ├── session.py           # Async SQLAlchemy engine + session factory
│       │   └── migrations/          # Alembic migrations
│       └── config/
│           └── settings.py          # Base Pydantic Settings
│
├── infra/
│   ├── docker/
│   │   └── docker-compose.yml       # Local dev: api + worker + postgres + redis + jaeger
│   └── k8s/
│       ├── api/                     # Deployment, Service, HPA, PDB
│       ├── worker/                  # Deployment, HPA
│       ├── postgres/                # StatefulSet, PVC
│       ├── redis/                   # StatefulSet, PVC
│       ├── monitoring/              # Prometheus, Grafana, AlertManager
│       └── config/                  # ConfigMaps, Secrets (sealed)
│
├── tests/
│   ├── contract/                    # OpenAPI schema conformance tests
│   ├── integration/                 # Inter-service + DB + cache tests
│   ├── unit/                        # Pure domain logic (no I/O)
│   └── load/                        # Locust scenarios
│
└── .github/
    └── workflows/
        ├── ci.yml                   # lint → test → build → push
        └── deploy.yml               # staging → production promotion
```

**Structure Decision**: Multi-service monorepo. `services/api` handles HTTP; `services/worker`
handles async ingestion. Both depend on `shared/` which owns all domain models, provider
interfaces, and implementations. No service imports internals of the other. `tests/` at repo
root covers cross-service scenarios (integration, contract, load).

## Phase 0: Research Summary

See [research.md](research.md) for full decision log. Key decisions:

| Concern | Decision |
|---------|----------|
| Async task queue | Celery + Redis broker (vs. ARQ, Dramatiq) |
| Relational store | PostgreSQL 15 async (SQLAlchemy 2 + asyncpg) |
| Embedding model | `all-MiniLM-L6-v2` (sentence-transformers) for MVP |
| Vector isolation | One FAISS index per user, stored at `/data/faiss/{user_id}/` on PVC |
| LLM primary | OpenAI GPT-4o via `openai` SDK |
| LLM secondary | Anthropic Claude Sonnet via `anthropic` SDK |
| Auth validation | `python-jose` + JWKS endpoint fetch from IdP |
| Rate limiting | `slowapi` with Redis storage (token bucket, per user_id claim) |
| Tracing | OpenTelemetry SDK + OTLP exporter (Jaeger in dev, Tempo in prod) |
| Chunk strategy | Recursive character splitter, 512 tokens default, 64 token overlap |
| PDF parsing | `pdfplumber` (layout-aware, handles multi-column) |
| CI/CD | GitHub Actions: lint (ruff+mypy) → unit tests → build images → push to GHCR |

## Phase 1: Design Artifacts

See:
- [data-model.md](data-model.md) — full entity schema with field types and constraints
- [contracts/query.md](contracts/query.md) — `POST /api/v1/query`
- [contracts/ingest.md](contracts/ingest.md) — `POST /api/v1/ingest`
- [contracts/ingest-status.md](contracts/ingest-status.md) — `GET /api/v1/ingest/{job_id}`
- [contracts/health.md](contracts/health.md) — `GET /api/v1/health`, `GET /api/v1/ready`
- [quickstart.md](quickstart.md) — local dev setup and first API call

## Implementation Phases

### Phase 0 — Foundation
**Goal**: Runnable skeleton with health endpoint, config, logging, and CI.

- Repo structure scaffolded per Project Structure above.
- `shared/` package: Pydantic Settings (env-driven config), structlog JSON logging bootstrap,
  SQLAlchemy async engine factory, Alembic migration baseline.
- `services/api`: FastAPI app factory, lifespan hook (DB connection pool), health router
  (`/api/v1/health` returns `{"status":"healthy"}`), OpenTelemetry middleware wired.
- `services/worker`: Celery app with Redis broker, signal handlers for structured startup log.
- `infra/docker/docker-compose.yml`: api + worker + postgres + redis + jaeger (all pinned versions).
- `.github/workflows/ci.yml`: ruff lint → mypy type check → pytest unit → docker build.
- **Exit gate**: `docker compose up` runs all services; `GET /api/v1/health` returns 200.

### Phase 1 — Ingestion Pipeline
**Goal**: Upload document → job created → async processing → stored chunks in DB.

- `POST /api/v1/ingest` endpoint: multipart upload, Pydantic validation, quota check,
  content hash deduplication (409 if duplicate), store Document record (status=pending),
  create IngestionJob, dispatch Celery task, return 202 with job_id.
- `GET /api/v1/ingest/{job_id}` endpoint: returns IngestionJob status.
- Celery task `ingest_document`: update job status → parse file → chunk → store Chunk records
  → update Document status (completed/failed).
- Parsers: `pdfplumber` for PDF, `python-docx` for DOCX, `csv.reader` for CSV.
- Chunker: recursive character splitter with configurable `CHUNK_SIZE` and `CHUNK_OVERLAP`.
- No embeddings yet — chunks stored as text only in this phase.
- **Exit gate**: Upload a PDF → poll job until `completed` → query DB and see Chunk rows.

### Phase 2 — Embeddings + Vector Store
**Goal**: Chunks → embeddings → FAISS index persisted to volume.

- `EmbeddingProvider` ABC: `embed_texts(texts: list[str]) -> list[list[float]]`.
- `SentenceTransformerEmbedding` implementation (all-MiniLM-L6-v2, batch encode).
- `VectorStoreProvider` ABC: `add(chunks)`, `search(query_vector, k, owner_id) -> list[Chunk]`.
- `FAISSVectorStore` implementation: one `IndexFlatIP` per user at `/data/faiss/{user_id}/index.faiss`;
  loaded on first use, persisted after each write, reloaded from disk on startup.
- Indexer in worker calls embedding provider → vector store provider; stores embedding in Chunk.
- **Exit gate**: Upload PDF → job completes → FAISS file exists on volume → direct Python
  call to `FAISSVectorStore.search(...)` returns relevant chunks.

### Phase 3 — Retrieval System
**Goal**: Query text → semantically relevant chunks filtered by owner.

- Retrieval service function: `retrieve(query: str, owner_id: UUID, k: int) -> list[Chunk]`.
- Embeds query via `EmbeddingProvider` → calls `VectorStoreProvider.search(owner_id=...)`.
- Owner isolation guaranteed at retrieval layer — search scoped to user's own FAISS index.
- Relevance threshold: configurable minimum similarity score; chunks below threshold excluded.
- Empty retrieval path: returns empty list (caller handles "no relevant info" response).
- **Exit gate**: HTTP call to `POST /api/v1/query` returns source segments for a known-good
  query without LLM (inference stubbed to return `degraded: true`).

### Phase 4 — LLM Inference
**Goal**: Retrieved chunks + query → synthesized answer or degraded segments.

- `LLMProvider` ABC: `generate(system_prompt, context_chunks, query) -> str`.
- `OpenAILLMProvider`: GPT-4o, async streaming disabled (sync for MVP), configurable model.
- `ClaudeLLMProvider`: Anthropic Claude Sonnet, same interface.
- Active provider selected by `LLM_PROVIDER` env var (`openai` | `claude`).
- Prompt template: system prompt + concatenated chunk texts + user query. Token budget enforced.
- Degraded path: if provider raises `ProviderUnavailableError`, return `{degraded: true, sources: [...]}`
  without calling LLM.
- Answer assembled as `Answer` domain model with `answer_text`, `sources`, `degraded` flag.
- **Exit gate**: `POST /api/v1/query` returns a complete `Answer` with `degraded: false`
  and `sources` populated from a real document.

### Phase 5 — Caching + Auth
**Goal**: JWT auth on all routes; Redis cache for repeated queries; rate limiting.

- Auth middleware: extract Bearer token → fetch JWKS from configured IdP URL →
  validate RS256 signature + exp + iss claims → inject `current_user` into request context.
- Role enforcement: `reader` = query only; `contributor` = query + ingest. 403 if insufficient role.
- Redis response cache: cache key = `sha256(user_id + normalized_query_text)`, TTL configurable.
  Cache-hit path skips retrieval + LLM; returns cached `Answer` with `cache_hit: true`.
- Rate limiter: `slowapi` with Redis storage; limits defined per role (configurable env vars).
  429 response includes `Retry-After` header.
- **Exit gate**: Token-less request returns 401; contributor uploads doc; reader queries and
  gets cached response on second call; rate limit returns 429 after threshold.

### Phase 6 — Observability
**Goal**: Full structured logging, Prometheus metrics, distributed traces; Grafana dashboards.

- structlog configured globally: JSON output, log level from env, auto-injects `trace_id`,
  `service_name`, `user_id_hash` (SHA-256 of user_id), `timestamp` (ISO8601).
- Prometheus: `prometheus-fastapi-instrumentator` auto-instruments HTTP metrics. Custom counters:
  `rag_cache_hits_total`, `rag_cache_misses_total`, `rag_llm_tokens_used_total`,
  `rag_ingestion_jobs_total{status}`, `rag_degraded_responses_total`.
- OpenTelemetry: SDK initialized with OTLP exporter; every router operation creates a span;
  `traceparent` propagated to worker via Celery task headers.
- `/api/v1/ready` readiness probe: checks DB connection + Redis ping; returns 503 if either fails.
- Grafana dashboards defined as JSON in `infra/k8s/monitoring/dashboards/`.
- **Exit gate**: Prometheus scrape returns all custom metrics; Jaeger UI shows end-to-end
  trace from HTTP request through Celery task; Grafana dashboard loads with live data.

### Phase 7 — Deployment
**Goal**: Production Docker images + K8s manifests + GitHub Actions deploy pipeline.

- Dockerfiles: multi-stage (builder → runtime); non-root user (`appuser`); `python:3.11-slim`.
  Image tags = git SHA. Built and pushed to GHCR in CI.
- K8s `services/api`: Deployment (minReplicas=2), HPA (CPU 70%), PDB (minAvailable=1),
  Service (ClusterIP), Ingress (TLS), liveness + readiness probes.
- K8s `services/worker`: Deployment (minReplicas=1), HPA (Celery queue depth metric).
- K8s storage: PostgreSQL StatefulSet + PVC; Redis StatefulSet + PVC;
  FAISS data PVC (ReadWriteMany or per-worker PVC + index sync strategy).
- Secrets: Kubernetes Secrets for DB URL, Redis URL, IdP JWKS URL, OpenAI/Anthropic API keys.
- `deploy.yml`: on push to `main` → build → push → `kubectl rollout restart` (staging);
  manual approval gate for production.
- **Exit gate**: `kubectl rollout status deployment/api` completes; `kubectl get hpa`
  shows metrics attached; end-to-end smoke test passes against K8s deployment.

## Complexity Tracking

No constitution violations. No complexity justification required.
