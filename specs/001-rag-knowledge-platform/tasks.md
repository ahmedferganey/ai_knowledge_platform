---
description: "Task list for AI Knowledge Assistant Platform (RAG System)"
---

# Tasks: AI Knowledge Assistant Platform (RAG System)

**Input**: Design documents from `specs/001-rag-knowledge-platform/`
**Prerequisites**: plan.md ✅ · spec.md ✅ · research.md ✅ · data-model.md ✅ · contracts/ ✅

**Tests**: Included — constitution mandates TDD (Red → Green → Refactor). Tests are written
and confirmed failing before each implementation task.

**Organization**: Tasks grouped by user story to enable independent incremental delivery.
Ingestion (US2) is built before Query (US1) because an indexed knowledge base is required.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no shared state dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Exact file paths included in all task descriptions

## Path Conventions

```
services/api/src/        FastAPI HTTP service source
services/worker/src/     Celery worker source
shared/src/              Shared library (models, providers, implementations, DB, cache)
infra/docker/            Local dev Docker Compose
infra/k8s/               Kubernetes manifests
tests/unit/              Pure logic tests (no I/O)
tests/contract/          API schema conformance tests
tests/integration/       Inter-service + DB + cache tests
tests/load/              Locust load scenarios
```

---

## Phase 1: Setup

**Purpose**: Repo scaffolding, package initialization, local dev environment, CI skeleton.

- [ ] T001 Create full project directory structure per plan.md (services/api/, services/worker/, shared/, infra/docker/, infra/k8s/, tests/unit/, tests/contract/, tests/integration/, tests/load/, .github/workflows/)
- [ ] T002 [P] Initialize shared/ as installable Python package in shared/pyproject.toml (Python 3.11+, SQLAlchemy 2, Pydantic v2, asyncpg, structlog, opentelemetry-sdk, faiss-cpu, sentence-transformers, openai, anthropic, redis, celery)
- [ ] T003 [P] Initialize services/api/ package in services/api/pyproject.toml (FastAPI 0.111+, python-jose[cryptography], slowapi, prometheus-fastapi-instrumentator, httpx; depends on shared/)
- [ ] T004 [P] Initialize services/worker/ package in services/worker/pyproject.toml (Celery[redis], pdfplumber, python-docx; depends on shared/)
- [ ] T005 [P] Create infra/docker/docker-compose.yml (services: api, worker, postgres:15-alpine, redis:7-alpine, jaeger:latest, mock-idp; health checks, named volumes, .env file reference)
- [ ] T006 [P] Create infra/docker/.env.example (all env vars: DATABASE_URL, REDIS_URL, CELERY_BROKER_URL, FAISS_DATA_PATH, LLM_PROVIDER, OPENAI_API_KEY, ANTHROPIC_API_KEY, AUTH_JWKS_URL, AUTH_TOKEN_ISSUER, CHUNK_SIZE, CHUNK_OVERLAP, CACHE_TTL_SECONDS, QUERY_RATE_LIMIT_PER_MINUTE, UPLOAD_RATE_LIMIT_PER_MINUTE, MAX_FILE_SIZE_BYTES, LOG_LEVEL, OTEL_EXPORTER_OTLP_ENDPOINT)
- [ ] T007 [P] Create .github/workflows/ci.yml skeleton (jobs: lint with ruff, type-check with mypy --strict, unit-test with pytest tests/unit/, build docker images for api and worker)

**Checkpoint**: All packages install cleanly; `docker compose config` validates without errors.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared library, DB schema, provider ABCs, FastAPI skeleton, health endpoint.
All user story work depends on this phase being complete.

**⚠️ CRITICAL**: No user story implementation begins until this phase is complete.

