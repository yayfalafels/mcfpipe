# Database API

The `Database API` provides a RESTful interface for CRUD operations on DynamoDB tables defined in the system data model. The API is implemented as a **generic Lambda function** behind API Gateway, supporting dynamic routing based on path parameters and validating requests using the canonical schema file `db_schema.json`.

This service is designed to act as a **thin, schema-aware wrapper** over the DynamoDB backend to enable flexible, centralized, and secure access to all operational data in the jobsearch system.

## Design Principles

- **Generic Routing**: Dynamic table access via path parameters.
- **Schema Enforcement**: All incoming payloads are validated against `db_schema.json`.
- **Minimal Endpoints**: A small set of HTTP routes supports all CRUD and batch operations.
- **Modular**: Tables can be added/updated without code changes.
- **Internal Use**: This API is intended for trusted internal services (e.g., ingestion, screening, CRM).
- **API Gateway Thin Infra wrapper** use API gateway as a thin infrastructure wrapper, leave most of the implementation to the main `jobdb` api app. 

## Route Definitions

__Single Record Operations__

| Method | Path                    | Description                 |
|--------|-------------------------|-----------------------------|
| GET    | `/[table]/{id}`         | Fetch item by primary key   |
| PUT    | `/[table]/{id}`         | Replace existing item       |
| DELETE | `/[table]/{id}`         | Delete item by primary key  |

__Bulk Operations__

| Method | Path                     | Description                                |
|--------|--------------------------|--------------------------------------------|
| POST   | `/[table]`               | Create a new item                          |
| POST   | `/[table]/batch`         | Create or update multiple items            |
| GET    | `/[table]/search`        | Query items using secondary keys           |
| POST   | `/[table]/delete`        | Delete multiple items (by key list)        |

## Path Parameters

| Param       | Type   | Description                     |
|-------------|--------|---------------------------------|
| `table`     | string | Target table name from schema   |
| `id`        | string | Primary key value               |

## Body Format

### POST /[table]
sample body for POST `/{job}` request

request
```json
{
  "posted_date": "2025-08-01",
  "position": "Data Engineer",
  "url": "https://example.com/jobs/abc123",
  ...
}
```

response body
```json
{
    "status": 1,
    "ids": ["abc123"]
}

```

### POST /[table]/batch
sample body for batch POST `/{job}/batch` request

request
```json
[
  {
      "posted_date": "2025-08-02",
      "position": "ML Engineer",
      "load_status": 0
  },
  {
      "posted_date": "2025-08-05",
      "position": "Data Analyst",
      "load_status": 0
  }
]
```

response body
```json
[
  {
      "id": "job_0000001",
      "posted_date": "2025-08-02",
      "position": "ML Engineer",
      "load_status": 0
  },
  {
      "id": "job_0000002",
      "posted_date": "2025-08-05",
      "position": "Data Analyst",
      "load_status": 0
  }
]
```
## DynamoDB

**table name prefix** to uniquely identify the DynamoDB tables in the account, table names include a prefix for `<env>_mcfpipe_`, so the full DynamoDB table name is `<env>_mcfpipe_<table_name>`. Since the API requests and responses are based on the base `table_name`, the full path to the DDB resource must be resolved by the API handler.

## Search

**GET** `/{table}/search`

- **table must exist** in `db_schema.json`.
- **Primary (partition) key** queries are available on any table
- **Global Secondary Indexes (GSI)** extend search to other declared columns.

### Global Secondary Indexes (GSI)

- the GSI must be declared in the DynamoDB table definition
- DynamoDB requires an `IndexName` for non-PK queries; this API exposes a thin, validated façade over `Query`.

__GSI specification__

_Data model_

GSI specification for `job` table in the data model `docs/data_model.md`

```md
### Table: job

...

__Global Secondary Indexes__

| id | Partition key   | Sort key | Projection  | Purpose |
|----|----------|----------|----|-------|
| 01 | user_id  | id | INCLUDE [post_id, position, company_name, posted_date, url] | Per-user timeline & list (newest-first)   |
| 02 | post_id  | id | KEYS_ONLY  | Dedupe / fetch job by post |
| 04 | user_id  | company_name | KEYS_ONLY  | Filter a user’s jobs by company |
| 05 | user_id  | position | KEYS_ONLY  | Filter a user’s jobs by position |

```

_DB schema JSON_

GSI specification for `job` table in the DB schema JSON file `storage/db_schema.json`

```json
{
  "table_name": "job",
  ...
  "secondary_indexes": {
    "global": [
      { "partition_key": "user_id", "sort_key": "created", "projection": {"type": "INCLUDE", "attributes": ["post_id", "position", "company_name", "posted_date", "url"]}},
      { "partition_key": "post_id", "sort_key": "id", "projection": {"type": "KEYS_ONLY"}},
      { "partition_key": "user_id", "sort_key": "company_name", "projection": {"type": "KEYS_ONLY" }},
      { "partition_key": "user_id", "sort_key": "position", "projection": {"type": "KEYS_ONLY" }}
    ]
  }
}

```

_DynamoDB resource in CF Template_

