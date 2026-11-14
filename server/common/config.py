"""Shared config loader (T01, contract C10).

`load_config()` reads `shared/config.json` and lets environment variables named
`GENRATOR_<KEY>` override any key, cast to the type of the default in the file.
Keys starting with `_` (such as `_doc`) are documentation and are not returned.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "shared" / "config.json"
ENV_PREFIX = "GENRATOR_"

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off", ""}


def _cast(raw: str, default: Any, key: str) -> Any:
    try:
        if isinstance(default, bool):
            low = raw.strip().lower()
            if low in _TRUE:
                return True
            if low in _FALSE:
                return False
            raise ValueError(raw)
        if isinstance(default, int):
            return int(raw)
        if isinstance(default, float):
            return float(raw)
        if isinstance(default, (list, dict)):
            return json.loads(raw)
        return raw
    except ValueError as exc:
        raise ValueError(
            f"{ENV_PREFIX}{key}={raw!r} cannot be cast to {type(default).__name__}"
        ) from exc


def load_config(path: str | os.PathLike | None = None, env: dict | None = None) -> dict:
    """Return the config dict with `GENRATOR_<KEY>` env overrides applied."""
    env = os.environ if env is None else env
    with open(path or CONFIG_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    cfg = {k: v for k, v in raw.items() if not k.startswith("_")}
    for key, default in cfg.items():
        name = ENV_PREFIX + key
        if name in env:
            cfg[key] = _cast(env[name], default, key)
    return cfg
