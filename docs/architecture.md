## System architecture
There are several components of the app, broadly grouped into **storage** and **compute**

__Storage__

| id | component | description | current | AWS Infra |
| - | - | - | - | - |
| 01 | job posts data | jobs and job posts | local SQLite database | DynamoDB |
| 02 | dimension tables | config, tracks, keyword libraries | GSheet tables | DynamoDB |
| 03 | CRM data | screened, applied, closed, responses, track assignment | GSheet tables | DynamoDB |
| 04 | jobs applied status | jobs applied status from MCF apply | Gsheet table | DynamoDB |
| 05 | reports | jobs by stage CRM performance analysis | Gsheet table | SQLite on S3 |

__Compute__

| id | component | description | current | AWS Infra |
| - | - | - | - | - |
| 01 | Webscraper | get MCF search results and job post pages | local python scripts | Fargate container |
| 02 | HTML Parser | HTML parse and write to DB | local python scripts | Lambda + SQS |
| 03 | Job Recommender | score the posts | local python scripts | Fargate container |
| 04 | GSheet Connector | GSheet UI interface | local python scripts | Lambda |
| 05 | MCF Login | refresh session cookie | manual | S3 + Lambda |
| 06 | MCF Apply | apply jobs | local python scripts | container Fargate + ECR  |
| 07 | CRM API | write-back, status updates, select jobs to apply, config update | GSheet | CRM API on EC2 |
| 08 | Analytics ETL | Denormalize from DynamoDB to Parquet | GSheet | Lambda, Glue, Athena |
| 09 | Dashboard | Reports and data visualization | GSheet | PowerBI connect to SQLite on S3 |
| 10 | DynamoDB API | DynamoDB interface API | - | API Gateway + Lambda |
| 11 | Network | VPC and network infrastructure | - | Networking |


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
| 03 | ECR Dockerimage | Github Action | before Webscraper stack deploy |

## Network 
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


## Database API
The Database API is a single interface point to the backend DynamoDB database


## Webscraper container
The webscraper runs on a **Fargate** container and runs the following tasks.
The scope of the webscraper is interface with the MCF website using selenium webdriver.
The webscraper uses the python library `mcfscrape`.

__Base image__
Base image: `python:3.11-slim`

__Requirements__

_docker environment_

- apt-get update (standard)
- ca-certificates
- chromium chromium-driver

_python dependencies_

- selenium >= 4.6
- boto3
- BeautifulSoup (bs4)
- requests (optional)

__Tasks__

Tasks include either

1. **POST** to apply for selected jobs
2. **GET** content and save into raw HTML source code files for downstream processing.

| id | task | description |
| - | - | - | 
| 01 | keyword search | search by keyword and paginate search results to html files by page |
| 02 | job pages fetch | fetch job post page save to html file |
| 03 | jobs apply | use stored session cookie from S3, submit job application from job toapply config and navigate through apply pages |
