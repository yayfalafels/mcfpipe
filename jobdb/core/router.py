#!/usr/bin/env python3
import json
import os
import re
from typing import Any, Dict, List, Optional

from .responses import Responses
from .util import parse_json_body, parse_query, norm_path


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

    def _load_routes(self):
        here = os.path.dirname(__file__)
        cfg_path = os.path.join(os.path.dirname(here), 'config', 'routes.json')
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        self.routes = [Route(r['name'], r['method'], r['path'], r['op']) for r in cfg.get('routes', [])]

    def dispatch(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        method = (event.get('httpMethod') or event.get('requestContext', {}).get('http', {}).get('method', 'GET')).upper()
        path = norm_path(event.get('path') or event.get('rawPath') or '/')
        request_id = (event.get('requestContext') or {}).get('requestId') or (event.get('headers') or {}).get('x-amzn-requestid')

        for r in self.routes:
            params = r.match(method, path)
            if params is None:
                continue
            try:
                if r.op == 'health':
                    return self.responses.json(200, {'success': True})
                if r.op == 'reload':
                    data = self.engine.reload()
                    return self.responses.json(200, {'reloaded_at': data.get('reloaded_at')})
                if r.op == 'version':
                    return self.responses.json(200, {'service': self.engine.app_name, 'version': self.engine.version, 'stage': self.engine.stage})

                logical = params.get('table')
                if not logical:
                    return self.responses.error(400, 'bad_request', 'missing table', request_id=request_id)
                table = self.engine.table(logical)
                if not table:
                    return self.responses.error(404, 'not_found', f'table {logical} not found', request_id=request_id)

                # Body / query
                body, body_err = parse_json_body(event)
                query = parse_query(event)

                if r.op == 'get':
                    id_val = params.get('id')
                    sk_val = query.get('sk') or query.get(table.sk) if table.sk else None
                    item = table.get(id_val, sk_val)
                    if not item:
                        return self.responses.error(404, 'not_found', f'item not found in {logical}', request_id=request_id)
                    return self.responses.json(200, item)

                if r.op == 'create':
                    if body_err:
                        return self.responses.error(400, 'validation_error', body_err, request_id=request_id)
                    res = table.create(body)
                    return self.responses.json(201, res)

                if r.op == 'put':
                    if body_err:
                        return self.responses.error(400, 'validation_error', body_err, request_id=request_id)
                    id_val = params.get('id')
                    sk_val = query.get('sk') or query.get(table.sk) if table.sk else None
                    res = table.put(id_val, body, sk_val)
                    return self.responses.json(200, res)

                if r.op == 'delete':
                    id_val = params.get('id')
                    sk_val = query.get('sk') or query.get(table.sk) if table.sk else None
                    res = table.delete(id_val, sk_val)
                    return self.responses.json(200, res)

                if r.op == 'batch_write':
                    items = body.get('items') if isinstance(body, dict) else body
                    if not isinstance(items, list):
                        return self.responses.error(400, 'validation_error', 'expected list of items', request_id=request_id)
                    res = table.batch_write(items)
                    return self.responses.json(200, res)

                if r.op == 'batch_delete':
                    keys = body.get('keys') if isinstance(body, dict) else body
                    if not isinstance(keys, list):
                        return self.responses.error(400, 'validation_error', 'expected list of keys/ids', request_id=request_id)
                    res = table.batch_delete(keys)
                    return self.responses.json(200, res)

                if r.op == 'search':
                    res = table.search(query)
                    return self.responses.json(200, res)

            except ValueError as ve:
                return self.responses.error(400, 'validation_error', str(ve), request_id=request_id)
            except Exception as e:
                return self.responses.error(500, 'internal_error', 'unexpected_error', request_id=request_id, details={'error': str(e)})

        return self.responses.error(404, 'not_found', f'route {method} {path} not found', request_id=request_id)

