# API Contract: Submit Document for Ingestion

**Endpoint**: `POST /api/v1/ingest`
**Auth**: Bearer token required (role: `contributor` or `admin`)
**Rate limit**: Configured per role via env var (default 10 req/min)
**Content-Type**: `multipart/form-data`

---

## Request

| Field | Type | Required | Constraints | Notes |
|-------|------|----------|-------------|-------|
| `file` | binary | Yes | Max size: operator-configured (default 10 MB) | PDF, DOCX, or CSV only |
| `description` | string | No | Max 500 characters | Optional human label for the document |

**Accepted MIME types**: `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `text/csv`

---

## Response: 202 Accepted — Processing started

```json
{
  "job_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "document_id": "a1b2c3d4-0000-0000-0000-000000000001",
  "status": "pending",
  "message": "Document accepted for processing. Poll /api/v1/ingest/{job_id} for status."
}
```

| Field | Type | Notes |
|-------|------|-------|
| `job_id` | UUID string | Use to poll `/api/v1/ingest/{job_id}` |
| `document_id` | UUID string | Platform identifier for this document |
| `status` | string | Always `pending` at acceptance time |
| `message` | string | Human-readable guidance |

The caller MUST poll the job status endpoint to confirm processing completion before
querying the document's content.

---

## Error Responses

| Status | Code | When |
|--------|------|------|
| 400 | `unsupported_file_type` | File extension/MIME type not in allowed list |
| 401 | `unauthorized` | Missing or invalid bearer token |
| 403 | `forbidden` | Token valid but role is `reader` (requires `contributor`) |
| 409 | `duplicate_document` | Content hash matches an existing document owned by this user |
| 413 | `file_too_large` | File exceeds configured maximum size |
| 422 | `validation_error` | Missing required field or malformed multipart request |
| 429 | `rate_limit_exceeded` | Per-user upload rate limit hit |
| 507 | `quota_exceeded` | File would exceed user's storage quota |
| 500 | `internal_error` | Unexpected server error |

```json
{
  "error": "duplicate_document",
  "message": "A document with identical content already exists in your knowledge base.",
  "existing_document_id": "a1b2c3d4-0000-0000-0000-000000000001"
}
```

```json
{
  "error": "quota_exceeded",
  "message": "Upload would exceed your storage quota of 1073741824 bytes. Current usage: 1020000000 bytes.",
  "quota_bytes": 1073741824,
  "used_bytes": 1020000000
}
```

---

## Headers

**Request headers required**:
```
Authorization: Bearer <token>
Content-Type: multipart/form-data; boundary=<boundary>
```

**Response headers always present**:
```
X-Request-ID: <uuid>
```