GSI specification for `job` DynamoDB table resource in the CloudFormation template `aws/cloudformation/db_api_stack.yaml`

```yaml
Resources:
  JobTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: job
      BillingMode: PAY_PER_REQUEST
       ...
      GlobalSecondaryIndexes:
        - IndexName: gsi_user_id_created
          KeySchema:
            - AttributeName: user_id
              KeyType: HASH
            - AttributeName: created
              KeyType: RANGE
          Projection:
            ProjectionType: INCLUDE
            NonKeyAttributes:
              - post_id
              - position
              - company_name
              - posted_date
              - url
        - IndexName: gsi_post_id_id
          KeySchema:
            - AttributeName: post_id
              KeyType: HASH
            - AttributeName: id
              KeyType: RANGE
          Projection:
            ProjectionType: KEYS_ONLY
        - IndexName: gsi_user_id_company_name
          KeySchema:
            - AttributeName: user_id
              KeyType: HASH
            - AttributeName: company_name
              KeyType: RANGE
          Projection:
            ProjectionType: KEYS_ONLY
        - IndexName: gsi_user_id_position
          KeySchema:
            - AttributeName: user_id
              KeyType: HASH
            - AttributeName: position
              KeyType: RANGE
          Projection:
            ProjectionType: KEYS_ONLY

```

__specification mapping JSON to YAML__

GSI mapping method in `generate_table_resource()` function in python constructor `jobdb/cf_template_constructor.py`

```python
def generate_table_resource(table, table_prefix: str=''):
    stem_name = table.get('table_name', '')
    table_name = f'{table_prefix}{stem_name}' if table_prefix else stem_name
    logical_name = f"{to_cfn_logical_id(stem_name)}Table"
    ...

    # GSIs
    gsi_list = []
    for gsi in table.get("secondary_indexes", {}).get("global", []):
        gpk = gsi["partition_key"]
        gsk = gsi.get("sort_key")
        gpk_dtype = next(c for c in table["columns"] if c["column_name"] == gpk)["data_type"]
        ensure_attr(gpk, gpk_dtype)
        if gsk:
            gsk_dtype = next(c for c in table["columns"] if c["column_name"] == gsk)["data_type"]
            ensure_attr(gsk, gsk_dtype)

        index_name = f"gsi_{gpk}" + (f"_{gsk}" if gsk else "")

        # projection handling
        proj = gsi.get("projection", "ALL")
        proj_type = proj["type"] if isinstance(proj, dict) else str(proj)
        proj_block = {"ProjectionType": proj_type}

        if isinstance(proj, dict) and proj_type.upper() == "INCLUDE":
            attrs = proj.get("attributes", [])
            # DynamoDB limit is 20 non-key attributes for INCLUDE
            if len(attrs) > 20:
                raise ValueError(f"{table_name}:{index_name} INCLUDE has >20 attributes")
            proj_block["NonKeyAttributes"] = attrs

        gsi_entry = {
            "IndexName": index_name,
            "KeySchema": [{"AttributeName": gpk, "KeyType": "HASH"}],
            "Projection": proj_block
        }
        if gsk:
            gsi_entry["KeySchema"].append({"AttributeName": gsk, "KeyType": "RANGE"})

        gsi_list.append(gsi_entry)

    props = {
        "TableName": table_name,
        "BillingMode": "PAY_PER_REQUEST",
        "AttributeDefinitions": attr_defs,
        "KeySchema": key_schema
    }
    if gsi_list:
        props["GlobalSecondaryIndexes"] = gsi_list

```

## Deployment Resources

### API Gateway + Lambda (Private)

- **Isolation**: Both API Gateway and the Lambda function run inside the VPC private subnets.  
  - They are **not directly reachable from the public internet**.  
  - Access is restricted to internal services (e.g., tester Fargate, other backend modules) via VPC endpoints and security groups.
- **Routing strategy**: API Gateway acts only as a thin wrapper, forwarding all HTTP methods to Lambda.  
  - A catch-all `{proxy+}` route is configured to pass requests through to the handler.  
  - Request validation, routing, and schema checks are implemented inside the `jobdb` application.
- **Execution environment**: Lambda runs from a Docker image hosted in Amazon ECR 
  - This allows bundling Python dependencies and the `jobdb` app into a single immutable image.
- **Logging**: Log output is automatically forwarded to CloudWatch Logs.

### Compute: Docker Image in ECR

The DB API Lambda function executes inside a container built from the following image:

- **Base image**: [`public.ecr.aws/lambda/python:3.12`](https://gallery.ecr.aws/lambda/python)  
  Provides AWS Lambda runtime with Python 3.12 preinstalled.
- **Build contents**:  
  - Installs dependencies from `jobdb/requirements.txt`.  
  - Copies application source under `jobdb/*` including `handler.py`.  
  - Exposes entry point: `handler.lambda_handler`.  
- **Versioning**:  
  - Image is tagged by GitHub Actions with the short commit SHA.  
  - Each commit to the repo refreshes the image and triggers redeployment.  
  - Old image versions are retained in ECR unless pruned by a cleanup workflow.

