# Database API

The `Database API` provides a RESTful interface for CRUD operations on DynamoDB tables defined in the system data model. The API is implemented as a **generic Lambda function** behind API Gateway, supporting dynamic routing based on path parameters and validating requests using the canonical schema file `db_schema.json`.

This service is designed to act as a **thin, schema-aware wrapper** over the DynamoDB backend to enable flexible, centralized, and secure access to all operational data in the jobsearch system.

## Design Principles

- **Generic Routing**: Dynamic table access via path parameters.
- **Schema Enforcement**: All incoming payloads are validated against `db_schema.json`.
- **Minimal Endpoints**: A small set of HTTP routes supports all CRUD and batch operations.
- **Modular**: Tables can be added/updated without code changes.
- **Internal Use**: This API is intended for trusted internal services (e.g., ingestion, screening, CRM).


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

