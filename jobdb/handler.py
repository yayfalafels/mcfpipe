#!/usr/bin/env python3
"""Lambda entrypoint for jobdb API.

Wires together the config-driven router with the DB engine and domain hooks.
Follows docs/database_api/design.md.
"""

import json
import os
import datetime
from typing import Any, Dict

# Constants -------------------------------------------------------------------------------
APP_NAME = 'mcfpipe-dbapi'
VERSION_FILE = 'VERSION'

# Env -------------------------------------------------------------------------------------
ENV_STAGE = os.getenv('ENV_STAGE', 'dev')
AWS_REGION = os.getenv('AWS_REGION', os.getenv('AWS_DEFAULT_REGION', ''))
GITHUB_SHA = os.getenv('GITHUB_SHA', '')[:7]


def _get_version() -> str:
    v = os.getenv('VERSION')
    if v:
        return v
    try:
        here = os.path.dirname(__file__)
        with open(os.path.join(here, 'VERSION'), 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception:
        return '0.0.0-dev'


def _utcnow_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds') + 'Z'


# Lazy import after cold start for faster init ------------------------------------------------
_ENGINE = None
_ROUTER = None


def _bootstrap():
    global _ENGINE, _ROUTER
    if _ENGINE is None:
        from jobdb.core.engine import DBEngine
        _ENGINE = DBEngine(app_name=APP_NAME, version=_get_version(), stage=ENV_STAGE, region=AWS_REGION, commit=GITHUB_SHA)
    if _ROUTER is None:
        from jobdb.core.router import Router
        _ROUTER = Router(engine=_ENGINE)


def _about() -> Dict[str, Any]:
    return {
        'service': APP_NAME,
        'version': _get_version(),
        'stage': ENV_STAGE,
        'region': AWS_REGION,
        'commit': GITHUB_SHA,
        'time_utc': _utcnow_iso(),
    }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    _bootstrap()

    # Normalize minimal API Gateway proxy shape
    method = event.get('httpMethod') or event.get('requestContext', {}).get('http', {}).get('method', 'GET')
    path = event.get('path') or event.get('rawPath') or '/'

    if path in ('/', '') and method in ['GET', 'HEAD']:
        # Root: version payload
        return _ROUTER.responses.json(200, _about())

    # Delegate to config-driven router
    return _ROUTER.dispatch(event, context)
