<!--
SYNC IMPACT REPORT
==================
Version change:     (template) → 1.0.0
Bump type:          INITIAL — first concrete population of template; establishes all principles and governance.
Modified principles: N/A (no prior version)
Added sections:
  - Core Principles (I–VIII)
  - Technology Standards
  - Development Workflow & Quality Gates
  - Governance
Removed sections:   N/A
Templates status:
  - .specify/templates/plan-template.md     ✅ Constitution Check gates aligned (see Governance)
  - .specify/templates/spec-template.md     ✅ Functional/NFR alignment confirmed
  - .specify/templates/tasks-template.md    ✅ Phase categories reflect principles (Security, Observability tasks)
  - .specify/templates/checklist-template.md ✅ No structural changes required
  - docs/AI_Knowledge_Assistant_RAG_Requirements.md ✅ Source of truth — all requirements reflected
Deferred TODOs:
  - TODO(RATIFICATION_DATE): If a prior informal decision date exists before 2026-04-17, update accordingly.
-->

# AI Knowledge Assistant Platform Constitution

## Core Principles

### I. Production-First Mindset (NON-NEGOTIABLE)

Every design decision, code pattern, and dependency choice MUST target a production-quality
outcome. Prototypes, "TODO: fix later" shortcuts, hardcoded secrets, in-memory-only state,
and non-idempotent operations are prohibited from entering any branch that merges to `main`.

**Rationale**: RAG systems carry real data, real user trust, and real cost. A prototype that
"mostly works" shipped under time pressure creates compounding technical debt that undermines
correctness of AI-generated answers.

**Enforcement gates**:
- PR review MUST include a production-readiness checklist item.
- Any deviation MUST be documented in the Complexity Tracking table of the feature plan.

---

### II. Modular Architecture with Strict Separation of Concerns

The system is organized into six named domains. Each domain owns its own service boundary,
data contracts, and failure modes:

| Domain        | Responsibility                                                   |
|---------------|------------------------------------------------------------------|
| Ingestion     | Document parsing, cleaning, chunking; emits chunk events        |
| Embeddings    | Vector generation; owns embedding model config and versioning   |
| Retrieval     | Semantic search (Top-K), context enrichment, ranking            |
| Inference     | LLM prompt assembly, provider abstraction, response parsing     |
| Caching       | Response and embedding cache (Redis); TTL and invalidation      |
| Observability | Logs, metrics, traces; cross-cutting — never domain-specific    |

**Rules**:
- No domain MUST directly import internal implementation details of another domain.
- Cross-domain communication MUST go through defined async interfaces or HTTP contracts.
- Each domain MUST be deployable and testable independently.

**Rationale**: Separation allows independent scaling (e.g., Ingestion scales with document
volume; Inference scales with query volume) and prevents cascade failures.

---

### III. API-First Design with Versioned Contracts

All capabilities MUST be exposed through explicit, versioned API contracts before
implementation begins. Contracts define request/response schemas, error codes, and
auth requirements.

**Rules**:
- FastAPI MUST be used as the API framework with full async (`async def`) route handlers.
- All endpoints MUST be prefixed with `/api/v{N}/` for versioning.
- OpenAPI schemas MUST be auto-generated and committed as part of each contract.
- Breaking changes to an existing version MUST create a new version, not modify the old one.
- Minimum required endpoints: `/api/v1/query`, `/api/v1/ingest`, `/api/v1/health`.

**Rationale**: API-first prevents implementation leaking into contracts and enables parallel
client/server development. Versioning protects downstream consumers.

---

### IV. Containerization and Kubernetes-Readiness

Every service MUST be shipped as a Docker container image. The system MUST be deployable
to a Kubernetes cluster without manual intervention.

**Rules**:
- Each domain service MUST have its own `Dockerfile` using multi-stage builds.
- Images MUST be non-root and use minimal base images (e.g., `python:3.11-slim`).
- All services MUST expose `/health` (liveness) and `/ready` (readiness) probes.
- Kubernetes manifests (Deployments, Services, HPA, ConfigMaps, Secrets) MUST be
  maintained in `infra/k8s/`.
- Services MUST be stateless at the application layer; all shared state via external stores.
- Configuration MUST be injected via environment variables (12-Factor App compliance).

**Rationale**: Kubernetes-readiness enables horizontal scaling under load and ensures
fault-tolerant operation through automatic pod rescheduling and rolling updates.

---

### V. Observability is Mandatory (NON-NEGOTIABLE)

