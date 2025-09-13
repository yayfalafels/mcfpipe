# User Guide

_Last generated: 2025-09-10 08:37_

This document describes the DB API.

> **Scope**
> This documentation is a "Swagger‑style" Markdown that end‑users can read. It covers authentication, base URL conventions, every available route, example requests/responses, query semantics, and error codes.

---

## Base URL Endpoint

The API is intended to be **private** and accessed from inside the VPC via a VPC Interface Endpoint. 
Typical base URLs:

- **Private API Gateway via VPCE**  
  `https://<vpce-id>-<api-id>.execute-api.<region>.amazonaws.com/<stage>`

- **(FUTURE) Public API Gateway**  
  `https://<api-id>.execute-api.<region>.amazonaws.com/<stage>`

> Replace `<stage>` with your deployment stage (e.g., `dev`, `prod`).

---

## Authentication

**Mode:** `none` (no token/JWT expected). The API assumes **network‑level** access control:
- Deployed as a **Private API** in API Gateway
- Accessible **only** from inside the VPC or through the configured **Execute API VPCE**

No `Authorization` header is required by the handler. 

---

## Content & Headers

- **Content-Type:** `application/json`
- **Cache-Control:** `no-store` (responses)
- **Max request body:** ~1048576 bytes
- **Character encoding:** UTF‑8

---

## Resources & Tables

Each CRUD/search route is **table‑agnostic** and takes a `{table}` path segment. Valid values come from the schema bundled with the service.

| Table | Partition Key | Sort Key | Global Secondary Indexes |
|---|---|---|---|
| `post` | `id` | `posted_date` | `status` / `posted_date` projection: **ALL**|
| `post_details` | `post_id` | `(none)` | `url_slug` / `post_id` projection: **KEYS_ONLY**|
| `post_source` | `id` | `(none)` | _(none)_|
| `user` | `id` | `(none)` | `email` / `(none)` — projection: **KEYS_ONLY**|
|  |  |  | `username` / `(none)` projection: **KEYS_ONLY** |
|  |  |  | `status` / `(none)` projection: **ALL**|
| `user_config` | `user_id` | `(none)` | _(none)_|
| `role` | `id` | `(none)` | _(none)_|
| `track` | `id` | `user_id` |  `user_id` / `(none)` projection: **KEYS_ONLY**|
| `search_profile` | `track_id` | `(none)` | _(none)_|
| `job_track` | `id` | `track_id` | `job_id` / `track_id` projection: **KEYS_ONLY**|
| | | | `user_id` / `id` projection: **INCLUDE**|
| | | | `post_id` / `id` projection: **KEYS_ONLY**|
| | | | `user_id` / `company_name` projection: **KEYS_ONLY**|
| `job_details` | `job_id` | `(none)` | _(none)_|
| `track_score` | `job_track_id` | `(none)` | _(none)_|
| `track_cv` | `track_id` | `(none)` | _(none)_|
| `crm_status` | `job_id` | `(none)` | _(none)_|
| `apply_status` | `job_id` | `(none)` | _(none)_|

> You'll typically use `job`, `post`, `track`, etc. Keys must match each table's schema.

---

## Routes