- [ ] T008 Create shared/src/config/settings.py (Pydantic BaseSettings: all env vars from T006 with types, defaults, and validators; export Settings singleton via `get_settings()`)
- [ ] T009 [P] Create shared/src/db/session.py (create_async_engine from DATABASE_URL, AsyncSessionLocal factory, get_db() async generator dependency)
- [ ] T010 [P] Configure Alembic in shared/src/db/ (alembic.ini targeting DATABASE_URL, env.py with async engine, versions/ directory; run `alembic init` equivalent)
- [ ] T011 Create shared/src/models/user.py (User SQLAlchemy 2 mapped class: id UUID PK, external_id UNIQUE, email, role, query_rate_limit_per_minute, storage_quota_bytes, used_storage_bytes, tenant_id, created_at, updated_at; index on external_id)
- [ ] T012 [P] Create shared/src/models/document.py (Document model: id, owner_id FK→users, tenant_id, original_filename, content_type, content_hash CHAR(64), size_bytes, processing_status, error_message, created_at, updated_at; UniqueConstraint(owner_id, content_hash); index on owner_id)
- [ ] T013 [P] Create shared/src/models/chunk.py (Chunk model: id, document_id FK, owner_id FK, tenant_id, chunk_index, page_number nullable, row_range nullable, text_content, token_count, created_at; indexes on document_id, owner_id)
- [ ] T014 [P] Create shared/src/models/ingestion_job.py (IngestionJob model: id, document_id FK, owner_id FK, status, error_message, celery_task_id, created_at, updated_at, completed_at; indexes on owner_id, celery_task_id)
- [ ] T015 [P] Create shared/src/models/query_log.py (QueryLog model: id, user_id FK, tenant_id, query_hash, response_latency_ms, cache_hit, degraded, top_k_requested, chunks_retrieved, created_at; index on user_id + created_at)
- [ ] T016 Create Alembic initial migration in shared/src/db/migrations/versions/0001_initial_schema.py (creates all 5 tables from T011–T015; reversible downgrade)
- [ ] T017 Create shared/src/providers/vector_store.py (VectorStoreProvider ABC: abstract methods add_chunks(chunks, embeddings, owner_id), search(query_vector, k, owner_id) -> list[ChunkResult], delete_by_document(document_id, owner_id); ChunkResult dataclass: chunk_id, score)
- [ ] T018 [P] Create shared/src/providers/embedding.py (EmbeddingProvider ABC: abstract methods embed_texts(texts: list[str]) -> list[list[float]], embed_query(text: str) -> list[float])
- [ ] T019 [P] Create shared/src/providers/llm.py (LLMProvider ABC: abstract method generate(system_prompt, context_chunks, user_query) -> str; ProviderUnavailableError exception class)
- [ ] T020 Create services/api/src/main.py (FastAPI app factory with title="RAG API", version from env; lifespan context manager: init DB connection pool on startup, close on shutdown; include health router; OpenAPI at /docs)
- [ ] T021 [P] Create services/api/src/schemas/health.py (HealthResponse, ServiceChecks, ReadinessResponse Pydantic v2 models matching contracts/health.md)
- [ ] T022 Create services/api/src/routers/health.py (GET /api/v1/health: return HealthResponse{status:"healthy"}; GET /api/v1/ready: ping DB + Redis, return ReadinessResponse with check statuses, 503 if any critical check fails)
- [ ] T023 Write contract tests tests/contract/test_health.py (test GET /health returns 200 + HealthResponse schema; GET /ready returns 200/503 + ReadinessResponse schema; no auth required on either endpoint) — **FAIL before T022**
- [ ] T024 Run `docker compose up --build` and verify GET /api/v1/health returns 200; GET /api/v1/ready returns 200 with all checks ok; T023 contract tests pass

**Checkpoint**: Foundation ready — all user story phases may now begin in sequence.

---

## Phase 3: User Story 2 — Document Ingestion (Priority: P2) 🎯 MVP Enabler

**Goal**: Upload a document → async processing → parsed, chunked, embedded, indexed content ready for queries.

**Independent Test**: Upload a PDF fixture → poll `/api/v1/ingest/{job_id}` until `completed` → query DB and confirm Chunk rows exist with text content → verify FAISS index file created at `/data/faiss/{user_id}/`.

### Contract Tests for US2 ⚠️ Write First, Must FAIL

- [ ] T025 [P] [US2] Write contract tests tests/contract/test_ingest.py (POST /ingest returns 202 + IngestResponse schema; 409 on duplicate content hash; 413 on oversized file; 415 on unsupported type; 507 on quota exceeded; GET /ingest/{job_id} returns JobStatusResponse schema with all valid statuses; 404 on unknown job_id; 403 on job belonging to different user) — **FAIL before T040**

### Unit Tests ⚠️ Write First, Must FAIL

