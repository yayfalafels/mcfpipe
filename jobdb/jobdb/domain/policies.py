#!/usr/bin/env python3
"""Route/table guardrails (placeholder)."""

from typing import Any, Dict


def allow(operation: str, table: str, stage: str) -> bool:
    # Example: block delete in prod for certain tables (not enforced now)
    return True

