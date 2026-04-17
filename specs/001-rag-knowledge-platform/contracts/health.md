# API Contract: Health and Readiness

## Liveness Probe

**Endpoint**: `GET /api/v1/health`
**Auth**: None required
**Purpose**: Kubernetes liveness probe — confirms the process is alive and the app is running.

### Response: 200 OK

```json
{
  "status": "healthy",
  "service": "api",
  "version": "1.0.0",
  "timestamp": "2026-04-17T10:05:00Z"
}
```

This endpoint MUST always return 200 as long as the process is running. It does NOT check
downstream dependencies. Kubernetes restarts the pod if this returns non-2xx.

| Field | Type | Notes |
|-------|------|-------|
| `status` | string | Always `healthy` when process is alive |
| `service` | string | Service name identifier |
| `version` | string | Application version from build artifact |
| `timestamp` | string | ISO 8601 current server time |

---

## Readiness Probe

**Endpoint**: `GET /api/v1/ready`
**Auth**: None required
**Purpose**: Kubernetes readiness probe — confirms the service can accept traffic.
Checks all required downstream dependencies.

### Response: 200 OK — Ready to serve traffic

```json
{
  "status": "ready",
  "timestamp": "2026-04-17T10:05:00Z",
  "checks": {
    "database": "ok",
    "cache": "ok",
    "vector_store": "ok"
  }
}
```

### Response: 503 Service Unavailable — Not ready

```json
{
  "status": "not_ready",
  "timestamp": "2026-04-17T10:05:00Z",
  "checks": {
    "database": "error",
    "cache": "ok",
    "vector_store": "ok"
  }
}
```

Kubernetes removes the pod from the Service's endpoint list when this returns 503.
Traffic is not routed until the pod becomes ready again.

| Check | Healthy condition | Failure behavior |
|-------|-------------------|------------------|
| `database` | PostgreSQL connection pool can execute `SELECT 1` | Returns 503; pod removed from rotation |
| `cache` | Redis `PING` responds within 200ms | Returns 503; pod removed from rotation |
| `vector_store` | FAISS data directory is accessible on PV | Returns 503 |

**Note**: `llm_provider` is intentionally NOT a readiness check. LLM provider unavailability
triggers degraded mode (see query contract), not pod removal from service rotation.

| Check field value | Meaning |
|-------------------|---------|
| `ok` | Dependency reachable and responding normally |
| `degraded` | Dependency reachable but elevated latency or partial function |
| `error` | Dependency unreachable or returning errors |
