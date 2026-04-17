# API Contract: Submit Query

**Endpoint**: `POST /api/v1/query`
**Auth**: Bearer token required (role: `reader` or `contributor`)
**Rate limit**: Configured per role via env var (default 20 req/min)
**Content-Type**: `application/json`

---

## Request

```json
{
  "query": "string",
  "top_k": "integer (optional)"
}
```

| Field | Type | Required | Constraints | Notes |
|-------|------|----------|-------------|-------|
| `query` | string | Yes | 1–2000 characters | Natural language question |
| `top_k` | integer | No | 1–20, default 5 | Number of chunks to retrieve |

---

## Response: 200 OK — Answer returned (uncached or cached)

```json
{
  "query_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
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
  "latency_ms": 1842
}
```

| Field | Type | Nullable | Notes |
|-------|------|----------|-------|
| `query_id` | UUID string | No | Unique identifier for this query event |
| `answer` | string | Yes | Null when `degraded: true` |
| `degraded` | boolean | No | True when LLM was unavailable; sources returned without synthesis |
| `cache_hit` | boolean | No | True when response served from cache |
| `sources` | array | No | Empty array when no relevant segments found |
| `sources[].document_id` | UUID string | No | |
| `sources[].document_name` | string | No | Original filename |
| `sources[].chunk_index` | integer | No | 0-based position in document |
| `sources[].page_number` | integer | Yes | Null for CSV documents |
| `sources[].text` | string | No | Verbatim retrieved segment text |
| `latency_ms` | integer | No | End-to-end response time in milliseconds |

---

## Response: 200 OK — No relevant information found

```json
{
  "query_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "answer": null,
  "degraded": false,
  "cache_hit": false,
  "sources": [],
  "latency_ms": 743
}
```

When `sources` is empty, `answer` is always null. The system does not fabricate answers.

---

## Response: 200 OK — Degraded (LLM unavailable)

```json
{
  "query_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "answer": null,
  "degraded": true,
  "cache_hit": false,
  "sources": [
    {
      "document_id": "a1b2c3d4-0000-0000-0000-000000000001",
      "document_name": "remote-work-policy-2025.pdf",
      "chunk_index": 4,
      "page_number": 2,
      "text": "Employees may work remotely for up to three days per week..."
    }
  ],
  "latency_ms": 312
}
```

`degraded: true` signals the LLM was unreachable. Retrieved segments are returned as-is.
Callers SHOULD display the source segments directly and inform users of degraded service.

---

## Error Responses

| Status | Code | When |
|--------|------|------|
| 401 | `unauthorized` | Missing or invalid bearer token |
| 403 | `forbidden` | Token valid but role lacks query permission |
| 422 | `validation_error` | Request body fails schema validation |
| 429 | `rate_limit_exceeded` | Per-user rate limit hit; includes `Retry-After` header |
| 500 | `internal_error` | Unexpected server error |

```json
{
  "error": "rate_limit_exceeded",
  "message": "Query rate limit of 20 requests per minute exceeded.",
  "retry_after_seconds": 43
}
```

---

## Headers

**Request headers required**:
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Response headers always present**:
```
X-Request-ID: <uuid>      ← correlation identifier (same as query_id for query endpoint)
X-Cache: HIT | MISS
```

**Rate limit response headers**:
```
Retry-After: 43
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1713398400
```
