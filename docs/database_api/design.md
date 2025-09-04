# Design Specification
Implementation target: AWS Lambda (zip or container image) behind API Gateway (private) in a VPC.
Style: config-driven routing, re-usable core, thin domain layer.

## Design principles

- **Generic Routing**: Dynamic table access via path parameters.
- **Schema Enforcement**: All incoming payloads are validated against a DB Schema config JSON.
- **Minimal Endpoints**: A small set of HTTP routes supports all CRUD and batch operations.
- **Modular**: Tables can be added/updated without code changes.
- **Internal Use**: API is intended for trusted internal services (e.g., ingestion, screening, CRM).
- **API Gateway Thin Infra wrapper**: API Gateway acts only as a thin infrastructure layer; the main jobdb app handles routing, validation, and business rules.

__AWS Deployment__

- **API Gateway (private)**: runs in VPC private subnets, not publicly accessible.
- **Routing strategy**: catch-all {proxy+} route forwards to Lambda; all validation handled in jobdb.
- **Execution environment**: Lambda runs as container from Amazon ECR image.
- **Image versioning**: GitHub Actions tags image by commit SHA; hot reload supported for schema/config.
- **Logging**: output auto-forwarded to CloudWatch Logs.

## 01 Functional Requirements

### 1.1 Core

- CRUD for multiple logical tables in DynamoDB, defined by a shared db_schema.json.
- Batch write and batch delete.
- Query/search with optional GSI support and pagination.
- Config-driven routes (no code change to add/remove endpoints).
- Hot reload of schema/config without redeploy.
- Health/version endpoints.

### 1.2 Non-Functional

- Cold-start efficient; minimal imports in handler path.
- Idempotent writes (opt-in via header).
- Structured, single-line logging.
- Rate/size limits per route (configurable).
- Works as ZIP or Container image.
- Private API only accessible via VPC Endpoint; optional auth (JWT/API key/allowlist).

## 02 Primary Use Cases

