# API Contract: Poll Async Query Status

**Endpoint**: `GET /api/v1/query/{query_job_id}`
**Auth**: Bearer token required (role: `reader`, `contributor`, or `admin`)
**Rate limit**: Shares the query rate limit pool (counted against per-user 20 req/min)

> This endpoint is only populated when a prior `POST /api/v1/query` returned **202 Accepted**.
> Synchronous queries (200 OK) are not tracked here.

---

## Path Parameters

| Parameter | Type | Notes |
|-----------|------|-------|
| `query_job_id` | UUID string | Returned by `POST /api/v1/query` 202 response |

---

## Response: 200 OK — Job is still processing

```json
{
  "query_job_id": "9f1c2d3e-1234-5678-abcd-ef0123456789",
  "status": "pending",
  "created_at": "2026-04-17T14:32:00Z"
}
```

```json
{
  "query_job_id": "9f1c2d3e-1234-5678-abcd-ef0123456789",
  "status": "processing",
  "created_at": "2026-04-17T14:32:00Z"
}
```

| Field | Type | Notes |
|-------|------|-------|
| `query_job_id` | UUID string | |
| `status` | string | `pending` or `processing` |
| `created_at` | ISO 8601 string | |

Callers SHOULD poll with exponential backoff (e.g., 1s → 2s → 4s → max 30s).

---

## Response: 200 OK — Job completed

```json
{
  "query_job_id": "9f1c2d3e-1234-5678-abcd-ef0123456789",
  "status": "completed",
  "created_at": "2026-04-17T14:32:00Z",
  "completed_at": "2026-04-17T14:32:04Z",
  "result": {
    "query_id": "9f1c2d3e-1234-5678-abcd-ef0123456789",
    "answer": "The remote work policy allows employees to work remotely up to 3 days per week...",
    "degraded": false,
    "cache_hit": false,
    "sources": [
      {
        "document_id": "a1b2c3d4-0000-0000-0000-000000000001",
        "document_name": "remote-work-policy-2025.pdf",
        "chunk_index": 4,
        "page_number": 2,
        "text": "Employees may work remotely for up to three days per week, subject to manager approval..."
      }
    ],
    "latency_ms": 3920
  }
}
```

The `result` object has the same schema as a synchronous `POST /api/v1/query` 200 response.

---

## Response: 200 OK — Job failed

```json
{
  "query_job_id": "9f1c2d3e-1234-5678-abcd-ef0123456789",
  "status": "failed",
  "created_at": "2026-04-17T14:32:00Z",
  "completed_at": "2026-04-17T14:32:05Z",
  "error": "LLM provider unavailable and no cached result exists.",
  "result": null
}
```

A failed async query returns `status: failed` with an `error` description, not a 5xx response.
Callers SHOULD surface the error message and allow the user to retry.

---

## Error Responses

| Status | Code | When |
|--------|------|------|
| 401 | `unauthorized` | Missing or invalid bearer token |
| 403 | `forbidden` | `query_job_id` belongs to a different user |
| 404 | `not_found` | `query_job_id` does not exist or has expired |
| 429 | `rate_limit_exceeded` | Per-user rate limit hit |
| 500 | `internal_error` | Unexpected server error |

```json
{
  "error": "not_found",
  "message": "Query job 9f1c2d3e-1234-5678-abcd-ef0123456789 not found or has expired."
}
```

---

## Headers

**Request headers required**:
```
Authorization: Bearer <token>
```

**Response headers always present**:
```
X-Request-ID: <uuid>
```
