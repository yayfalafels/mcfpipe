#!/usr/bin/env python3
"""Project-specific hooks (no-ops for now)."""

from typing import Any, Dict


def before_create(table: str, item: Dict[str, Any]) -> Dict[str, Any]:
    return item


def after_create(table: str, result: Dict[str, Any]) -> Dict[str, Any]:
    return result