- **GET /**  → `meta.version`
- **GET /__admin/refresh**  → `engine.reload`
- **GET /__admin/health**  → `engine.health`
- **GET /table/{table}/{id}**  → `table.get`
- **POST /table/{table}**  → `table.create`
- **PUT /table/{table}/{id}**  → `table.put`
- **DELETE /table/{table}/{id}**  → `table.delete`
- **POST /table/{table}/batch**  → `table.batch_write`
- **POST /table/{table}/delete**  → `table.batch_delete`
- **GET /table/{table}/search**  → `table.search`

---

## Conventions

### Path parameters
- `{table}` — logical table name from the schema (e.g., `job`, `post`)
- `{id}` — value for the table's partition key

### Common query parameters
- `sk` or `{sort_key}` — optional when the table defines a sort key
- `limit` — page size for `/search` (default ~100, max 1000)
- `index` — query a named GSI (when supported by the table)
- If **no key conditions** are provided to `/search`, the API performs a limited **Scan** (internal/low‑cost usage only).

### Errors & body validation
- JSON bodies are parsed and validated against the table schema.
- On **create**, missing `nullable:false` fields trigger errors like `missing_required:<field>`
- Type mismatches produce `invalid_type:<field>:<ExpectedType>`

---

## Endpoints

### GET `/`
__Service version__

Returns service metadata.

**Response 200**
```json
{ "service": "mcfpipe-dbapi", "version": "<git-sha or VERSION>", "stage": "<stage>" }
```

---

### GET `/__admin/refresh` 
__Reload schema__

Reloads the in‑memory schema/table registry. Useful after updating the schema file in S3 or the bundled artifact.

**Response 200**
```json
{ "reloaded_at": "<version>" }
```

---

### GET `/__admin/health`
__Health check__

Returns a simple success flag.

**Response 200**
```json
{ "success": true }
```

> **Note:** The route is configured as `engine.health`. The internal handler currently checks `meta.health` inside the meta/engine block; both resolve through the same internal path, but if you see a no‑op response, update `router._meta_engine` to accept `engine.health`.

---

### GET /table/{table}/{id}
__Get table item by id__

**Query**
sort key is required for tables with composite key [partition_key, sort_key]
`sk={sort_key_value}` (or `?{sort_key}=...`)

`GET /table/{table}/{id}?<sort_key>=sort_key_value`

**Example**
```bash
curl -s "$BASE/job/12345"
# or, if the table uses a sort key:
curl -s "$BASE/post/abc?sk=2025-08-01"
```

**Response 200**
```json
{ "id": "12345", "posted_date": "2025-08-01", "field1": "...", "field2": "...", "...": "..." }
```

**Response 404**
```json
{ "error": true, "code": "not_found", "message": "item not found in <table>", "request_id": "<req-id>" }
```

---

### POST /table/{table} 
__Create an item__

Body is a JSON object. If the table defines a partition key and you omit it, the API auto‑generates a UUIDv4 hex id.

**Example (`job`)**
```bash
curl -s -X POST "$BASE/job" -H "Content-Type: application/json" -d @- <<'JSON'
{ 
  "user_id": "u_001",
  "post_id": "p_789",
  "post_source_id": "mcf",
  "position": "Data Engineer",
  "posted_date": "2025-08-01",
  "closing_date": "2025-08-31",
  "company_name": "ACME Corp",
  "url": "https://acme.jobs/abc123"
}
JSON
```

**Response 200**
```json
{ "id": "generated-or-provided-id" }
```

**Response 400 (validation)**
```json
{ "error": true, "code": "validation_error", "message": "missing_required:user_id,missing_required:post_id", "request_id": "<req-id>" }
```

---

### PUT /table/{table}/{id}
Upsert/replace an item

Include `sk` as URL parameter when the table defines one.  See GET for details

**Example**
```bash
curl -s -X PUT "$BASE/job/12345" -H "Content-Type: application/json" -d @- <<'JSON'
{ 
  "user_id": "u_001",
  "post_id": "p_789",
  "post_source_id": "mcf",
  "position": "Data Engineer",
  "posted_date": "2025-08-01"
}
JSON
```

**Response 200**
```json
{ "id": "12345" }
```

**Response 400 (validation)**
```json
{ "error": true, "code": "validation_error", "message": "invalid_type:salary_high_sgd:Number", "request_id": "<req-id>" }
```

---

### DELETE /table/{table}/{id} 
__Delete an item__

Include `sk` for composite‑key tables. See GET for details

**Response 200**
```json
{ "id": "12345" }
```

---

### POST /table/{table}/batch
__Batch write__

Accepts **either** a bare JSON list or an object with `items`.

**Example**
```bash
curl -s -X POST "$BASE/job/batch" -H "Content-Type: application/json" -d @- <<'JSON'
[
  { "user_id": "u_001", "post_id": "p_1", "post_source_id": "mcf", "position": "Data Engineer", "posted_date": "2025-08-01" },
  { "user_id": "u_001", "post_id": "p_2", "post_source_id": "mcf", "position": "ML Engineer",   "posted_date": "2025-08-02" }
]
JSON
```

**Response 200**
```json
{ "success": 2, "failed": [], "items": [ { "...": "..." }, { "...": "..." } ] }
```

**Response 400**
```json
{ "error": true, "code": "validation_error", "message": "expected list of items", "request_id": "<req-id>" }
```

---

### POST /table/{table}/delete
__Batch delete__

Accepts **either** a list of key objects or a list of ids. For composite‑key tables, each key object should include both partition and sort keys.

**Example**
```bash
curl -s -X POST "$BASE/job/delete" -H "Content-Type: application/json" -d @- <<'JSON'
[ "id_1", "id_2", "id_3" ]
JSON
```

**Response 200**
```json
{ "success": 3, "failed": [] }
```

---

### GET /table/{table}/search
__Query or Scan__

Query by primary key and optional sort key, or fall back to a limited Scan.

**Query parameters**
- `limit` — page size (default ~100, max 1000)
- `index` — GSI name (optional)
- `{primary_key}=...` — equals match
- `{sort_key}=...` — equals match (when table has a sort key)

> **Note:** In the current code, advanced filters (e.g., `eq[field]=...`, `begins[field]=...`) are not wired in; equality on keys is supported. If no key condition is provided, the API performs a limited **Scan**.

**Example**
```bash
# Query all jobs for a user_id via GSI (if defined):
curl -s "$BASE/job/search?index=user_id-index&user_id=u_001&limit=100"
```

**Response 200**
```json
{ "items": [ { "...": "..." } ], "next": { "..." } }
```

> The `next` cursor (DynamoDB `LastEvaluatedKey`) is returned for chaining, but the handler does not yet accept a `next`/`cursor` parameter to continue pagination.

---

## Error model

All error responses follow the same shape and include a request id when available:

```json
All error responses follow the same shape and include a request id when available:

```json
{
  "error": true,
  "code": "<error_code>",
  "message": "<human_readable>",
  "request_id": "<aws-request-id>",
  "hint": "<optional-short-suggestion>",
  "details": { "...": "optional structured context" }
}
```

**Status and codes**

__DB API errors__

|HTTP status|	`code` tag |	When it happens |	Example message |
| - |	- |	- |	- |
| 400 |	`bad_request` |	Handler guardrails: missing/invalid `httpMethod`/`path`; `isBase64Encoded=true` and no body |	`isBase64Encoded=True but body is null` |
| 400	| `validation_error` |	JSON parse or schema validation failed; `missing_required:*` / `invalid_type:*:*`; wrong batch shape |	`missing_required:user_id,missing_required:post_id` |
| 404	| `not_found` |	Unknown route/table; or item not found on `GET /{table}/{id}` |	`item not found in <table>` |
| 500	| `internal_error` |	Unhandled exception from router/engine |	`unexpected_error` |

**Notes**
• Authentication/authorization is not enforced by this Lambda (private VPC-only API), so 401/403 are not emitted by the service code.
• Some errors below may be returned by API Gateway/infrastructure (and will not follow the JSON shape above):


__API Gateway / infra errors__

| HTTP status	| Origin	|  Typical trigger | Notes | 
| -	| -	| - | - | 
| 401	| API Gateway/Auth | If a future IAM/authorizer is added and credentials fail | Not used by current deployment |
| 403	| API Gateway/Policy | Resource policy/VPC policy denies access	 | Not used by current deployment |
| 413	| API Gateway | Payload too large	 | Enforced before Lambda runs |
| 429	| API Gateway | Throttling (rate/burst limits) | Enforced before Lambda runs |
| 502/504	API Gateway | Integration error or timeout | Upstream timeout/health issues |

---

## Tips

- Always send `Content-Type: application/json` for bodies.
- For composite keys, pass `sk` as a **query parameter** on GET/PUT/DELETE.
- Use `/__admin/refresh` after deploying a new schema to S3.
- Keep request bodies under ~1048576 bytes.
- For `/search`, prefer key‑based queries (fast) over scans (slow/limited).

---
