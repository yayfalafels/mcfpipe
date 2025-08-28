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

## AWS Infrastructure
The AWS infrastructure is organized into layered CloudFormation stacks, segregated by function and coupled through the repository via parameters and configuration files.

__Cloudformation stacks__
Cloudformation stack layers

| id | stack | purpose | resources |
| - | - | - | - |
| 01 | networking | network and VPC for public and private subnets | VPC, subnets, security groups, internet gateway |
| 02 | tester | serverless Fargate compute resource for validating app resources | Fargate compute task(s) |
| 03 | db api | storage database and connector API | DynamoDB tables, API Gateway + Lambda handler |

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

| id | artifact | file name | source code | S3 |
| - | - | - | - | - |
| 01 | db schema | `db_schema.json` | `storage/` | `storage/` |
| 02 | template constructor script | `cf_template_constructor.py` | `jobdb/` | - |
| 03 | CF template | `db_api_stack.yaml` | `aws/cloudformation/` | - |
| 04 | Lambda handler source code | `lambda_sc_jobdb.zip` | `jobdb/*` | `apps/jobdb/` |
| 05 | db api config | `db_api.json` | - | `storage/` |

__Config JSON__
contents of the DB API config JSON

| id | variable | description |
| - | - | - |
| 01 | DB_API_URL | API endpoint |

__Github action steps__

| id | step | description |
| - | - | - |
| 01 | schema load | load the db schema to workspace, upload to S3 |
| 02 | cf template generate | generate the CF template from schema using template constructur script |
| 03 | zip lambda handlder | zip and upload the lambda handler function code to S3 |
| 04 | stack deploy | deploy the db api stack |
| 05 | artifacts | upload artifacts to config JSON |

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
| 10 | open | BUG | [test 00 basic route fail 400 Forbidden #13](https://github.com/yayfalafels/mcfpipe/issues/13) | test 00 basic route failed 400 Forbidden |
| 11 | open | ENHANCEMENT | [GHA and CF conditional refresh #14](https://github.com/yayfalafels/mcfpipe/issues/14) | GHA and CF conditional refresh |

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

### (open) 11 GHA and CF conditional refresh
Github issue [GHA and CF conditional refresh #14](https://github.com/yayfalafels/mcfpipe/issues/14)
type: `ENHANCEMENT`

__situation__
Current CF stack refreshes the docker images for `tester` and `jobdb` under any trigger for the GHA workflow, many of which do not require an image refresh. Consequence is a build-up of redundant image copies that add clutter and storage costs.  Additionally, the DB API CF stack combines the storage DB schema resources with the compute Gateway API layer and includes a forced deploy refresh on each CF deploy trigger. While it's expected there many be frequent DB Schema changes in the future, the DB API has already been designed as a thin wrapper decoupled from schema specifics, so it shouldn't need to be updated for only DB schema changes.

__requirements__

| id | status | enhancement |
| - | - | - |
| 01 | closed | CF separate DB storage resources from Gateway API + Lambda |
| 02 | open | decouple tests to run from tester generic compute |
| 03 | open | GHA tester image conditional refresh |
| 04 | open | GHA jobdb image conditional refresh |

### (closed) 01. CF separate DB storage resources from Gateway API + Lambda

_CF templates_

| id | template | location |
| - | - | - |
| 01 | db stack base | `aws/cloudformation/db_base.yaml` |
| 02 | db stack | `aws/cloudformation/db_stack.yaml` |
| 03 | db api stack | `aws/cloudformation/db_api_stack.yaml` |

__01 db stack__

stack name: `mcfpipe-database`
resources: DynamoDB tables

_steps_

01. upload the DB Schema JSON to S3
02. generate the CF template from DB Schema JSON
03. deploy tables CF stack
04. (on failure) report CF stack fail diagnostics

__02 db api stack__

stack name: `mcfpipe-dbapi`
resources: API Gateway, URL handler Lambda 

- dropped StageDescription property, caused Stack Fail
- attached Resource policy -- turns out it is required

_steps_

01. download network config from S3
02. build container image register to ECR
03. deploy CF stack
04. (on failure) report CF stack fail diagnostics
05. get stack outputs upload to S3
06. get API ID
07. run tests on tester

### (open) 02. decouple tests to run from tester generic compute

_changes_

| id | status | location | change |
| - | - |  - | - |
| 01 | closed | `tester/*` | add a script to import the tests from S3 as file or zip |
| 02 | closed | `tester_task_execute.sh` | pass the S3 location to and call the S3 import script |
| 03 | closed | `tester/requirements.txt` | add `boto3` dependency |
| 04 | open | ECS task role | Grant the task role s3:GetObject on the tests prefix |
| 05 | open | DB API GHA `.github/workflows/db_api_gha.yml` | upload tests.py, or zip `tests/*` to S3 |

__(closed) 01 tester: script to import tests__
add a script to import the tests from S3 as file or zip

_s3 tests directory_
the tests are located in the S3 location: `apps/tests/*`

S3 bucket: `mcfpipe`

```
apps/                     # source code for apps
  jobdb/*
  tester/*
  tests/                  # unit tests for tester to run
    test_jobdb.py         # example: Unit tests for DB API
    ...

```

_tester tests import script_
Import unit tests from S3 into local test runner

location: `tester/import.py`

Steps:
  1) Process CLI args (overrides env defaults).
  2) Create local directories: tests/ and tmp/tests/.
  3) Download objects from S3 prefix to tmp/tests/.
  4) Unzip any *.zip found in tmp/tests/ into tests/.
  5) Copy other non-zip files from tmp/tests/ into tests/.
  6) Log activity; capture and report errors.

