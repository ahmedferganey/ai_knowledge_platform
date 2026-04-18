# Data Model: AI Knowledge Assistant Platform (RAG System)

**Branch**: `001-rag-knowledge-platform`
**Date**: 2026-04-17
**Source**: `spec.md` entities + `research.md` decisions

---

## Overview

Six primary entities persisted in PostgreSQL 15. One derived store (FAISS per-user index on
persistent volume). One ephemeral store (Redis response cache).

```
User (1) ──── (N) Document (1) ──── (N) Chunk
              │
              └── (1) IngestionJob
User (1) ──── (N) QueryLog
User (1) ──── (N) QueryJob          ← async query tracking (FR-015)
```

---

## Entity: User

Represents an authenticated identity whose profile is lazily created/synced on first
authenticated request. Credentials are managed entirely by the external IdP.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK, NOT NULL | Platform-internal user identifier |
| `external_id` | VARCHAR(255) | UNIQUE, NOT NULL | IdP `sub` claim value |
| `email` | VARCHAR(255) | UNIQUE, NULLABLE | From IdP `email` claim |
| `role` | VARCHAR(50) | NOT NULL, DEFAULT `reader` | `reader` \| `contributor` \| `admin` |
| `query_rate_limit_per_minute` | INT | NOT NULL, DEFAULT 20 | Operator-configurable per user |
| `storage_quota_bytes` | BIGINT | NOT NULL, DEFAULT 1073741824 | 1 GB default |
| `used_storage_bytes` | BIGINT | NOT NULL, DEFAULT 0 | Updated on each document accepted |
| `tenant_id` | UUID | NULLABLE | Reserved for future multi-tenancy; NULL in v1 |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Indexes**: `external_id` (unique lookup on every authenticated request).

**State**: No state machine — users are active or absent. Suspension is a future concern.

---

## Entity: Document

Represents an uploaded file at the metadata level. Raw file is not persisted after processing.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK, NOT NULL | |
| `owner_id` | UUID | FK → users.id, NOT NULL | Enforces per-user ownership |
| `tenant_id` | UUID | NULLABLE | Reserved for future multi-tenancy |
| `original_filename` | VARCHAR(500) | NOT NULL | As provided by the uploader |
| `content_type` | VARCHAR(10) | NOT NULL | `pdf` \| `docx` \| `csv` |
| `content_hash` | CHAR(64) | NOT NULL | SHA-256 of raw file bytes |
| `size_bytes` | BIGINT | NOT NULL | Must be ≤ operator-configured max |
| `processing_status` | VARCHAR(20) | NOT NULL, DEFAULT `pending` | See state machine below |
| `error_message` | TEXT | NULLABLE | Set when `processing_status = failed` |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Unique constraint**: `(owner_id, content_hash)` — enforces per-user duplicate rejection (FR-007).

**Indexes**: `owner_id` (list documents per user), `content_hash` (duplicate detection lookup).

**State machine**:
```
pending → processing → completed
                    ↘ failed
```
- `pending`: document accepted, ingestion job queued
- `processing`: Celery worker has claimed the job
- `completed`: all chunks extracted, embedded, and indexed
- `failed`: unrecoverable error (corrupted file, parse failure, chunk ceiling exceeded); no partial content indexed

**Chunk ceiling**: If processing would yield more than `MAX_CHUNKS_PER_DOCUMENT` chunks
(default 1 000, operator-configurable), the job transitions to `failed` with a descriptive
error. No partial content is indexed.

---

## Entity: Chunk

Represents a text segment extracted from a document. The primary retrieval unit.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK, NOT NULL | Also stored as FAISS index metadata for lookups |
| `document_id` | UUID | FK → documents.id, NOT NULL | |
| `owner_id` | UUID | FK → users.id, NOT NULL | Denormalized for efficient isolation enforcement |
| `tenant_id` | UUID | NULLABLE | Reserved for future multi-tenancy |
| `chunk_index` | INT | NOT NULL | 0-based position within document |
| `page_number` | INT | NULLABLE | Page number for PDF/DOCX; NULL for CSV |
| `row_range` | VARCHAR(50) | NULLABLE | e.g. `"rows 10-25"` for CSV; NULL for others |
| `text_content` | TEXT | NOT NULL | Raw text of this segment |
| `token_count` | INT | NOT NULL | Token count at embedding time |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Indexes**: `document_id` (fetch all chunks for a document), `owner_id` (ownership queries).

**FAISS mapping**: FAISS stores dense vectors indexed by integer position. A parallel
`chunk_map.json` file at `/data/faiss/{user_id}/chunk_map.json` maps FAISS integer position
→ chunk UUID, enabling DB lookups after retrieval.

**Note**: The embedding vector is NOT stored in PostgreSQL — it lives only in the FAISS index
on the persistent volume. Storing 384-float vectors in PG for every chunk is wasteful and
redundant; FAISS is the authoritative vector store.

---

## Entity: IngestionJob

