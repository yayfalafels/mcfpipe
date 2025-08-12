# Database API

release documentation `docs/releases/011_dbapi.md`

## Session Logs

session logs are timestamped to Singapore timezone in reverse chronological order, with latest entries at the top, and earlier entries at the bottom.

### GSI [Codex] 2025-08-12 16:37:07
- reviewed `docs/data_model.md` and removed outdated sort key for `post_details`
- expanded `storage/db_schema.json` with table schemas and declared GSI per data model

### GSI [Data Engineer] Codex prompt 2025-08-12 16:31

__situation__

The current version of the data model does not specify Global Secondary Indexes (GSI) for DynamoDB tables. The methodology for specifying and implementing GSI is described in the Database API doc `docs/database_api.md`.  

GSI have been specified in the data model, but have not been implemented into the db schema JSON file.

__scope__

 - data model `docs/data_model.md`
 - db schema JSON `storage/db_schema.json`

__task__

 - udpate db schema JSON for table specifications (name, partition key, sort key, column definitions) from the data model
 - update db schema JSON with the GSI attributes `"secondary_indexes": {...}` according to the specifications in the data model

### GSI [Data Engineer] JSON 2025-08-12 16:25
GSI specification methodology documentation `docs/database_api.md`

- data model table section
- DB Schema JSON, add new attribute `"secondary_indexes": {...}`
- CF Template YAML DynamoDB table
- CF template Python script constructor mapping method

CF Template YAML DynamoDB table

```yaml
        - IndexName: gsi_user_id_company_name
          KeySchema:
            - AttributeName: user_id
              KeyType: HASH
            - AttributeName: company_name
              KeyType: RANGE
```

### Agent [Data Engineer] update generic agent instructions 2025-08-12 15:38
update generic AGENTS.md instructions
 - task instructions for Codex
 - session log 
 - context navigation

### GSI [Data Engineer] Data model 2025-08-12 15:19

__GSI implementation__

_01 data model_
table-by-table updates for several considerations

- GSI
  - add GSI for common search, filter operations
- second pass at schema design
  - rationalize columns, place columns where they will be used most frequently
  - relaxed normalized considerations, duplicate columns from post -> job table

post
- migrated common columns [`salary_high_sgd`, `closing_date`] into `post`
- added `description` in `post_details`

job_track
- added GSI for jobs by track

job
- duplicate columns from post [`closing_date`, `salary_high_sgd`, etc..] migrate from `job_details` into `job`
- GSI user reports and user sorted by company and position
- add `status` in `job_details`

### GSI [Data Engineer] ChatGPT 2025-08-11 18:58
guided session GSI and search design with ChatGPT

### Documentation [Data Engineer] ChatGPT review 2025-08-10 19:20

__Open for followup__

1. implementation for 06 GSI
2. open follow-ups left over from last session
  -  `jobdb` app development
3. clean stack deploy cleanup `ROLLBACK_COMPLETE` status

__Issues__

_(closed) 01 PK type rule vs a table_
[ChatGPT] 
>Doc says PKs should be String (“Global patterns”), but post_source.id is Number in both docs and schema. Pick one rule and unify. 

_(closed) 02 Private subnet description_
[ChatGPT] 
>Network doc row for PrivateSubnetId says it has “a route to the IGW” (internet gateway). Private subnets should not route to an IGW. You’re using VPC endpoints (no NAT), which is correct—so fix that line. 

updated to read "private subnet: private subnet with no allowed inbound traffic the internet"

_(closed) 03 CICD repo layout_
[ChatGPT] 
>CICD doc mentions a jobcrm/ backend folder that isn’t in the repo today; mark it TBD or remove to avoid confusion.

this is intentional that CICD doc shows some organization not yet implemented

_(closed) 04 Route coverage vs API config_
[ChatGPT] 
>Docs list /[table]/search and /[table]/delete. Make sure API Gateway includes an ANY /{proxy+} resource or explicit routes for these; otherwise the handler won’t see them. 

_follow-up clarification prompt(s)_

