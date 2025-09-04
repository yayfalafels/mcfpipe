#!/usr/bin/env python3
import json
import os
from typing import Any, Dict

import boto3

from .logging import Log
from .responses import Responses
from .table import Table


class DBEngine:
    def __init__(self, app_name: str, version: str, stage: str, region: str = "", commit: str = ""):
        self.app_name = app_name
        self.version = version
        self.stage = stage
        self.region = region
        self.commit = commit
        self.log = Log(service=app_name, stage=stage, version=version, commit=commit)
        self.responses = Responses()

        # Settings
        self.s3_bucket = os.getenv('S3_BUCKET')
        self.db_schema_s3_path = os.getenv('DB_SCHEMA_S3', 'storage/db_schema.json')
        self.table_prefix = os.getenv('DDB_TABLE_PREFIX', 'mcfpipe')

        # Loaded state
        self._schema: Dict[str, Any] = {}
        self._tables: Dict[str, Table] = {}

        self.reload()

    # Schema loading ----------------------------------------------------------------------
    def _load_schema_from_s3(self) -> Dict[str, Any] | None:
        if not self.s3_bucket:
            return None
        try:
            s3 = boto3.client('s3', region_name=self.region or None)
            obj = s3.get_object(Bucket=self.s3_bucket, Key=self.db_schema_s3_path)
            data = obj['Body'].read()
            return json.loads(data)
        except Exception as e:
            self.log.error('schema_s3_load_failed', error=str(e), bucket=self.s3_bucket, key=self.db_schema_s3_path)
            return None

    def _load_schema_from_bundle(self) -> Dict[str, Any]:
        here = os.path.dirname(__file__)
        bundle_path = os.path.join(os.path.dirname(here), 'schemas', 'db_schema.json')
        with open(bundle_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _physical_name(self, logical: str) -> str:
        # e.g., prod_mcfpipe_job
        return f"{self.stage}_{self.table_prefix}_{logical}"

    def reload(self) -> Dict[str, Any]:
        schema = self._load_schema_from_s3() or self._load_schema_from_bundle()
        self._schema = schema
        # Build tables registry
        self._tables = {}
        for t in schema.get('tables', []):
            logical = t.get('table_name')
            physical = self._physical_name(logical)
            self._tables[logical] = Table(name=physical, spec=t, region=self.region)
        self.log.info('engine_reloaded', tables=len(self._tables))
        return {'reloaded_at': self.version}

    # Accessors ---------------------------------------------------------------------------
    def table(self, logical: str) -> Table | None:
        return self._tables.get(logical)