Tracks the full lifecycle of an ingestion request. Decoupled from Document to allow
re-ingestion in future (e.g., embedding model upgrade).

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK, NOT NULL | Returned to caller in 202 response |
| `document_id` | UUID | FK → documents.id, NOT NULL | |
| `owner_id` | UUID | FK → users.id, NOT NULL | |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT `pending` | Mirrors Document processing_status |
| `error_message` | TEXT | NULLABLE | Human-readable failure reason |
| `celery_task_id` | VARCHAR(255) | NULLABLE | For Celery task status correlation |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| `completed_at` | TIMESTAMPTZ | NULLABLE | Set on `completed` or `failed` |

**Indexes**: `owner_id` (list jobs per user), `celery_task_id` (worker correlation).

---

## Entity: QueryJob

Tracks the lifecycle of an asynchronous query request (FR-015). Only populated when the
synchronous query path is bypassed due to projected tail latency. Synchronous queries that
return within timeout are not persisted here — they are recorded only in `QueryLog`.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK, NOT NULL | Returned as `query_job_id` in 202 response |
| `user_id` | UUID | FK → users.id, NOT NULL | |
| `tenant_id` | UUID | NULLABLE | Reserved for future multi-tenancy |
| `query_hash` | CHAR(64) | NOT NULL | SHA-256 of normalised query text; used for cache lookup on completion |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT `pending` | See state machine below |
| `result_json` | TEXT | NULLABLE | Serialised `QueryResponse` JSON; set on `completed` |
| `error_message` | TEXT | NULLABLE | Set on `failed` |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| `completed_at` | TIMESTAMPTZ | NULLABLE | Set on `completed` or `failed` |

**Indexes**: `user_id` + `created_at`, `query_hash`.

**State machine**:
```
pending → processing → completed
                    ↘ failed
```

**Retention**: Records older than `QUERY_JOB_RETENTION_DAYS` (default 7) may be pruned.
`completed` jobs with cached results are effectively superseded by the Redis cache entry.

---

## Entity: QueryLog

Append-only audit and observability record. Never used to serve responses.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK, NOT NULL | |
| `user_id` | UUID | FK → users.id, NOT NULL | |
| `tenant_id` | UUID | NULLABLE | Reserved for future multi-tenancy |
| `query_hash` | CHAR(64) | NOT NULL | SHA-256 of normalized query text (for cache correlation) |
| `response_latency_ms` | INT | NULLABLE | End-to-end latency including LLM |
| `cache_hit` | BOOLEAN | NOT NULL, DEFAULT FALSE | |
| `degraded` | BOOLEAN | NOT NULL, DEFAULT FALSE | True when LLM was unavailable |
| `top_k_requested` | INT | NULLABLE | |
| `chunks_retrieved` | INT | NULLABLE | Actual number of chunks returned |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Indexes**: `user_id` + `created_at` (user query history), `query_hash` (cache analysis).
**Retention**: No deletion policy enforced in v1; future compliance story.

---

## FAISS Index Store (Persistent Volume)

Not a relational entity — documented here for completeness.

```
/data/faiss/
└── {user_id}/
    ├── index.faiss       # FAISS IndexFlatIP (384-dim vectors, cosine sim via L2-normalize)
    └── chunk_map.json    # { "0": "chunk-uuid-1", "1": "chunk-uuid-2", ... }
```

**Operations**:
- **Write** (in worker): load existing index (or create new) → add new vectors → serialize →
  atomic rename to replace file (prevents corruption on partial write).
- **Read** (in API): load from disk on first use per user per process lifetime (memory cached).
- **Concurrency**: Worker writes are serialized per user (Celery task routing by `owner_id`).
  Concurrent reads safe (FAISS is read-safe from multiple threads after load).

---

## Redis Cache Schema

Response cache. Key format and TTL are operator-configured.

| Key Pattern | Value | TTL |
|-------------|-------|-----|
| `rag:cache:{user_id}:{query_hash}` | Serialized `Answer` JSON | `CACHE_TTL_SECONDS` (default 3600) |

`query_hash` = SHA-256 of `lowercase(strip(query_text))`.
Cache is per-user — two users submitting the same query get independent cache entries,
preventing any cross-user response leakage via cache.

---

## Database Migrations

Managed by **Alembic** (`shared/src/db/migrations/`).

- Migration files are version-controlled.
- CI runs `alembic upgrade head` against a test database before any test suite execution.
- Production upgrade via K8s init container that runs `alembic upgrade head` before the
  API pod starts (ensures schema is current before traffic is served).
- Rollback: `alembic downgrade -1` available but manual — production rollback requires
  explicit operator action.

---

## Field Naming Conventions

| Convention | Example |
|------------|---------|
| Primary keys | `id` (UUID, not serial int) |
| Foreign keys | `{entity}_id` (e.g., `owner_id`, `document_id`) |
| Timestamps | `{event}_at` (e.g., `created_at`, `completed_at`) |
| Status enums | snake_case strings, not integers |
| Booleans | Positive framing (`cache_hit`, `degraded`, not `is_hit`) |
| Reserved fields | `tenant_id` present on all entities, nullable in v1 |
