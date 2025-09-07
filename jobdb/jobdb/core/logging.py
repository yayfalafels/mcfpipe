#!/usr/bin/env python3
# jobdb/core/logging.py
# dependencies ----------------------------------------------------------------------------------------
import logging
import json
import sys
import time


# constants ----------------------------------------------------------------------------------------
STD_LOGGING_PARAMS = [
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process"
]


# classes ----------------------------------------------------------------------------------------
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": int(time.time()),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # include any extra fields (e.g., request_id, route, status...)
        for k, v in record.__dict__.items():
            if k not in (STD_LOGGING_PARAMS):
                payload[k] = v
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"))


def init_logging(level: str, service: str, stage: str, version: str):
    root = logging.getLogger()

    for h in list(root.handlers):
        root.removeHandler(h)
    root.handlers.clear()

    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root.addHandler(h)

    # quiet noisy deps if desired
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.Warning if level.upper() == "DEBUG" else logging.ERROR)
    root.setLevel(level.upper())

    # inject static fields into every record
    class Static(logging.Filter):
        def filter(self, record):
            record.service = service
            record.stage = stage
            record.version = version
            return True

    root.addFilter(Static())
