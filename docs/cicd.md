# CICD
Deployment from source code

## CICD resources

- **Github repository**: [mcfpipe](https://github.com/yayfalafels/mcfpipe) source code storage
- **Github Actions**: deployment engine
- **AWS CloudFormation**: IaC templates for managing cloud infrastructure on AWS

## repository layout
the repository files are organized in the following structure

/root
```
.github/
  workflows/            # github deploy actions
     ...
aws/                    # cloudformation templates and specifications for AWS infrastructure
  dynamodb/
    ...
  ecr/
    ...
  fargate/
    ...
  lambda/
    ...
  s3/
    ...
compute/                # source code and config for compute resources
  webscraper/
    ...
dev/
  releases/             # documentation for each release
    ...
docs/                   # app documentation
  ...
jobsearch/              # legacy app source code
  ...
gsheetui/               # Gsheet connector using Google Sheets API
  gsheet/
    __init__.py
    ...
  gsheet_schema.json
  api_config.json
  requirements.txt
mcfparse/              # HTML Parser python module source code
  mcfparse/
    __init__.py
    parser.py
    ...
  requirements.txt
mcfscrape/              # Webscraper python module source code
  mcfscrape/
    __init__.py
    webscraper.py
    ...
  requirements.txt
jobcrm/                 # CRM Backend API
  app/
    __init__.py
  requirements.txt
  ...
jobmatch/                 # Job recommendation python module
  jobmatch/
    __init__.py
  requirements.txt
  ...
jobpipe/                 # Analytics ETL python module
  jobpipe/
    __init__.py
  requirements.txt
  ...
storage/                # schema and config for storage resources
  search_profile/
    ...
  jobs/
    ...  
.gitignore
AGENTS.md               # instructions for Developer AI assistants
LICENSE
mkdocs.yml
requirements.txt
VERSION
```

__excluded__
files and directories excluded from the source code from `.gitignore`

.gitignore
```
env
site
.env
```
