# Database API

release documentation `docs/releases/011_dbapi.md`

## Session Logs

session logs are timestamped to Singapore timezone in reverse chronological order, with latest entries at the top, and earlier entries at the bottom.

### JobDB API [Developer] issues 2025-09-11 <>:<>


### JobDB API [Developer] issue docker image dir 2025-09-11 16:25
issue: container image dir not able to import `handler.py`
correct dockerfile

```Dockerfile
WORKDIR /var/task
...
COPY . /var/task
```

### JobDB API [Developer] issues 2025-09-10 20:15

__documentation__

- user docs `docs/database_api/user.md`
- list routes and error codes

__issues__

- **22 (closed) admin table namespace clash**:
  - for the route GET "__admin/health" `__admin` is interpreted as a a table logical `{table}`="__admin"
  - resolution 01: namespace the table methods `/table/{table}/*`

### JobDB API [Developer] issue logging to CW logs 2025-09-08 15:03
issue: logging to CW log
found multiple issues

  - **01 (root cause) wrong URI image mapping**:
    - wrong mapping docker image URI to Lambda function
    - resolution: use full digest `@sha...` instead of the shorthand tag
  - **02 API deployment version mismatch with Lambda**: 
    - resolution: add `${RestApi}` to the SourceArn in the CF logical resource `DbLambdaInvokeFromApiGw`

### JobDB API [Codex] 2025-09-07 17:55:48
- added debug print before bootstrap in `jobdb/handler.py`
- ran tests

### JobDB API [Developer] issue logging 2025-09-07 16:30:00
force reset logging handler
- remove the `if not root.handlers:` and replace with a forced reset

location: `jobdb/jobdb/core/logging.py`

```python
def init_logging(level: str, service: str, stage: str, version: str):
    root = logging.getLogger()

    for h in list(root.handlers):
        root.removeHandler(h)
    root.handlers.clear()

    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root.addHandler(h)

```

### JobDB API [Developer] 2025-09-07 15:38:00
jobdb codex review

__validation__

- **default route `/`**:
  - created local validation script `testscript_jobdb.py`
  - ran unit test on ECS container

__review__

- **review**:reviewed Codex implementation, summarized issues `docs/database_api/issues.md`
- **logging**: refactored `handle.py` and `router.py` to consolidate  to `router.Router` class
  - use python `logging` package instead of custom `Log` class

### JobDB API [Codex] 2025-09-04 16:42:04
Implemented config-driven jobdb API per design.

- Core: added `jobdb/core/{engine,router,table,validators,expressions,responses,logging,util}.py`
- Domain: added stubs `jobdb/domain/{hooks,search_maps,policies,auth}.py`
- Config: added `jobdb/config/{routes.json,settings.json,policies.json,schema_map.json}`
- Schemas: added fallback `jobdb/schemas/db_schema.json` (S3 primary remains authoritative)
- Handler: wired router/engine in `jobdb/handler.py` with root, health, CRUD, batch, search, admin-refresh
- Version: bumped `jobdb/VERSION` to `0.1.1`

Notes:
- Physical table naming derived as `<stage>_<prefix>_<table>` (e.g., `prod_mcfpipe_job`); env var `DDB_TABLE_PREFIX` overrides prefix (default `mcfpipe`).
- Validation: basic required/type checks from schema; allow extra attributes for now.
- Search: supports `index`, `limit`, `pk/sk` equality, otherwise limited scan (internal use only).
- Error model: standardized JSON envelope; logs are single-line structured.

### high costs VPCE [Developer] 2025-09-04 13:19
__tester run in public subnet__

Network stack
 - remove 3x unused VPCE

DB API GHA
 - location: `.github/workflows/db_api_gha.yml`
 - pass public subnet and SG HTTP to ECS task run script 

ECS task run script
 - location: `tester/tester_task_execute.sh`
 - set default value `ASSIGN_PUBLIC_IP`=ENABLED

### high costs VPCE [Developer] 2025-09-02 17:10
__tester run in public subnet__

tester stack
 - location: `aws/cloudformation/tester_stack.yaml` 
 - remove references to VPC information

tester GHA
 - location: `.github/workflows/tester_gha.yml` 
 - remove the network config lookup step
 - pass parameters for tests bucket and dir to CF stack deploy

