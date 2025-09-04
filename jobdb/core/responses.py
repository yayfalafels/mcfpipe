#!/usr/bin/env python3
import json
from typing import Any, Dict, Optional


def json_resp(status: int, body: Any, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    h = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-store',
    }
    if headers:
        h.update(headers)
    return {
        'statusCode': status,
        'headers': h,
        'body': json.dumps(body, separators=(',', ':'), ensure_ascii=False),
    }


def error(status: int, code: str, message: str, request_id: str | None = None, hint: str | None = None, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    body = {
        'status': status,
        'error': code,
        'message': message,
    }
    if request_id:
        body['request_id'] = request_id
    if hint:
        body['hint'] = hint
    if details:
        body['details'] = details
    return json_resp(status, body)


class Responses:
    json = staticmethod(json_resp)
    error = staticmethod(error)