01. **Create** in a table from an internal service.
02. **Read** item by key
03. Replace/**Update** item by primary key (and optional sort key).
04. **Delete** item by key.
05. **Batch** write/delete from background jobs.
06. **Search** by partition key + index (with pagination).
07. **Admin**: refresh schema/config after S3 updates.
08. **Health**: check liveness/version from tester job.

## 03 Routes

All routes and behaviors are declared in routes config file `config/routes.json`. Below is the default set.

| Name | Method |  Path |  Operation | Request | Response | 
| - | - | - | - | - | - | 
| root | GET | `/` | version | – | `{"service":"dbapi","version":"x.y.z","stage":"prod"}` |
| get-item | GET | `/{table}/{id}` | Table.get(id) | – | 200 item or 404 |
| create-item | POST | `/{table}` | Table.create(body) | JSON body | 201 {"id":…} |
| put-item | PUT | `/{table}/{id}` | Table.put(id, body) | JSON body | 200 {"id":…} |
| delete-item | DELETE | `/{table}/{id}` | Table.delete(id) | – | 200 {"id":…} |
| batch-write | POST | `/{table}/batch` | Table.batch_write(items) | `{"items":[...]}` or [...] | 200 `{"success":N,"failed":[...]}` |
| batch-delete | POST | `/{table}/delete` | Table.batch_delete(keys) | `{"keys":[{id},...]}` | 200 `{"success":N,"failed":[...]}` |
| search | GET | `/{table}/search` | Table.search(...) | querystring | 200 `{"items":[...],"next":"token?"}` |
| admin-reload | GET | `/__admin/refresh` | Engine.reload() | – | 200 `{"reloaded_at": epoch}` |
| health | GET | `/__admin/health` | ping | – | 200 `{"success":true}` |

### 3.1 Path Parameters

- **table** → target table name
- **id** → primary key value

### 3.2 Search Query Parameters (default mapping)

- **index** → GSI name (optional)
- **limit** → page size (default 100, max 1000)
- **next** → pagination token (opaque base64)

Equality conditions:

- pk=…, sk=… (mapped into KeyConditionExpression)
- Optional filters: eq[field]=val, begins[field]=prefix (mapped to FilterExpression)

You can override/extend this mapping per table via the `search_maps` module.

### 3.3 Sample request/response bodies

__POST /{table}__

_Request_
```json
{
  "posted_date": "2025-08-01",
  "position": "Data Engineer",
  "url": "https://example.com/jobs/abc123"
}
```

_Response_
```json
{"id":"abc123"}
```

__POST /{table}/batch__

_Request_
```json
[
  {"posted_date": "2025-08-02", "position": "ML Engineer"},
  {"posted_date": "2025-08-05", "position": "Data Analyst"}
]
```

_Response_
```json
{
  "success":[
      {"id": "abc123", "posted_date": "2025-08-02", "position": "ML Engineer"}, 
      ...
  ],
  "failed":[]
}
```

## 04 Authentication & Authorization

__Authentication modes__

- **VPC-only**: API Gateway resource policy allows traffic only from vpce-*. No per-request auth.
- **Bearer JWT (future release)**: Validate Authorization: Bearer <JWT> (Cognito/JWKS). Configurable issuer, audience, JWKS URL.

## 05 Validation

- **DB Schema**: (S3 primary, bundled fallback). Describes each table’s keys and allowed attributes.
- **Request**: Body/params validated against table spec. Optional jsonschema rules per table/route.
- **Hard rules**: PK presence, type coercion (string/number/bool), size caps, reserved attribute bans (_internal, etc.).

## 06 Error Model Responses
All responses are JSON with this envelope:

```json
{
  "status": 400,
  "error": "validation_error",
  "message": "Missing required field: id",
  "request_id": "aws-request-id",
  "hint": "See docs for table Users",
  "details": { "field": "id" }
}
```

__Error Mapping__

| http code | error |
| - | - |
| 400 | validation_error, bad_request |
| 401 | unauthorized |
| 403 | forbidden |
| 404 | not_found |
| 409 | conflict (conditional check failed / idempotency) |
| 413 | payload_too_large |
| 429 | rate_limited |
| 500 | internal_error (include request_id, masked details) |

## 07 Logging and Metrics

One structured single line per request:

```
[ts, request_id, method, path, route, table, op, user/principal?, status, duration_ms, items_count, stage, version]
```

- Errors include error_code and compact stack trace.
- Optionally emit CloudWatch EMF for ok_count, error_count, throttle_count.

## 08 OOP Architecture

### 8.1 Core Classes 
re-usable design

| Class | description |
| - | - |
| DBEngine | Loads schema/config from S3 (with local fallback) |
|  | Builds Table registry |
|  | reload() hot-reloads schema & configs |
|  | Settings: table prefix, limits, auth mode |
| Table | Encapsulates DynamoDB table (pk, sk?, GSIs, allowed columns) |
|  | Ops: get, create, put, delete, batch_write, batch_delete, search |
|  | Optional validator mixin |
| Router | Loads routes.json; tokenizes paths, matches (method, path) |
|  | Dispatches to Table or Engine |
| Auth | Pluggable strategies: none/jwt/key |
| Validator | Core field/type/required checks; optional jsonschema |
| Expr | Helpers to build KeyCondition/Filter expressions |
| Responses | Helpers to produce standardized HTTP responses |
| Log | Structured logger |

### 8.2 Domain Layer
project-specific

- **hooks**: before_*/after_* for cross-cutting transforms.
- **search_maps**: custom query builders per table/index.
- **policies**: route/table guardrails (e.g., block delete in prod).
- **auth**: glue code to chosen auth mode (e.g., Cognito claim mapping).

## 09 Directory Layout

```
/jobdb
├─ handler.py                       # Lambda entrypoint: def handler(event, context)
├─ core/                            # reusable framework
│  ├─ __init__.py
│  ├─ engine.py
│  ├─ table.py
│  ├─ router.py
│  ├─ validators.py
│  ├─ expressions.py
│  ├─ responses.py
│  ├─ logging.py
│  └─ util.py
├─ domain/                          # project-specific
│  ├─ __init__.py
│  ├─ hooks.py
│  ├─ search_maps.py
│  ├─ policies.py
│  └─ auth.py
├─ config/                          # default/bundled configs
│  ├─ routes.json
│  ├─ policies.json
│  ├─ settings.json
│  └─ schema_map.json
├─ schemas/
│  └─ db_schema.json                # fallback
├─ tests/
│  ├─ test_router.py
│  ├─ test_engine.py
│  ├─ test_table.py
│  └─ test_integration_smoke.py
├─ VERSION
└─ requirements.txt
```

__Packaging__

Container dockerfile

```dockerfile
# jobdb/Dockerfile
FROM public.ecr.aws/lambda/python:3.12
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /var/task

# install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# copy working directory
COPY . .

# point to the entry point
CMD ["handler.lambda_handler"]
```

## 10 Config Specifications

__10.1 Settings__