Every service MUST emit structured logs, expose Prometheus-compatible metrics, and
propagate distributed traces. Observability MUST be wired in before a service is considered
shippable.

**Rules**:
- **Logging**: Structured JSON logs (via `structlog` or equivalent). Log levels: DEBUG,
  INFO, WARNING, ERROR, CRITICAL. Logs MUST include `trace_id`, `service`, `timestamp`.
- **Metrics**: Prometheus metrics endpoint (`/metrics`) on each service. MUST track:
  request latency (histogram), error rate (counter), cache hit/miss (counter),
  LLM token usage (counter), embedding generation time (histogram).
- **Tracing**: OpenTelemetry distributed tracing. Each cross-service call MUST propagate
  `traceparent` headers. Traces MUST be exported to a configured backend (Jaeger/Tempo).
- **AI-specific metrics**: Answer relevance score, retrieval Top-K hit rate, hallucination
  flag rate (when evaluators are integrated).

**Rationale**: Without observability, diagnosing RAG quality degradation (e.g., stale
embeddings, LLM timeouts, cache poisoning) is impossible in production.

---

### VI. Security by Default (NON-NEGOTIABLE)

Security controls MUST be applied at every layer. Security is a first-class concern, not
a post-deployment hardening step.

**Rules**:
- **Authentication**: All non-health endpoints MUST require a valid JWT bearer token.
  JWTs MUST use asymmetric keys (RS256 or ES256). Tokens MUST include `exp`, `sub`, `iat`.
- **Authorization**: Role-based access MUST be enforced at the route level. Roles: `reader`,
  `contributor`, `admin`. Future multi-tenant support MUST be additive, not a rewrite.
- **Rate limiting**: All public-facing endpoints MUST enforce per-user rate limits via a
  middleware layer (e.g., `slowapi` or Redis-backed token bucket).
- **Input validation**: All request bodies MUST be validated using Pydantic v2 models.
  File uploads MUST enforce type allowlist (PDF, DOCX, CSV) and size limits.
- **Secrets**: No secrets in source code or Docker images. Use Kubernetes Secrets or a
  vault-compatible provider. `.env` files MUST be gitignored.
- **Dependency scanning**: `pip-audit` or equivalent MUST run in CI on every PR.

**Rationale**: The platform handles organizational knowledge bases — data confidentiality
and access control are legally and operationally critical.

---

### VII. Test-First Discipline

Tests MUST be written and confirmed failing before implementation code is written for
any new capability. Tests are evidence of intent, not optional documentation.

**Rules**:
- **TDD cycle**: Red (failing test) → Green (minimal implementation) → Refactor.
- **Test categories required**:
  - Unit tests: pure domain logic, no I/O (target ≥ 80% coverage per domain).
  - Integration tests: inter-service calls, database interactions, cache behavior.
  - Contract tests: API schema conformance — any endpoint contract change MUST break
    its contract test before the implementation changes.
- **Load testing**: Every public endpoint MUST have a Locust/k6 load test scenario
  validating <2s cached response and <5s LLM response under expected concurrency.
- Tests live in `tests/unit/`, `tests/integration/`, `tests/contract/`, `tests/load/`.
- CI MUST block merge if unit or contract tests fail.

**Rationale**: RAG system correctness depends on retrieval precision and LLM integration
stability. Tests catch regressions that are otherwise only visible as answer quality
degradation in production.

---

### VIII. Loose Coupling and Extensibility

No service MUST depend on the internal implementation of another. The system MUST be
designed for future extension without requiring rewrites of existing components.

**Rules**:
- **Provider abstraction**: LLM providers (OpenAI, Anthropic Claude, local models) MUST
  be accessed through a common `LLMProvider` interface. Switching providers MUST require
  only a configuration change.
- **Embedding abstraction**: Embedding models MUST be accessed through a common
  `EmbeddingProvider` interface.
- **Vector DB abstraction**: Storage backends (FAISS, Pinecone, Weaviate, Qdrant) MUST
  be accessed through a common `VectorStoreProvider` interface.
- **Multi-tenancy readiness**: All data models MUST include a `tenant_id` field (even if
  single-tenant in v1). Query paths MUST be filterable by tenant from day one.
- **Event-driven ingestion**: The Ingestion pipeline MUST publish domain events (e.g.,
  `document.ingested`, `chunk.embedded`) to enable future consumer extension without
  modifying the ingestion service.

**Rationale**: The platform will evolve — new LLM providers emerge, enterprise customers
require tenant isolation, and vector DB technology is rapidly changing. Coupling today
means rewrites tomorrow.

