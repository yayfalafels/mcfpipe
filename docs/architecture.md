# Architecture
System architecture for the serverless App

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
| 03 | Post Scoring | score the posts | local python scripts | Lambda |
| 04 | Config Sync | syncs config from GSheet | local python scripts | Lambda |
| 05 | MCF Login | refresh session cookie | manual | S3 + Lambda |
| 06 | MCF Apply | apply jobs | local python scripts | container Fargate + ECR  |
| 07 | CRM API | write-back, status updates, select jobs to apply, config update | GSheet | CRM API on EC2 |
| 08 | Analytics ETL | Denormalize from DynamoDB to SQlite | GSheet | Lambda |
| 09 | Dashboard | Reports and data visualization | GSheet | PowerBI connect to SQLite on S3 |

## Webscraper container
The webscraper is 