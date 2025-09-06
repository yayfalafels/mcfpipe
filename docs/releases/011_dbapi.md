# Database API
This release covers the setup of Database API on AWS, it is part of the broader release series for the `job search` app workflow.

## Release sequence

- In an **earlier release `0.1.0`** in the `job search` workflow series: the networking layer was setup along with creation of S3 bucket for the `mcfpipe` project.  So the networking resources; VPC, subnets, etc.. are available for this release.
- for the **next release(s)**: The compute resources in the `job search` workflow such as; webscraper, lambda and testers depend on the DB API being already setup so that they can use the DB API for storage.  

## Objectives and Aims
Create and validate the DB API

## Requirements
The `Database API` provides a RESTful interface for CRUD operations on DynamoDB tables defined in the system data model. The API is implemented as a **generic Lambda function** behind API Gateway, supporting dynamic routing based on path parameters and validating requests using the canonical schema file `db_schema.json`.

This service is designed to act as a **thin, schema-aware wrapper** over the DynamoDB backend to enable flexible, centralized, and secure access to all operational data in the jobsearch system.

## Scope
The current scope includes the **Database API**, deployed via CICD Github Action

- **CICD** github deploy action workflows
- **Database** DynamoDB tables from schema
- **DB API** API Gateway + Lambda functions
- **Tester** Tester fargate container to validate the DB API and the Network infrastructure

## App Implementation (0.1.1)

- Config-driven router and reusable core implemented under `jobdb/core/*` with domain stubs in `jobdb/domain/*`.
- Default routes defined in `jobdb/config/routes.json` covering CRUD, batch, search, health and admin reload.
- Fallback schema bundled at `jobdb/schemas/db_schema.json`; primary schema source remains S3 `storage/db_schema.json`.
- Physical DynamoDB table names derived as `<stage>_<prefix>_<table>`; default prefix `mcfpipe` and stage from env `ENV_STAGE`.
- Lambda entrypoint `jobdb/handler.py` wires router/engine and serves version at `/`.

## AWS Infrastructure
The AWS infrastructure is organized into layered CloudFormation stacks, segregated by function and coupled through the repository via parameters and configuration files.

__Cloudformation stacks__
Cloudformation stack layers

| id | stack | purpose | resources |
| - | - | - | - |
| 01 | network | initial setup S3 bucket, config and network and VPC for public and private subnets | VPC, subnets, security groups, internet gateway |
| 02 | database | data storage | DynamoDB tables |
| 03 | tester | stand-alone tester to validate DB API and other app services | Fargate ECS container |
| 04 | db api | database connector API | DB API container image, API Gateway, Lambda handler |

__Dev stack: EC2 vs Fargate__
It may be necessary to have two parallel stacks for each compute resources 

1. **DEV**: on EC2 for dev, diagnostic and troubleshooting, can SSH into instance
2. **PROD**: Fargate container cost-optimized for production, limited SSH need to use ECS Exec to run specific diagnostic commands.

__AWS CLI__
Additional resources created outside of the cloudformation stack either manually from local PC or via Github actions. 

These resources must be deleted in a separate cleanup workflow.

_manual setup resources_

| id | resource | executor | sequence |
| - | - | - | - |
| 01 | S3 bucket | Github Action | initial setup |
| 02 | S3 config | Github Action | initial setup after s3 bucket creation |
| 03 | ECR Dockerimages | Github Action | before the stack they are used in |

__Stack deploy__
The stack deploy performed by GHA runner includes

 - **parameters** read-in/export to S3
 - **idempotent deploy** checks if the target stack is already in state `ROLLBACK_COMPLETE` or `CREATE_FAIL`
  - deletes the stack and then triggers a re-deploy
 - **fail diagnostics** captures diagnostic logs for stack deploy fail and prints out in the runner logs

The stack deploy AWS CLI command includes these standard arguments:

