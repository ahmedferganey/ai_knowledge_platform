# API Contract: Get Ingestion Job Status

**Endpoint**: `GET /api/v1/ingest/{job_id}`
**Auth**: Bearer token required (any authenticated role)
**Rate limit**: Shared with ingest endpoint pool

---

## Path Parameter

| Parameter | Type | Notes |
|-----------|------|-------|
| `job_id` | UUID string | Returned by `POST /api/v1/ingest` |

---

## Response: 200 OK — Job status

```json
{
  "job_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "document_id": "a1b2c3d4-0000-0000-0000-000000000001",
  "document_name": "remote-work-policy-2025.pdf",
  "status": "completed",
  "error_message": null,
  "created_at": "2026-04-17T10:00:00Z",
  "updated_at": "2026-04-17T10:01:42Z",
  "completed_at": "2026-04-17T10:01:42Z"
}
```

| Field | Type | Nullable | Notes |
|-------|------|----------|-------|
| `job_id` | UUID string | No | |
| `document_id` | UUID string | No | |
| `document_name` | string | No | Original filename |
| `status` | string | No | `pending` \| `processing` \| `completed` \| `failed` |
| `error_message` | string | Yes | Human-readable reason; present only when `status = failed` |
| `created_at` | string | No | ISO 8601 timestamp |
| `updated_at` | string | No | ISO 8601 timestamp |
| `completed_at` | string | Yes | Set when `status` reaches `completed` or `failed` |

---

## Status Lifecycle

```
pending → processing → completed
                    ↘ failed
```

Callers SHOULD poll with exponential backoff starting at 2s. Typical completion time for
a 50-page PDF is 30–90 seconds. Jobs do not expire in v1.

---

## Error Responses

| Status | Code | When |
|--------|------|------|
| 401 | `unauthorized` | Missing or invalid bearer token |
| 403 | `forbidden` | Job exists but belongs to a different user |
| 404 | `job_not_found` | No job with this ID exists |
| 500 | `internal_error` | Unexpected server error |

```json
{
  "error": "job_not_found",
  "message": "No ingestion job found with ID 7c9e6679-7425-40de-944b-e07fc1f90ae7."
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
