# Data model
data model with list of tables and schema information

__Groups__

| id | group | description |
| - | - | - |
| 01 | user | users and settings |
| 02 | search | role, role-specific tracks and search profile |
| 03 | job | job information with workflow status and details scraped from posts and user-updated |

__Tables__

| id | group | table | description |
| - | - | - | - |
| 01 | jobs | job | list of registered jobs, includes url and workflow status codes |
| 02 | jobs | post_details | job details either scraped from post or manually updated |
| 03 | user | user | list of users |
| 04 | user | user_config | user profile and customization settings |
| 05 | search | role | generic job roles ex Data Engineer, Data Scientist |
| 06 | search | track | strategic tracks user-role pairs with additional specification for seniority |
| 07 | search | search_profile | search configuration by track: keywords, target salary |


## Jobs
data tables to describe job information scraped from job post

__ERD__

```mermaid
erDiagram
    job {
        String id PK
        String posted_date
        String position
        String company_name
        String url
        String card_position
        String card_company_name
        Number load_status
        Number crm_status
        Number apply_status
    }

    post_details {
        String jobid PK, FK
        String closing_date
        Number salary_high_sgd
        String mcf_ref
    }

    job ||--o{ post_details : has
```

### Table: job

- Primary Key: `id`  
- Sort Key: `posted_date`

| Column Name       | Data Type | Nullable | Description                             |
|-------------------|-----------|----------|-----------------------------------------|
| id                | String    | No       | Unique job identifier                   |
| posted_date       | String    | No       | Date the job was posted                 |
| position          | String    | No       | Job title                               |
| company_name      | String    | Yes      | Full company name                       |
| url               | String    | Yes      | URL to the job post                     |
| card_position     | String    | Yes      | Position title from card preview        |
| card_company_name | String    | Yes      | Company name from card preview          |
| load_status       | Number    | No       | Ingestion stage (e.g., 0=CARD, 1=POST)  |
| crm_status        | Number    | Yes      | CRM funnel stage (e.g., SHORTLIST, etc.)|
| apply_status      | Number    | Yes      | Application outcome (e.g., TOAPPLY)     |

### Table: post_details

- Primary Key: `jobid`
- Sort Key: `closing_date`

| Column Name      | Data Type | Nullable | Description                    |
|------------------|-----------|----------|--------------------------------|
| jobid            | String    | No       | Foreign key to job table       |
| closing_date     | String    | No       | Application deadline date      |
| salary_high_sgd  | Number    | Yes      | Maximum salary in SGD          |
| mcf_ref          | String    | Yes      | MCF reference code             |

## Users
user-related configuration tables

__ERD__

```mermaid
erDiagram
    user {
        String id PK
        String email
        String username
        String name
        String created_date
        String deactivated_date
        Number status
    }

    user_config {
        String userid PK, FK
        Boolean email_notifications
    }

    user ||--o{ user_config : has
```

### Table: user

- Primary Key: `id`

| Column Name       | Data Type | Nullable | Description                     |
|-------------------|-----------|----------|---------------------------------|
| id                | String    | No       | Unique user identifier          |
| email             | String    | No       | Email address                   |
| username          | String    | No       | Username                        |
| name              | String    | Yes      | Full name                       |
| created_date      | String    | No       | Account creation date           |
| deactivated_date  | String    | Yes      | Account deactivation date       |
| status            | Number    | No       | User status (e.g., 1=active)    |

### Table: user_config

- Primary Key: `userid`

| Column Name          | Data Type | Nullable | Description                              |
|----------------------|-----------|----------|------------------------------------------|
| userid               | String    | No       | Foreign key to user                      |
| email_notifications  | Boolean   | Yes      | Whether user receives email notifications|


## Search
tables related to search configuration

__ERD__

```mermaid
erDiagram
    user {
        String id PK
    }

    role {
        String id PK
        String role_name
        String description
    }

    track {
        String id PK
        String userid FK
        String roleid FK
        Number seniority
    }

    search_profile {
        String trackid PK, FK
        String keywords
        Number salary_target_sgd
    }

    user ||--o{ track : has
    role ||--o{ track : has
    track ||--o{ search_profile : has
```

### Table: role

- Primary Key: `id`

| Column Name  | Data Type | Nullable | Description         |
|--------------|-----------|----------|---------------------|
| id           | String    | No       | Role identifier     |
| role_name    | String    | No       | Name of the role    |
| description  | String    | Yes      | Description of role |

### Table: track

- Primary Key: `id`
- Sort Key: `userid`

| Column Name | Data Type | Nullable | Description                  |
|-------------|-----------|----------|------------------------------|
| id          | String    | No       | Track identifier             |
| userid      | String    | No       | Foreign key to user          |
| roleid      | String    | No       | Foreign key to role          |
| seniority   | Number    | Yes      | Level of seniority (e.g., 1) |

### Table: search_profile

- Primary Key: `trackid`

| Column Name         | Data Type | Nullable | Description                        |
|---------------------|-----------|----------|------------------------------------|
| trackid             | String    | No       | profile ID and foreign key to track|
| keywords            | String    | Yes      | Keywords for job search            |
| salary_target_sgd   | Number    | Yes      | Target salary in SGD               |
