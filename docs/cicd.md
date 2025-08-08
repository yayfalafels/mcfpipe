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
  ecr/
    ...
  fargate/
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
```

## S3 bucket layout

S3 bucket: `mcfpipe`
```
apps/                     # source code for apps
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

__Cloudformation stacks__
Cloudformation stack layers

| id | stack | purpose | resources |
| - | - | - | - |
| 01 | network | initial setup S3 bucket, config and network and VPC for public and private subnets | VPC, subnets, security groups, internet gateway |
| 02 | database api | storage database and connector API | DynamoDB tables |
| 03 | tester | stand-alone tester to validate DB API and other app services | Fargate ECS container |
| 04 | webscraper | serverless Fargate compute resource for Webscraper | Fargate compute tasks |

__AWS CLI__
Additional resources created outside of the cloudformation stack either manually from local PC or via Github actions. 

These resources must be deleted in a separate cleanup workflow.

_manual setup resources_

| id | resource | executor | sequence |
| - | - | - | - |
| 01 | S3 bucket | Github Action | initial setup |
| 02 | S3 config | Github Action | initial setup after s3 bucket creation |
| 03 | ECR Dockerimages | Github Action | before the stack they are used in |


## Github Action Workflows

| id | workflow | app feature | description |
| - | - | - | - |
| 01 | network | initial setup and network | initial setup, create S3 bucket, global IAM roles, network infrastructure |
| 02 | db api | database api | load database schema, deploy database dynamodb tables and db api stack, upload db api config ex API URL |
| 03 | tester | tester | create docker image for tester Fargate container image, deploy tester stack and upload tester config for SSH access ex tester instance_id |
| 01 | webscraper | webscraper | create docker image |

### Setup

initial setup, create S3 bucket, global IAM roles, network infrastructure

| id | step | description |
| - | - | - |
| 01 | create S3 bucket | |
| 02 | upload global config | |
| 03 | deploy network stack |  |
| 04 | record, upload deploy artifacts to S3 | example: VPC id and endpoints |

