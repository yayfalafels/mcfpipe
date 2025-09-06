#!/usr/bin/env python3
"""Auth strategies (none/jwt/key) - default none for private API."""

from typing import Any, Dict


def authenticate(event: Dict[str, Any], mode: str = 'none') -> Dict[str, Any]:
    # No-op authentication: assume VPC-only access
    return {'principal': None}

