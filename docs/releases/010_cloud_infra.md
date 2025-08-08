# Network Infrastructure
This release covers the setup of Network infrastructure on AWS for the MCF pipe serverless backend API and database

## Situation
The current version of the app `jobsearch` runs locally on PC.  Migrating to the cloud improves maintainability and pathway for full automation, with some drawback in development and small cloud operating costs. The deployment to cloud is organized into stack layers, with the first layer to setup the network infrastructure.

## Objectives and aims
Migrate current functionality to AWS Cloud. First step setup Network infrastructure.

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
| 04 | Private Subnet | PrivateSubnetId |subnet-**** | private subnet: associated with a route table that has a route to the IGW. Use for internet-facing things or tasks that need a public IP |
| 05 | security group: Public HTTP | SGHTTP | sg-**** | Inbound: 80/443 from 0.0.0.0/0 |
| 06 | security group: Private | SGPrivate | sg-**** |private services. Usually no inbound from the internet, only from trusted SGs or within VPC |
| 07 | security group: SSH | SGSSH |  sg-**** | SSH access to public instances |