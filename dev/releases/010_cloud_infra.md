# Cloud Infrastructure
This release covers the setup of Cloud infrastructure on AWS for the MCF pipe serverless backend API and database

## Situation
The current version of the app `jobsearch` runs locally on PC.  Migrating to the cloud improves maintainability and pathway for full automation, with some drawback in development and small cloud operating costs.

## Objectives and aims
Migrate current functionality to AWS Cloud. 

## Scope
The current scope includes the `jobs search` workflow

__Jobs search__
Scrape data from MCF website parse and store into cloud AWS DynamoDB database

## System architecture
There are several components of the app, broadly grouped into **storage** and **compute**

__Data__

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
| 01 | Webscraper | get MCF search results and job post pages | local python scripts | container Fargate + ECR |
| 02 | HTML Parser | HTML parse and write to DB | local python scripts | Lambda + SQS |
| 03 | Job Recommender | score the posts | local python scripts | Lambda |
| 04 | Config Sync | syncs config from GSheet | local python scripts | Lambda |
| 05 | MCF Login | refresh session cookie | manual | S3 + Lambda |
| 06 | MCF Apply | apply jobs | local python scripts | container Fargate + ECR  |
| 07 | CRM API | write-back, status updates, select jobs to apply, config update | GSheet | CRM API on EC2 |
| 08 | Analytics ETL | Denormalize from DynamoDB to SQlite | GSheet | Lambda |
| 09 | Dashboard | Reports and data visualization | GSheet | PowerBI connect to SQLite on S3 |


## Session Logs

session logs are timestamped to Singapore timezone in reverse chronological order, with latest entries at the top, and earlier entries at the bottom.

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