- [ ] T026 [P] [US2] Write unit tests tests/unit/test_parser.py (test PDF parse returns non-empty string and page metadata; test DOCX parse returns text; test CSV parse returns rows as text; test corrupted file raises ParseError; test unsupported type raises ValueError; use fixture files in tests/fixtures/) — **FAIL before T032**
- [ ] T027 [P] [US2] Write unit tests tests/unit/test_chunker.py (test chunk_text returns correct number of chunks for known input; test overlap produces shared tokens; test short text returns single chunk; test empty text returns empty list; test chunk_size=512 default) — **FAIL before T034**
- [ ] T028 [P] [US2] Write unit tests tests/unit/test_ingestion_job.py (test IngestionJob status transitions pending→processing→completed; test pending→processing→failed; test completed_at set on terminal state) — **FAIL before T038**

### Implementation for User Story 2

- [ ] T029 [US2] Create tests/fixtures/ directory with sample files (sample.pdf 3 pages, sample.docx 2 pages, sample.csv 10 rows, corrupted.pdf invalid bytes)
- [ ] T030 [P] [US2] Create services/worker/src/config.py (WorkerSettings extending shared Settings: EMBEDDING_MODEL_NAME default "all-MiniLM-L6-v2", FAISS_DATA_PATH, CELERY_BROKER_URL)
- [ ] T031 [P] [US2] Create services/worker/src/main.py (Celery app with Redis broker URL from config, task autodiscovery from services.worker.tasks, worker_hijack_root_logger=False for structlog compatibility)
- [ ] T032 [US2] Create services/worker/src/processors/parser.py (parse_document(file_bytes: bytes, content_type: str) -> ParseResult; PDFParser using pdfplumber extracting text + page numbers; DOCXParser using python-docx; CSVParser using csv.reader rows joined as text; ParseError for failures) — passes T026
- [ ] T033 [US2] Create services/worker/src/processors/chunker.py (chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[ChunkData]; ChunkData: text, token_count, page_hint; recursive character splitter respecting sentence then word boundaries) — passes T027
- [ ] T034 [P] [US2] Create services/api/src/schemas/ingest.py (IngestResponse Pydantic v2: job_id, document_id, status, message; JobStatusResponse: job_id, document_id, document_name, status, error_message, created_at, updated_at, completed_at; IngestError: error, message, fields)
- [ ] T035 [US2] Create services/api/src/dependencies.py (get_db using shared/src/db/session.py; get_celery() returns Celery app instance; get_current_user() STUB returning hardcoded User(id=uuid4(), external_id="stub", role="contributor") for US2 testing — replaced in US4)
- [ ] T036 [US2] Create services/api/src/routers/ingest.py — POST /api/v1/ingest (validate content_type against allowlist; check size ≤ MAX_FILE_SIZE_BYTES; compute SHA-256 content hash; check UniqueConstraint(owner_id, content_hash) → 409 with existing_document_id; check used_storage_bytes + size ≤ quota → 507; insert Document(status=pending); insert IngestionJob; dispatch ingest_document.delay(job_id); return 202 IngestResponse)
- [ ] T037 [US2] Create services/api/src/routers/ingest.py — GET /api/v1/ingest/{job_id} (fetch IngestionJob by id; verify job.owner_id == current_user.id → 403; return JobStatusResponse; 404 if not found)
- [ ] T038 [US2] Create services/worker/src/tasks/ingestion.py — ingest_document Celery task (fetch Document + IngestionJob; update status→processing; call parser; call chunker; batch-insert Chunk records via DB; update Document status→completed; set IngestionJob.completed_at; on any exception: status→failed + error_message; retry on transient errors max 3 times) — passes T028
- [ ] T039 [US2] Register ingest router in services/api/src/main.py (app.include_router with prefix /api/v1; wire get_db and get_current_user dependencies)
- [ ] T040 [US2] Wire parser + chunker + DB persistence in services/worker/src/tasks/ingestion.py; run T025 contract tests and confirm they pass
- [ ] T041 [US2] Write integration test tests/integration/test_ingestion.py (upload sample.pdf fixture via HTTP POST; poll job status until completed; query DB for Chunk rows with document_id; assert chunk count > 0 and text_content non-empty) — **FAIL before T042**
- [ ] T042 [US2] Verify T041 integration test passes end-to-end with running docker compose stack

**Checkpoint**: US2 fully functional — upload PDF → job completes → Chunk rows in DB.

---

## Phase 4: User Story 1 — Natural Language Knowledge Query (Priority: P1) 🎯 MVP