| argument | description |
| - | - |
| `--template-file` | Path to the rendered CFN template the runner will submit. Typically `${CF_TEMPLATE_DIR}/${STACK_TEMPLATE_FILE}`. |
| `--stack-name` | Logical name of the stack to create/update. Used for change sets, events, and cross-stack exports. |
| `--capabilities` | Required when your template creates/updates IAM resources. `CAPABILITY_NAMED_IAM` confirms you understand IAM changes with explicit names. |
| `--no-fail-on-empty-changeset` | Makes updates idempotent: if the template/params/tags don’t change, CFN returns an empty change set and the CLI exits **successfully** instead of erroring. |
| `--parameter-overrides` | Inline key=value pairs that bind to your template’s `Parameters`. Values here take precedence over any defaults in the template. |
| `--tags` | Key=value pairs to tag the **stack** (and, for many resource types, the resources). Useful for ownership, cost allocation, and environment scoping. |

 ```bash
aws cloudformation deploy \
--template-file $CF_TEMPLATE_DIR/$STACK_TEMPLATE_FILE \
--stack-name $STACK_NAME \
--capabilities CAPABILITY_NAMED_IAM \
--no-fail-on-empty-changeset \
--parameter-overrides \
  ...
--tags \
  role=$ROLE \
  project=$PROJECT_NAME

 ```

## Github Action Workflows
CICD to deploy each of the stacks are orchestrated via Github Actions 

| id | workflow | app feature | description |
| - | - | - | - |
| 01 | network | initial setup and network | initial setup, create S3 bucket, global IAM roles, network infrastructure |
| 02 | tester | tester | create docker image for tester Fargate container image, deploy tester stack |
| 03 | db api | database api | load database schema, deploy database dynamodb tables and db api stack, upload db api config ex API URL |

### Github action 02: DB API
load database schema, deploy database dynamodb tables and db api stack, upload db api config 
ex API URL

__Artifacts__

| id | artifact | file name | source code | AWS / S3 |
| - | - | - | - | - |
| 01 | db schema | `db_schema.json` | `storage/` | `storage/` |
| 02 | template constructor script | `cf_template_constructor.py` | `storage/` | - |
| 03 | CF template | `db_api_stack.yaml` | `aws/cloudformation/` | - |
| 04 | Lambda container image        | (ECR)  | `jobdb/*`  | ECR repo: `mcfpipe-dbapi` |
| 05 | stack outputs | `jobdb_stack_config.json` | - | `apps/jobdb/` |

__Stack outputs__
contents of the DB API stack config JSON

| key                 | description                           |
| ------------------- | ------------------------------------- |
| DbApiUrl            | Base URL for the deployed stage       |
| RestApiId           | API Gateway RestApi ID                |
| ApiStageName        | Stage name                            |
| RootResourceId      | Resource ID of `/`                    |
| ProxyResourceId     | Resource ID of `/{proxy+}`            |
| DbLambdaFunctionName| Name of the DB API Lambda function    |
| DbLambdaRoleArn     | ARN of the Lambda IAM role            |

__Github action steps__

| id | step | description |
| - | - | - |
| 01 | schema load | load the db schema to workspace, upload to S3 |
| 02 | (conditional) build container image | build image from source code register in ECR. Conditional when `jobdb/**` changed or `force_rebuild` |
| 03 | stack deploy | deploy the db api stack, pass container image either new created in GHA or latest. on stack failure, print diagnostics |
| 04 | artifacts | upload artifacts to config JSON |
| 05 | tests upload | upload unit tests to S3 |
| 06 | tests run | run tests on the DB API routes |

## Design

### DynamoDB Database

__table name prefix__

to uniquely identify the DynamoDB tables in the account, table names include a prefix for `<env>_mcfpipe_`, so the full DynamoDB table name is `<env>_mcfpipe_<table_name>`. Since the API requests and responses are based on the base `table_name`, the full path to the DDB resource must be resolved by the API handler.

__Search__

**GET** `/{table}/search`

- **table must exist** in `db_schema.json`.
- **Primary (partition) key** queries are available on any table
- **Global Secondary Indexes (GSI)** extend search to other declared columns.

__Global Secondary Indexes (GSI)__

- the GSI must be declared in the DynamoDB table definition
- DynamoDB requires an `IndexName` for non-PK queries; this API exposes a thin, validated façade over `Query`.

### DB API app


### Tester
The tester app uses the test module `tester` and runs on a dedicated AWS Fargate container
The app runs `tests.py` which uses `requests` package to send HTTPS requests to the API endpoint.

__docker image__

- base image: `python:3.11-slim`
- minimal python dependencies [pytest, requests]

__environment variables__
environment variables are passed to the container by Github actions at the `run-task` cli command

| id | variable | description |
| - | - | - |
| 01 | DB_API_URL | API endpoint |

