#!/usr/bin/env python3
# dependencies --------------------------------------------------------------------------------
import logging

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from .responses import Responses
from .util import parse_json_body, parse_query, norm_path


# constants --------------------------------------------------------------------------------
ROUTES_JSON_FILE = 'routes.json'
META_METHODS = [
    'meta.version', 'engine.health', 'engine.reload'
]
TABLE_CRUD_METHODS = [
    'get', 'create', 'put', 'delete',
    'batch_write', 'batch_delete', 'search'
]

# dynamic variables ----------------------------------------------------------------------
log = logging.getLogger()


# helper methods ------------------------------------------------------------------------
def _infer_items_count(payload: Any) -> int:
    """
    Best-effort count of items in a response payload for logging/metrics.

    Rules (first match wins):
    - list/tuple/set            -> len(container)
    - dict with 'items' (list)  -> len(items)                   # e.g., search
    - dict with 'success' (list)-> len(success)                 # e.g., batch write/delete
    - dict with numeric 'count' -> count                        # if caller precomputed
    - dict with single object   -> 1 if it looks like a single item/id response
                                  (keys like 'id', 'pk', table-specific primary key,
                                   or common aliases: 'item', 'Item')
    - anything else / None      -> 0

    NOTE: This never iterates generators to avoid side-effects.
    """
    if payload is None:
        return 0

    # Plain collections
    if isinstance(payload, (list, tuple, set)):
        return len(payload)

    # Dict-like envelopes
    if isinstance(payload, dict):
        # common paged/search shape
        items = payload.get("items")
        if isinstance(items, list):
            return len(items)

        # batch result shape
        success = payload.get("success")
        if isinstance(success, list):
            return len(success)
        if isinstance(success, int):
            return success

        # explicit count if provided
        count = payload.get("count")
        if isinstance(count, int):
            return count

        # single-object heuristics (create/get/put/delete)
        # - obvious keys for “one thing”
        single_keys = {"id", "pk", "item", "Item"}
        if single_keys & set(payload.keys()):
            return 1

        # fallback: if there appears to be exactly one non-empty scalar-ish entry
        # (avoid miscounting composite/list values)
        scalar_like = 0
        for v in payload.values():
            if v is None:
                continue
            if isinstance(v, (list, tuple, set, dict)):
                continue
            scalar_like += 1
            if scalar_like > 1:
                break
        if scalar_like == 1:
            return 1

    # Unknown shape
    return 0


def _status_of(response: Any, default: int = 200) -> int:
    """Extract HTTP statusCode from an APIGW-style response dict, else default."""
    if isinstance(response, dict):
        sc = response.get("statusCode")
        if isinstance(sc, int):
            return sc
    return default


# classes --------------------------------------------------------------------------------
class Route:
    def __init__(self, name: str, method: str, path: str, op: str):
        self.name = name
        self.method = method.upper()
        self.path = path
        self.op = op
        # Convert template to regex
        pat = re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", r"(?P<\1>[^/]+)", path)
        self.regex = re.compile(f"^{pat}$")

    def match(self, method: str, path: str) -> Optional[Dict[str, str]]:
        if method.upper() != self.method:
            return None
        m = self.regex.match(path)
        if not m:
            return None
        return m.groupdict()


