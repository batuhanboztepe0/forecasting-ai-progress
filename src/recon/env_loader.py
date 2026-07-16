"""
env_loader.py — Securely load API keys from .env (never print or expose values).

Rules (hard):
- Keys are returned as strings; callers must not print, log, or persist them.
- This module NEVER writes key material to any file.
- Keys go into request headers only (Authorization / x-api-key), never query params.
"""

import os
from typing import Optional

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
_ENV_PATH = os.path.join(_REPO_ROOT, ".env")

# Module-level cache — populated on first call to _ensure_loaded()
_env_cache: dict = {}
_loaded: bool = False


def _parse_env_file(path: str) -> dict:
    """
    Parse a .env file into a dict.  Handles KEY=value, KEY="value", KEY='value'.
    Ignores comment lines and blank lines.

    Args:
        path: Absolute path to the .env file.

    Returns:
        Dict mapping key names to value strings.
    """
    result: dict = {}
    if not os.path.exists(path):
        return result
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k:
                result[k] = v
    return result


def _ensure_loaded() -> None:
    """Load .env into the module cache on first call (idempotent)."""
    global _loaded, _env_cache
    if not _loaded:
        _env_cache.update(_parse_env_file(_ENV_PATH))
        # Process environment overrides .env
        for k in list(_env_cache.keys()):
            if k in os.environ:
                _env_cache[k] = os.environ[k]
        _loaded = True


def get_key(name: str) -> Optional[str]:
    """
    Retrieve an API key by name.  Returns None if not set.

    Args:
        name: Environment variable name (e.g., 'METACULUS_API_TOKEN').

    Returns:
        The key value string, or None.
    """
    _ensure_loaded()
    return _env_cache.get(name)


def require_key(name: str) -> str:
    """
    Like get_key but raises ValueError if the key is missing.

    Args:
        name: Environment variable name.

    Returns:
        The key value string.

    Raises:
        ValueError: If the key is not set.
    """
    val = get_key(name)
    if not val:
        raise ValueError(
            f"Required key '{name}' not found in .env or environment. "
            f"Add it to {_ENV_PATH} (git-ignored)."
        )
    return val


def key_present(name: str) -> bool:
    """Return True if the key is set and non-empty."""
    val = get_key(name)
    return bool(val)