**Goal**: Submit a natural language question → retrieve relevant chunks → LLM synthesizes answer with sources.

**Independent Test**: Seed FAISS index with chunks from a known document → POST /api/v1/query with a question whose answer is in that document → response contains non-null `answer`, `degraded: false`, non-empty `sources`, `latency_ms` populated.

### Contract Tests for US1 ⚠️ Write First, Must FAIL

- [ ] T043 [P] [US1] Write contract tests tests/contract/test_query.py (POST /query returns 200 + QueryResponse schema; answer is string or null; degraded is boolean; sources is array; cache_hit is boolean; latency_ms is integer; 401 on no auth; 422 on invalid body; 429 schema with retry_after_seconds) — **FAIL before T057**

### Unit Tests ⚠️ Write First, Must FAIL

- [ ] T044 [P] [US1] Write unit tests tests/unit/test_faiss_store.py (test add_chunks stores vectors; test search returns closest chunk IDs in correct order; test per-user isolation: user A chunks not returned for user B search; test empty index returns empty list; test delete_by_document removes correct vectors) — **FAIL before T047**
- [ ] T045 [P] [US1] Write unit tests tests/unit/test_embedding.py (test embed_texts returns list of 384-dim float vectors; test embed_query returns single 384-dim vector; test vectors are L2-normalized (norm ≈ 1.0); test batch of 1 works; test empty list returns empty list) — **FAIL before T049**
- [ ] T046 [P] [US1] Write unit tests tests/unit/test_llm_providers.py (mock openai SDK: test generate() returns string; test ProviderUnavailableError raised on APIConnectionError; test ProviderUnavailableError raised on Timeout; same tests for anthropic SDK mock) — **FAIL before T051**

### Implementation for User Story 1

