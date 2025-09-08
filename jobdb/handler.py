#!/usr/bin/env python3
"""Lambda entrypoint for jobdb API.

Wires together the config-driven router with the DB engine and domain hooks.
Follows docs/database_api/design.md.
"""

# dependencies ---------------------------------------------------------------------------
import os
import sys
import json
import logging
from typing import Any, Dict
from .jobdb.core.engine import DBEngine
from .jobdb.core.router import Router
from .jobdb.core.logging import init_logging


# constants ----------------------------------------------------------------------------------
APP_NAME = 'mcfpipe-dbapi'
VERSION_FILE = 'VERSION'


# environment variables ----------------------------------------------------------------------
LOGGING_LEVEL = os.getenv('LOGGING_LEVEL', 'INFO')
ENV_STAGE = os.getenv('ENV_STAGE', 'dev')
AWS_REGION = os.getenv('AWS_REGION', os.getenv('AWS_DEFAULT_REGION', ''))
GITHUB_SHA = os.getenv('GITHUB_SHA', '')[:7]


# module variables ----------------------------------------------------------------------------
_ENGINE = None
_ROUTER = None


# helper functions ----------------------------------------------------------------------------------
def _get_version() -> str:
    v = os.getenv(VERSION_FILE)
    if v:
        return v
    try:
        here = os.path.dirname(__file__)
        with open(os.path.join(here, VERSION_FILE), 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception:
        return '0.0.0-dev'


# initialization --------------------------------------------------------------------------------
def _bootstrap():
    global _ENGINE, _ROUTER
    if _ENGINE is None:
        init_logging(
            level=LOGGING_LEVEL,
            service=APP_NAME,
            stage=ENV_STAGE,
            version=_get_version(),
        )

        _ENGINE = DBEngine(
            app_name=APP_NAME, version=_get_version(), 
            stage=ENV_STAGE, region=AWS_REGION, commit=GITHUB_SHA
        )
        
    if _ROUTER is None:
        _ROUTER = Router(engine=_ENGINE)


def lambda_handler(event, context):
    sys.stdout.write("STDOUT_MARK\n"); sys.stdout.flush()
    sys.stderr.write("STDERR_MARK\n"); sys.stderr.flush()
    return {"statusCode": 200, "headers": {"content-type": "application/json"}, "body": json.dumps({"ok": True})}


# entry point -------------------------------------------------------------------------------------
def _lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    print("TEST. Handling request .. ")
    try:
        _bootstrap()
    except Exception as e:
        ex_msg = f"Unhandled at handler: {type(e).__name__}"
        return _ROUTER.fail({'path': '/', 'httpMethod': 'GET'}, context, 500, "internal_error", ex_msg) 
    else:
        logging.info(f'post boostrap, handling request...')
        if not isinstance(event, dict):
            ex_msg = "Event must be a JSON object"
            return _ROUTER.fail({'path': '/', 'httpMethod': 'GET'}, context,  400, "bad_request", ex_msg)

        # Normalize method/path across REST/HTTP API shapes
        method = (event.get("httpMethod")
                  or event.get("requestContext", {}).get("http", {}).get("method"))
        path = (event.get("path")
                or event.get("rawPath")
                or "/")

        if not method or not isinstance(method, str):
            ex_msg = f"Missing or invalid HTTP method {method}"
            return _ROUTER.fail({"path": path or "/", "httpMethod": method or ""}, context,  400, "bad_request", ex_msg)

        if not isinstance(path, str):
            ex_msg = f"Invalid path: {path}"
            return _ROUTER.fail({"path": "/", "httpMethod": method}, context, 400, "bad_request", ex_msg)

        if event.get("isBase64Encoded") and event.get("body") is None:
            ex_msg = "isBase64Encoded=True but body is null"
            return _ROUTER.fail({"path": path, "httpMethod": method}, context, 400, "bad_request", ex_msg)

        # else
        return _ROUTER.dispatch({"httpMethod": method, "path": path, **event}, context)
