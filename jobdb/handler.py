#!/usr/bin/env python3
# jobdb/handler.py

# dependencies -------------------------------------------------------------------------------
import json
import os
import datetime

# trigger


# constants -------------------------------------------------------------------------------
APP_NAME = 'mcfpipe-dbapi'
VERSION_FILE = 'VERSION'


# env variables ----------------------------------------------------------------------------
LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG')
S3_BUCKET = os.getenv('S3_BUCKET', 'mcfpipe')
DB_SCHEMA_S3_PATH = os.getenv('DB_SCHEMA_S3', 'storage/db_schema.json')
ENV_STAGE = os.getenv('ENV_STAGE', 'dev')
AWS_REGION = os.getenv('AWS_REGION', os.getenv('AWS_DEFAULT_REGION', ''))
GITHUB_SHA = os.getenv('GITHUB_SHA', '')[:7]


# helper functions -------------------------------------------------------------------------
def _get_version() -> str:
    # Prefer env injected by CF/GHA; fall back to bundled VERSION file; default to dev tag
    v = os.getenv('VERSION')
    if v:
        return v
    try:
        # If you package the repo root VERSION file into the zip
        here = os.path.dirname(__file__)
        with open(os.path.join(here, '..', VERSION_FILE), 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception:
        return '0.0.0-dev'

def _json(status: int, body: dict, headers: dict | None = None):
    h = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-store',
    }
    if headers:
        h.update(headers)
    response = {
        'statusCode': status, 
        'headers': h, 
        'body': json.dumps(body)
    }
    return response


def get_utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds') + 'Z'


# main handler ---------------------------------------------------------
def lambda_handler(event, context):
    now_timestamp = get_utcnow()
    method = event.get('httpMethod', 'GET')
    path   = event.get('path', '/')

    # 1) About/version on root
    if path in ('/', '') and method in ['GET', 'HEAD']:
        body = {
            'service': APP_NAME,
            'version': _get_version(),
            'stage': ENV_STAGE,
            'region': AWS_REGION,
            'commit': GITHUB_SHA,
            'time_utc': now_timestamp,
            'routes': [
                '/{table}/{id}',
                '/{table}',
                '/{table}/batch',
                '/{table}/search',
                '/{table}/delete',
            ],
        }
        return _json(200, body)

    # 2) Simple health endpoint
    if path in ['/health', '/healthz'] and method == 'GET':
        return _json(200, {"ok": True})

    # 3) Fall through to your existing router (replace with your dispatcher)
    # from .app import handle  # if you already have an app router
    # return handle(event, context)

    # Temporary 404 if you haven't wired the router yet:
    return _json(404, {"error": "Not Found", "path": path, "method": method})
