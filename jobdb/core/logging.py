#!/usr/bin/env python3
import json
import os
import time
from typing import Any, Dict


class Log:
    def __init__(self, service: str, stage: str, version: str, commit: str = ""):
        self.service = service
        self.stage = stage
        self.version = version
        self.commit = commit
        self.level = os.getenv('LOG_LEVEL', 'INFO')

    def _emit(self, level: str, payload: Dict[str, Any]):
        base = {
            'ts': int(time.time() * 1000),
            'service': self.service,
            'stage': self.stage,
            'version': self.version,
            'commit': self.commit,
            'level': level,
        }
        base.update(payload or {})
        print(json.dumps(base, separators=(',', ':'), ensure_ascii=False))

    def info(self, msg: str, **kwargs):
        self._emit('INFO', {'msg': msg, **kwargs})

    def error(self, msg: str, **kwargs):
        self._emit('ERROR', {'msg': msg, **kwargs})

