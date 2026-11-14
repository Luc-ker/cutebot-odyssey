"""Shared validators (contract C7).

- World part (T02): `validate_world(obj) -> list[str]` against `shared/schemas/world.schema.json` (C4).
- Envelope part (T04): `validate_envelope(obj) -> list[str]` against `shared/schemas/topics.schema.json`
  (C2 envelope plus one schema per C3 topic).

An empty list means valid. Errors are human-readable strings of the form `"<path>: <problem>"`.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "shared" / "schemas"
log = logging.getLogger(__name__)


def _path(err: ValidationError, root: str) -> str:
    out = root
    for part in err.absolute_path:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out or "(root)"


def _leaf_errors(errors: Iterable[ValidationError]) -> Iterable[ValidationError]:
    """Flatten anyOf/allOf/if-then so messages point at the real problem, not the combinator."""
    for err in errors:
        if err.validator in ("allOf", "then") and err.context:
            yield from _leaf_errors(err.context)
        else:
            yield err


def _format(errors: Iterable[ValidationError], root: str = "") -> list[str]:
    out = []
    for err in sorted(_leaf_errors(errors), key=lambda e: list(map(str, e.absolute_path))):
        if err.validator == "required":
            msg = err.message.replace("is a required property", "is required")
        elif err.validator == "anyOf":
            msg = f"{err.instance!r} does not match any allowed shape"
        else:
            msg = err.message
        out.append(f"{_path(err, root)}: {msg}")
    return out


# --------------------------------------------------------------------------- world part (T02)

@lru_cache(maxsize=1)
def _world_validator() -> Draft202012Validator:
    schema = json.loads((SCHEMA_DIR / "world.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_world(obj: Any) -> list[str]:
    """Validate a World (C4). Returns a list of readable errors; empty means valid."""
    return _format(_world_validator().iter_errors(obj))


# --------------------------------------------------------------------------- envelope part (T04)

@lru_cache(maxsize=1)
def _topics_doc() -> dict:
    return json.loads((SCHEMA_DIR / "topics.schema.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _validator_for(pointer: str) -> Draft202012Validator:
    """A validator for `#/<pointer>` inside topics.schema.json, so local `$ref`s resolve."""
    doc = _topics_doc()
    schema = {k: v for k, v in doc.items() if k != "_samples"}
    schema["$ref"] = "#/" + pointer
    return Draft202012Validator(schema)


def known_topics() -> list[str]:
    return sorted(_topics_doc()["topics"])


def check_envelope(obj: Any) -> tuple[list[str], list[str]]:
    """Return `(errors, warnings)` for a hub envelope. Unknown topics produce a warning only."""
    errors = _format(_validator_for("envelope").iter_errors(obj))
    warnings: list[str] = []
    if errors:
        return errors, warnings
    topic = obj["topic"]
    if topic not in _topics_doc()["topics"]:
        warnings.append(f"topic: unknown topic {topic!r} (data not checked)")
        return errors, warnings
    pointer = "topics/" + topic.replace("~", "~0").replace("/", "~1")
    errors = _format(_validator_for(pointer).iter_errors(obj["data"]), root="data")
    return errors, warnings


def validate_envelope(obj: Any, warnings: list[str] | None = None) -> list[str]:
    """Validate a hub envelope and, for known topics, its `data`. Returns errors only;
    pass a list as `warnings` to collect warnings (e.g. unknown topic)."""
    errors, warns = check_envelope(obj)
    if warnings is not None:
        warnings.extend(warns)
    for w in warns:
        log.debug("envelope warning: %s", w)
    return errors
