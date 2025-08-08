# Cloud Infrastructure
This release covers the setup of Cloud infrastructure on AWS for the MCF pipe serverless backend API and database

## Situation
The current version of the app `jobsearch` runs locally on PC.  Migrating to the cloud improves maintainability and pathway for full automation, with some drawback in development and small cloud operating costs.

## Objectives and aims
Migrate current functionality to AWS Cloud. 

## Scope
The current scope includes the **network stack infrastructure**, deployed via CICD Github Aciton

## AWS Infrastructure
The AWS infrastructure is organized into layered CloudFormation stacks, segregated by function and coupled through the repository via parameters and configuration files.

__Cloudformation stacks__
Cloudformation stack layers

| id | stack | purpose | resources |
| - | - | - | - |
| 01 | networking | network and VPC for public and private subnets | VPC, subnets, security groups, internet gateway |
| 02 | database | storage database and connector API | DynamoDB tables |
| 03 | webscraper | serverless Fargate compute resource for Webscraper | Fargate compute tasks |

__AWS CLI__
Additional resources created outside of the cloudformation stack either manually from local PC or via Github actions. 

These resources must be deleted in a separate cleanup workflow.

_manual setup resources_

| id | resource | executor | sequence |
| - | - | - | - |
| 01 | S3 bucket | Github Action | initial setup |
| 02 | S3 config | Github Action | initial setup after s3 bucket creation |
| 03 | ECR Dockerimages | Github Action | before the stack they are used in |

## Network infrastructure
Network access control requirements for AWS-based components in the application architecture. 

- All public subnets must be associated with an **Internet Gateway**.
- VPC endpoints are required for private subnets that need to reach the internet
- Security groups should be tightly scoped to match access intent (SSH only, HTTP only, etc.).
- Where possible, use **least privilege IAM roles** and **environment-specific configuration**.

__Access Groups__

| id | access group   | access control  | resources  |
|----|---|----|--|
| 01 | global AWS managed  | IAM credentials | S3, Athena, Glue Catalog |
| 02 | private subnet | VPC + IAM | Lambda ETL, DB API, Glue jobs |
| 03 | public subnet: outbound only + SSH  | IAM + SSH key, no inbound HTTP allowed | Webscraper, Sheets UI, test EC2 |
| 04 | public subnet: inbound/outbound HTTP| IAM + app-level authentication | CRM API (e.g., Flask on EC2/ALB/Fargate) |

## Github Action Workflows
CICD to deploy each of the stacks are orchestrated via Github Actions 

| id | workflow | app feature | description |
| - | - | - | - |
| 01 | network | initial setup and network | initial setup, create S3 bucket, global IAM roles, network infrastructure |
| 02 | db api | database api | load database schema, deploy database dynamodb tables and db api stack, upload db api config ex API URL |
| 03 | tester | tester | create docker image for tester Fargate container image, deploy tester stack and upload tester config for SSH access ex tester instance_id |
| 01 | webscraper | webscraper | create docker image |

### Github action: Setup
initial setup, create S3 bucket, global IAM roles, network infrastructure

| id | step | description |
| - | - | - |
| 01 | create S3 bucket | |
| 02 | upload global config | |
| 03 | deploy network stack |  |
| 04 | record, upload deploy artifacts to S3 | example: VPC id and endpoints |

network config JSON artifact `mcfpipe/aws/network/network_config.json`

__parameters__
network config parameters

| id | resource | parameter | value | description |
| - | - | - | - | - |
| 01 | VPC | VpcId |vpc-*** | The VPC every resource should live in. You’ll pass this to anything that needs VPC context (Lambda-in-VPC, ECS/Fargate, RDS, ALB, endpoints). |
| 02 | Public Subnet 01 | PublicSubnet1Id | subnet-**** | public subnets: two for different AZs, associated with a route table that has a route to the IGW. Use for internet-facing things or tasks that need a public IP |
| 03 | Public Subnet 02 | PublicSubnet2Id | subnet-**** | - same - |
| 04 | PrivateSubnetId |subnet-**** | private subnet: associated with a route table that has a route to the IGW. Use for internet-facing things or tasks that need a public IP |
| 05 | security group: Public HTTP | SGHTTP | sg-**** | Inbound: 80/443 from 0.0.0.0/0 |
| 06 | security group: Private | SGPrivate | sg-**** |private services. Usually no inbound from the internet, only from trusted SGs or within VPC |
| 07 | security group: SSH | SGSSH |  sg-**** | SSH access to public instances |

## Session Logs

session logs are timestamped to Singapore timezone in reverse chronological order, with latest entries at the top, and earlier entries at the bottom.

### Network stack [Data Engineer] Deploy 2025-08-08 20:56
network stack deploy

- successfully setup network infra with network config artifact

`mcfpipe/aws/network/network_config.json`