### high costs VPCE [Developer] issue diagnostics 2025-09-02 16:45
Github issue [duplicate VPCE costs tester private subnet #15](https://github.com/yayfalafels/mcfpipe/issues/15)
type: `ENHANCEMENT`

- **cost explorer**: found monthly costs high $40.55 SGD for Aug 2025
- **diagnostics** found cause from 4x VPCE
  - may only need 1x for API Gateway endpoint, 
  - rest 3x for tester ECR API, ECR DKR and CW Logs not needed 
- **resolution**: run tester in **public** subnet

### GHA conditional refresh [Developer] jobdb conditional refresh 2025-09-01 18:29
__jobdb conditional refresh__

_requirements_
only rebuild the DB API container image on changes to jobdb source code `jobdb/*`
skip on other changes; GHA, CF stack template, etc..

_implementation_

| id | status | task | description |
| - | - | - | - |
| 01 | closed | detect file changes `jobdb/*` | use path filter action `dorny/paths-filter@v3` to set a variable `app_changed` |
| 02 | closed | add manual image refresh | add `workflow_dispatch` input `force_rebuild` |
| 03 | closed | add conditional logic to image tasks  | use variables `app_changed` and `force_rebuild`, steps: docker image build/publish, ECR login |

_validation issues_

_(closed) issue 01: diff ref for same-branch commits and PR_
the reference for diff is different for same-branch commits vs pull requests
the initial implementation for `dorny/paths-filter@v3` is for PR and detects all changes relative to `main`

the desired behavior is to conditionally change the ref

- pull requests: `main`
- same branch commits: `HEAD^` vs `HEAD`

implementation uses a support bash script `.github/scripts/diff_detect.sh`

_(closed) issue 02: always pull the latest URI image

situation: the current behavior sets the `IMAGE_URI` from the current branch SHA, 
however, when the image rebuild is skipped, then this resolves to an invalid `IMAGE_URI`
instead, it should pull from the most recent valid `IMAGE_URI`


### GHA conditional refresh [Developer] tester conditional refresh 2025-09-01 14:55
__tester conditional refresh__

_requirements_
only rebuild the tester image on changes to tester source code `tester/*`
skip on other changes; CF stack template, etc..

_implementation_

| id | status | task | description |
| - | - | - | - |
| 01 | closed | detect file changes `tester/*` | use path filter action `dorny/paths-filter@v3` to set a variable `tester_changed` |
| 02 | closed | add manual image refresh | add `workflow_dispatch` input `force_rebuild` |
| 03 | closed | add conditional logic to image tasks  | use variables `tester_changed` and `force_rebuild`, steps: docker image build/publish, ECR login |

_validation issues_
- reference correct step name
- treat filter output value as string, not bool

### tester decoupled [Developer] GHA upload tests to S3 validate 2025-09-01 13:08
validate: DB API GHA upload tests to S3

_issues_

 - (closed): task failed to execute
  - location: `tester/tester_task_execute.sh`
  - exact cause unknown, most likely due to typo wrong argument spelling for `AWS_REGION`
 - (closed): task exception: reference before assignment 'e'
  - location: `tester/import.py`    `logger.info(f'Ensured directory exists: {d}. {e} ')`
  - remove the `{e}` default behavior in try-except is to include exception so this is redundant

### tester decoupled [Developer] GHA upload tests to S3 2025-08-31 20:25
_DB API GHA: upload tests to S3_

- GHA DB API declare additional env variables

- **TESTS_UPLOAD_SCRIPT**: `tester/tests_upload_to_s3.sh`
- **TESTER_TASK_SCRIPT**: `tester/tester_task_execute.sh`
- **TESTER_S3_PREFIX**: `apps/tests/jobdb`
- **PYTEST_ARGS**: `-q`

- GHA DB API upload tests to S3
 - location: `.github/workflows/db_api_gha.yml`
 - add env variables `TESTS_UPLOAD_SCRIPT`, `TESTER_S3_PREFIX`
 - call S3 upload script

- S3 upload script
 - location: `tester/tests_upload_to_s3.sh`
 - uploads flexibly either as *.zip or single file
 - uploads to common `apps/tests` S3 dir to simplify task execution and S3 permissions

- tester task execute script additional args S3 to ECS task run 
 - location: `tester/tester_task_execute.sh`
 - additional args: `S3_BUCKET`, `TESTS_S3_DIR`, `LOGGING_LEVEL`, `PYTEST_ARGS`
 - GHA pass tests S3 args to ECS task execute via execute script

### tester decoupled [Developer] tester import script 2025-08-28 18:18
_tester import script_

- import and run bash script
  - location: `tester/import_run_tests.sh`
- Dockerfile change entrypoint to import and run script
- ECS Task IAM role: Grant s3:GetObject on the tests prefix
  - location: `aws/cloudformation/tester_stack.yaml`

### tester decoupled [Developer] tester import script 2025-08-27 16:00
_tester import script_

Import unit tests from S3 into local test runner
- location: `tester/import.py`

### tester decoupled [Developer] separate storage and compute stacks 2025-08-21 18:03
Github issue [GHA and CF conditional refresh #14](https://github.com/yayfalafels/mcfpipe/issues/14)
type: `ENHANCEMENT`

| id | status | enhancement |
| - | - | - |
| 01 | closed | CF separate DB storage resources from Gateway API + Lambda |
| 02 | open | decouple tests to run from tester generic compute |
| 03 | open | GHA tester image conditional refresh |
| 04 | open | GHA jobdb image conditional refresh |

_(closed) CF separate DB storage resources from Gateway API + Lambda_

- **db stack**: isolated stack to only the DynamoDB tables generated from DB Schema JSON
- **db api stack**: dropped the DynamoDB tables
  - dropped StageDescription property, caused Stack Fail
  - attached Resource policy -- turns out it is required

_(open) decouple tests to run from tester generic compute_

- listed changes to make

changes

| id | location | change |
| - | - | - |
| 01 | `tester/*` | add a script to import the tests from S3 as file or zip |
| 02 | `tester_task_execute.sh` | pass the S3 location to and call the S3 import script |
| 03 | `tester/requirements.txt` | add `boto3` dependency |
| 04 | ECS task role | Grant the task role s3:GetObject on the tests prefix |
| 05 | DB API GHA `.github/workflows/db_api_gha.yml` | upload tests.py, or zip `tests/*` to S3 |


### DB API [Developer] app design 2025-08-20 16:15
detailed design `docs/database_api/detailed_design.md`
- format from ChatGPT response

### Issue API Forbidden [Developer] diagnostics and resolution 2025-08-19 18:30
Issue [test 00 basic route fail 400 Forbidden #13](https://github.com/yayfalafels/mcfpipe/issues/13) 
RESOLVED

found cause from two issues

01. VPCE not attached to the API
02. API not re-deployed: [Stack Overflow: getting message forbidden reply from aws api gateway](https://stackoverflow.com/questions/40988051/getting-message-forbidden-reply-from-aws-api-gateway)

01. explicitly attach VPCE to the RestApi resource

```yaml
  RestApi:
    Type: AWS::ApiGateway::RestApi
    Properties:
      Name: !Sub mcfpipe-dbapi-${StageName}
      EndpointConfiguration:
        Types: [PRIVATE]
        VpcEndpointIds:
          - !Ref ExecuteApiVpceId
```
02.  add a GHA step to ensure that a new deployment is created on each CF redeploy.

location: `.github/workflows/db_api_gha.yml`

```yaml
  - name: Force API Gateway Deployment
    id: api_deploy
    if: steps.stack_deploy.outcome == 'success'
    run: |
```


### DB API [Developer] validation 2025-08-18 18:30
db api stack validate

stuck at issue 10 400 Forbidden

__issues__

| id | status | type | issue | description |
| - | - | - | - | - |
| 05 | closed | BUG | [API IAM CW log #8](https://github.com/yayfalafels/mcfpipe/issues/8) | API does not have IAM role to read/write to CW log group |
| 06 | closed | BUG | [CF API log format #9](https://github.com/yayfalafels/mcfpipe/issues/9) | YAML line break fold `>-` not working as expected |
| 07 | closed | BUG | [DB_API_URL not passed #10](https://github.com/yayfalafels/mcfpipe/issues/10) | GHA parameter `DB_API_URL` not passed from stack outputs |
| 08 | closed | BUG | [ECS run container name conflict #11](https://github.com/yayfalafels/mcfpipe/issues/11) | container name conflict btw CF template and GHA env variable |
| 09 | closed | BUG | [tester container script failures #12](https://github.com/yayfalafels/mcfpipe/issues/12) | missing IAM `AmazonECSTaskExecutionRolePolicy` on the `TesterExecutionRole` |
| 10 | open | BUG | [test 00 basic route fail 400 Forbidden #13](https://github.com/yayfalafels/mcfpipe/issues/13) | test 00 basic route failed 400 Forbidden |


### DB API [Developer] documentation 2025-08-18 13:56
release documentation updates

- db api `docs/database_api.md`
  - compute resources API Gateway, ECR image
- cicd `docs/cicd.md`
  - tester design
- release `docs/releases/011_dbapi.md`
  - tester design
  - CF stack deploy - idempotent, failure diagnostics, parameters export
  - issues - open issue 6 ECR cleanup, 7 ECR refresh, validation tasks

### DB API [Developer] 2025-08-16 15:42
tester and DB API stack switch Lambda to container URI

__next__
validate DB API stack

__follow-up issues__

 - issue ECR cleanup [#6](https://github.com/yayfalafels/mcfpipe/issues/6) created
  - add GHA or ECR policy to periodically cleanup old images to avoid excess storage charges

__completed__

- switch to docker image for DB API Lambda
- tester stack validated

__files worked on__

| id | file | path | description |
| - | - | - | - |
| 01 | Dockerfile | `jobdb/Dockerfile` | Dockerfile for the `jobdb` Lambda container image |
| 02 | db api stack | `aws/cloudformation/db_api_base.yaml` | CF template update Lambda resource source code from container URI instead of zip |
| 03 | db api GHA | `.github/workflows/db_api_gha.yml` | GHA to create the docker image, register in ECR and pass URI to CF stack deploy |

### DB API [Developer] basic route 2025-08-15 20:05
add a basic route `/` that returns DB API about and version info

handler python code `tester/handler.py`

### Tester [Developer] docker image 2025-08-15 19:39
build tester docker image locally

!Docker desktop must be running

```bash
cd tester
docker build -t mcfpipe-tester:local .
```
run the container with dummy endpoint "http://127.0.0.1:8000/"
alternate can use "https://fake-json-api.mock.beeceptor.com/users"

```bash
docker run --rm   -e DB_API_URL="http://127.0.0.1:8000/"   mcfpipe-tester:local
```

temporarily skip main API unit tests 1-N using `@unittest.skip()`
leave only basic endpoint test `test_00_*`

result: expected: 1 passed, 13 skipped

```bash
$ docker run --rm -e DB_API_URL=$FAKE_URL $CONTAINER_NAME:local
.sssssssssssss                                                           [100%]
1 passed, 13 skipped in 2.90s
```

```python
    def test_00_endpoint_valid(self):
        response = requests.get(f"{BASE_URL}")
        self.assertEqual(response.status_code, 200, f'expected status code 200, got {response.status_code}. {response.text}')

    @unittest.skip("TEMPORARY SKIP TEST")
    def test_01_post_valid(self):
        """POST Create new job (positive)"""
        payload = self.__class__.test_record.copy()

```

### Tester [Developer] GHA workflow 2025-08-15 16:33
tester build deploy and run task

__next__

1. local docker image build 
2. **basic route**: add a basic route `/` to return basic api version info
  - jobdb handler: update with basic non-empty lambda payload with handler outline and functionality for the basic route
  - test case: add a test case to handle the basic route `/` and return passed. Silence the other tests temporarily

__files worked on__

| id | file | path | description |
| - | - | - | - |
| 01 | GHA build image and deploy | `.github/workflows/tester_gha.yml` | build and register image, pass URI with deploy |
| 02 | tester stack | `aws/cloudformation/tester_stack.yaml` | CF template define cluster, task, IAM, attach SG, takes URI input |
| 03 | Dockerfile | `tester/Dockerfile` | Dockerfile for ECS task |
| 04 | ECS task run |`tester/tester_task_execute.sh` | bash script to run ECS task and show CW logs on failure |
| 05 | DB API GHA | `.github/workflows/db_api_gha.yml` | run ECS task from bash script |

### Tester [Developer] GHA workflow 2025-08-15 12:24
tester GHA `.github/workflows/tester_gha.yml`

- draft outline copy from other GHA YAML scripts

### Tester [Developer] 2025-08-14 16:58

cf stack `aws/cloudformation/tester_stack.yaml`
 - documentation updates
 - GHA steps and artifacts define

__network configuration__
review networking configuration to ensure tester container can reach DB API endpoint
- migrate the network config JSON export to a bash script

### Tester [Data Engineer] 2025-08-13 17:00
cf stack `aws/cloudformation/tester_stack.yaml`
 - minimal stack 

__network configuration__
review networking configuration to ensure tester container can reach DB API endpoint

- update network stack `aws/cloudformation/networking_stack.yaml`
  - add VPC Endpoint for Execute API for the API Gateway

### CF stack deploy [Data Engineer] idempotent deploy 2025-08-12 22:09

__follow-up__

**intermediate milestone**: TDD closed-loop build-test with the DB API
- **01 hello world** jobdb app + lambda handler, just enough to have an EP to send to tester
- **02 tester app** stack ready with test cases
- then loop back to `jobdb` now ready with full TDD closed-loop

_(closed) CFN stack deploy fail diagnostics to GHA runner_

- validated
- create a diagnostics bash extraction script `aws/cloudformation/cf_stack_diagnostics.sh`
- run this script from a GHA step

__control flow__

- set `continue-on-error`=true for the deploy step
- fail the job after completing the diagnostics print-out step, so that the remaining steps skip

```yaml
      - name: Deploy CloudFormation Stack
        id: stack_deploy
        continue-on-error: true
        ...

      - name: CFN failure diagnostics
        id: stack_fail_diagnostics
        if: steps.stack_deploy.outcome == 'failure'
        run: |
          bash $STACK_FAIL_DIAGNOSTICS_SCRIPT "$STACK_NAME" "$AWS_REGION" --nested
          echo "DB API deploy failed"
          exit 1
```

__GAH runner logs__

```
|                                                                                                                                                                                     DescribeStackEvents                                                                                                                                                                                     |
+----------------------------------+-----------------------------+----------------+-----------------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
|  2025-08-12T13:48:44.026000+00:00|  AWS::CloudFormation::Stack |  mcfpipe-dbapi |  ROLLBACK_COMPLETE    |  None                                                                                                                                                                                                                                                                             |
|  2025-08-12T13:48:18.754000+00:00|  AWS::CloudFormation::Stack |  mcfpipe-dbapi |  ROLLBACK_IN_PROGRESS |  The following resource(s) failed to create: [UserTable, DbLambda]. Rollback requested by user.                                                                                                                                                                                   |
|  2025-08-12T13:48:18.360000+00:00|  AWS::DynamoDB::Table       |  UserTable     |  CREATE_FAILED        |  Resource creation cancelled                                                                                                                                                                                                                                                      |
|  2025-08-12T13:48:17.935000+00:00|  AWS::Lambda::Function      |  DbLambda      |  CREATE_FAILED        |  Resource handler returned message: "Uploaded file must be a non-empty zip (Service: Lambda, Status Code: 400, Request ID: f7d54580-6977-476e-942b-369788c79d31) (SDK Attempt Count: 1)" (RequestToken: f9ec6ddb-7cdd-04e2-fe47-e4d4d0eefd78, HandlerErrorCode: InvalidRequest)   |

```

_(resolved) 02 idempotent deploy_

GHA fails if a previous stack deploy failed --> stack is in `ROLLBACK_COMPLETE` or `CREATE_FAILED` status

**solution**: add a pre-flight check before deploy to check status [`ROLLBACK_COMPLETE`, `CREATE_FAILED`]

```bash
STATE=$(aws cloudformation describe-stacks --stack-name "$STACK" \
  --query 'Stacks[0].StackStatus' --output text 2>/dev/null || true)

if [[ "$ALLOW_STACK_DELETE" == "true" ]] && [[ "$STATE" =~ ^(ROLLBACK_COMPLETE|CREATE_FAILED)$ ]]; then
  aws cloudformation delete-stack --stack-name "$STACK"
  aws cloudformation wait stack-delete-complete --stack-name "$STACK"
fi

# Safe repeatable deploy
aws cloudformation deploy \
  --stack-name "$STACK" \
  --template-file "$TEMPLATE" \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset

```

[ChatGPT] suggestion

 ```
Short answer: do it up front.

Pre-flight cleanup at the start of the deploy is safer and more deterministic:
If a previous create failed, the stack will be ROLLBACK_COMPLETE and can’t be updated. Deleting it before deploy avoids an immediate re-fail.
It keeps the main deploy path idempotent and avoids branching logic after a failure.
You can still make the step a no-op for healthy stacks (UPDATE_COMPLETE, CREATE_COMPLETE).

What I recommend:

Pre-check at the beginning

If status is ROLLBACK_COMPLETE or CREATE_FAILED → delete-stack + wait stack-delete-complete, then proceed with deploy.
Otherwise just deploy --no-fail-on-empty-changeset.
Keep a post-failure aid, not auto-delete
If deploy fails, run a tiny “diagnose” step to dump recent stack events and the template validation error, but don’t auto-delete. You’ll want the stack artifacts for debugging.

Guardrails

Only auto-delete when an env flag is set (e.g., ALLOW_STACK_DELETE=true) so you don’t nuke prod by accident.
Consider not auto-deleting UPDATE_ROLLBACK_COMPLETE (that stack is still usable) unless you really need to recreate.
Net: pre-flight cleanup + post-failure diagnostics gives you fast green paths and good debuggability without surprise deletions.

 ```


### GSI and table prefix [Data Engineer] stack deploy validation 2025-08-12 17:33
triggered GHA, deployed stack, validated works as expected

### DDB YAML constructor [Data Engineer] DDB table namespace 2025-08-12 17:26

 --> validated works as expected

[Developer] ChatGPT prompt
>Regarding DynamoDB table namespace, can I organize DynamoDB tables by schema or database, in a similar manner as an SQL table <schema>.<table_name>? Or are table names global? Do I need to add a `mcfpipe_` prefix to all of the tables to prevent namespace clashes with other projects?

suggestion to pass argument `table_prefix` to function `generate_table_resource()`

```python
def generate_table_resource(table, table_prefix: str = ""):
    table_name = table["table_name"]
    logical_name = f"{to_cfn_logical_id(table_name)}Table"

    # ---- NEW: apply physical name prefix (if any)
    physical_table_name = f"{table_prefix}{table_name}" if table_prefix else table_name

```

updated CLI parser, suggestion by ChatGPT

```python
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate CF from DB schema")
    parser.add_argument("db_schema_path", nargs="?", default="db_schema.json")
    parser.add_argument("base_yaml_path", nargs="?", default="db_api_base.yaml")
    parser.add_argument("output_yaml_path", nargs="?", default="db_api_stack.yaml")
    parser.add_argument("--env", dest="dev_env", default="", help="Environment tag, e.g. dev, prod")
    parser.add_argument("--project", dest="project_prefix", default="", help="Project prefix, e.g. mcfpipe")
    args = parser.parse_args()

    # Build "<env>_<project>_" only from provided parts; keep underscores for DynamoDB
    parts = [p for p in [args.dev_env, args.project_prefix] if p]
    table_name_prefix = ("_".join(parts) + "_") if parts else ""

    print(
        "generating YAML file from\n"
        f"schema: {args.db_schema_path}\n"
        f"base CF template: {args.base_yaml_path}\n"
        f"writing to {args.output_yaml_path} ...\n"
        f"table name prefix: '{table_name_prefix}'"
    )

    run(args.db_schema_path, args.base_yaml_path, args.output_yaml_path, table_name_prefix)

```

update constructor call to include arguments `--env` and `--project`

```yaml
      # manual trigger
      - name: Generate CloudFormation template
        id: cf_template_generate
        run: |
          pip install -r $DBAPI_APP_DIR/requirements.txt >/dev/null
          python $DBAPI_APP_DIR/$TEMPLATE_CONSTRUCTOR \
            $STORAGE_S3_DIR/$DB_SCHEMA_JSON \
            $CF_TEMPLATE_DIR/$BASE_TEMPLATE_FILE \
            $CF_TEMPLATE_DIR/$STACK_TEMPLATE_FILE \
            --env $DEV_ENV \
            --project $PROJECT_NAME

```

add parameters `DEV_ENV` and `PROJECT_NAME` to config `setup/config.env`

```
DEV_ENV=prod
ROLE=Bridges
PROJECT_NAME=mcfpipe
```

### GSI [Data Engineer] update db schema and yaml 2025-08-12 16:56
validate changes and manually apply the suggested update for `generate_table_resource()` function in python constructor `jobdb/cf_template_constructor.py` which was proposed by ChatGPT.

### GSI [Codex] 2025-08-12 16:37:07
- reviewed `docs/data_model.md` and removed outdated sort key for `post_details`
- expanded `storage/db_schema.json` with table schemas and declared GSI per data model

### GSI [Data Engineer] Codex prompt 2025-08-12 16:31
prior to implementing the specific instructions in this prompt, first review generic instructions in `AGENTS.md`

__situation__

The current version of the data model does not specify Global Secondary Indexes (GSI) for DynamoDB tables. The methodology for specifying and implementing GSI is described in the Database API doc `docs/database_api.md`.  

GSI have been specified in the data model, but have not been implemented into the db schema JSON file.

__scope__

 - data model `docs/data_model.md`
 - db schema JSON `storage/db_schema.json`

__task__

 - udpate db schema JSON for table specifications (name, partition key, sort key, column definitions) from the data model
 - update db schema JSON with the GSI attributes `"secondary_indexes": {...}` according to the specifications in the data model

### GSI [Data Engineer] JSON 2025-08-12 16:25
GSI specification methodology documentation `docs/database_api.md`

- data model table section
- DB Schema JSON, add new attribute `"secondary_indexes": {...}`
- CF Template YAML DynamoDB table
- CF template Python script constructor mapping method

CF Template YAML DynamoDB table

```yaml
        - IndexName: gsi_user_id_company_name
          KeySchema:
            - AttributeName: user_id
              KeyType: HASH
            - AttributeName: company_name
              KeyType: RANGE
```

### Agent [Data Engineer] update generic agent instructions 2025-08-12 15:38
update generic AGENTS.md instructions
 - task instructions for Codex
 - session log 
 - context navigation

### GSI [Data Engineer] Data model 2025-08-12 15:19

__GSI implementation__

_01 data model_
table-by-table updates for several considerations

- GSI
  - add GSI for common search, filter operations
- second pass at schema design
  - rationalize columns, place columns where they will be used most frequently
  - relaxed normalized considerations, duplicate columns from post -> job table

post
- migrated common columns [`salary_high_sgd`, `closing_date`] into `post`
- added `description` in `post_details`

job_track
- added GSI for jobs by track

job
- duplicate columns from post [`closing_date`, `salary_high_sgd`, etc..] migrate from `job_details` into `job`
- GSI user reports and user sorted by company and position
- add `status` in `job_details`

### GSI [Data Engineer] ChatGPT 2025-08-11 18:58
guided session GSI and search design with ChatGPT

### Documentation [Data Engineer] ChatGPT review 2025-08-10 19:20

__Open for followup__

1. implementation for 06 GSI
2. open follow-ups left over from last session
  -  `jobdb` app development
3. clean stack deploy cleanup `ROLLBACK_COMPLETE` status

__Issues__

_(closed) 01 PK type rule vs a table_
[ChatGPT] 
>Doc says PKs should be String (“Global patterns”), but post_source.id is Number in both docs and schema. Pick one rule and unify. 

_(closed) 02 Private subnet description_
[ChatGPT] 
>Network doc row for PrivateSubnetId says it has “a route to the IGW” (internet gateway). Private subnets should not route to an IGW. You’re using VPC endpoints (no NAT), which is correct—so fix that line. 

updated to read "private subnet: private subnet with no allowed inbound traffic the internet"

_(closed) 03 CICD repo layout_
[ChatGPT] 
>CICD doc mentions a jobcrm/ backend folder that isn’t in the repo today; mark it TBD or remove to avoid confusion.

this is intentional that CICD doc shows some organization not yet implemented

_(closed) 04 Route coverage vs API config_
[ChatGPT] 
>Docs list /[table]/search and /[table]/delete. Make sure API Gateway includes an ANY /{proxy+} resource or explicit routes for these; otherwise the handler won’t see them. 

_follow-up clarification prompt(s)_

[Developer]
>For item 04 "04 Route coverage vs API config" I don't catch what you mean, `/[table]/search` is listed in the doc `docs/database_api.md` Could you elaborate and explain what kinds of operations would fail in the current design and how adding the `ANY /{proxy+}` would help? What are the security implications of adding this feature?

(summary of conversation with ChatGPT)

-> Design choice: accept the ANY/{proxy+} proposal and use API gateway as a thin wrapper,  leave most of the implementation to the main `jobdb` api app. 

Ultimately a design choice of using API gateway vs the Lambda handler (app) for many of the app features such as routing, validation, error handling. Ultimately, go with the suggestion to use API Gateway as a thin wrapper and leave most of the implementation to the main `jobdb` api app. Some considerations for this choice 

1. CF not as ideal choice, managing version control in multiple locations (app + CF)
2. It's a backend DB, not exposed to internet already in a private subnet so risk is lower.

update snippet to CF file `aws/cloudformation/db_api_base.yaml`

```yaml
  # ANY on root "/"
  RootAnyMethod:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref RestApi
      ResourceId: !GetAtt RestApi.RootResourceId
      HttpMethod: ANY
      AuthorizationType: !Ref ApiAuthType
      Integration:
        Type: AWS_PROXY
        IntegrationHttpMethod: POST
        Uri: !Sub arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${DbLambda.Arn}/invocations

  # Catch-all /{proxy+}
  ProxyResource:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref RestApi
      ParentId: !GetAtt RestApi.RootResourceId
      PathPart: "{proxy+}"

  ProxyAnyMethod:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref RestApi
      ResourceId: !Ref ProxyResource
      HttpMethod: ANY
      AuthorizationType: !Ref ApiAuthType
      Integration:
        Type: AWS_PROXY
        IntegrationHttpMethod: POST
        Uri: !Sub arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${DbLambda.Arn}/invocations

```

_(closed) 05 ID generation language_
[ChatGPT] 
>“Auto-incremented UUID is a running MAX” is contradictory; decide: sequential (MAX+1) or UUID/ULID. For DynamoDB, favor ULID/KSUID to avoid hot partitions and racey “MAX” scans. 

_follow-up clarification prompt(s)_

[Developer]
>for item 05 "ID generation language" The motivation for using MAX+1 is to ensure uniqueness even after a record is deleted from the table.  Explain what you mean by "racey MAX scans" and how UUID/ULID/KSUID is different from MAX+1, a description of methods and comparison for how these methods would handle uniqueness after record deletion 

[ChatGPT] 
(relevant snippet from full response)
>UUIDv4 (random), ULID, KSUID (time-sortable)
>Method: IDs are generated client-side.
>UUIDv4: 128-bit random.
>ULID: 128-bit, first 48 bits timestamp (ms) + 80 bits randomness; lexicographically sortable >by time.
>KSUID: 160-bit, 32-bit timestamp (s) + 128-bit payload; also time-sortable.
>Uniqueness after deletion: Unaffected. You never consult existing rows, so deletes don’t >matter; the chance of collision is astronomically small (UUIDv4) or practically negligible (ULID/KSUID).
>Concurrency/scale: Excellent. No shared state, no scans, no lock. Horizontal scale “for free.”
>Ordering:
>- UUIDv4: not ordered.
>- ULID/KSUID: roughly time-ordered (nice for pagination and range queries).
>Partition heat: Good—high cardinality distribution if you use the ID as the partition key.
>- multiple mature libs (ulid-py, python-ulid, ulid-transform) and good cross-language parity (Go, JS/TS, Rust, etc.). Monotonic ULID support is common.

[Developer] 
>are there any implementation considerations for ULID vs KSUID, are either one more native either in python, boto3 or AWS DynamoDB?

[ChatGPT] 
>- 128-bit: first 48 bits = milliseconds. 
>- Lexicographic sort == chronological (ms). 
>- Many libs support monotonic ULIDs, if you generate multiple in the same ms, the random tail is incremented so sort order stays strictly increasing within one process.
>- 26 chars, Crockford Base32, uppercase alphabet without ambiguous chars (no I, L, O, U). 
>- Regex: ^[0-9A-HJKMNP-TV-Z]{26}$. Case-insensitive by spec, but store as uppercase to preserve lexical ordering semantics everywhere.

Design decision: take suggestion and update to ULID, doc `docs/data_model.md` updated accordingly

_(open) 06 Search/indexing gap_
[ChatGPT]
>Docs offer /[table]/search, but there’s no doc section mapping access patterns to GSIs per table. Add a table-by-table list of keys/GSIs that support your queries.

[Developer] 
>could you elaborate more about 06 "mapping access patterns to GSIs per table" what do you mean, what is "GSI" and keys in this context. Where would you apply the updates? Could you describe some situations that would fail with the current design, and how it would be improved with the update you are proposing?

_synopsis of ChatGPT response_

GSI, "Global Secondary Index" are user-defined is regarding query design, how the queries and search are implemented from user queries by non-PK columns, ex by user or by date range.

_summary of updates_ 

data model doc `docs/data_model.md`

```md
**GSI naming convention (global pattern):** use `gsi_<partitionkey>_<sortkey>` (omit `_<sortkey>` if none). Index names are not repeated in the per-table sections below.
```

```md

__Global Secondary Indexes__

| id | Partition key | Sort key      | Projection | Purpose                    |
| - |---------------|---------------|------------|----------------------------|
| 01 | user_id (S)   | created (S)   | ALL        | Per-user timeline (newest) |
| 02 | post_id (S)   | id (S)        | ALL        | Fetch job by post_id       |

```

example of updated GSI section in DynamoDB Table resource in CF stack template `aws/cloudformation/db_api_stack.yaml`.

Details of how the converter python script writes the resource section from the db schema JSON are documented in the updates to the converter script.

```yaml
      GlobalSecondaryIndexes:
        - IndexName: gsi_user_created
          KeySchema:
            - AttributeName: user_id
              KeyType: HASH
            - AttributeName: created
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
```

db schema `storage/db_schema.json`

```json
  "global_secondary_indexes": [
    {
      "index_name": "gsi_user_created",
      "partition_key": "user_id",
      "sort_key": "created",
      "projection": "ALL"
    }
  ]

```

example of how the GSI are used by the `jobdb` app python handler

```python
# Table primary index: PK = id
table.query(
    KeyConditionExpression=Key("id").eq(job_id)          # ✅ OK
)

# GSI: gsi_user_created (PK=user_id, SK=created_ulid)
table.query(
    IndexName="gsi_user_created",
    KeyConditionExpression=Key("user_id").eq(u) & Key("created_ulid").between(lo, hi),
    ScanIndexForward=False                                # ✅ OK (newest first)
)

```

### CF stack [Data Engineer] review 2025-08-09 19:10
dbapi GHA debugging

- now CF stack deploy step fails at expected breakpoint -> empty lambda zip payload
- follow-up to cleanup the stack deploy so it doesn't get tripped up on a previous stack rollback or create fail

__issues__

_(resolved) 01 CF stack logical resource name restrictions underscore not allowed_

 - CF stack resources don't allow underscores "_"
    - remove underscore in the constructor *.py
        - constructor refactor: `logical_name = table_name.replace("_", "").capitalize() + "Table"`

 - also applies to Output variables names

`jobdb/cf_template_constructor.py`

```python
def generate_table_resource(table):
    table_name = table["table_name"]
    logical_name = table_name.replace("_", "").capitalize() + "Table"
```

_(open) 02 idempotent deploy_

GHA fails if a previous stack deploy failed --> stack is in `ROLLBACK_COMPLETE` or `CREATE_FAILED` status

 - solution -> add a check 

 ChatGPT suggestion

 ```
Short answer: do it up front.

Pre-flight cleanup at the start of the deploy is safer and more deterministic:
If a previous create failed, the stack will be ROLLBACK_COMPLETE and can’t be updated. Deleting it before deploy avoids an immediate re-fail.
It keeps the main deploy path idempotent and avoids branching logic after a failure.
You can still make the step a no-op for healthy stacks (UPDATE_COMPLETE, CREATE_COMPLETE).

What I recommend:

Pre-check at the beginning

If status is ROLLBACK_COMPLETE or CREATE_FAILED → delete-stack + wait stack-delete-complete, then proceed with deploy.
Otherwise just deploy --no-fail-on-empty-changeset.
Keep a post-failure aid, not auto-delete
If deploy fails, run a tiny “diagnose” step to dump recent stack events and the template validation error, but don’t auto-delete. You’ll want the stack artifacts for debugging.

Guardrails

Only auto-delete when an env flag is set (e.g., ALLOW_STACK_DELETE=true) so you don’t nuke prod by accident.
Consider not auto-deleting UPDATE_ROLLBACK_COMPLETE (that stack is still usable) unless you really need to recreate.
Net: pre-flight cleanup + post-failure diagnostics gives you fast green paths and good debuggability without surprise deletions.

 ```

### CF stack [Data Engineer] review 2025-08-09 18:15
dbapi GHA review

 - network config load step to correctly parse the JSON
 - parameterize network config path and lambda app path
 - add output section to CF template to correctly pass `DB_API_URL`
 - validate commit and re-test GHA

__ChatGPT prompts__

_01 GHA fail: wrong JSON parse_

>update the GHA step "network_config" to correctly parse the network config JSON from the actual JSON format

- refactored the step from ChatGPT suggestion

_02 stack parameter DB URL clarification_

>would the artifact step fail in the GHA? where is DB_URL defined in the CF stack?

- added output section to cf template, after a couple of back-and-forth iterations

`aws/cloudformation/db_api_base.yaml`

```yaml
Outputs:
  DB_API_URL:
    Description: Base URL for the Database API Gateway
    Value: !Sub "https://${DatabaseAPI}.execute-api.${AWS::Region}.amazonaws.com/prod"
    Export:
      Name: !Sub "${AWS::StackName}-DB_API_URL"

```

### CF stack [Codex] 2025-08-09 17:28

- reviewed release docs and `cicd.md` for DB API workflow design
- noted discrepancies in skeleton GHA:
  - push trigger referenced `.github/workflows/db_api.yml` instead of `dbapi.yml`
  - environment variable `TEMPLATE_DIR` mismatched with `CF_TEMPLATE_DIR`
  - missing steps for schema upload, template generation, lambda packaging, and network config loading
  - CloudFormation templates lack outputs for `DB_API_URL`
  - repository uses branch `work` rather than documented `011_dbapi`
- implemented full workflow with parameterized steps for schema load, template generation, lambda packaging, stack deploy, and artifact upload
- verified formatting with `yamllint` and `mdformat`

### CF stack [Data Engineer] Codex prompt 2025-08-09 17:26

for context, refer to the reference docs

- release doc `docs/releases/011_dbapi.md`
- release session notes `dev/releases/011_dbapi.md`
- cicd doc `docs/cicd.md`
- other relevant sections of docs and source code as required

scope

- dbapi GHA `.github/workflows/dbapi.yml`

your task

- review the design from the reference docs and the current skeleton template version for dbapi GHA
- review for consistiency between documents and flag, document any discrepancies in your session log
- review the patterns and layout of the skeleton template dbapi GHA, in particular the parameter passing, step naming
- implement the dbapi GHA in full from design
- record your session activity as a timestamped session log in the release session notes with log header ### CF stack [Codex] 2025-08-09 <HH>:<MM>
- create a PR for the changes to the dbapi GHA and your session log

### CF stack [Data Engineer] 2025-08-09 17:14

github action workflow

- describe the steps for the github action workflow `.github/workflows/dbapi.yml`
- skeleton outline
- define parameters

documentation

- update release doc `docs/releases/011_dbapi.md`

### Release note [Data Engineer] 2025-08-08 21:15

- create new release note `dev/releases/011_dbapi.md`
- switch to new branch `011_dbapi`