```json
{
  "stage": "prod",
  "log_level": "INFO",
  "cors_origins": ["*"],
  "auth": { "mode": "none" },
  "limits": {
    "max_batch": 25,
    "max_body_kb": 512,
    "default_page_size": 100,
    "max_page_size": 1000
  }
}
```

__10.2 Routes__

```json
{
  "routes": [
    {"name":"root","method":"GET","path":"/","op":"meta.version"},
    {"name":"get-item","method":"GET","path":"/{table}/{id}","op":"table.get"},
    {"name":"create-item","method":"POST","path":"/{table}","op":"table.create","body":"json"},
    {"name":"put-item","method":"PUT","path":"/{table}/{id}","op":"table.put","body":"json"},
    {"name":"delete-item","method":"DELETE","path":"/{table}/{id}","op":"table.delete"},
    {"name":"batch-write","method":"POST","path":"/{table}/batch","op":"table.batch_write","body":"json"},
    {"name":"batch-delete","method":"POST","path":"/{table}/delete","op":"table.batch_delete","body":"json"},
    {"name":"search","method":"GET","path":"/{table}/search","op":"table.search",
     "query_to_search": {"index":"index","limit":"limit","next":"next",
       "eq":["pk","sk"], "begins":[],"filters":[]}},
    {"name":"admin-reload","method":"GET","path":"/__admin/refresh","op":"engine.reload"},
    {"name":"health","method":"GET","path":"/__admin/health","op":"meta.health"}
  ]
}
```

__10.3 Policies__

```json
{
  "deny_in_prod": [
    {"method":"DELETE","path":"/{table}/{id}"},
    {"method":"POST","path":"/{table}/delete"}
  ],
  "rate_limits": [
    {"name":"writes","match":{"method":"POST|PUT"},"rps":50,"burst":100}
  ],
  "body_size_kb": [
    {"match":{"path":"/{table}/batch"},"max":1024}
  ],
  "auth": {
    "mode": "none",
    "jwt": {"issuer":"https://cognito-idp...","audience":"...","jwks_uri":"..."},
    "api_keys_sha256": ["<hash>","<hash2>"]
  }
}
```

__10.4 DB SCHEMA__

```json
{
  "tables": [
    {
      "table_name": "Jobs",
      "primary_key": "job_id",
      "sort_key": null,
      "columns": [
        {"name":"job_id","type":"string","required":true},
        {"name":"title","type":"string","required":true},
        {"name":"company","type":"string"},
        {"name":"created_at","type":"number"}
      ],
      "gsis": [
        {"name":"CompanyIndex","pk":"company","sk":"created_at"}
      ]
    }
  ]
}
```

### 10.5 Environment Variables

__from CloudFormation__

_S3 locations_

- **schema**: `SCHEMA_S3_BUCKET`, `SCHEMA_S3_KEY`
- **config**: `CONFIG_S3_BUCKET`, `ROUTES_S3_KEY`, `POLICIES_S3_KEY`, `SETTINGS_S3_KEY`

_database_

- `TABLE_PREFIX`

_operational_

- `LOG_LEVEL`
- `STAGE`
- `IDEMPOTENCY_TTL_SECONDS`

## 11 DynamoDB and GSI Mapping
The GSI specification mapping is consistent across:
This ensures GSIs declared in schema are correctly realized in CFN and exposed in API search.

- Data model
- DB schema JSON
- CloudFormation template
- Constructor script

**Table name prefix**: `<env>_mcfpipe_<table_name>` e.g., `prod_mcfpipe_job`.

## 12 Module Specifications
_selected methods_

### 12.1 core/engine.py

```python
class DBEngine:
    def __init__(self, schema_src, config_src, table_prefix="", now=None): ...
    def reload(self) -> dict: ...
    def table(self, name:str) -> "Table": ...
    def meta(self) -> dict: ...  # version, stage, loaded_at
```

### 12.2 core/table.py

```python
class Table:
    def __init__(self, boto_table, name, pk, sk=None, columns=None, gsis=None): ...
    def get(self, id_, sort=None) -> dict|None: ...
    def create(self, item:dict, idem_key:str|None=None) -> dict: ...
    def put(self, id_, payload:dict, sort=None, idem_key:str|None=None) -> dict: ...
    def delete(self, id_, sort=None) -> dict: ...
    def batch_write(self, items:list[dict]) -> dict: ...
    def batch_delete(self, keys:list[dict]) -> dict: ...
    def search(self, index=None, key_conditions=None, filters=None, limit=100, next_token=None) -> dict: ...
```

