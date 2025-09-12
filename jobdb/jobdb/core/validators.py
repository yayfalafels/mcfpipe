#!/usr/bin/env python3
"""input validation from user-supplied inputs
"""
# dependencies ----------------------------------------------------------------------------------------
from typing import Any, Dict, List, Tuple
import logging


log = logging.getLogger()


# constants -------------------------------------------------------------------------------------------
_SYSTEM_READONLY = ['id', 'created', 'last_modified']
_TYPE_MAP = {
    'String': str,
    'Number': (int, float),
    'Boolean': bool,
}


# classes -------------------------------------------------------------------------------------------
class Validator:
    def __init__(self, table_spec: Dict[str, Any]):
        self.table = table_spec
        cols = table_spec.get('columns', [])
        self.columns = {c['column_name']: c for c in cols}
        self.pk = table_spec.get('primary_key')
        self.sk = table_spec.get('sort_key')

    def _is_readonly(self, name: str) -> bool:
        spec = self.columns.get(name, {})
        return (
            name in _SYSTEM_READONLY
            or spec.get('readonly', False) is True
            or spec.get('auto', False) is True
        )

    def check_item(self, item: Dict[str, Any], mode: str = 'create') -> Tuple[bool, List[str]]:
        errs: List[str] = []
        log.info(f'checking item {item} compare to table spec {self.columns}')

        # 1) Disallow user-supplied readonly/system fields
        for name in item.keys():
            log.info(f'checking disallow rules: {name} is readonly? {self._is_readonly(name)}')
            if self._is_readonly(name):
                tag = 'readonly_field_update' if mode != 'create' else 'readonly_field_supplied'
                errs.append(f"{tag}:{name}")

        # 2) Required (on create): only for non-nullable fields that are NOT readonly/auto/system
        if mode == 'create':
            for name, col in self.columns.items():
                not_passed = name not in item or item.get(name) is None
                log.info(f'checking required fields rules: {name} is nullable? {col.get('nullable')} is readonly? {self._is_readonly(name)} not passed by user? {not_passed}')
                if col.get('nullable'):
                    continue
                elif self._is_readonly(name):
                    # server will populate these; don't require from user
                    continue
                elif not_passed:
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