class Router:
    def __init__(self, engine):
        self.engine = engine
        self.responses = Responses()
        self.routes: List[Route] = []
        self._load_routes()

    # ---------- logging helpers ----------
    def _log_success(
        self,
        response: Dict[str, Any],
        request_id: Optional[str],
        method: str,
        path: str,
        route_obj: Route,
        payload: Any,
        params: Optional[dict],
        t0: float,
    ) -> None:
        duration_ms = int((time.time() - t0) * 1000)
        status = _status_of(response, 200)
        items_count =  _infer_items_count(payload)
        log.info(
            "request_complete",
            extra={
                "request_id": request_id,
                "method": method,
                "path": path,
                "route": getattr(route_obj, "name", ""),
                "table": (params or {}).get("table", ""),
                "op": getattr(route_obj, "op", ""),
                "status": status,
                "duration_ms": duration_ms,
                "items_count": items_count,
            },
        )

    def _error_handle(
        self,
        status: int,
        code: str,
        message: str,
        request_id: Optional[str],
        method: str,
        path: str,
        route: str = "",
        table: Optional[str] = None,
        op: Optional[str] = None,
        t0: float = 0,
        details: Optional[dict] = None,
        with_stack: bool = False,
    ) -> Dict[str, Any]:
        duration_ms = int((time.time() - t0) * 1000)
        log.error(
            "request_error",
            extra={
                "request_id": request_id,
                "method": method,
                "path": path,
                "route": route,
                "table": table,
                "op": op,
                "status": status,
                "duration_ms": duration_ms,
                "error_code": code,
                **({"details": details} if details else {}),
            },
            exc_info=with_stack,
        )
        return self.responses.error(status, code, message, request_id=request_id, details=details)

    # ---------- routes ----------
    def _load_routes(self):
        here = os.path.dirname(__file__)
        cfg_path = os.path.join(os.path.dirname(here), 'config', ROUTES_JSON_FILE)
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        self.routes = [Route(r['name'], r['method'], r['path'], r['op']) for r in cfg.get('routes', [])]

    def _meta_engine(self, request_id, method, path, r, params, t0):

        if r.op not in META_METHODS:
            return self._error_handle(
                404, 'not_found', f'meta method {r.op} not found. allowed values {META_METHODS}',
                request_id, method, path, route=r.name, op=r.op, t0=t0,
            )

        if r.op == 'meta.version':
            payload = {'service': self.engine.app_name, 'version': self.engine.version, 'stage': self.engine.stage}
            resp = self.responses.json(200, payload)
            self._log_success(resp, request_id, method, path, r, payload, params, t0)
            return resp

        if r.op == 'engine.health':
            payload = {'success': True}
            resp = self.responses.json(200, payload)
            self._log_success(resp, request_id, method, path, r, payload, params, t0)
            return resp

        if r.op == 'engine.reload':
            data = self.engine.reload()
            payload = {'reloaded_at': data.get('reloaded_at')}
            resp = self.responses.json(200, payload)
            self._log_success(resp, request_id, method, path, r, payload, params, t0)
            return resp

    def _table_crud(self, logical, event, request_id, method, path, r, params, t0):
        if not logical:
            return self._error_handle(
                400, 'bad_request', 'missing table',
                request_id, method, path, route=r.name, table=None, op=r.op, t0=t0,
            )

        table = self.engine.table(logical)
        if not table:
            return self._error_handle(
                404, 'not_found', f'table {logical} not found',
                request_id, method, path, route=r.name, table=logical, op=r.op, t0=t0,
            )

        # Body / query
        try:
            crud_method = r.op.split('.')[1]
        except Exception as e:
            return self._error_handle(
                400, 'bad_request', f'bad request format. Could not parse table method after . from op table.<table_method>',
                request_id, method, path, route=r.name, table=logical, op=r.op, t0=t0,
            )
        
        try:
            body, body_err = parse_json_body(event)
            query = parse_query(event)
        except Exception as e:
            return self._error_handle(
                400, 'bad_request', f'error parsing parameters from request body. {e}',
                request_id, method, path, route=r.name, table=logical, op=r.op, t0=t0,
            )
        else:
            if body_err:
                return self._error_handle(
                    400, 'validation_error', body_err,
                    request_id, method, path, route=r.name, table=logical, op=r.op, t0=t0,
                )

        if crud_method not in TABLE_CRUD_METHODS:
            return self._error_handle(
                404, 'not_found', f' table method {crud_method} not found. allowed values {TABLE_CRUD_METHODS}',
                request_id, method, path, route=r.name, table=logical, op=r.op, t0=t0,
            )

        if crud_method == 'get':
            id_val = params.get('id')
            sk_val = (query.get('sk') or (query.get(table.sk) if getattr(table, 'sk', None) else None))
            item = table.get(id_val, sk_val)
            if not item:
                return self._error_handle(
                    404, 'not_found', f'item not found in {logical}',
                    request_id, method, path, route=r.name, table=logical, op=r.op, t0=t0,
                )
            payload = item
            resp = self.responses.json(200, payload)
            self._log_success(resp, request_id, method, path, r, payload, params, t0)
            return resp

        if crud_method == 'create':
            payload = table.create(body)
            resp = self.responses.json(201, payload)
            self._log_success(resp, request_id, method, path, r, payload, params, t0)
            return resp

        if crud_method == 'put':
            id_val = params.get('id')
            sk_val = (query.get('sk') or (query.get(table.sk) if getattr(table, 'sk', None) else None))
            payload = table.put(id_val, body, sk_val)
            resp = self.responses.json(200, payload)
            self._log_success(resp, request_id, method, path, r, payload, params, t0)
            return resp

        if crud_method == 'delete':
            id_val = params.get('id')
            sk_val = (query.get('sk') or (query.get(table.sk) if getattr(table, 'sk', None) else None))
            payload = table.delete(id_val, sk_val)
            resp = self.responses.json(200, payload)
            self._log_success(resp, request_id, method, path, r, payload, params, t0)
            return resp

        if crud_method == 'batch_write':
            items = body.get('items') if isinstance(body, dict) else body
            if not isinstance(items, list):
                return self._error_handle(
                    400, 'validation_error', 'expected list of items',
                    request_id, method, path, route=r.name, table=logical, op=r.op, t0=t0,
                )
            payload = table.batch_write(items)
            resp = self.responses.json(200, payload)
            self._log_success(resp, request_id, method, path, r, payload, params, t0)
            return resp

        if crud_method == 'batch_delete':
            keys = body.get('keys', []) if isinstance(body, dict) else body
            if not isinstance(keys, list):
                return self._error_handle(
                    400, 'validation_error', 'expected list of keys/ids',
                    request_id, method, path, route=r.name, table=logical, op=r.op, t0=t0,
                )
            payload = table.batch_delete(keys)
            resp = self.responses.json(200, payload)
            self._log_success(resp, request_id, method, path, r, payload, params, t0)
            return resp

        if crud_method == 'search':
            # Pass full query; Table.search() is responsible for mapping (index, pk/sk, filters, next)
            payload = table.search(query)
            resp = self.responses.json(200, payload)
            self._log_success(resp, request_id, method, path, r, payload, params, t0)
            return resp

    # ---------- dispatch ----------
    def dispatch(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        t0 = time.time()
        log.info(f'dispatching request from event {event}')

        method = (event.get('httpMethod', '') or event.get('requestContext', {}).get('http', {}).get('method', 'GET')).upper()
        path = norm_path(event.get('path', '') or event.get('rawPath', '') or '/')
        rc = event.get('requestContext', '') or {}
        request_id = rc.get('requestId', '') or (event.get('headers', '') or {}).get('x-amzn-requestid', '')

        for r in self.routes:
            params = r.match(method, path)
            if params is None:
                continue

            try:
                route_namespace = r.op.split('.')[0]

            except ValueError as ve:
                return self._error_handle(
                    400, 'validation_error', str(ve),
                    request_id, method, path, route=r.name, table=params.get('table'), op=r.op, t0=t0,
                )
            except Exception as e:
                return self._error_handle(
                    500, 'internal_error', 'unexpected_error',
                    request_id, method, path, route=r.name, table=params.get('table'), op=r.op, t0=t0,
                    details={'error': str(e)},
                    with_stack=True,
                )
            else:
                # ------ meta engine ------
                if route_namespace in ['meta', 'engine']:
                    log.info(f'dispatching to _meta_engine methods for op {r.op}')
                    return self._meta_engine(
                        request_id=request_id,
                        method=method,
                        path=path,
                        r=r,
                        params=params,
                        t0=t0                   
                    )

                # ------ table ops ------
                logical = params.get('table', '')
                if route_namespace in ['table']:
                    return self._table_crud(
                        logical,
                        event,
                        request_id=request_id,
                        method=method,
                        path=path,
                        r=r,
                        params=params,
                        t0=t0                   
                    )

                # Unknown op (matched path but unrecognized op)
                return self._error_handle(
                    500, 'internal_error', f'unhandled op {r.op}',
                    request_id, method, path, route=r.name, table=logical, op=r.op, t0=t0,
                )

        # No route matched
        return self._error_handle(
            404, 'not_found', f'route {method} {path} not found',
            request_id, method, path, route='', table=None, op=None, t0=t0,
        )

    # For handler guardrails (so handler doesn't call responses.error directly)
    def fail(self, event, context, status: int, code: str, message: str):
        req_id = getattr(context, "aws_request_id", None) or (event.get("requestContext", {}) or {}).get("requestId")
        method = event.get("httpMethod", "") or (event.get("requestContext", {}).get("http", {}) or {}).get("method", "")
        path = event.get("path") or event.get("rawPath") or "/"
        return self._error_handle(
            status, code, message,
            request_id=req_id, method=method, path=path,
            route="(handler-guard)", table=None, op=None, t0=0,
        )
