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

### (closed) 09 tester container script failure
multiple exceptions tester container script failure

multiple sub-issues

| id	| status | sub-issue |
| 01 | closed |	insufficient IAM permissions on task execution role |
| 02 | closed |	CW log stream not found |
| 03 | closed |	unknown flag `--no-follow` |

__(closed) 09.01 insufficient IAM permissions on task execution role__

location: `tester/tester_task_execute.sh` plus possible other locations

CF stack template `aws/cloudformation/tester_stack.yaml`
GHA `tester_gha.yml`

_situation_

exception: insufficient permissions on tester execution role for ECR: GetAuthorizationToken

```
Stopped reason: ResourceInitializationError: unable to pull secrets or registry auth: execution resource retrieval failed: unable to retrieve ecr registry auth: service call has been retried 1 time(s): operation error ECR: GetAuthorizationToken, https response error StatusCode: 400, RequestID: 24460c33-1d7d-4ee9-99cf-c259d53e7b44, api error AccessDeniedException: User: arn:aws:sts::***:assumed-role/mcfpipe-tester-TesterExecutionRole-aWok1pIh26Gk/a5209a25e2424cafa8d2f56406f57b35 is not authorized to perform: ecr:GetAuthorizationToken on resource: * because no identity-based policy allows the ecr:GetAuthorizationToken action
CloudWatch Logs for failed task
  An error occurred (ResourceNotFoundException) when calling the GetLogEvents operation: The specified log stream does not exist.
  (could not fetch exact stream, falling back to recent tail)
  Unknown options: --no-follow
```

_resolution_

location: `aws/cloudformation/tester_stack.yaml`

```yaml
attach AmazonECSTaskExecutionRolePolicy to the TesterExecutionRole
remove the cw-logs inline policy (redundant)
TesterExecutionRole:
  Type: AWS::IAM::Role
  Properties:
    AssumeRolePolicyDocument:
      Version: "2012-10-17"
      Statement:
        - Effect: Allow
          Principal: { Service: ecs-tasks.amazonaws.com }
          Action: sts:AssumeRole
    ManagedPolicyArns:
      - arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

__(closed) 09.02 CW log stream not found__

_situation_

exception: CW log group not found

```
CloudWatch Logs for failed task
  An error occurred (ResourceNotFoundException) when calling the GetLogEvents operation: The specified log stream does not exist.
  (could not fetch exact stream, falling back to recent tail)
```

_diagnostics_

symptom of underlying cause for sub-issue 01

__(closed) 09.03 unknown flag no follow__

_situation_

exception 03: unknown flag --no-follow

  Unknown options: --no-follow
location: `tester/tester_task_execute.sh`

```bash
### --- On failure: print CW logs to runner output ----------------------------
if [[ "$EXIT_CODE" != "0" ]]; then
  echo "::group::CloudWatch Logs for failed task"
  STREAM="${STREAM_PREFIX}/${CONTAINER_NAME}/${TASK_ID}"
  # small delay to allow final log flush
  sleep 3 || true
  if ! aws logs get-log-events \
        --region "$REGION" \
        --log-group-name "$LOG_GROUP" \
        --log-stream-name "$STREAM" \
        --query 'events[].message' \
        --output text ; then
    echo "(could not fetch exact stream, falling back to recent tail)"
-->   aws logs tail "$LOG_GROUP" --region "$REGION" --since 1h --format short --no-follow || true
  fi
  echo "::endgroup::"
fi
```
_resolution_

drop the `--no-follow` argument from the line

```bash
aws logs tail "$LOG_GROUP" --region "$REGION" --since 1h --format short --no-follow || true
```

### (open) 10 test 00 basic route fail 400 Forbidden
Github issue [test 00 basic route fail 400 Forbidden #12](https://github.com/yayfalafels/mcfpipe/issues/13)
type: `BUG`

__situation__

test 00 fails with status code 400 "Forbidden"

ECS task CW logs

```
August 18, 2025 at 17:10
> self.assertEqual(response.status_code, 200, f'expected status code 200, got {response.status_code}. {response.text} from BASE_URL: {BASE_URL}')
tester
August 18, 2025 at 17:10
E AssertionError: 400 != 200 : expected status code 200, got 400. {"message":"Forbidden"} from BASE_URL: https://1vrt51wp19.execute-api.ap-southeast-1.amazonaws.com/prod
tester
```

__diagnostics__
root cause: **API not yet deployed** [Stack Overflow: getting message forbidden reply from aws api gateway](https://stackoverflow.com/questions/40988051/getting-message-forbidden-reply-from-aws-api-gateway)

several diagnostic steps taken, some improvements made, explicitly attach VPCE
but ultimately cause was not yet deployed.

- correct Base URL passed in (print-out in logs)
- X base URL returns expected response from console 
  actually this is unexpected because supposed to be PRIVATE

location `aws/cloudformation/db_api_base.yaml`

X REGIONAL (Public IP)

```yaml
  RestApi:
    Type: AWS::ApiGateway::RestApi
    Properties:
      Name: !Sub mcfpipe-dbapi-${StageName}
      EndpointConfiguration:
        Types: [REGIONAL]

```

OK PRIVATE 

```yaml
  RestApi:
    Type: AWS::ApiGateway::RestApi
    Properties:
      Name: !Sub mcfpipe-dbapi-${StageName}
      EndpointConfiguration:
        Types: [PRIVATE]

```

_detailed diagnostic_

  - script `issues/010_dbapi_vpce/vpce_diagnostics.sh`
  - gha `.github/workflows/issue_dbapi_vpce_gha.yml`

- **OK** DNS resolves the API host to a 10.0.x.x address → the request is going through the execute-api VPC endpoint (Private DNS path).
- **OK** TLS is OK → SGs/NACL/routes are fine.
- **OK** API type is PRIVATE.
- **X API Gateway blocking** Both GET / and GET /health return {"message":"Forbidden"} (mapped to 400 by your DEFAULT_4XX) → API Gateway is authoritatively rejecting the request (not Lambda/integration).

initial diagnostics narrow cause to two possible causes
further diagnostics confirm VPCE is not attached to the API Gateway

--> 01. REST API resource policy (on the API itself)
02. VPCE endpoint policy (on the interface endpoint)

- only shows `{ "types": ["PRIVATE"] }`
- does not show VPCE ID

```bash
aws apigateway get-rest-api --rest-api-id 1vrt51wp19 \
  --query 'endpointConfiguration'
```

__resolution(s)__
01.  add a step to GHA to deploy the API after stack deploy

02. explicitly attach VPCE to the RestApi resource

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

 