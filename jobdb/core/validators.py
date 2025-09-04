#!/usr/bin/env python3
from typing import Any, Dict, List, Tuple


_TYPE_MAP = {
    'String': str,
    'Number': (int, float),
    'Boolean': bool,
}


class Validator:
    def __init__(self, table_spec: Dict[str, Any]):
        self.table = table_spec
        cols = table_spec.get('columns', [])
        self.columns = {c['column_name']: c for c in cols}
        self.pk = table_spec.get('primary_key')
        self.sk = table_spec.get('sort_key')

    def check_item(self, item: Dict[str, Any], mode: str = 'create') -> Tuple[bool, List[str]]:
        errs: List[str] = []
        # Required fields
        for name, col in self.columns.items():
            if not col.get('nullable') and mode == 'create':
                if name not in item or item.get(name) is None:
                    errs.append(f"missing_required:{name}")
        # Types
        for name, val in item.items():
            spec = self.columns.get(name)
            if not spec:
                # Allow extra attributes for now, can restrict via policies later
                continue
            dtype = spec.get('data_type')
            if dtype in _TYPE_MAP and val is not None and not isinstance(val, _TYPE_MAP[dtype]):
                errs.append(f"invalid_type:{name}:{dtype}")
        return (len(errs) == 0, errs)

