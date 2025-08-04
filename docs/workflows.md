# Workflows

__App workflows__

| id | workflow | description |
| - | - | - |
| 01 | jobs search | scrape data from MCF website parse and store into database |
| 02 | jobs screen | score and screen jobs for curated report jobs to apply |
| 03 | jobs apply | apply jobs through MCF website from shortlisted jobs to apply |
| 04 | CRM API | CRUD operational actions to manage search and move leads through pipeline |
| 05 | analytics ETL | update SQLite DB from data sources DynamoDB tables and refresh PowerBI report |
| 06 | config sync | update config settings |

## Jobs search

```mermaid
graph TB

%% Config
DynamoConfig["Dynamo: Search config"]

%% Extraction phase
CardScraper["Fargate: Card Scraper"]
S3Cards["S3: Card HTML"]
CardsQueue["SQS: Cards Queue"]
Parser1["Lambda: HTML Parser (cards)"]
JobsDB["DynamoDB: Jobs"]

PostScraper["Fargate: Post Scraper"]
S3Posts["S3: Full Post HTML"]
PostsQueue["SQS: Post Queue"]
Parser2["Lambda: HTML Parser (posts)"]

%% Transformation + Enrichment
Scorer["Lambda: Job Scorer"]

%% Flow
DynamoConfig --> CardScraper
CardScraper --> S3Cards
CardScraper --> CardsQueue
CardsQueue --> Parser1
S3Cards --> Parser1
Parser1 --> CardsQueue
Parser1 --> JobsDB
CardsQueue --> PostScraper

JobsDB --> PostScraper
PostScraper --> S3Posts
PostScraper --> PostsQueue
PostsQueue --> Parser2
Parser2 --> PostsQueue
S3Posts --> Parser2
Parser2 --> JobsDB
PostsQueue --> Scorer

```

## Jobs screen

```mermaid
graph TB

%% Config
DynamoConfig["Dynamo: Search config"]

%% Transformation + Enrichment
JobsDB["DynamoDB: Jobs"]
PostsQueue["SQS: Post Queue"]
Scorer["Lambda: Job Scorer"]
Scores["DynamoDB: Job Scores"]

%% Decisioning
Screener["Lambda: Screener"]
CRM["DynamoDB: CRM Data (screened)"]

%% Flow
PostsQueue --> Scorer
DynamoConfig --> Scorer
JobsDB --> Scorer
Scorer --> Scores

Scores --> Screener
JobsDB --> Screener
Screener --> CRM

```


## Jobs apply

```mermaid
graph TB

%% Cookies
CredRefresh["laptop: login MFA cookie refresh"]
Cookie["DynamoDB: User config (MCF session cookie)"]

%% Jobs Apply
User["User"]
JobsApply["Fargate: MCF jobs apply"]
ToApply["DynamoDB: CRM Data (jobs to apply)"]

%% Flow
User --> CredRefresh
User --> JobsApply
CredRefresh --> Cookie
Cookie --> JobsApply
ToApply --> JobsApply
JobsApply --> ToApply

```


## CRM API

```mermaid
graph RL

FEApp["EC2 Front-end App"]
LegacyGSheet["Legacy Gsheet UI"]
GsheetSync["Lambda Gsheet API interface"]
CRMAPI["CRM API"]

%% CRM API
FEApp --> CRMAPI
CRMAPI --> FEApp 
GsheetSync --> CRMAPI
GsheetSync --> LegacyGSheet
LegacyGSheet --> GsheetSync
CRMAPI --> GsheetSync

```

## Analytics ETL

```mermaid
graph TB

DynamoJobs["DynamoDB: Job Posts"]
DynamoCRM["DynamoDB: CRM Data"]
DynamoConfig["DynamoDB: Dimension Tables"]
LambdaETL["Lambda ETL to SQLite"]
BI["PowerBI: Analytics reports"]

%% ETL flow
DynamoJobs --> LambdaETL
DynamoCRM --> LambdaETL
DynamoConfig --> LambdaETL
LambdaETL --> S3SQLite
S3SQLite --> BI
```

