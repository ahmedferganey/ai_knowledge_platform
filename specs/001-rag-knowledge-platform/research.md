# Research: AI Knowledge Assistant Platform (RAG System)

**Branch**: `001-rag-knowledge-platform`
**Date**: 2026-04-17
**Feeds into**: [plan.md](plan.md)

---

## Decision 1: Async Task Queue

**Decision**: Celery with Redis as broker

**Rationale**: Document ingestion (parse → chunk → embed → index) is CPU and I/O bound and
can take 10–180 seconds for a large document. It must not block the HTTP request lifecycle.
Celery with Redis broker is the most mature Python async task system, with strong
observability (Celery Flower), retry semantics, task state persistence, and wide ecosystem
support. It integrates cleanly with FastAPI via `BackgroundTasks` dispatch or direct
`.delay()` / `.apply_async()` calls.

**Alternatives considered**:
- **ARQ** (asyncio-native): Lighter weight, excellent for small projects, but less mature
  ecosystem, limited task visibility tooling, and less battle-tested at scale.
- **Dramatiq**: Good alternative but smaller community and fewer integrations.
- **FastAPI BackgroundTasks**: Runs in-process — cannot be scaled independently, no retry,
  no task state persistence. Unacceptable for production ingestion.

---

## Decision 2: Relational Database

**Decision**: PostgreSQL 15 with SQLAlchemy 2 (async) + asyncpg driver + Alembic migrations

**Rationale**: PostgreSQL is the production-standard relational database for Python services.
SQLAlchemy 2's async mode with asyncpg provides the performance needed for concurrent requests.
Alembic provides schema migration management. The data model requires transactional guarantees
(ingestion job state transitions, per-user duplicate detection via unique constraint).

**Alternatives considered**:
- **SQLite**: No concurrent write support, no production K8s PV story. Rejected.
- **MySQL**: Weaker JSON support, less idiomatic with SQLAlchemy async. Rejected.
- **MongoDB**: Schema-less flexibility not needed here; relational integrity on job state is
  important. Rejected for primary metadata store.

---

## Decision 3: Embedding Model

**Decision**: `all-MiniLM-L6-v2` via `sentence-transformers` for v1 MVP

**Rationale**: `all-MiniLM-L6-v2` produces 384-dimensional embeddings with excellent
semantic quality for English-language retrieval tasks. At 22M parameters it runs efficiently
on CPU (sub-100ms per batch). It is freely available, requires no external API call (no
latency, no cost, no dependency on external service for embedding), and is the most commonly
used model for RAG prototypes that graduate to production.

**Alternatives considered**:
- **OpenAI text-embedding-3-small**: Higher quality embeddings but adds API dependency,
  latency, and cost for every ingestion. Switching to it later is easy via the
  `EmbeddingProvider` interface.
- **OpenAI text-embedding-ada-002**: Older model, superseded by 3-small.
- **BAAI/bge-large-en-v1.5**: Higher quality but larger model (335M params), requires GPU
  for production throughput. Future upgrade path.

---

## Decision 4: Vector Store Isolation Strategy

**Decision**: One FAISS `IndexFlatIP` (inner product / cosine similarity) per user, stored
at `/data/faiss/{user_id}/index.faiss` on a persistent volume. Chunk ID mapping stored in a
parallel JSON file `{user_id}/chunk_map.json` (maps FAISS index position → chunk UUID).

**Rationale**: Per-user FAISS index gives the simplest possible isolation guarantee — no
query-time filtering needed, no risk of cross-user data leakage from a misconfigured filter.
`IndexFlatIP` with L2-normalized vectors is equivalent to cosine similarity and requires no
training. For v1 corpus sizes (hundreds to low thousands of chunks per user) it is fast enough
without an ANN index. The `VectorStoreProvider` abstraction means this is replaced by
Pinecone/Qdrant with a new implementation when scale demands it.

**Alternatives considered**:
- **Single shared FAISS index + metadata filter**: Requires custom filtering post-search,
  risk of filter bugs causing data leakage. Rejected for v1.
- **Pinecone managed**: Excellent production choice but adds cost and external dependency.
  Future upgrade via provider interface.
- **Qdrant self-hosted**: Strong metadata filtering, good Kubernetes story. Best future
  upgrade path for multi-tenant scale.
- **ChromaDB**: Good embedded option but lacks production horizontal scaling story.

---

## Decision 5: LLM Provider Strategy

**Decision**: `openai` SDK (GPT-4o) as primary; `anthropic` SDK (Claude Sonnet) as secondary.
Active provider selected by `LLM_PROVIDER` env var. Both implement `LLMProvider` ABC.

**Rationale**: OpenAI GPT-4o offers the best balance of response quality, context window
(128k tokens), and JSON-mode reliability for structured answer generation. The Anthropic SDK
(Claude Sonnet) is the secondary option, providing a fallback if pricing, rate limits, or
quality requirements shift. The `LLMProvider` ABC ensures zero application code changes when
switching.

