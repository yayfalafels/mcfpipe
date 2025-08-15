# CICD
Deployment from source code

## CICD resources

- **Github repository**: [mcfpipe](https://github.com/yayfalafels/mcfpipe) source code storage
- **Github Actions**: deployment engine
- **AWS CloudFormation**: IaC templates for managing cloud infrastructure on AWS
- **Tester App**: Tester module runs on a dedicated Fargate container in the public subnet

## repository layout
the repository files are organized in the following structure

/root
```
.github/
  workflows/            # github deploy actions
     ...
aws/                    # cloudformation templates and specifications for AWS infrastructure
  dynamodb/
    ...
  ecs/
    tasks/
      ...
  ecr/
    ...
  lambda/
    ...
  s3/
    ...
compute/                # source code and config for compute resources
  webscraper/
    ...
dev/
  releases/             # documentation for each release
    ...
docs/                   # app documentation
  ...
jobsearch/              # legacy app source code
  ...
gsheetui/               # Gsheet connector using Google Sheets API
  gsheet/
    __init__.py
    ...
  gsheet_schema.json
  api_config.json
  requirements.txt
mcfparse/              # HTML Parser python module source code
  mcfparse/
    __init__.py
    parser.py
    ...
  requirements.txt
mcfscrape/              # Webscraper python module source code
  mcfscrape/
    __init__.py
    webscraper.py
    ...
  requirements.txt
jobcrm/                 # CRM Backend API
  app/
    __init__.py
  requirements.txt
  ...
jobdb/                   # Database API
  db/
    __init__.py
  requirements.txt
jobmatch/                 # Job recommendation python module
  jobmatch/
    __init__.py
  requirements.txt
  ...
jobpipe/                 # Analytics ETL python module
  jobpipe/
    __init__.py
  requirements.txt
  ...
setup/                  # Initial setup and global configuration
  config.env            # global env variables ex: S3_BUCKET 
storage/                # schema and config for storage resources
  search_profile/
    ...
  jobs/
    ...  
tester/                # Tester app that runs on Fargate container
  tester/
    __init__.py
  tests.py
  Dockerfile
  requirements.txt
.gitignore
AGENTS.md               # instructions for Developer AI assistants
LICENSE
mkdocs.yml
requirements.txt
VERSION
```

__excluded__
files and directories excluded from the source code from `.gitignore`

.gitignore
```
env
site
.env
*client_secret.json
.pytest_cache*
s3-mcfpipe*           # local copy of the contents of the S3 directory
```

## S3 bucket layout

S3 bucket: `mcfpipe`
```
apps/                     # source code for apps
  jobdb/*
  tester/*
config/                   # setup infrastructure and app configuration
aws/                      # information for the AWS infrastructure
  network/
    network_config.json
  ecr/
    containers.json
storage/
  db_api.json             # endpoint access for database API
  db_schema.json
user_data/                # user-specific settings and configuration data
  user_#####/
    ...
```

## Github Actions

__secrets__
secrets used by Github Actions runner to authenticate to AWS

| id | variable | value | description |
| - | - | - | - |
| 01 | AWS_ACCESS_KEY_ID | **** | AWS admin credential |
| 02 | AWS_SECRET_ACCESS_KEY | **** | AWS admin credential |

__environment variables__
environment variables used by Github Actions runner

| id | variable | value | description |
| - | - | - | - |
| 01 | AWS_REGION | ap-southeast-1 | AWS region |

## Dev stack: EC2 vs Fargate
It may be necessary to have two parallel stacks for each compute resources 

1. **DEV**: on EC2 for dev, diagnostic and troubleshooting, can SSH into instance
2. **PROD**: Fargate container cost-optimized for production, limited SSH need to use ECS Exec to run specific diagnostic commands.

## Tester
The tester app uses the test module `tester` and runs on a dedicated AWS Fargate container

__docker image__


__environment variables__
environment variables are passed to the container by Github actions at the `run-task` cli command

| id | variable | description |
| - | - | - |
| 01 | DB_API_URL | API endpoint |


## AWS Infrastructure
The AWS infrastructure is organized into layered CloudFormation stacks, segregated by function and coupled through the repository via parameters and configuration files.

__CloudFormation (CF) stacks__
CloudFormation stack layers

| id | stack | purpose | resources |
| - | - | - | - |
| 01 | network | initial setup S3 bucket, config and network and VPC for public and private subnets | VPC, subnets, security groups, internet gateway |
| 02 | database api | storage database and connector API | DynamoDB tables, API Gateway, Lambda handler |
| 03 | tester | stand-alone tester to validate DB API and other app services | Fargate ECS container |
| 04 | webscraper | serverless Fargate compute resource for Webscraper | Fargate compute tasks |
| 05 | html parser | serverless Lambda(s) for HTML parsing and Step Function for `job search` workflow orchestration | Lambda Step Function and Functions |
| 06 | job scorer | serverless Fargate compute resource for Job scoring and screening | Fargate compute tasks |

__AWS CLI__
Additional resources created outside of the cloudformation stack either manually from local PC or via Github actions. 

These resources must be deleted in a separate cleanup workflow.

_manual setup resources_

| id | resource | executor | sequence |
| - | - | - | - |
| 01 | S3 bucket | Github Action | initial setup |
| 02 | S3 config | Github Action | initial setup after s3 bucket creation |
| 03 | ECR Dockerimages | Github Action | before the stack they are used in |

## CF Stack deploy
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

| id | workflow | app feature | description |
| - | - | - | - |
| 01 | network | initial setup and network | initial setup, create S3 bucket, global IAM roles, network infrastructure |
| 02 | tester | tester | create docker image for tester Fargate container image, deploy tester stack |
| 03 | db api | database api | load database schema, deploy database dynamodb tables and db api stack, upload db api config ex API URL |
| 04 | webscraper | webscraper | create docker image for Webscraper Fargate container image, deploy webscraper stack |
| 05 | html parser | html parser | create HTML Parser Lambda functions and Step Function to orchestrate the `job search` workflow |
| 06 | job scorer | job scorer | create docker image for job scorer Fargate container image, deploy job scorer stack  |
 
### 01 Network setup
initial setup, create S3 bucket, global IAM roles, network infrastructure

__Github action steps__

| id | step | description |
| - | - | - |
| 01 | create S3 bucket | |
| 02 | upload global config | |
| 03 | deploy network stack |  |
| 04 | record, upload deploy artifacts to S3 | example: VPC id and endpoints |

__network config parameters__

format of the network config JSON file

```json
[
    {
        "OutputKey": "SGHTTP",
        "OutputValue": "sg-*****"
    },
    ...
]
```

### 02 Tester
create the tester image, register to ECR, deploy tester stack, upload artifacts

__Github action steps__

| id | step | description |
| - | - | - |
| 01 | resolve version + image tags | Derive `IMAGE_TAG` (e.g., short SHA or semver) and `IMAGE_URI` (account.dkr.ecr.region.amazonaws.com/repo:tag). |
| 02 | docker build | Build tester image from `tester/` (uses `tester/requirements.txt`). |
| 03 | ecr repo ensure | Create ECR repo if missing (idempotent). |
| 04 | ecr push | Tag & push image to ECR; capture digest. |
| 05 | write image manifest | Emit `containers.json` with `{ repo, tag, digest, image_uri }`. |
| 06 | load network config | Download `aws/network/network_config.json` from S3; parse VPC, subnets, SGs. |
| 07 | deploy tester stack | `aws cloudformation deploy` with params: VpcId, PublicSubnetIds, SG(s), EcrImageUri, DBApiUrl |
| 08 | capture CFN outputs | Save stack outputs (cluster, task def ARN, log group, security groups, etc.) to `tester_config.json`. |

__Artifacts__

| id | artifact | input / output | file name | source code | S3 |
| - | - | - | - | - | - |
| 01 | tester Docker context | input | * | `tester/` | — |
| 02 | tester stack template | input | `tester_stack.yaml` | `aws/cloudformation` | — |
| 03 | network config | input | `network_config.json` | — | `aws/network` |
| 04 | image manifest | output | `containers.json` | generated in workflow | `aws/ecr` |
| 05 | CFN stack outputs | output | `tester_config.json` | - | `apps/tester` |

### 03 DB API
load database schema, deploy database dynamodb tables and db api stack, upload db api config 
ex API URL

__Artifacts__

| id | artifact | file name | source code | S3 |
| - | - | - | - | - |
| 01 | network config | `network_config.json` | - | `aws/network/` |
| 01 | db schema | `db_schema.json` | `storage/` | `storage/` |
| 02 | template constructor script | `cf_template_constructor.py` | `jobdb/` | - |
| 03 | CF template | `db_api_stack.yaml` | `aws/cloudformation/` | - |
| 04 | Lambda handler source code | `lambda_sc_jobdb.zip` | `jobdb/*` | `apps/jobdb/` |
| 05 | db api config | `db_api.json` | - | `storage/` |

__DB API Config JSON__
contents of the DB API config JSON

| id | variable | description |
| - | - | - |
| 01 | DB_API_URL | API endpoint |

__Github action steps__

| id | step | description |
| - | - | - |
| 01 | network config load | load the network config from S3 |
| 02 | schema load | load the db schema to workspace, upload to S3 |
| 03 | cf template generate | generate the CF template from schema using template constructur script |
| 04 | zip lambda handlder | zip and upload the lambda handler function code to S3 |
| 05 | stack deploy | deploy the db api stack |
| 06 | artifacts | upload artifacts to config JSON |