---

## Technology Standards

These standards are binding. Deviations MUST be approved and documented.

| Concern            | Standard                                               |
|--------------------|--------------------------------------------------------|
| Runtime language   | Python 3.11+                                          |
| API framework      | FastAPI (async-first, Pydantic v2 models)             |
| Containerization   | Docker (multi-stage, non-root, slim base images)      |
| Orchestration      | Kubernetes (manifests in `infra/k8s/`)                |
| Vector storage     | FAISS (dev/test), Pinecone or Qdrant (production)     |
| Response cache     | Redis 7+                                              |
| LLM providers      | OpenAI GPT-4o (primary), Anthropic Claude (secondary) |
| Observability      | structlog + Prometheus + OpenTelemetry (OTLP export)  |
| Testing            | pytest, pytest-asyncio, Locust                        |
| CI/CD              | GitHub Actions (lint → test → build → push → deploy)  |
| Secret management  | Kubernetes Secrets / HashiCorp Vault                  |
| Linting/formatting | ruff + black + mypy (strict mode)                     |
| API versioning     | URL-path versioning (`/api/v1/`, `/api/v2/`)          |
| Auth               | JWT RS256 via `python-jose`                           |
| Rate limiting      | `slowapi` (Redis-backed in production)                |

---

## Development Workflow & Quality Gates

### Feature Development Lifecycle

1. **Spec** — Feature spec written (`/speckit.specify`). Constitution Check gate passed.
2. **Plan** — Implementation plan drafted (`/speckit.plan`). Architecture reviewed.
3. **Tests written** — Contract + unit tests written and confirmed failing (Red phase).
4. **Implementation** — Code written to make tests pass (Green phase).
5. **Refactor** — Code simplified without breaking tests.
6. **Observability wired** — Metrics, logs, traces added before PR opened.
7. **Security validated** — `pip-audit` passes. Auth/validation applied on all routes.
8. **PR opened** — CI must be green. Code review requires Constitution Check sign-off.
9. **Merge to main** — Only after all gates pass.

### Constitution Check Gates (required in every plan.md)

All feature plans MUST verify the following before Phase 0 research:

- [ ] All new endpoints define a versioned API contract before implementation.
- [ ] New domain code does not import internals of another domain.
- [ ] JWT auth applied to all non-health routes.
- [ ] Structured logging, metrics, and trace propagation added.
- [ ] Rate limiting configured for any new public endpoint.
- [ ] Pydantic v2 models used for all request/response validation.
- [ ] Tests written (contract + unit) and failing before implementation.
- [ ] `tenant_id` included in any new data model.
- [ ] Provider interface used for any LLM, embedding, or vector store access.
- [ ] Docker image builds and readiness/liveness probes work before merge.

### Quality Thresholds

| Metric                        | Minimum Threshold                              |
|-------------------------------|------------------------------------------------|
| Unit test coverage (per domain) | ≥ 80%                                        |
| Cached query response time    | < 2 seconds at p95                             |
| LLM query response time       | < 5 seconds at p95                             |
| API error rate                | < 0.1% in steady state                         |
| Security scan (pip-audit)     | 0 critical/high CVEs                           |
| Linting (ruff + mypy)         | 0 errors on merge                              |

---

## Governance

This constitution supersedes all other informal practices, README conventions, and verbal
agreements. It is the authoritative engineering standard for the AI Knowledge Assistant Platform.

**Amendment procedure**:
1. Open a PR with proposed changes to this file.
2. PR description MUST include: motivation, impact on existing features, Sync Impact Report.
3. Version MUST be incremented per semantic versioning rules (MAJOR/MINOR/PATCH).
4. Minimum two reviewers with domain knowledge MUST approve.
5. Update `LAST_AMENDED_DATE` to the merge date.

**Versioning policy**:
- MAJOR: Removal or backward-incompatible redefinition of any principle.
- MINOR: New principle added, new mandatory section, or material expansion of guidance.
- PATCH: Clarifications, wording improvements, typo corrections.

**Compliance review**: Every PR MUST include the Constitution Check gate items from the
Development Workflow section. Reviewers MUST verify compliance before approving. Any
violation requires a documented exception in the Complexity Tracking table.

**Guidance file**: Refer to `docs/AI_Knowledge_Assistant_RAG_Requirements.md` for the
canonical product requirements that inform but do not supersede this constitution.

**Version**: 1.0.0 | **Ratified**: 2026-04-17 | **Last Amended**: 2026-04-17