**Prompt architecture**: System prompt (role + grounding instructions) + formatted chunk
context (up to `MAX_CONTEXT_TOKENS` tokens) + user query. Chunk context is trimmed from the
end if token budget is exceeded. Grounding instruction: "Answer only based on the provided
context. If the answer cannot be determined from the context, say so explicitly."

**Alternatives considered**:
- **LangChain / LlamaIndex**: Useful abstractions but add significant dependency weight,
  version churn, and opacity. Direct SDK calls with our own `LLMProvider` interface gives
  full control and simpler debugging. Rejected for v1.
- **vLLM / local models**: Out of scope for v1 per spec assumptions. Provider interface
  supports future addition.

---

## Decision 6: Authentication & Token Validation

**Decision**: `python-jose[cryptography]` for JWT validation. JWKS endpoint URL configured
via `AUTH_JWKS_URL` env var. Token claims: `sub` (user external ID), `email`, `role` (custom
claim), `exp`, `iss`. JWKS keys cached in memory with a **10-minute TTL** (operator-configurable
via `AUTH_JWKS_CACHE_TTL_SECONDS`). If the IdP JWKS endpoint is unreachable, the system
continues validating tokens from the cached key set until the cache expires; after expiry, all
authenticated endpoints return 503 until keys are refreshed. Cold start with no cached keys
and an unreachable IdP is a hard startup failure.

**Rationale**: `python-jose` is the standard Python JWT library supporting RS256 and ES256.
Fetching public keys from the IdP's JWKS endpoint (rather than storing them in config) means
key rotation is handled automatically. The `role` claim approach avoids a DB lookup on every
request — user profile is created/synced lazily on first authenticated request.

**Alternatives considered**:
- **authlib**: More complete OAuth2 client library but heavier weight than needed for
  token validation only.
- **jwt (PyJWT)**: Also viable, similar weight. `python-jose` has broader algorithm support.

---

## Decision 7: Rate Limiting

**Decision**: `slowapi` with Redis storage. Limits: `reader` = 20 queries/min,
`contributor` = 20 queries/min + 10 uploads/min. Configured via env vars, not hardcoded.

**Rationale**: `slowapi` is a FastAPI-native rate limiting library (inspired by Flask-Limiter)
with Redis backend support for distributed rate counting across multiple API pod replicas.
Redis storage ensures counts are shared across pods — an in-memory counter would be incorrect
in a horizontally scaled deployment.

**Alternatives considered**:
- **Kong / Nginx rate limiting**: Infrastructure-level rate limiting; removes visibility from
  application code and loses `user_id`-based limiting precision. Suitable as a future
  additional layer, not a replacement.
- **Custom Redis token bucket**: Viable but unnecessary when `slowapi` already solves this.

---

## Decision 8: Chunking Strategy

**Decision**: Recursive character text splitter. Default: `CHUNK_SIZE=512` tokens,
`CHUNK_OVERLAP=64` tokens. Configurable via env vars per deployment.

**Rationale**: Recursive splitting (try paragraph → sentence → word boundaries before hard
split) preserves semantic coherence better than fixed-size splitting. 512 tokens with 64-token
overlap is the empirically validated sweet spot for most RAG retrieval quality benchmarks
(MTEB, BEIR). Configurable to allow tuning per document corpus.

**Alternatives considered**:
- **Semantic chunking** (split at sentence embedding similarity drops): Higher quality but
  significantly more compute per document. Future upgrade path.
- **Fixed 256-token chunks**: Too small, fragments multi-sentence concepts. Rejected.
- **Document-level chunks**: Too large, dilutes similarity scores. Rejected.

---

## Decision 9: PDF Parsing

**Decision**: `pdfplumber` for PDF parsing.

**Rationale**: `pdfplumber` provides layout-aware text extraction, handles multi-column
documents, tables, and headers/footers better than `PyPDF2`. It exposes page coordinates
for future page-number attribution in source references. Pure Python, no system dependencies.

**Alternatives considered**:
- **PyPDF2 / pypdf**: Simpler but poor layout handling on complex PDFs. Rejected.
- **pymupdf (fitz)**: High quality but AGPL license — requires careful license review before
  production use. Deferred.
- **Apache Tika / Unstructured**: Best-in-class document parsing but require JVM or heavy
  system dependencies. Future upgrade for complex document types.

---

## Decision 10: CI/CD Pipeline

**Decision**: GitHub Actions. `ci.yml`: on every PR → ruff (lint) → mypy (type check) →
pytest unit+contract → docker build (no push). `deploy.yml`: on merge to `main` → build +
push to GHCR → `kubectl rollout restart` staging → manual approval → production rollout.

**Rationale**: GitHub Actions is already in the ecosystem (repo on GitHub), zero additional
infrastructure, GHCR is free for private images. Staging promotion with manual approval gate
prevents accidental production deployments.

**Image tagging**: `ghcr.io/{owner}/{service}:{git_sha}` + `latest` tag updated on main.
Kubernetes manifests reference the SHA tag (immutable), not `latest` (mutable).

---

## Decision 11: Async Query Path

