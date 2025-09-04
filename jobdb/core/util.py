#!/usr/bin/env python3
import base64
import json
from typing import Any, Dict, Tuple


def parse_json_body(event: Dict[str, Any]) -> Tuple[Dict[str, Any], str | None]:
    body = event.get('body')
    if not body:
        return {}, None
    if event.get('isBase64Encoded'):
        body = base64.b64decode(body).decode('utf-8')
    try:
        return json.loads(body), None
    except Exception as e:
        return {}, f'invalid_json: {e}'


def parse_query(event: Dict[str, Any]) -> Dict[str, Any]:
    # Supports both REST and HTTP API Gateway shapes
    q = event.get('queryStringParameters') or {}
    if q is None:
        q = {}
    return q


def b64e(s: str) -> str:
    return base64.b64encode(s.encode('utf-8')).decode('ascii')


def b64d(s: str) -> str:
    return base64.b64decode(s.encode('ascii')).decode('utf-8')


def norm_path(p: str) -> str:
    if not p:
        return '/'
    if p != '/' and p.endswith('/'):
        return p[:-1]
    return p