### 12.3 core/router.py

```python
class Router:
    def __init__(self, routes_config, engine, domain_hooks=None, policies=None, auth=None): ...
    def dispatch(self, event:dict) -> dict: ...
```

### 12.4 domain/hooks.py

```python
def before_create(table_name, item, ctx): return item
def after_get(table_name, item, ctx): return item

# Similar hooks: before_put, before_delete, before_search
```

### 12.5 domain/search_maps.py

```python
def build_conditions(table_name, qs:dict) -> dict:
    """Return dict suitable for Table.search: {KeyConditionExpression,...}"""
```

## 13 Coding Patterns

- Early return in router; smallest possible if chain
- Pure functions in domain hooks, deterministic transforms
- Backoff and retry on ProvisionedThroughputExceededException (jitter)
- Idempotency: honor Idempotency-Key header by writing a small token record (optional table) or using conditional writes
- Pagination tokens: encode DynamoDB LastEvaluatedKey as URL-safe base64

## 14 Dependencies
Minimal, pinned:

requirements.txt
```
boto3==1.34.*
botocore==1.34.*
python-jose[cryptography]==3.3.0     # if JWT mode enabled
jsonschema==4.23.0                   # optional, for strict validation
```

## 15 Test Plan

### 15.1 Unit Tests
python module: `pytest`

| test module | tests, sequence |
| - | - |
| `engine` | loads schema/config (S3 mocked) |
| | reload() rebuilds registry |
| `table` | create/get/put/delete happy paths (boto3 stubber) |
| | conditional write conflict ⇒ 409 |
| | batch write/delete partial failures ⇒ failed list |
| | search builds correct expressions |
| `router` | route matching and param extraction |
| | body parsing, error on malformed JSON |
| | policies deny in prod (DELETE) |
| | auth modes (none/key/jwt) happy + failure |

### 15.2 Integration
local

- Lambda handler invoked with synthetic API Gateway events
- Verify response envelopes, status codes, headers

## 15.3 End-to-end
within-VPC

Tester container runs:

| test route | expected response |
| - | - |
| GET /__admin/health | 200 |
| POST /Jobs | 201 |
| GET /Jobs/{id} | 200 |
| PUT /Jobs/{id} | 200 |
| GET /Jobs/search?pk=... | 200 with items |
| DELETE /Jobs/{id} | (blocked in prod by policy) 403/200 in dev |
| Pagination across 2+ pages | |
| Rate limit behavior | 429 under stress |

## 16 Handler
skeleton snippet

```python
# handler.py
from core.router import Router
from core.engine import DBEngine
from core.responses import to_http
from domain import hooks, auth as domain_auth
from core.util import load_config_bundle

engine = DBEngine(schema_src="s3+fallback", config_src="s3+fallback")
routes, policies, settings = load_config_bundle()
router = Router(routes, engine, domain_hooks=hooks, policies=policies, auth=domain_auth.make(settings))

def handler(event, context):
    resp = router.dispatch(event)
    return to_http(resp)
```

## 17 Operational Notes

- **CloudWatch Logs**: Lambda logs auto-ingested; ensure a log retention policy (e.g., 14–30 days).
- **Limits**: Keep payloads < 1 MB typical; compression can be enabled on clients.

## 18 Security Considerations

- stricter authentication for sensitive tables
- Deny destructive routes in prod via policies JSON
- Input validation on every write; strip unknown fields unless allow_unknown=true per table.
- Log redaction for fields listed in policies.json (e.g., password, ssn).
- Strict JSON parsing (Content-Type: application/json required for bodies).

## 19 Acceptance Criteria

- All default routes functional with schema-defined tables.
- Configs can be updated via S3 and picked up by /__admin/refresh.
- Unit coverage **≥ 80%** of core.
- E2E tester passes all CRUD/search flows in VPC.
- Logs are single-line JSON and include request id and duration.
- Auth mode selectable by config and enforced.

## 20 Appendix — Sample Events and Responses

__Create__

_request_

```
POST /Jobs
Content-Type: application/json
Idempotency-Key: 3c1a...

{"title":"DE","company":"RSK"}
```

_response_

```json
201 {"id":"J123"}
```

__Search__

_request_

```sql
GET /Jobs/search?pk=RSK&index=CompanyIndex&limit=50
```

_response_

```json
{"items":[{...}], "next":"eyJMYXN0RXZhbHVhdGVkS2V5Ijp7..."} 
```