[Developer]
>For item 04 "04 Route coverage vs API config" I don't catch what you mean, `/[table]/search` is listed in the doc `docs/database_api.md` Could you elaborate and explain what kinds of operations would fail in the current design and how adding the `ANY /{proxy+}` would help? What are the security implications of adding this feature?

(summary of conversation with ChatGPT)

-> Design choice: accept the ANY/{proxy+} proposal and use API gateway as a thin wrapper,  leave most of the implementation to the main `jobdb` api app. 

Ultimately a design choice of using API gateway vs the Lambda handler (app) for many of the app features such as routing, validation, error handling. Ultimately, go with the suggestion to use API Gateway as a thin wrapper and leave most of the implementation to the main `jobdb` api app. Some considerations for this choice 

1. CF not as ideal choice, managing version control in multiple locations (app + CF)
2. It's a backend DB, not exposed to internet already in a private subnet so risk is lower.

update snippet to CF file `aws/cloudformation/db_api_base.yaml`

```yaml
  # ANY on root "/"
  RootAnyMethod:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref RestApi
      ResourceId: !GetAtt RestApi.RootResourceId
      HttpMethod: ANY
      AuthorizationType: !Ref ApiAuthType
      Integration:
        Type: AWS_PROXY
        IntegrationHttpMethod: POST
        Uri: !Sub arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${DbLambda.Arn}/invocations

  # Catch-all /{proxy+}
  ProxyResource:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref RestApi
      ParentId: !GetAtt RestApi.RootResourceId
      PathPart: "{proxy+}"

  ProxyAnyMethod:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref RestApi
      ResourceId: !Ref ProxyResource
      HttpMethod: ANY
      AuthorizationType: !Ref ApiAuthType
      Integration:
        Type: AWS_PROXY
        IntegrationHttpMethod: POST
        Uri: !Sub arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${DbLambda.Arn}/invocations

```

_(closed) 05 ID generation language_
[ChatGPT] 
>“Auto-incremented UUID is a running MAX” is contradictory; decide: sequential (MAX+1) or UUID/ULID. For DynamoDB, favor ULID/KSUID to avoid hot partitions and racey “MAX” scans. 

_follow-up clarification prompt(s)_

[Developer]
>for item 05 "ID generation language" The motivation for using MAX+1 is to ensure uniqueness even after a record is deleted from the table.  Explain what you mean by "racey MAX scans" and how UUID/ULID/KSUID is different from MAX+1, a description of methods and comparison for how these methods would handle uniqueness after record deletion 

[ChatGPT] 
(relevant snippet from full response)
>UUIDv4 (random), ULID, KSUID (time-sortable)
>Method: IDs are generated client-side.
>UUIDv4: 128-bit random.
>ULID: 128-bit, first 48 bits timestamp (ms) + 80 bits randomness; lexicographically sortable >by time.
>KSUID: 160-bit, 32-bit timestamp (s) + 128-bit payload; also time-sortable.
>Uniqueness after deletion: Unaffected. You never consult existing rows, so deletes don’t >matter; the chance of collision is astronomically small (UUIDv4) or practically negligible (ULID/KSUID).
>Concurrency/scale: Excellent. No shared state, no scans, no lock. Horizontal scale “for free.”
>Ordering:
>- UUIDv4: not ordered.
>- ULID/KSUID: roughly time-ordered (nice for pagination and range queries).
>Partition heat: Good—high cardinality distribution if you use the ID as the partition key.
>- multiple mature libs (ulid-py, python-ulid, ulid-transform) and good cross-language parity (Go, JS/TS, Rust, etc.). Monotonic ULID support is common.

[Developer] 
>are there any implementation considerations for ULID vs KSUID, are either one more native either in python, boto3 or AWS DynamoDB?

