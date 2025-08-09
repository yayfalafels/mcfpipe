# Database API
release documentation `docs/releases/011_dbapi.md`

## Session Logs

session logs are timestamped to Singapore timezone in reverse chronological order, with latest entries at the top, and earlier entries at the bottom.

### CF stack [Codex] 2025-08-09 <HH>:<MM>


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
- switch to new branch `011_dbapi`w