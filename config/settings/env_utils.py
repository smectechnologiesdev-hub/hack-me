"""
Tiny helpers for reading typed values out of environment variables.

Keeping these in one place avoids repeating ``os.environ.get(...)`` parsing
logic throughout the settings modules and gives consistent behaviour for
booleans, integers and comma-separated lists.
"""

import os
from typing import List, Optional


def env_str(name: str, default: str = "") -> str:
    """Return an environment variable as a stripped string."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip()


def env_bool(name: str, default: bool = False) -> bool:
    """Interpret common truthy/falsey strings as a boolean."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int = 0) -> int:
    """Return an environment variable parsed as an integer."""
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def env_csv(name: str, default: Optional[List[str]] = None) -> List[str]:
    """Split a comma-separated environment variable into a clean list."""
    if default is None:
        default = []
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()]
