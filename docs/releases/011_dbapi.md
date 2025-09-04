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
| 10 | open | BUG | [test 00 basic route fail 400 Forbidden #13](https://github.com/yayfalafels/mcfpipe/issues/13) | test 00 basic route failed 400 Forbidden |
| 11 | closed | ENHANCEMENT | [GHA and CF conditional refresh #14](https://github.com/yayfalafels/mcfpipe/issues/14) | GHA and CF conditional refresh |
| 12 | closed | ENHANCEMENT | [duplicate VPCE costs tester private subnet #15](https://github.com/yayfalafels/mcfpipe/issues/15) | switch tester to public subnet, delete unnecessary VPCE |


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

### (closed) 12 duplicate VPCE costs tester private subnet
Github issue [duplicate VPCE costs tester private subnet #15](https://github.com/yayfalafels/mcfpipe/issues/15)
type: `ENHANCEMENT`

__situation__
Currently there are **4x Interface VPC endpoints** attached to the private subnet

 - Execute-API
 - ECR API
 - ECR DKR
 - CloudWatch Logs

The network spec explicitly defines the Execute-API and ECR endpoints in the VPC config and outputs, with guidance that private-only tasks need those endpoints (or a NAT) to work. Keeping four always-on VPCEs means **idle hourly charges accumulate** with little data processed.

The reason for the extra VPCE is that the **Tester** runs in a **private subnet**  

__resolution__

- **Keep only one Interface VPCE: API Gateway Execute-API** — this preserves a **private** DB API surface reachable within the VPC and avoids NAT costs for DB API calls.  
- **Run the Tester in a public subnet with `assignPublicIp: ENABLED`** so it can pull from ECR and write logs over the internet (no ECR/Logs VPCEs needed).  
- DB API remains on API Gateway + Lambda; the API stays private and restricted via the Execute-API VPCE allow-list (no policy churn).

__implementation__

| id | resource | task | description |
| - | - | - | - |
| 01 | network stack | remove 3x VPCE | ECR API, ECR DKR and CW Logs |
| 02 | Tester stack | switch to public subnet | with Public IP Enabled |

__Network CF stack__

- **Remove** ECR Interface endpoints from template/outputs: `VpceEcrApiId`, `VpceEcrDkrId` (and Logs VPCE if present).  
- **Keep** only `VPCExecuteApiId` for **API Gateway Execute-API**.  
- Regenerate and re-upload `aws/network/network_config.json` without ECR/Logs endpoint outputs.

__DB API CF stack__

- **No policy change** needed; continue restricting the private API to your **Execute-API VPCE**.  
- Confirm stack outputs (URL, stage, RestApiId) remain intact after network changes.

__Tester stack and GHA__

tester stack
 - location: `aws/cloudformation/tester_stack.yaml` 
 - remove references to VPC information

tester GHA
 - location: `.github/workflows/tester_gha.yml` 
 - remove the network config lookup step
 - pass parameters for tests bucket and dir to CF stack deploy

__Tester run__

- **Use public subnet(s)** for Tester runs instead of the private subnet.  
- In the **GHA `run-task`** call, set:
 - `awsvpcConfiguration.subnets=[PublicSubnetXId]`
 - `awsvpcConfiguration.assignPublicIp=ENABLED`
 - SG with outbound egress only e.g., `SGHTTP` 
 - Ensure the **task execution role** keeps `AmazonECSTaskExecutionRolePolicy` for ECR auth/logs drivers.

DB API GHA
 - location: `.github/workflows/db_api_gha.yml`
 - pass public subnet and SG HTTP to ECS task run script 

ECS task run script
 - location: `tester/tester_task_execute.sh`
 - set default value `ASSIGN_PUBLIC_IP`=ENABLED

__CICD updates__

 - **Stop creating/managing ECR/Logs VPCEs** in network workflow; only publish the Execute-API VPCE ID to S3 config for downstream stacks.
 - Adjust any scripts that read `network_config.json` to **not expect** ECR/Logs VPCE outputs.

__Cleanup__

- Delete existing **ECR API**, **ECR DKR**, and **Logs** interface endpoints.  
- Tag stacks/resources to reflect the simplified design for future cost attribution.