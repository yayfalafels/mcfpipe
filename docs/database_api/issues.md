# DB API: Issues

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
| 20 | closed | BUG | logging to CW log | lambda not resolve correct image digest from image tag |
| 21 | closed | BUG | lambda import error | Dockerfile copy jobdb dir |
| 22 | closed | BUG | admin table route clash | namespace table methods `/table` |
| 23 | closed | BUG | skip validation auto assigned fields | |
| 24 | closed | BUG | s3_schema_load_failed | set db schema variables in GHA |
| 25 | closed | BUG | delete key fail | Github issue BUG [DynamoDB requires sort key #17](https://github.com/yayfalafels/mcfpipe/issues/17) |
| 27 | closed | BUG | defeated logging | set logger by name |
| 28 | open | BUG | GET table item Decimal is not JSON serializable |  |
| 26 | open | ENHANCEMENT | DynamoDB batch catch errors per item | Github issue [DB API DynamoDB batch delete catch errors per item and retry with backoff #16](https://github.com/yayfalafels/mcfpipe/issues/16)  |
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

_20 (closed) BUG logging to CW log_

unable to find CW logs for event handling

**diagnostics**

observations

- cannot see any logging or `print()` from lambda runtime
- can see lambda invoke START / STOP

X (ruled out) possible cause 01: API deployment version mismatch with Lambda

validation failed --> did not resolve the logging issue

resolution

add `${RestApi}` to the SourceArn in the CF logical resource `DbLambdaInvokeFromApiGw`

```
SourceArn: !Sub arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${RestApi}/*/*/*
```

location: `aws/cloudformation/db_api_stack.yaml`

```yaml
  # Let API Gateway invoke the Lambda for any stage/method/path
  DbLambdaInvokeFromApiGw:
    Type: AWS::Lambda::Permission
    Properties:
      Action: lambda:InvokeFunction
      FunctionName: !Ref DbLambda
      Principal: apigateway.amazonaws.com
      SourceArn: !Sub arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${RestApi}/*/*/*

```

root cause (closed) possible cause 02: Lambda pointing to wrong image

from the ECR list, for latest image "6286dfd" last pull date shows blank

from the Lambda console, it shows

image URI `339953771490.dkr.ecr.ap-southeast-1.amazonaws.com/mcfpipe-dbapi:6286dfd` 

Resolved Image URI `339953771490.dkr.ecr.ap-southeast-1.amazonaws.com/mcfpipe-dbapi@sha256:8828308fb75011ce096f2a344fd3ee5dcf1f66bcc28a1a9071e62bc0c5b83e98`

The latest published image is 

URI `339953771490.dkr.ecr.ap-southeast-1.amazonaws.com/mcfpipe-dbapi:6286dfd`
digest `sha256:e999332cefd3b9e92b1b5e0aa9d9e40558d2e61d0de3b614cd978c70785bc22f`
tag `6286dfd`

resolution:

pass `DIGEST_URI` with the full `@sha...` digest reference to CF stack deploy instead of `IMAGE_URI` which uses the tag

```yaml
- name: Push image to ECR
id: docker_image_ecr
if: steps.app_dir_change.outputs.app == 'true' || inputs.force_rebuild == true
run: |
    docker push "$IMAGE_URI"
    DIGEST=$(aws ecr describe-images \
    --repository-name "$REPO_NAME" \
    --image-ids imageTag="$IMAGE_TAG" \
    --query 'imageDetails[0].imageDigest' --output text)
    DIGEST_URI="${IMAGE_REPO}@${DIGEST}"
    echo "DIGEST_URI=$DIGEST_URI" >> $GITHUB_ENV
```

and for the case of no change detected

```yaml
      - name: Set image tags and ECR URI
        id: image_tag_name
        env:
          REBUILD: ${{ steps.decide.outputs.rebuild }}
        run: |
          set -euo pipefail
          SHORT_SHA="${GITHUB_SHA::7}"
          REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
          IMAGE_REPO="${REGISTRY}/${REPO_NAME}"

          if [[ "${REBUILD}" == "true" ]]; then
            IMAGE_TAG="sha-${SHORT_SHA}"
            IMAGE_URI="${IMAGE_REPO}:sha-${SHORT_SHA}"            
          else
            # Pull the most recently pushed TAGGED image (any tag)
            # If you only want sha-* tags, add a jq filter: select(.imageTags[]|test("^sha-"))
            IMAGE_TAG="$(aws ecr describe-images \
              --repository-name "${REPO_NAME}" \
              --filter tagStatus=TAGGED \
              --query 'reverse(sort_by(imageDetails,&imagePushedAt))[0].imageTags[0]' \
              --output text)"
            if [[ -z "${IMAGE_TAG}" || "${IMAGE_TAG}" == "None" ]]; then
              echo "No tagged images found in ECR for ${REPO_NAME}" >&2
              exit 1
            fi
            IMAGE_URI="${IMAGE_REPO}:${IMAGE_TAG}"
            DIGEST=$(aws ecr describe-images \
              --repository-name "$REPO_NAME" \
              --image-ids imageTag="$IMAGE_TAG" \
              --query 'imageDetails[0].imageDigest' --output text)
            DIGEST_URI="${IMAGE_REPO}@${DIGEST}"
            echo "DIGEST_URI=$DIGEST_URI" >> $GITHUB_ENV
            fi

          echo "IMAGE_URI=${IMAGE_URI}" | tee -a "$GITHUB_OUTPUT"
          {
            echo "IMAGE_REPO=${IMAGE_REPO}"
            echo "IMAGE_TAG=${IMAGE_TAG}"
            echo "IMAGE_URI=${IMAGE_URI}"
           } >> "$GITHUB_ENV" 

```

CF stack deploy

```bash
aws cloudformation deploy \
--template-file $CF_TEMPLATE_DIR/$STACK_TEMPLATE_FILE \
--stack-name $STACK_NAME \
--capabilities CAPABILITY_NAMED_IAM \
--no-fail-on-empty-changeset \
--parameter-overrides \
    VpcId=$VPC_ID \
    PrivateSubnetIds=$PRIVATE_SUBNET \
    DBLambdaSG=$SG_PRIVATE \
    S3Bucket=$S3_BUCKET \
    LambdaImageUri=$DIGEST_URI \
```

_21 (closed) BUG lambda import error_

after some revisions in issue 20, now lambda pointing to the latest image digest
now lambda is throwing exception fail to import handler module

```
2025-09-08T06:02:55.221Z
[WARNING] 2025-09-08T06:02:55.220Z LAMBDA_WARNING: Unhandled exception. The most likely cause is an issue in the function code. However, in rare cases, a Lambda runtime update can cause unexpected function behavior. For functions using managed runtimes, runtime updates can be triggered by a function change, or can be applied automatically. To determine if the runtime has been updated, check the runtime version in the INIT_START log entry. If this error correlates with a change in the runtime version, you may be able to mitigate this error by temporarily rolling back to the previous runtime version. For more information, see https://docs.aws.amazon.com/lambda/latest/dg/runtimes-update.html
2025-09-08T06:02:55.221Z
[ERROR] Runtime.ImportModuleError: Unable to import module 'handler': attempted relative import with no known parent package
Traceback (most recent call last):

```

diagnostics

01 cause: Lambda image wrong dir 

```Dockerfile
COPY . .
```
update to : 

correct dockerfile

```Dockerfile
WORKDIR /var/task
...
COPY . /var/task
```

_22 (closed) admin table route clash_

for the route GET "__admin/health" `__admin` is interpreted as a a table logical `{table}`="__admin"

resolution 01: namespace the table methods `/table/{table}/*`

_23 (closed) skip validation auto assigned fields_

`validator.Validator.check_items` fails validation for non-nullable auto assigned fields such as ['id', 'created', 'last_updated'].
Although yes they are non-nullable, they are auto-assigned so should not be passed in by user for create.
solution is to add properties to these columns in the spec `auto` and `readonly`.
If either of these are true -> then they should NOT be passed by user.

_24 (closed) BUG s3 schema load failed_

_diagnostics_

```
"An error occurred (NoSuchKey) when calling the GetObject operation: The specified key does not exist."

bucket: "mcfpipe"
key: "/"

```

--> variables not set 

 - STORAGE_S3_DIR
 - DB_SCHEMA_JSON

_resolution_

set variables

```yaml
STORAGE_S3_DIR: storage
DB_SCHEMA_JSON: db_schema.json
```

fails at this line in step "Deploy CloudFormation Stack"

```bash
DBSchemaS3=$STORAGE_S3_DIR/$DB_SCHEMA_JSON
```

location: `.github/workflows/db_api_gha.yml`

```yaml
  - name: Deploy CloudFormation Stack
    id: stack_deploy
```

```bash
aws cloudformation deploy \
  --template-file $CF_TEMPLATE_DIR/$STACK_TEMPLATE_FILE \
  --stack-name $STACK_NAME \
    ...
    DBSchemaS3=$STORAGE_S3_DIR/$DB_SCHEMA_JSON \
    ...

```

_25 (closed) BUG delete key fail_
Github issue BUG [DynamoDB requires sort key #17](https://github.com/yayfalafels/mcfpipe/issues/17) 

```
[ERROR] ClientError: An error occurred (ValidationException) when calling the BatchWriteItem operation: The provided key element does not match the schema
Traceback (most recent call last):
```

diagnostics

DynamoDB requires sort key for get put delete operations. Documentation is consistent with the implementation and mentions to include the URL parameter for the sort key `{id}?<sort_key>=sort_key_value` but the test methods did not include the sort key.

- **get**: `GET /table/{table}/{id}?<sort_key>=sort_key_value`
- **delete**: `DELETE /table/{table}/{id}?<sort_key>=sort_key_value`
- **batch delete**: `POST /table/{table}/delete body={"id": <pk value>, "<sort_key>":sort_key_value}`

resolution: update the test methods to include the the sort key as URL parameter or key in batch operations

_26 (open) ENHANCEMENT DynamoDB batch catch errors per item_
Github issue [DB API DynamoDB batch delete catch errors per item and retry with backoff #16](https://github.com/yayfalafels/mcfpipe/issues/16) 

`boto3.DynamoDB.Table.batch_writer()` only buffers writes and then sends them to DynamoDB in 25-item chunks. `try/except` around `bw.delete_item(...)` won’t catch item-specific failures because the actual API call (and any exception) happens later during `__exit__/_flush()`. The batch writer will also auto-retry `UnprocessedItems`, so by design it doesn’t expose per-item failures.

suggestion from ChatGPT

for item-by-item results, don’t use `batch_writer`. Use the low-level `client.batch_write_item`, inspect `UnprocessedItems`, retry with backoff, and record anything that still fails. For malformed requests that trigger a `ValidationException` for the whole batch, you can “bisect” the batch to pinpoint the bad item.

_27 (closed) BUG defeated logging_
defeated logging in prior commits

_diagnostics_
believe cause due to inconsistent logger initiation

location: `router.py`

```python
import logging
log = logging.getLogger()
```

location: `logging.py`

```python
import logging
logger_name = '<something other than root>'
log = logging.getLogger(logger_name)
```

_resolution_
use consistent logger reference

```python
from . import logging

log = logging.logging.getLogger(logging.LOGGER_NAME)

```

_28 (open) BUG table item update Decimal is not JSON serializable_

exception

```
[ERROR] TypeError: Object of type Decimal is not JSON serializable 
```

_diagnostics_
DynamoDB uses types that are not JSON serializable. specifically: `Decimal`

_resolution_

- add a utility function  `json_serializable` to convert native DynamoDB dict to JSON serializable
- use the utility function in `Table` methods to convert to JSON serializable format

location: `jobdb/jobdb/core/table.py`

```python
from .util import json_serializable
...

    # CRUD ------------------------------------------------------------------
    def get(self, id_val: Any, sk_val: Any | None = None) -> Dict[str, Any] | None:

        if not self.sk:
            resp = self._dynamo().get_item(Key={self.pk: id_val})
            item_dict = resp.get('Item')
            return json_serializable(item_dict)

    ...

```

location: `jobdb/jobdb/core/util.py`

```python
import decimal
 ...

def json_serializable(obj):
    if isinstance(obj, decimal.Decimal):
        # int if safe, else float
        return int(obj) if obj % 1 == 0 else float(obj)
    elif isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, bytes):
        return base64.b64encode(obj).decode('utf-8')
    elif isinstance(obj, dict):
        return {k: json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [json_serializable(v) for v in obj]
    else:
        return obj

```

_diagnostics details_

full traceback

```
[ERROR] TypeError: Object of type Decimal is not JSON serializable
Traceback (most recent call last):
  File "/var/task/handler.py", line 98, in lambda_handler
    return _ROUTER.dispatch({"httpMethod": method, "path": path, **event}, context)
  File "/var/task/jobdb/core/router.py", line 384, in dispatch
    return self._table_crud(
  File "/var/task/jobdb/core/router.py", line 281, in _table_crud
    resp = self.responses.json(200, payload)
  File "/var/task/jobdb/core/responses.py", line 18, in json_resp
    'body': json.dumps(body, separators=(',', ':'), ensure_ascii=False),
  File "/var/lang/lib/python3.12/json/__init__.py", line 238, in dumps
    **kw).encode(obj)
  File "/var/lang/lib/python3.12/json/encoder.py", line 200, in encode
    chunks = self.iterencode(o, _one_shot=True)
  File "/var/lang/lib/python3.12/json/encoder.py", line 258, in iterencode
    return _iterencode(o, 0)
  File "/var/lang/lib/python3.12/json/encoder.py", line 180, in default
    raise TypeError(f'Object of type {o.__class__.__name__} '

```

location: `jobdb/jobdb/core/table.py`
method: `Table.get`

```python
    # CRUD ------------------------------------------------------------------
    def get(self, id_val: Any, sk_val: Any | None = None) -> Dict[str, Any] | None:

        if not self.sk:
            resp = self._dynamo().get_item(Key={self.pk: id_val})
            return resp.get('Item')

        elif sk_val is None:
            # Without sort key, attempt to query by id and return first
            q = self._dynamo().query(KeyConditionExpression=Key(self.pk).eq(id_val), Limit=1)
            items = q.get('Items', [])
            return items[0] if items else None

        resp = self._dynamo().get_item(Key={self.pk: id_val, self.sk: sk_val})
        return resp.get('Item')

```

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