[ChatGPT] 
>- 128-bit: first 48 bits = milliseconds. 
>- Lexicographic sort == chronological (ms). 
>- Many libs support monotonic ULIDs, if you generate multiple in the same ms, the random tail is incremented so sort order stays strictly increasing within one process.
>- 26 chars, Crockford Base32, uppercase alphabet without ambiguous chars (no I, L, O, U). 
>- Regex: ^[0-9A-HJKMNP-TV-Z]{26}$. Case-insensitive by spec, but store as uppercase to preserve lexical ordering semantics everywhere.

Design decision: take suggestion and update to ULID, doc `docs/data_model.md` updated accordingly

_(open) 06 Search/indexing gap_
[ChatGPT]
>Docs offer /[table]/search, but there’s no doc section mapping access patterns to GSIs per table. Add a table-by-table list of keys/GSIs that support your queries.

[Developer] 
>could you elaborate more about 06 "mapping access patterns to GSIs per table" what do you mean, what is "GSI" and keys in this context. Where would you apply the updates? Could you describe some situations that would fail with the current design, and how it would be improved with the update you are proposing?

_synopsis of ChatGPT response_

GSI, "Global Secondary Index" are user-defined is regarding query design, how the queries and search are implemented from user queries by non-PK columns, ex by user or by date range.

_summary of updates_ 

data model doc `docs/data_model.md`

```md
**GSI naming convention (global pattern):** use `gsi_<partitionkey>_<sortkey>` (omit `_<sortkey>` if none). Index names are not repeated in the per-table sections below.
```

```md

__Global Secondary Indexes__

| id | Partition key | Sort key      | Projection | Purpose                    |
| - |---------------|---------------|------------|----------------------------|
| 01 | user_id (S)   | created (S)   | ALL        | Per-user timeline (newest) |
| 02 | post_id (S)   | id (S)        | ALL        | Fetch job by post_id       |

```

example of updated GSI section in DynamoDB Table resource in CF stack template `aws/cloudformation/db_api_stack.yaml`.

Details of how the converter python script writes the resource section from the db schema JSON are documented in the updates to the converter script.

```yaml
      GlobalSecondaryIndexes:
        - IndexName: gsi_user_created
          KeySchema:
            - AttributeName: user_id
              KeyType: HASH
            - AttributeName: created
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
```

db schema `storage/db_schema.json`

```json
  "global_secondary_indexes": [
    {
      "index_name": "gsi_user_created",
      "partition_key": "user_id",
      "sort_key": "created",
      "projection": "ALL"
    }
  ]

```

example of how the GSI are used by the `jobdb` app python handler

```python
# Table primary index: PK = id
table.query(
    KeyConditionExpression=Key("id").eq(job_id)          # ✅ OK
)

# GSI: gsi_user_created (PK=user_id, SK=created_ulid)
table.query(
    IndexName="gsi_user_created",
    KeyConditionExpression=Key("user_id").eq(u) & Key("created_ulid").between(lo, hi),
    ScanIndexForward=False                                # ✅ OK (newest first)
)

```

### CF stack [Data Engineer] review 2025-08-09 19:10
dbapi GHA debugging

- now CF stack deploy step fails at expected breakpoint -> empty lambda zip payload
- follow-up to cleanup the stack deploy so it doesn't get tripped up on a previous stack rollback or create fail

__issues__

_(resolved) 01 CF stack logical resource name restrictions underscore not allowed_

 - CF stack resources don't allow underscores "_"
    - remove underscore in the constructor *.py
        - constructor refactor: `logical_name = table_name.replace("_", "").capitalize() + "Table"`

 - also applies to Output variables names

`jobdb/cf_template_constructor.py`

```python
def generate_table_resource(table):
    table_name = table["table_name"]
    logical_name = table_name.replace("_", "").capitalize() + "Table"
```

_(open) 02 idempotent deploy_

