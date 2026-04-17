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
claim), `exp`, `iss`. JWKS keys cached in memory with 1-hour refresh TTL.

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
