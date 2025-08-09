# Database API

release documentation `docs/releases/011_dbapi.md`

## Session Logs

session logs are timestamped to Singapore timezone in reverse chronological order, with latest entries at the top, and earlier entries at the bottom.

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