GHA fails if a previous stack deploy failed --> stack is in `ROLLBACK_COMPLETE` or `CREATE_FAILED` status

 - solution -> add a check 

 ChatGPT suggestion

 ```
Short answer: do it up front.

Pre-flight cleanup at the start of the deploy is safer and more deterministic:
If a previous create failed, the stack will be ROLLBACK_COMPLETE and can’t be updated. Deleting it before deploy avoids an immediate re-fail.
It keeps the main deploy path idempotent and avoids branching logic after a failure.
You can still make the step a no-op for healthy stacks (UPDATE_COMPLETE, CREATE_COMPLETE).

What I recommend:

Pre-check at the beginning

If status is ROLLBACK_COMPLETE or CREATE_FAILED → delete-stack + wait stack-delete-complete, then proceed with deploy.
Otherwise just deploy --no-fail-on-empty-changeset.
Keep a post-failure aid, not auto-delete
If deploy fails, run a tiny “diagnose” step to dump recent stack events and the template validation error, but don’t auto-delete. You’ll want the stack artifacts for debugging.

Guardrails

Only auto-delete when an env flag is set (e.g., ALLOW_STACK_DELETE=true) so you don’t nuke prod by accident.
Consider not auto-deleting UPDATE_ROLLBACK_COMPLETE (that stack is still usable) unless you really need to recreate.
Net: pre-flight cleanup + post-failure diagnostics gives you fast green paths and good debuggability without surprise deletions.

 ```

### CF stack [Data Engineer] review 2025-08-09 18:15
dbapi GHA review

 - network config load step to correctly parse the JSON
 - parameterize network config path and lambda app path
 - add output section to CF template to correctly pass `DB_API_URL`
 - validate commit and re-test GHA

__ChatGPT prompts__

_01 GHA fail: wrong JSON parse_

>update the GHA step "network_config" to correctly parse the network config JSON from the actual JSON format

- refactored the step from ChatGPT suggestion

_02 stack parameter DB URL clarification_

>would the artifact step fail in the GHA? where is DB_URL defined in the CF stack?

- added output section to cf template, after a couple of back-and-forth iterations

`aws/cloudformation/db_api_base.yaml`

```yaml
Outputs:
  DB_API_URL:
    Description: Base URL for the Database API Gateway
    Value: !Sub "https://${DatabaseAPI}.execute-api.${AWS::Region}.amazonaws.com/prod"
    Export:
      Name: !Sub "${AWS::StackName}-DB_API_URL"

```

### CF stack [Codex] 2025-08-09 17:28

- reviewed release docs and `cicd.md` for DB API workflow design
- noted discrepancies in skeleton GHA:
  - push trigger referenced `.github/workflows/db_api.yml` instead of `dbapi.yml`
  - environment variable `TEMPLATE_DIR` mismatched with `CF_TEMPLATE_DIR`
  - missing steps for schema upload, template generation, lambda packaging, and network config loading
  - CloudFormation templates lack outputs for `DB_API_URL`
  - repository uses branch `work` rather than documented `011_dbapi`
- implemented full workflow with parameterized steps for schema load, template generation, lambda packaging, stack deploy, and artifact upload
- verified formatting with `yamllint` and `mdformat`

### CF stack [Data Engineer] Codex prompt 2025-08-09 17:26

for context, refer to the reference docs

- release doc `docs/releases/011_dbapi.md`
- release session notes `dev/releases/011_dbapi.md`
- cicd doc `docs/cicd.md`
- other relevant sections of docs and source code as required

scope

- dbapi GHA `.github/workflows/dbapi.yml`

your task

- review the design from the reference docs and the current skeleton template version for dbapi GHA
- review for consistiency between documents and flag, document any discrepancies in your session log
- review the patterns and layout of the skeleton template dbapi GHA, in particular the parameter passing, step naming
- implement the dbapi GHA in full from design
- record your session activity as a timestamped session log in the release session notes with log header ### CF stack [Codex] 2025-08-09 <HH>:<MM>
- create a PR for the changes to the dbapi GHA and your session log

### CF stack [Data Engineer] 2025-08-09 17:14

github action workflow

- describe the steps for the github action workflow `.github/workflows/dbapi.yml`
- skeleton outline
- define parameters

documentation

- update release doc `docs/releases/011_dbapi.md`

### Release note [Data Engineer] 2025-08-08 21:15

- create new release note `dev/releases/011_dbapi.md`
- switch to new branch `011_dbapi`
