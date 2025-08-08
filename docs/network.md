# Network 
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

## Resources

__network config parameters__
parameters stored in network config JSON artifact `mcfpipe/aws/network/network_config.json`

| id | resource | parameter | value | description |
| - | - | - | - | - |
| 01 | VPC | VpcId |vpc-*** | The VPC every resource should live in. You’ll pass this to anything that needs VPC context (Lambda-in-VPC, ECS/Fargate, RDS, ALB, endpoints). |
| 02 | Public Subnet 01 | PublicSubnet1Id | subnet-**** | public subnets: two for different AZs, associated with a route table that has a route to the IGW. Use for internet-facing things or tasks that need a public IP |
| 03 | Public Subnet 02 | PublicSubnet2Id | subnet-**** | - same - |
| 04 | PrivateSubnetId |subnet-**** | private subnet: associated with a route table that has a route to the IGW. Use for internet-facing things or tasks that need a public IP |
| 05 | security group: Public HTTP | SGHTTP | sg-**** | Inbound: 80/443 from 0.0.0.0/0 |
| 06 | security group: Private | SGPrivate | sg-**** |private services. Usually no inbound from the internet, only from trusted SGs or within VPC |
| 07 | security group: SSH | SGSSH |  sg-**** | SSH access to public instances |

## 01. Global AWS Managed Services

- These services are accessed over the public AWS network.
- No subnet or VPC routing is required.
- Access is controlled entirely via IAM permissions.

**Includes**:

- S3 (data lake, Parquet storage)
- Athena (SQL query interface)
- Glue Catalog (metadata management)

## 02. Private Subnet (VPC-Only)

- Resources are **not publicly accessible**.
- Outbound access is granted via VPC endpoints.
- Designed for secure backend tasks and services.

**Includes**:

- Lambda ETL functions
- Glue transformation jobs
- Internal-facing Database API

## 03. Public Subnet: Outbound + SSH

- Public subnet with **internet access for outbound requests**.
- Allows **SSH inbound**, but blocks HTTP traffic (ports 80/443).
- Public IPs are assigned automatically (Fargate or EC2).
- Useful for browser automation, debugging, or interactive tools.

**Includes**:
- Webscraper (e.g., Selenium headless on Fargate)
- Google Sheets UI connector
- Temporary EC2 debug instances

## 04. Public Subnet: Inbound/Outbound HTTP

- Public-facing APIs with full internet access.
- Allows **inbound HTTP/S** via security group.
- Should include **authentication** to protect API endpoints.
- Can be hosted on EC2, Fargate, or fronted with ALB.

**Includes**:
- CRM API (Flask or Django)
- Optional: ALB if scaling to multiple instances
