# CICD
Deployment from source code

## CICD resources

- **Github repository**: [mcfpipe](https://github.com/yayfalafels/mcfpipe) source code storage
- **Github Actions**: deployment engine
- **AWS CloudFormation**: IaC templates for managing cloud infrastructure on AWS
- **Tester App**: Tester module runs on a dedicated Fargate container in the public subnet

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
jobdb/                   # Database API
  db/
    __init__.py
  requirements.txt
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
tester/                # Tester app that runs on Fargate container
  tester/
    __init__.py
  tests.py
  requirements.txt
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

## S3 bucket layout

S3 bucket: `mcfpipe`
```
apps/                     # source code for apps
config/                   # setup infrastructure and app configuration
aws/                      # information for the AWS infrastructure
  network/
    network_config.json
  ecr/
    containers.json
storage/
  db_api.json             # endpoint access for database API
  db_schema.json
user_data/                # user-specific settings and configuration data
  user_#####/
    ...
```

## Tester
The tester app uses the test module `tester` and runs on a dedicated Fargate container

__docker image__


__environment variables__
environment variables are passed to the container by Github actions at the `run-task` cli command

| id | variable | description |
| - | - | - |
| 01 | DB_API_URL | API endpoint |