## Issues

| id | status | type | issue | description |
| - | - | - | - | - |
| 01 | open | ENHANCEMENT | [ECR cleanup #6](https://github.com/yayfalafels/mcfpipe/issues/6) | Add a cleanup function to cleanup old ECR image versions |
| 02 | closed | SDLC | tester stack | validated 2025-08-16 |
| 03 | open | SDLC | DB API stack | validation pending |
| 04 | open | ENHANCEMENT | [ECR refresh on changes #7](https://github.com/yayfalafels/mcfpipe/issues/7) | update the logic in GHA to only refresh the DB API ECR docker image either no image is present OR changes that would affect the docker image |
| 05 | closed | BUG | [API IAM CW log #8](https://github.com/yayfalafels/mcfpipe/issues/8) | API does not have IAM role to read/write to CW log group |
| 06 | closed | BUG | [CF API log format #9](https://github.com/yayfalafels/mcfpipe/issues/9) | YAML line break fold `>-` not working as expected |
| 07 | closed | BUG | [DB_API_URL not passed #10](https://github.com/yayfalafels/mcfpipe/issues/10) | GHA parameter `DB_API_URL` not passed from stack outputs |
| 08 | closed | BUG | [ECS run container name conflict #11](https://github.com/yayfalafels/mcfpipe/issues/11) | container name conflict btw CF template and GHA env variable |
| 09 | closed | BUG | [tester container script failures #12](https://github.com/yayfalafels/mcfpipe/issues/12) | missing IAM `AmazonECSTaskExecutionRolePolicy` on the `TesterExecutionRole` |
| 10 | closed | BUG | [test 00 basic route fail 400 Forbidden #13](https://github.com/yayfalafels/mcfpipe/issues/13) | test 00 basic route failed 400 Forbidden |
| 11 | closed | ENHANCEMENT | [GHA and CF conditional refresh #14](https://github.com/yayfalafels/mcfpipe/issues/14) | GHA and CF conditional refresh |
| 12 | closed | ENHANCEMENT | [duplicate VPCE costs tester private subnet #15](https://github.com/yayfalafels/mcfpipe/issues/15) | switch tester to public subnet, delete unnecessary VPCE |
| 13 | open | SDLC | DB API first pass review | * |

__Issue details__

### (open) 01 ECR cleanup
Github issue [ECR cleanup #6](https://github.com/yayfalafels/mcfpipe/issues/6)
type: `ENHANCEMENT`

__situation__
Current behavior keeps versioned ECR images. Each image is tagged to a commit and size ~ 60 MB. Over time, this can accumulate for excess storage costs.

__resolution__
Add a cleanup function, either separate lambda (recommended) or a setup in the GHA to cleanup old ECR image versions

### (open) 04 ECR refresh on changes
Github issue [ECR refresh on changes #7](https://github.com/yayfalafels/mcfpipe/issues/7)
type: `ENHANCEMENT`

__situation__
The current configuration refreshes the DB API ECR docker image for all GHA triggers, including those which have no effect on the container, such as changes to `db_schema.json` which the container pulls directly from S3 and is not pre-loaded to the container at image build runtine.

__resolution__
update the logic in GHA to only refresh the DB API ECR docker image either no image is present OR changes that would affect the docker image, such as any change to `jobdb/*` contents.

### (open) 13 DB API first pass review
type: `SDLC`

__Assessment__

Core structure matches the intended architecture (handler + core + domain + config).  
Addressing these issues will bring the implementation much closer to the design, while the additional unit/integration/E2E tests will harden behavior and prevent regressions.

The biggest gaps are

- schema/validator key mismatch
- opaque pagination token
- reload payload
- envelope & route consistency
- tests diverging from spec

__issues__

| id | status | type | issue | description |
| - | - | - | - | - |
| 01 | open | BUG | engine.reload payload | |
| 02 | open | BUG | opaque pagination token | |
| 17 | open | BUG | validator schema keys mismatch | |
| 03 | open | BUG | router garbled error code | |
| 04 | open | BUG | health version payload | |
| 05 | open | BUG | UTC time format | |
| 06 | open | BUG | variable name mismatch | |
| 07 | open | BUG | empty default schema JSON | |
| 08 | open | BUG | DynamoDB number types | |
| 09 | open | BUG | policies not enforced | |
| 10 | open | BUG | routing and op naming | |
| 11 | open | BUG | root version behavior | |
| 12 | open | BUG | item key naming | |
| 13 | open | BUG | write-delete request-response spec | |
| 14 | open | BUG | search query params | |
| 15 | open | BUG | settings keys mismatch | |
| 16 | open | BUG | tests error mapping | |
| 17 | open | ENHANCEMENT | consolidated response build | |
| 18 | open | ENHANCEMENT | logging format | |
| 19 | open | ENHANCEMENT | auth placeholder | |

__Potential bugs and exceptions__

_01 (open) BUG engine.reload payload_

`engine.reload()` returns the wrong payload. It currently returns `{'reloaded_at': self.version}` instead of a timestamp. Spec calls for an epoch/instant (e.g., ISO or unix seconds). Fix to return a real time value.

Quick patch:

```python
import time
def reload(self) -> dict:
    ...
    self.log.info('engine_reloaded', tables=len(self._tables))
    return {'reloaded_at': int(time.time())}
```

_02 (open) BUG opaque pagination token_

Pagination token is not opaque/base64. `Table.search()` returns DynamoDB’s raw LastEvaluatedKey in next. Design requires an opaque base64 token; requests should also accept next and decode it into ExclusiveStartKey.

Pagination token (opaque):

```python
# in Table.search(...)
import json, base64
...
if 'LastEvaluatedKey' in resp:
    token_json = json.dumps(resp['LastEvaluatedKey'], separators=(',',':'))
    next_token = base64.urlsafe_b64encode(token_json.encode()).decode()
else:
    next_token = None
return {'items': items, 'next': next_token}
```

…and in Router, if query has next, base64-decode and set ExclusiveStartKey.

_17 (open) BUG validator schema keys mismatch_

Validator schema keys don’t match the spec.  
mismatch validator module `core/validators.py` with the schema in the design
This will skip required/type checks silently. Align keys or support both.

- as implemented: "column_name", "data_type", "nullable" 
- design:  "name", "type", "required" 

Validator key alignment:

```python
# build columns map tolerant to both styles
def _name(c): return c.get('name') or c.get('column_name')
def _type(c): return c.get('type') or c.get('data_type')
def _required(c): 
    return bool(c.get('required')) or not c.get('nullable', True)
self.columns = { _name(c): {'type': _type(c), 'required': _required(c)} for c in cols if _name(c) }
```

__Response envelope mismatches and typos__

_03 (open) BUG router garbled error code_

Router returns error code 'internal_err...cted_error' (string is garbled). Needs a stable "internal_error" with mapped error names per table.

_04 (open) BUG health version payloads_

Health/version payloads differ from spec—see §2 and §3 below.

Health route payload. Spec says health => `{"ok": true}` (detailed_design) or `{"success": true}` `design.md`. Your test asserts `status == 1`. Pick one and standardize test + code (recommend {"ok": true}).

Return {"ok": true} for health and unify tests to that.
Prefer routing / through Router (meta.version) returning {service, version, stage} as spec’d.

_05 (open) BUG UTC time format_

Handler time formatting. `_utcnow_iso()` builds an ISO string with +00:00 then appends 'Z', yielding ...+00:00Z. Either use `.strftime('%Y-%m-%dT%H:%M:%SZ')` or produce a clean UTC ISO8601.

_06 (open) BUG variable name mismatch design and implementation_

S3/env var names drift. `engine.py` 
Support both names or switch to the spec.

- separate config keys too
- `engine.py` looks for `S3_BUCKET` and `DB_SCHEMA_S3`
- design specifies  `SCHEMA_S3_BUCKET` and `SCHEMA_S3_KEY` 

_07 (open) BUG empty default schema JSON_

Empty bundled schema. `schemas/db_schema.json` has "tables": []. If S3 isn’t set/available, all CRUD routes will fail at runtime. Consider raising a clear startup error or ship a minimal example schema.

_08 (open) BUG DynamoDB number types_

DynamoDB number types. Writes may send floats; DynamoDB prefers Decimal. Consider coercing numeric types (or document the expectation) to avoid precision/type issues.

Type safety and numbers. Consider Decimal for numeric attributes to play nicely with DynamoDB. Add mypy type hints where feasible.

_09 (open) BUG policies not enforced_

Idempotency & limits not enforced. Spec mentions idempotency and rate/size caps; code paths for those aren’t present (policies file is a stub).

__implementation consistency vs design__

_10 (open) BUG routing and op naming_

Routes & op naming: Your `config/routes.json` uses simple ops: "get", "create", "search", etc. Spec shows namespaced ops like "table.get", "engine.reload", "meta.health" plus a query_to_search mapping. You can either: (a) update Router to normalize both styles, or (b) adopt the namespaced ops and mapping from the spec.

Router op names & mapping. Consider adopting the namespaced ops from spec (table.get, engine.reload, meta.health) and a query_to_search map to decouple URL/params from Table.search.

_11 (open) BUG root version behavior_

Root/version behavior. The handler short-circuits / and returns version inline; spec models this as a route via router (minor but worth aligning for consistency/config-driven behavior).

_12 (open) BUG item key naming_

Single-item response body keys: One spec table shows { "id": ... }, another shows { "pk": ... } for create/put/delete responses—your Table.create/put/delete return {<actual_pk_name>: value}. Choose one convention and lock it: (a) standardize on { "id": ... } for UX simplicity, or (b) echo actual PK (e.g., job_id). Update docs & tests accordingly.

_13 (open) BUG batch write-delete request-response_

Batch write/delete shapes: Spec alternates between {"items":[...]} vs raw [...] for batch write and requires {"keys":[{pk,sk?},...]} for batch delete. Your tests appear to POST a raw list of ids to /{table}/delete. Align both code and tests to one documented request shape.

Batch-delete request. Your cleanup uses a plain list of ids; spec requires {"keys":[{pk,sk?},...]}. Update test to post {"keys":[{"job_id": "..."}]} or update the API to tolerate both.

Create/Put/Delete response shape. Tests should assert the same response envelope the spec declares (see §2 above), not "status": 1.

Batch-delete request shape tolerance:
Accept either {"keys":[...]} or [...] (ids) to ease migration, but document the canonical shape (recommend {"keys":[...]}).

_14 (open) BUG search query params_

Search query params. Spec defines index, limit, next, pk, sk, eq[field], begins[field]. Ensure the router feeds these into expression builders and uses base64 next.

Search behavior. Tests don’t appear to cover: index, limit, next (base64), eq[...], begins[...], or GSI flows. Add these per the spec.

_15 (open) BUG settings keys mismatch_

Settings keys. Your `config/settings.json` uses payload_max_bytes; spec shows max_body_kb, max_batch, etc. Align naming and enforcement.

_16 (open) BUG tests error mapping_

Error mapping. Add tests that assert 400/401/403/404/409/413/429/500 mappings with the standardized error envelope.

__Coding style, parameterization and design patterns__

_17 (open) ENHANCEMENT consolidated response build_

Consistent envelopes. Centralize response building in `core/responses.py` so all success/error shapes are uniform and tested (health, version, CRUD results).

_18 (open) ENHANCEMENT logging format_

Logging correlation. Extend core/logging.Log emissions to always include request_id, method, path, route, table, op, status, duration_ms, stage, version as per spec. (Router can supply context.)

_18 (open) ENHANCEMENT auth placeholder_

Auth/Policies. Even if default is VPC-only, keep the pluggable strategy (none, key, jwt) ready and wire policy denies (DELETE, batch-delete) in prod.

__Test coverage__
tests cases to add

| id | status | type | test | description |
| - | - | - | - | - |
| 01 | open | core/engine | S3 load success/fallback | reload() rebuilds tables; env var matrix (new+legacy names). |
| 02 | open | core/table | happy-path CRUD | conditional write conflict → 409, batch partial-failure list, search expression building (pk/sk + filters). |
| 03 | open | core/router | route matching: method-path | malformed JSON → 400; policy deny in prod (DELETE & batch-delete). |
| 04 | open | core/router | Integration local handler | Use synthetic APIGW events to verify headers, envelopes, pagination token round-trip. |
| 05 | open | core/router | End to end within VPC | Full CRUD, GSI search, pagination across >1 page, rate-limit behavior (429), and policy differences between envs. |
| 06 | open | edge | Empty/unknown attributes | Empty/unknown attributes (strip or allow?), max body/array sizes, missing PK, wrong types, unknown table, forbidden in prod, bad next token, Content-Type not application/json. |