- [ ] T047 [US1] Create shared/src/impl/faiss_store.py (FAISSVectorStore implements VectorStoreProvider: per-user IndexFlatIP(384); add_chunks() L2-normalizes embeddings before add; persists index.faiss + chunk_map.json to FAISS_DATA_PATH/{owner_id}/ via atomic temp-file rename; search() loads index from disk on first access, caches in process memory; delete_by_document() removes vectors and updates chunk_map.json) — passes T044
- [ ] T048 [US1] Create shared/src/impl/sentence_transformer.py (SentenceTransformerEmbedding implements EmbeddingProvider: load "all-MiniLM-L6-v2" lazily on first call; embed_texts() batch encodes with normalize_embeddings=True; embed_query() is embed_texts()[0]) — passes T045
- [ ] T049 [US1] Update services/worker/src/processors/indexer.py to inject EmbeddingProvider + VectorStoreProvider (batch embed ChunkData texts; call vector_store.add_chunks(chunks, embeddings, owner_id); update Chunk.token_count from ChunkData.token_count)
- [ ] T050 [US1] Update services/worker/src/tasks/ingestion.py to call indexer with embedding + vector store after DB chunk save (dependency inject FAISSVectorStore + SentenceTransformerEmbedding from config-driven factory)
- [ ] T051 [P] [US1] Create services/api/src/schemas/query.py (QueryRequest: query str 1–2000 chars, top_k int 1–20 default 5; SourceReference: document_id, document_name, chunk_index, page_number nullable, text; QueryResponse: query_id, answer nullable, degraded bool, cache_hit bool, sources list[SourceReference], latency_ms)
- [ ] T052 [US1] Create shared/src/impl/openai_llm.py (OpenAILLMProvider implements LLMProvider: async generate() using openai.AsyncOpenAI, model="gpt-4o", system prompt instructs grounding-only answers, context = chunk texts joined with separators, max_context_tokens=6000; catches APIConnectionError/RateLimitError/Timeout → raises ProviderUnavailableError) — passes T046
- [ ] T053 [P] [US1] Create shared/src/impl/claude_llm.py (ClaudeLLMProvider implements LLMProvider: async generate() using anthropic.AsyncAnthropic, model="claude-sonnet-4-6", same prompt structure as OpenAI impl; catches anthropic.APIConnectionError → raises ProviderUnavailableError) — passes T046
- [ ] T054 [US1] Create provider factory in shared/src/providers/factory.py (get_embedding_provider() → SentenceTransformerEmbedding; get_vector_store_provider() → FAISSVectorStore; get_llm_provider() → OpenAILLMProvider or ClaudeLLMProvider based on LLM_PROVIDER env var)
- [ ] T055 [US1] Create services/api/src/routers/query.py (POST /api/v1/query: validate QueryRequest; embed query via EmbeddingProvider; call VectorStoreProvider.search(owner_id=current_user.id, k=top_k); if no results return QueryResponse(answer=None, sources=[]); call LLMProvider.generate(); on ProviderUnavailableError return QueryResponse(degraded=True, sources=raw_chunks); insert QueryLog record; return QueryResponse with latency_ms)
- [ ] T056 [US1] Register query router in services/api/src/main.py (include_router with prefix /api/v1; wire providers via dependency injection from factory)
- [ ] T057 [US1] Write integration test tests/integration/test_query.py (seed test user's FAISS index with known chunk text; call POST /api/v1/query with matching question; assert response.answer is not None; assert response.degraded is False; assert len(response.sources) > 0; assert response.cache_hit is False; assert response.latency_ms > 0) — **FAIL before T058**
- [ ] T058 [US1] Verify T057 + T043 tests pass with full query pipeline running; run full ingestion → query round-trip test

**Checkpoint**: US1 functional — question returns grounded answer from indexed documents.

---

## Phase 5: User Story 3 — Answer Source Attribution (Priority: P3)

**Goal**: Every answer includes structured source references (document name, chunk index, page number, segment text) enabling users to verify answers against original documents.

**Independent Test**: Upload sample.pdf, query on known content → response.sources contains document_name matching uploaded filename + chunk_index + non-empty text matching uploaded content; multi-segment query returns multiple sources; cached response preserves identical sources.

### Contract + Integration Tests ⚠️ Write First, Must FAIL

- [ ] T059 [P] [US3] Write integration tests tests/integration/test_source_attribution.py (upload sample.pdf; query on known first-page content; assert sources[0].document_name == "sample.pdf"; assert sources[0].page_number == 1; assert sources[0].text contains expected phrase; test multi-chunk query returns multiple sources each with distinct chunk_index; test cached response sources == uncached sources) — **FAIL before T061**

### Implementation for User Story 3

- [ ] T060 [US3] Enrich source references in services/api/src/routers/query.py (after VectorStoreProvider.search() returns ChunkResult list: bulk-fetch Chunk + Document records from DB by chunk_ids; populate SourceReference.document_name from Document.original_filename; populate page_number from Chunk.page_number; populate text from Chunk.text_content; ensure all contributing chunks attributed in sources list)
- [ ] T061 [US3] Verify T059 integration tests pass; verify sources are identical in cached vs uncached responses (cache stores complete QueryResponse including sources)
- [ ] T062 [US3] Validate quickstart.md curl commands against running stack (execute each step; verify actual responses match documented response examples; update any discrepancies in quickstart.md)

**Checkpoint**: US3 functional — every answer is traceable to source document segments.

---

## Phase 6: User Story 4 — Rate-Limited Secure Multi-User Access (Priority: P4)

**Goal**: JWT validation from external IdP; per-user document isolation enforced; Redis response cache; per-user rate limiting with 429 + Retry-After.

**Independent Test**: User A uploads doc; User B queries → User B cannot see User A's content (empty sources); expired JWT returns 401; reader role calling ingest returns 403; rate limit exceeded returns 429 with Retry-After header; same query from same user returns cache_hit: true on second call.

### Contract + Unit Tests ⚠️ Write First, Must FAIL

- [ ] T063 [P] [US4] Write contract tests tests/contract/test_auth.py (request with no Authorization header → 401; request with expired JWT → 401; reader role calling POST /ingest → 403; valid token on GET /health → 200 (no auth required); rate limit exceeded → 429 with Retry-After and X-RateLimit-* headers in response) — **FAIL before T068**
- [ ] T064 [P] [US4] Write unit tests tests/unit/test_cache.py (test cache key = sha256(user_id + normalized_query_text); test two users same query produce different keys (isolation); test cache.get() returns None on miss; test cache.set() + cache.get() round-trip returns original QueryResponse; test expired TTL returns None) — **FAIL before T071**

### Implementation for User Story 4

- [ ] T065 [US4] Create services/api/src/middleware/auth.py (fetch JWKS from AUTH_JWKS_URL using httpx; cache JWKS keys in memory with 1-hour TTL; validate RS256 JWT: signature, exp, iss==AUTH_TOKEN_ISSUER; extract sub, email, role claims; lazy-create or update User in DB by external_id; inject UserContext(user_id, role, external_id) into request.state; return 401 on any validation failure with WWW-Authenticate header)
- [ ] T066 [US4] Create services/api/src/middleware/rate_limit.py (instantiate slowapi Limiter with Redis storage_uri from REDIS_URL; define limits: POST /query = QUERY_RATE_LIMIT_PER_MINUTE/minute keyed by user_id claim; POST /ingest = UPLOAD_RATE_LIMIT_PER_MINUTE/minute keyed by user_id; add X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset headers on all responses; 429 response includes retry_after_seconds)
- [ ] T067 [US4] Replace get_current_user STUB in services/api/src/dependencies.py with real implementation (extract UserContext from request.state set by auth middleware; raise 401 if not present; raise 403 if role check fails for protected operations)
- [ ] T068 [US4] Wire auth middleware and rate limit middleware into services/api/src/main.py (middleware stack order: tracing → auth → rate_limit; exclude /api/v1/health and /api/v1/ready from auth middleware; exclude /api/v1/health, /api/v1/ready, /metrics from rate limiting)
- [ ] T069 [US4] Verify T063 contract tests pass (401 on no/invalid token; 403 on wrong role; 429 with correct headers)
- [ ] T070 [US4] Create shared/src/cache/redis_cache.py (ResponseCache: get(user_id, query_text) → QueryResponse | None; set(user_id, query_text, response, ttl); cache_key = sha256(f"{user_id}:{query_text.lower().strip()}"); serialize/deserialize QueryResponse as JSON; connect to REDIS_URL) — passes T064
- [ ] T071 [US4] Integrate ResponseCache in services/api/src/routers/query.py (check cache before retrieval+LLM path; on cache hit: return with cache_hit=True, log QueryLog with cache_hit=True; on cache miss: execute retrieval+LLM, write to cache if not degraded, return with cache_hit=False)
- [ ] T072 [US4] Write integration tests tests/integration/test_auth_isolation.py (two users each upload a document; user A queries → sources only from user A's doc; user B queries → sources only from user B's doc; zero cross-contamination; expired JWT returns 401; same query twice returns cache_hit: true on second; cache entries are per-user isolated) — **FAIL before T073**
- [ ] T073 [US4] Verify T072 integration tests pass end-to-end; verify T064 unit tests pass

**Checkpoint**: US4 functional — multi-user isolation, JWT auth, Redis cache, and rate limiting all verified.

---

## Phase 7: User Story 5 — Platform Health Visibility and Observability (Priority: P5)

**Goal**: Structured JSON logs with trace_id; Prometheus metrics on /metrics; OpenTelemetry traces exported to Jaeger/Tempo; Grafana dashboard template; /ready probe validates all dependencies.

**Independent Test**: Execute a query → call GET /metrics → assert rag_cache_misses_total incremented; execute same query → assert rag_cache_hits_total incremented; inspect structlog output and confirm trace_id, service_name, user_id_hash fields present; Jaeger UI shows end-to-end trace from HTTP request through Celery task.

### Unit + Integration Tests ⚠️ Write First, Must FAIL

- [ ] T074 [P] [US5] Write unit tests tests/unit/test_logging.py (test structlog output is valid JSON; test trace_id field present when OTel span active; test user_id_hash is SHA-256 of user_id (not raw ID); test log level respects LOG_LEVEL env var) — **FAIL before T076**
- [ ] T075 [P] [US5] Write integration tests tests/integration/test_observability.py (call POST /query → GET /metrics → assert rag_cache_misses_total > 0; call same POST /query → assert rag_cache_hits_total > 0; assert rag_ingestion_jobs_total{status="completed"} increments after ingest; assert /metrics endpoint returns 200 without auth) — **FAIL before T082**

### Implementation for User Story 5

- [ ] T076 [US5] Create shared/src/config/logging.py (configure structlog globally: JSON renderer for production, colored console for development (LOG_LEVEL=debug); processors: add_log_level, add_timestamp ISO8601, inject trace_id from OTel span context, inject service_name from SERVICE_NAME env, inject user_id_hash as SHA-256 when available; call configure_structlog() on app startup) — passes T074
- [ ] T077 [P] [US5] Create shared/src/config/metrics.py (define Prometheus Counter/Histogram objects: rag_cache_hits_total, rag_cache_misses_total, rag_llm_tokens_used_total, rag_ingestion_jobs_total{status}, rag_degraded_responses_total, rag_query_duration_seconds histogram; export increment_* helper functions)
- [ ] T078 [US5] Add prometheus-fastapi-instrumentator to services/api/src/main.py (Instrumentator().instrument(app).expose(app) — exposes /metrics without auth; add custom metrics from T077)
- [ ] T079 [US5] Create services/api/src/middleware/tracing.py (initialize OpenTelemetry SDK: configure TracerProvider with OTLP exporter to OTEL_EXPORTER_OTLP_ENDPOINT; instrument FastAPI with opentelemetry-instrumentation-fastapi; instrument SQLAlchemy with opentelemetry-instrumentation-sqlalchemy; propagate traceparent header into Celery task headers on dispatch)
- [ ] T080 [US5] Add structlog logging calls in services/api/src/routers/query.py (log query_received with query_hash; log query_completed with latency_ms, cache_hit, degraded, chunks_retrieved; log query_failed on exception)
- [ ] T081 [US5] Add structlog logging calls in services/api/src/routers/ingest.py + middleware/auth.py (log ingest_accepted with document_id, job_id, size_bytes; log auth_failure with reason; log rate_limit_hit with endpoint, user_id_hash)
- [ ] T082 [US5] Add structlog + metric logging in services/worker/src/tasks/ingestion.py (log ingestion_started, ingestion_completed, ingestion_failed; extract traceparent from task headers and set as current OTel span parent; increment rag_ingestion_jobs_total{status} counter)
- [ ] T083 [US5] Create infra/k8s/monitoring/dashboards/rag-overview.json (Grafana dashboard JSON: panels for query rate, error rate, p95 query latency, cache hit ratio, LLM token usage rate, active ingestion jobs, ingestion failure rate, pod CPU/memory)
- [ ] T084 [US5] Verify T074 unit tests and T075 integration tests pass; confirm Jaeger UI at localhost:16686 shows traces from HTTP request through Celery task with traceparent propagation

**Checkpoint**: US5 functional — full observability stack verified end-to-end.

---

## Phase 8: Polish, Deployment & CI/CD

**Purpose**: Production Docker images, K8s manifests, complete CI/CD pipeline, load test validation, final documentation check.

- [ ] T085 [P] Create services/api/Dockerfile (multi-stage: FROM python:3.11-slim AS builder → pip install shared/ + services/api/; FROM python:3.11-slim AS runtime → RUN useradd -r appuser; COPY --from=builder /app; USER appuser; EXPOSE 8000; CMD uvicorn services.api.src.main:app --host 0.0.0.0 --port 8000)
- [ ] T086 [P] Create services/worker/Dockerfile (multi-stage same pattern as T085; CMD celery -A services.worker.src.main worker --loglevel=info --concurrency=4)
- [ ] T087 [P] Create infra/k8s/api/deployment.yaml (Deployment: image from GHCR, minReplicas=2, resources requests/limits, livenessProbe GET /api/v1/health, readinessProbe GET /api/v1/ready, envFrom ConfigMap + Secret)
- [ ] T088 [P] Create infra/k8s/api/hpa.yaml + infra/k8s/api/pdb.yaml (HPA: CPU target 70%, minReplicas=2, maxReplicas=10; PDB: minAvailable=1)
- [ ] T089 [P] Create infra/k8s/worker/deployment.yaml (Deployment: minReplicas=1, maxReplicas=5; FAISS PVC volumeMount at /data/faiss with ReadWriteMany or per-worker strategy)
- [ ] T090 [P] Create infra/k8s/postgres/statefulset.yaml + pvc.yaml (StatefulSet postgres:15, PVC 20Gi, Service ClusterIP; ConfigMap for init SQL)
- [ ] T091 [P] Create infra/k8s/redis/statefulset.yaml + pvc.yaml (StatefulSet redis:7-alpine, PVC 5Gi, Service ClusterIP; redis.conf via ConfigMap)
- [ ] T092 [P] Create infra/k8s/config/configmap.yaml + secrets-template.yaml (ConfigMap: non-secret env vars; Secrets template: DATABASE_URL, REDIS_URL, OPENAI_API_KEY, ANTHROPIC_API_KEY, AUTH_JWKS_URL with placeholder values and README instructions)
- [ ] T093 Complete .github/workflows/ci.yml (add steps: docker build api → docker build worker → push to ghcr.io on merge to main with ${{ github.sha }} tag + latest tag; add pip-audit step for dependency scanning)
- [ ] T094 Create .github/workflows/deploy.yml (trigger: workflow_dispatch or push to main after CI passes; steps: pull new image tags → kubectl set image deployment/api → kubectl rollout status → manual approval gate → repeat for production namespace)
- [ ] T095 Create tests/load/locustfile.py (LoadTestUser class with on_start() auth token fetch from mock IdP; tasks: @task(3) query with known question; @task(1) upload small fixture file + poll until completed; response time assertions in locust check: query p95 < 5000ms, cached query p95 < 2000ms)
- [ ] T096 Run load test: `locust -f tests/load/locustfile.py --host http://localhost:8000 --users 50 --spawn-rate 5 --run-time 120s --headless` and verify p95 latency thresholds from SC-001 and SC-002
- [ ] T097 Run full test suite `pytest tests/ -v --tb=short` and confirm zero failures
- [ ] T098 Review CLAUDE.md is accurate (commands, structure, code style match final implementation); verify quickstart.md walks cleanly from clone to first successful query

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — blocks ALL user story phases
- **US2 Ingestion (Phase 3)**: Depends on Foundational complete — no dependency on US1
- **US1 Query (Phase 4)**: Depends on US2 complete (chunks must exist for retrieval to work)
- **US3 Attribution (Phase 5)**: Depends on US1 complete (enriches query response)
- **US4 Auth (Phase 6)**: Depends on US1 + US2 complete (layers auth on working endpoints)
- **US5 Observability (Phase 7)**: Depends on US4 complete (instruments fully wired service)
- **Polish (Phase 8)**: Depends on all user stories complete

### Within Each Phase

- [P]-marked tasks within a phase run in parallel
- Tests MUST be written and FAIL before their implementation tasks
- Models before services; services before endpoints; endpoints before integration tests

### Parallel Opportunities

- T002, T003, T004, T005, T006, T007 all run in parallel (Phase 1)
- T011–T015 (all 5 models) run in parallel (Phase 2)
- T017, T018, T019 (provider ABCs) run in parallel (Phase 2)
- T026, T027, T028 (US2 unit tests) run in parallel
- T030, T031, T034 (US2 infra) run in parallel
- T044, T045, T046 (US1 unit tests) run in parallel
- T052, T053 (OpenAI + Claude LLM implementations) run in parallel
- T085–T092 (all K8s + Docker artifacts) run in parallel (Phase 8)

---

## User Story Dependencies

```
US2 (P2): Ingestion
  → chunks in DB + FAISS indexed
      ↓
US1 (P1): Query  [MVP after US2]
  → grounded answer + sources
      ↓
US3 (P3): Attribution  [enrich US1 sources]
      ↓
US4 (P4): Auth + Cache + Rate Limit  [layer on US1+US2]
      ↓
US5 (P5): Observability  [instrument everything]
```

---

## Implementation Strategy

### MVP Scope (Deliver US2 + US1)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: US2 Ingestion → **test independently**
4. Complete Phase 4: US1 Query → **test independently with seeded data**
5. **STOP AND VALIDATE**: upload a real PDF, query it, receive a grounded answer
6. Demo-able end-to-end without auth, caching, or observability

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US2 complete → Documents can be ingested ✅
3. US1 complete → Documents can be queried ✅
4. US3 complete → Answers are traceable to sources ✅
5. US4 complete → Secure, rate-limited, cached ✅
6. US5 complete → Fully observable in production ✅
7. Polish complete → Production deployment ready ✅

---

## Notes

- `[P]` = different files, no dependencies on sibling tasks in same phase
- TDD enforced: every `FAIL before Txxx` note means the test must run and fail before the named implementation task starts
- Commit after each checkpoint (end of each phase)
- `tenant_id` is present on all models but NULL in v1 — do not skip it
- Provider interfaces (VectorStoreProvider, EmbeddingProvider, LLMProvider) are imported from `shared/`; concrete implementations are never imported directly in router/service code
- Auth middleware stub (T035) allows US2 + US1 to be built and tested without a real IdP; replaced in US4 (T067)