**Decision**: POST /query returns 202 + `query_job_id` for long-running queries; result
polled via GET /query/{query_job_id}. This mirrors the ingestion job-status pattern already
established in the design. The synchronous path (200 immediate response) remains the default;
the async path activates only when LLM processing is projected to exceed the configured
`QUERY_SYNC_TIMEOUT_SECONDS` threshold. A new `QueryJob` entity tracks async query state.

**Rationale**: Reusing the polling pattern keeps the API surface consistent and avoids the
complexity of persistent WebSocket connections or Server-Sent Events for v1. The Celery
infrastructure needed for async dispatch is already in place for ingestion.

**Alternatives considered**:
- **Streaming (SSE)**: Higher UX quality for progressive token delivery but requires persistent
  connection management and more complex client support. Suitable future enhancement.
- **Synchronous-only**: Simpler but blocks on slow LLM responses, violating the <5s p95 SLA
  for all network conditions. Async path is a safety valve for tail latency.

---

## Decision 12: Query Content Privacy (PII in Logs)

**Decision**: Query text is never written to any log sink, metric label, or trace attribute.
Only the SHA-256 hash of the normalised query (`lowercase(strip(query_text))`) is recorded —
the same hash used for Redis cache key construction. This applies to structured logs,
Prometheus label values, and OpenTelemetry span attributes.

**Rationale**: Organizational knowledge base queries may contain confidential business
information, employee names, product plans, or legally sensitive content. Logging plaintext
queries creates data residency and compliance risk without meaningful operational benefit —
the hash is sufficient for cache analysis, deduplication, and latency attribution.

**Alternatives considered**:
- **Truncated prefix (first 50 chars)**: Partial protection but inconsistent — sensitive terms
  in the first 50 chars are still exposed. Rejected.
- **Full plaintext**: Maximum debuggability but unacceptable compliance risk for enterprise use.

---

## Decision 13: Document Chunk Ceiling

**Decision**: Hard ceiling on extracted chunks per document, default 1 000, configurable via
`MAX_CHUNKS_PER_DOCUMENT` env var. If the ingestion worker determines that a document would
produce more chunks than the ceiling, the job is set to `failed` with a descriptive error
message. No partial content is indexed.

**Rationale**: A 500-page PDF within the 10 MB file size limit can produce thousands of
512-token chunks, causing FAISS index size to balloon and degrading retrieval latency for
that user. Failing fast with a clear error is safer than silent truncation (which would yield
misleading answers from incomplete knowledge) or indefinite processing (which could consume
worker resources without bound).

**Alternatives considered**:
- **Silent truncation**: Index first N chunks, discard rest, mark completed. Rejected — users
  would receive answers that miss content from later in the document without any indication.
- **Auto-split into multiple jobs**: Adds coordination complexity for v1. Better future story.
- **No ceiling (rely on file size only)**: A 9 MB PDF with tiny fonts can have 10k+ chunks.
  File size alone is insufficient to bound processing time and index size.

---

## Decision 14: Admin Role Scope

**Decision**: Three roles defined from v1: `reader` (query only), `contributor` (query +
ingest), `admin` (all contributor actions; management API access reserved for v2). The `admin`
role is stored in the User record from day one, sourced from the IdP token `role` claim.
Dedicated admin management endpoints (user listing, quota adjustment, role changes) are out
of scope for v1 and deferred to v2. In v1, quota and role management is handled via IdP
claim configuration or direct operator tooling.

**Rationale**: Defining the role in the data model and RBAC enforcement now costs one enum
value and prevents a future schema migration. Deferring the management UI/API avoids scope
creep without compromising the long-term architecture. The `admin` check in auth middleware
is additive — it simply allows all contributor operations and future admin-gated routes.

**Alternatives considered**:
- **Two roles only (reader + contributor) in v1**: Simpler short-term but guaranteed schema
  migration when admin management is added. Rejected — the cost of adding the field now is
  near zero.
- **Full admin API in v1**: Increases scope of US4 significantly. Deferred to v2.

---

## Resolved NEEDS CLARIFICATION Items

All `NEEDS CLARIFICATION` items from the plan template have been resolved:

| Item | Resolution |
|------|-----------|
| Language/Version | Python 3.11+ confirmed |
| Primary Dependencies | All libraries selected (see above) |
| Storage | PostgreSQL + Redis + FAISS on PV |
| Testing | pytest + pytest-asyncio + Locust |
| Target Platform | Linux container, K8s 1.28+ |
| Performance Goals | <5s p95 uncached, <2s p95 cached, 100 concurrent |
| Constraints | External IdP, per-user FAISS, provider interfaces |
| Scale/Scope | 100 concurrent users, docs ≤10 MB |
| Async query path | Polling job ID (mirrors ingestion); sync default, async on tail latency |
| PII in query logs | Query hash only (SHA-256); plaintext never logged |
| IdP outage handling | JWKS cached 10 min TTL; fail closed on cache expiry |
| Large document ceiling | 1 000 chunks max per doc (configurable); fail job on exceed |
| Admin role | Defined in v1 data model + RBAC; management API deferred to v2 |