_import and run script_
location: `tester/import_run_tests.sh`
new script to call the `import.py` script to download and import tests from S3, 
and then run `pytests -q tests`

```bash
# ---- Import tests -----------------------------------------------------------
echo "[import_run_tests] importing tests from s3://${S3_BUCKET}/${TESTS_S3_DIR} -> ${TESTS_LOCAL_DIR}"
python /app/import.py \
  --region "${AWS_REGION}" \
  --bucket "${S3_BUCKET}" \
  --s3-dir "${TESTS_S3_DIR}" \
  --tests-dir "${TESTS_LOCAL_DIR}" \
  --tmp-dir "${TMP_TESTS_DIR}" \
  --log-file "${IMPORT_LOG_FILE}" \
  --clean-tmp

# ---- Run tests --------------------------------------------------------------
echo "[import_run_tests] running: pytest ${PYTEST_ARGS} ${TESTS_LOCAL_DIR}"

# keep the old log piping behavior
set -o pipefail
pytest ${PYTEST_ARGS} "${TESTS_LOCAL_DIR}" 2>&1 | tee /var/log/tests.log
```

_Dockerfile entrypoint_
change entry point to run bash script `import_run_tests.sh`

```Dockerfile  

# stage runtime helpers
COPY import.py /app/import.py
COPY import_run_tests.sh /app/import_run_tests.sh
RUN chmod +x /app/import_run_tests.sh

# default entry: import tests at runtime, then run pytest on tests/
CMD ["sh","-lc","/app/import_run_tests.sh"]

```

__(open) 04 ECS task IAM role: Grant s3:GetObject on the tests prefix__

ECS Task IAM role
- Grant s3:GetObject on the tests prefix

location: `aws/cloudformation/tester_stack.yaml`

```yaml
  TesterTaskRoleS3Policy:
    Type: AWS::IAM::Policy
    Properties:
      PolicyName: tester-s3-read-tests
      Roles: [ !Ref TesterTaskRole ]
      PolicyDocument:
        Version: '2012-10-17'
        Statement:
          # allow listing only inside your tests prefix
          - Sid: ListTestsPrefix
            Effect: Allow
            Action: s3:ListBucket
            Resource: !Sub arn:aws:s3:::${S3Bucket}
            Condition:
              StringLike:
                s3:prefix:
                  - !Ref TestsS3Prefix
                  - !Sub '${TestsS3Prefix}*'
          # allow reading any object within the tests prefix
          - Sid: GetObjectsInPrefix
            Effect: Allow
            Action:
              - s3:GetObject
              - s3:GetObjectVersion
            Resource: !Sub arn:aws:s3:::${S3Bucket}/${TestsPrefix}*

```
