#!/usr/bin/env python3
import os
import uuid
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key

from .validators import Validator


def _new_id() -> str:
    return uuid.uuid4().hex


class Table:
    def __init__(self, name: str, spec: Dict[str, Any], region: Optional[str] = None):
        self.logical_name = spec.get('table_name') or name
        self.name = name
        self.spec = spec
        self.validator = Validator(spec)
        self.pk = self.validator.pk
        self.sk = self.validator.sk
        self.region = region or os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION')
        self._resource = None
        self._table = None

    # Dynamo resource/table -------------------------------------------------
    def _dynamo(self):
        if self._resource is None:
            if self.region:
                self._resource = boto3.resource('dynamodb', region_name=self.region)
            else:
                self._resource = boto3.resource('dynamodb')
        if self._table is None:
            self._table = self._resource.Table(self.name)
        return self._table

    # CRUD ------------------------------------------------------------------
    def get(self, id_val: Any, sk_val: Any | None = None) -> Dict[str, Any] | None:
        if not self.sk:
            resp = self._dynamo().get_item(Key={self.pk: id_val})
            return resp.get('Item')
        if sk_val is None:
            # Without sort key, attempt to query by id and return first
            q = self._dynamo().query(KeyConditionExpression=Key(self.pk).eq(id_val), Limit=1)
            items = q.get('Items', [])
            return items[0] if items else None
        resp = self._dynamo().get_item(Key={self.pk: id_val, self.sk: sk_val})
        return resp.get('Item')

    def create(self, item: Dict[str, Any]) -> Dict[str, Any]:
        ok, errs = self.validator.check_item(item, mode='create')
        if not ok:
            raise ValueError(','.join(errs))
        # Auto id if present in schema but not provided
        if self.pk and self.pk not in item:
            item[self.pk] = _new_id()
        self._dynamo().put_item(Item=item)
        return {self.pk: item.get(self.pk)}

    def put(self, id_val: Any, item: Dict[str, Any], sk_val: Any | None = None) -> Dict[str, Any]:
        # Merge keys into item
        item[self.pk] = id_val
        if self.sk and sk_val is not None:
            item[self.sk] = sk_val
        ok, errs = self.validator.check_item(item, mode='update')
        if not ok:
            raise ValueError(','.join(errs))
        self._dynamo().put_item(Item=item)
        return {self.pk: id_val}

    def delete(self, id_val: Any, sk_val: Any | None = None) -> Dict[str, Any]:
        key = {self.pk: id_val}
        if self.sk and sk_val is not None:
            key[self.sk] = sk_val
        self._dynamo().delete_item(Key=key)
        return {self.pk: id_val}

    def batch_write(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        success = []
        failed = []
        with self._dynamo().batch_writer(overwrite_by_pkeys=[self.pk] if not self.sk else [self.pk, self.sk]) as bw:
            for it in items:
                ok, errs = self.validator.check_item(it, mode='create')
                if not ok:
                    failed.append({'item': it, 'error': ','.join(errs)})
                    continue
                if self.pk and self.pk not in it:
                    it[self.pk] = _new_id()
                try:
                    bw.put_item(Item=it)
                    success.append(it)
                except Exception as e:
                    failed.append({'item': it, 'error': str(e)})
        return {'success': len(success), 'failed': failed, 'items': success}

    def batch_delete(self, key_list: List[Dict[str, Any]] | List[Any]) -> Dict[str, Any]:
        success = 0
        failed = []
        delete_keys = []
        try:
            with self._dynamo().batch_writer() as bw:
                for k in key_list:
                    if isinstance(k, dict):
                        key = {self.pk: k.get(self.pk)}
                        if self.sk and self.sk in k:
                            key[self.sk] = k[self.sk]
                    else:
                        key = {self.pk: k}
                        delete_keys.append(key)
                        bw.delete_item(Key=key)
        except Exception as e:
            failed = f'batch delete failed for table {self.name} primary key {self.pk} and keys {delete_keys} {e}'
        else:
            success = len(key_list)    
        return {'success': success, 'failed': failed}

    def search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        limit = int(params.get('limit', 100))
        if limit > 1000:
            limit = 1000
        index = params.get('index')

        key_expr = None
        if self.pk in params:
            key_expr = Key(self.pk).eq(params[self.pk])
        if self.sk and self.sk in params:
            key_expr = (key_expr & Key(self.sk).eq(params[self.sk])) if key_expr is not None else Key(self.sk).eq(params[self.sk])

        kwargs: Dict[str, Any] = {'Limit': limit}
        if index:
            kwargs['IndexName'] = index
        if key_expr is not None:
            kwargs['KeyConditionExpression'] = key_expr

        # In absence of an explicit key condition, do a limited scan (internal API only)
        if 'KeyConditionExpression' in kwargs:
            resp = self._dynamo().query(**kwargs)
        else:
            resp = self._dynamo().scan(Limit=limit)
        items = resp.get('Items', [])
        next_token = resp.get('LastEvaluatedKey')
        return {'items': items, 'next': next_token}

