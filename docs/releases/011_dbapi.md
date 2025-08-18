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
| 07 | open | BUG | [DB_API_URL not passed #10](https://github.com/yayfalafels/mcfpipe/issues/10) | GHA parameter `DB_API_URL` not passed from stack outputs |

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

### (closed) 05 ECR refresh on changes
Github issue [API IAM CW log #8](https://github.com/yayfalafels/mcfpipe/issues/8)
type: `BUG`

__situation__
Stack deploy FAIL. An IAM Role for the API Gateway must have permissions to read/write to CW log group.

exception

```
|  2025-08-18T06:03:15.677000+00:00|  AWS::ApiGateway::Stage     |  ApiStage      |  CREATE_FAILED        |  Resource handler returned message: "CloudWatch Logs role ARN must be set in account settings to enable logging (Service: ApiGateway, Status Code: 400, Request ID: bc4ede82-d75d-4c43-9d5d-a88fc90aa24b) (SDK Attempt Count: 1)" (RequestToken: ce63743f-5eb5-23f9-0185-6bd7e6d2e752, HandlerErrorCode: InvalidRequest)
```

__resolution__
Create a simple IAM role with write access to CW log group using the managed policy `AmazonAPIGatewayPushToCloudWatchLogs`. 
 - attach the policy to an API Gateway account

```yaml
Resources:
  ApiGatewayCloudWatchRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: apigw-cw-logs
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: apigateway.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs

  ApiGatewayAccount:
    Type: AWS::ApiGateway::Account
    Properties:
      CloudWatchRoleArn: !GetAtt ApiGatewayCloudWatchRole.Arn

```

### (closed) 06 CF API log format
Github issue [CF API log format #8](https://github.com/yayfalafels/mcfpipe/issues/9)
type: `BUG`

__situation__
malformatted Access log with line break character `\n` in CF template

location: `aws/cloudformation/db_api_base.yaml` CF Resource:`ApiStage`

```yaml
  ApiStage:
    Type: AWS::ApiGateway::Stage
    Properties:
      StageName: !Ref StageName
      RestApiId: !Ref RestApi
      DeploymentId: !Ref ApiDeployment
      TracingEnabled: false
      ...
      AccessLogSetting:
        DestinationArn: !GetAtt ApiAccessLogs.Arn
        Format: >-
          { "requestId":"$context.requestId","ip":"$context.identity.sourceIp",
            "caller":"$context.identity.caller","user":"$context.identity.user",
            "requestTime":"$context.requestTime","httpMethod":"$context.httpMethod",
            "resourcePath":"$context.resourcePath","status":"$context.status",
            "protocol":"$context.protocol","responseLength":"$context.responseLength",
            "integrationError":"$context.integration.error",
            "errorMessage":"$context.error.message" }
```

exception

```
This AWS::ApiGateway::Stage resource is in a CREATE_FAILED state.

Resource handler returned message: "Access Log format must be single line, new line character is allowed only at end of the format: '{ "requestId":"$context.requestId","ip":"$context.identity.sourceIp", "caller":"$context.identity.caller","user":"$context.identity.user", "requestTime":"$context.requestTime","httpMethod":"$context.httpMethod", "resourcePath":"$context.resourcePath","status":"$context.status", "protocol":"$context.protocol","responseLength":"$context.responseLength", "integrationError":"$context.integration.error", "errorMessage":"$context.error.message" }' (Service: ApiGateway, Status Code: 400, Request ID: 65007eb0-8bfa-47ff-9bc5-9d188d874781) (SDK Attempt Count: 1)" (RequestToken: d5b2dec4-40cf-b3f3-ca96-f834b5e6173c, HandlerErrorCode: InvalidRequest)
```

__diagnostics__
`AWS::ApiGateway::Stage.AccessLogSetting.Format` contains one or more line break `\n` characters before the end of the string.

The [YAML line break fold operator](https://stackoverflow.com/questions/3790454/how-do-i-break-a-string-in-yaml-over-multiple-lines) `>-` _should_ have resolved the issue
    - but for some unknown reason, it didn't work as expected.

_Possible causes_

- **leading theory** baggage leftover `\r` from differences between Windows `\r\n` and linux `\n` line break
- Using | (literal) or plain multi-line YAML.
- Copy/pasting pretty JSON with line breaks.
- Using !Sub over a multi-line block without folding/chomping.

__resolution__
don't use line breaks and write as a single long line.

with line breaks

```yaml
        Format: >-
          { "requestId":"$context.requestId","ip":"$context.identity.sourceIp",
            "caller":"$context.identity.caller","user":"$context.identity.user",
            "requestTime":"$context.requestTime","httpMethod":"$context.httpMethod",
```

without line breaks

```yaml
        Format: >-
          { "requestId":"$context.requestId","ip":"$context.identity.sourceIp", "caller":"$context.identity.caller","user":"$context.identity.user", "requestTime":"$context.requestTime","httpMethod":"$context.httpMethod",
```

### (closed) 07 DB_API_URL not passed
Github issue [DB_API_URL not passed #10](https://github.com/yayfalafels/mcfpipe/issues/10)
type: `BUG`

__situation__
The GHA env variable `DB_API_URL` failed to set from stack outputs. variable was empty in the next step.

```bash
OUTPUTS=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query "Stacks[0].Outputs" \
  --output json)
echo "$OUTPUTS" > $ARTIFACTS_JSON
DB_URL=$(echo "$OUTPUTS" | jq -r --arg k "$CF_DB_API_URL_NAME" \
  '.[] | select(.OutputKey==$k) | .OutputValue')
echo "DB_API_URL=$DB_URL" >> $GITHUB_ENV
```

__diagnostics__

root cause (suspected)
incorrect CF stack output variable name in GHA env variable `CF_DB_API_URL_NAME`

expected: OK `DbApiUrl`
actual: X `DbAPIUrl`

location `.github/workflow/db_api_gha.yml`

```yaml
    env:
      CF_DB_API_URL_NAME: DbAPIUrl
```

diagnostic steps

| id | status | check | results |
| - | - | - | - |
| 01 | closed | stack output parameter exported to S3 config | OK `DbApiUrl=https://1vrt51wp19.execute-api.ap-southeast-1.amazonaws.com/prod` |
| 02 | open | GHA env variable correct  |X `CF_DB_API_URL_NAME=DbAPIUrl` should be `CF_DB_API_URL_NAME=DbApiUrl` |

__resolution__

update to correct variable name `DbApiUrl`

```yaml
    env:
      CF_DB_API_URL_NAME: DbApiUrl
```
