#!/usr/bin/env python3
from typing import Any, Dict, Tuple
from boto3.dynamodb.conditions import Key, Attr


def build_key_condition(params: Dict[str, Any], pk_name: str, sk_name: str | None = None) -> Tuple[Any, Dict[str, Any]]:
    expr = None
    values: Dict[str, Any] = {}

    pk_val = params.get('pk') or params.get(pk_name)
    if pk_val is not None:
        expr = Key(pk_name).eq(pk_val)

    if sk_name:
        sk_val = params.get('sk') or params.get(sk_name)
        if sk_val is not None:
            expr = (expr & Key(sk_name).eq(sk_val)) if expr is not None else Key(sk_name).eq(sk_val)

    return expr, values


def build_filter(params: Dict[str, Any]) -> Any:
    filt = None
    # eq[field]=val, begins[field]=prefix
    for k, v in list(params.items()):
        if k.startswith('eq[') and k.endswith(']'):
            field = k[3:-1]
            cond = Attr(field).eq(v)
        elif k.startswith('begins[') and k.endswith(']'):
            field = k[7:-1]
            cond = Attr(field).begins_with(v)
        else:
            continue
        filt = cond if filt is None else (filt & cond)
    return filt