```json
[
    {
        "OutputKey": "SGHTTP",
        "OutputValue": "sg-*****"
    },
    {
        "OutputKey": "SGPrivate",
        "OutputValue": "sg-*****"
    },
    {
        "OutputKey": "VpcId",
        "OutputValue": "vpc-*****"
    },
    {
        "OutputKey": "PublicSubnet1Id",
        "OutputValue": "subnet-*****"
    },
    {
        "OutputKey": "PublicSubnet2Id",
        "OutputValue": "subnet-*****"
    },
    {
        "OutputKey": "SGSSH",
        "OutputValue": "sg-*****"
    },
    {
        "OutputKey": "PrivateSubnetId",
        "OutputValue": "subnet-*****"
    }
]
```

### Network stack [Data Engineer] Github workflow 2025-08-07 15:30
network stack deploy yaml

- defined steps, minimal
   - create S3 bucket (if doesn't already exist)
   - deploy network stack
   - capture artifacts and upload to S3 bucket

### Data model [Data Engineer]  Codex container error 2025-08-07 13:42
FYI, can't use wildcard * when specifying domains ie *.aws.amazon.com, it causes container setup to fail.

Container failed multiple attempts using *.aws.amazon.com. resolved when it was removed.

Suggestion from ChatGPT is to list each domain separately and also to specify the region.

```
execute-api.ap-southeast-1.amazonaws.com
s3.ap-southeast-1.amazonaws.com
dynamodb.ap-southeast-1.amazonaws.com
athena.ap-southeast-1.amazonaws.com
glue.ap-southeast-1.amazonaws.com
```

### Data model [Data Engineer]  Codex prompt 2025-08-06 18:48
for context, refer to release doc `dev/releases/010_cloud_infra.md`, data model doc `docs/data_model.md` and DB schema `storage/db_schema.json`

your task
- update DB schema according to the specifications in the data model doc
- record your session activity as a timestamped entry in the release doc in the section 
- create a PR for the changes to the DB schema and your session log

### Data model [Data Engineer]  2025-08-06 18:38

db schema revisions: user-specific `job_search`

- create new user-specific table `job_search` which tags a user to a user-independent `job_id`
- all downstream processes, scoring, CRM are all keyed to the `job_s_id` FK to the `job_search` table
- remove `crm_status`, `apply_status` from the `job` table

data model

- standardize `created` and `last_modified` fields for all tables
- standardize id with underscore "_" `job_id`
- add date format `ISO_TIMESTAMP`: YYYY-MM-DD HH:MM and `ISO_DATE`: YYYY-MM-DD


### Database API [Data Engineer]  2025-08-05 21:15

tester

 - validation doc `docs/validation.md`, tester app `tester/*` and tester CF stack `aws/cloudformation/tester_stack.yaml`
 - scope for tester to test DB API, and extend to other features as they are developed
 - run on fargate container
 - `DB_API_URL` injected as env variable at ECS task-run by Github Action workflow 
 - listed 12x test cases positive and negative

stack segregation

 - separate stacks for setup, networking, Database API
 - some resources more expedient to setup via Github Action runner CLI outside of CF stack
    - ex: docker image builds

network infrastructure

 - CF stack `aws/cloudformation/network_stack.yaml` 
 - VPC with private endpoints, no NAT gateway ($30 per month)
 - multiple access groups identified for specific use cases
    - 01 global AWS managed - S3, Athena managed via IAM credentials
    - 02 private subnet - most applications Lambda ETL, DB API
    - 03 public subnet: outbound only + SSH - Tester, Webscraper
    - 04 public subnet: public subnet: inbound/outbound HTTP handled via app-level authentication, CRM API

database API

 - app `jobdb/*`
 - CF stack `aws/cloudformation/db_api_stack.yaml`
 - couple the DynamoDB tables + API Gateway, Lambda handler definitions in the same stack
 - generic route `/{table}/{id}` and let the lambda handler handle table-specific details
 - Lambda handler is aware of `db_schema.json`.  
    - responsible for enforcing schema data types and other constraints
 - uses base stack `aws/cloudformation/db_api_base.yaml` for the API resources
 - uses app script `jobdb/cf_template_constructor.py` to build the DynamoDB resources dynamically at runtime with the Github Action workflow

### Webscraper [Data Engineer] design and AWS Infra 2025-08-04 18:21

__aws infra__

 - drafted the webscraper CF stack template `aws/cloudformation/webscraper_stack.yaml`
 - design concept of layered approach to stacks, defining 3x layers 1. networking 2. database 3. compute (webscraper)
 - defined resources created outside of the CF stacks - such as S3 and config setup, and the Dockerimage build and ECR registration

__webscraper__

- dependencies specification: selenium, boto3, bs4
- sample dockerfile
- task definitions JSON --> YAML
- drafted CloudFormation stack resources

__architecture__

- identified separate workflows and separate libraries and compute resources
- defined repository folder organization

_workflow components_

| component | requirements | resource | app library |
| - | - | - | - |
| Webscraper | selenium, boto3, bs4 | Fargate container | mcfscrape |
| HTML Parser | boto3, bs4 | Lambda | mcfparse |
| Job Recommender | pandas, nltk, scikit-learn, openai | Fargate container | jobmatch |
| CRM API | TBD Flask/Django | API Gateway + Lambda | jobcrm |
| Analytics ETL | pandas, boto3, sqlite3 | Lambda | jobpipe |
| Gsheet Connector | pandas, google api, boto3 | Lambda | gsheetui |