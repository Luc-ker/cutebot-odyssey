"""World-composition prompt assembly (T72, contract C7)."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

PROMPT_PATH = Path(__file__).resolve().parents[2] / "shared" / "prompts" / "compose_world.md"


def _mapping(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return vars(value)
    return {}


def _world_summary(current_world: Any) -> str:
    world = _mapping(current_world)
    info = _mapping(world.get("world")) or world
    fields = ("id", "name", "setting", "mood", "time_of_day", "weather")
    summary = {key: value for key, value in (("id", world.get("id")), *[(k, info.get(k)) for k in fields[1:]]) if value}
    return json.dumps(summary, ensure_ascii=True, separators=(",", ":")) if summary else "none"


def build_compose_parts(audio_wav: bytes, image_jpeg: bytes, objects: list,
                        current_world: dict | None, vocab: list) -> list:
    """Return text, WAV and JPEG parts in the order expected by Gemini."""
    rules = PROMPT_PATH.read_text(encoding="utf-8").strip()
    object_lines = []
    for item in objects or []:
        obj = _mapping(item)
        object_id = obj.get("id", obj.get("object_id", "?"))
        cls = obj.get("cls", obj.get("class", "object"))
        pos = obj.get("pos", obj.get("position", []))
        object_lines.append(f"- id={object_id}; class={cls}; position={json.dumps(pos, separators=(',', ':'))}")
    role_lines = [
        f"- {entry['role']}: {entry.get('behaviour', 'neutral')}"
        for entry in (vocab or [])
        if entry.get("role") and entry.get("role") != "giant" and not entry.get("system_only")
    ]
    text = "\n".join((
        rules,
        f"Current world (keep it unless the music clearly implies a different world): {_world_summary(current_world)}",
        "Tracked objects (assign exactly one role to each id):",
        "\n".join(object_lines) or "(none)",
        "Allowed roles and behaviours (use only these role names):",
        "\n".join(role_lines) or "(none)",
        "Return one JSON object matching the supplied schema. Use id \"w-00000000\"; the scheduler assigns the final id.",
    ))
    return [
        {"text": text},
        {"inline_data": {"mime_type": "audio/wav", "data": audio_wav}},
        {"inline_data": {"mime_type": "image/jpeg", "data": image_jpeg}},
    ]