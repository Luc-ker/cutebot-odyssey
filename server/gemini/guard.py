"""Validate and repair Gemini world responses (T73, contracts C4, C5 and C7)."""

from __future__ import annotations

import copy
import json
import re
from difflib import SequenceMatcher
from typing import Any

from server.common.schemas import validate_world
from server.world.fallback_roles import pick_role

_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MARKDOWN = re.compile(r"[*_`>#~]")


def _clean_text(value: Any, limit: int) -> str:
    text = str(value or "")
    text = _MARKDOWN_LINK.sub(r"\1", text)
    text = _URL.sub("", text)
    text = _MARKDOWN.sub("", text)
    return " ".join(text.split())[:limit].strip()


def _object_map(object_ids: list) -> dict[int, dict]:
    result = {}
    for item in object_ids or []:
        if isinstance(item, dict):
            try:
                result[int(item.get("id", item.get("object_id")))] = item
            except (TypeError, ValueError):
                continue
        else:
            try:
                result[int(item)] = {"id": int(item), "cls": "object"}
            except (TypeError, ValueError):
                continue
    return result


def _fallback(world: dict, obj: dict, object_id: int, used: list[str], vocab: list) -> dict:
    picked = pick_role(world, obj.get("cls", obj.get("class", "object")), used,
                       obj_id=object_id, vocab=vocab)
    return {"object_id": object_id, **picked}


def _closest_role(role: str, allowed: list[dict]) -> dict | None:
    if not role or not allowed:
        return None
    match = max(allowed, key=lambda item: SequenceMatcher(None, role.lower(), item["role"].lower()).ratio())
    ratio = SequenceMatcher(None, role.lower(), match["role"].lower()).ratio()
    return match if ratio >= 0.55 else None


def guard_world(raw: Any, object_ids: list, vocab: list) -> dict | None:
    """Return a schema-valid world, fixing role vocabulary and object coverage where possible."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return None
    if not isinstance(raw, dict):
        return None
    world = copy.deepcopy(raw)
    info = world.get("world")
    terrain = world.get("terrain")
    if not isinstance(info, dict) or not isinstance(terrain, dict) or not isinstance(world.get("roles"), list):
        return None

    for key, limit in (("name", 40), ("setting", 80), ("mood", 40), ("time_of_day", 40), ("weather", 40)):
        if key in info:
            info[key] = _clean_text(info[key], limit)
    for key in ("open_space", "under_table"):
        if key in terrain:
            terrain[key] = _clean_text(terrain[key], 80)
    world["restyle_prompt"] = _clean_text(world.get("restyle_prompt"), 400)
    world["narration"] = _clean_text(world.get("narration"), 300)
    info["palette"] = [_clean_text(colour, 40) for colour in info.get("palette", [])]

    objects = _object_map(object_ids)
    allowed = [r for r in (vocab or []) if r.get("role") and r.get("role") != "giant" and not r.get("system_only")]
    by_role = {entry["role"]: entry for entry in allowed}
    roles = []
    seen = set()
    used = []
    for role in world["roles"]:
        if not isinstance(role, dict):
            continue
        try:
            object_id = int(role["object_id"])
        except (KeyError, TypeError, ValueError):
            continue
        if object_id not in objects or object_id in seen:
            continue
        seen.add(object_id)
        allowed_role = by_role.get(str(role.get("role", ""))) or _closest_role(str(role.get("role", "")), allowed)
        if allowed_role is None:
            normalized = _fallback(world, objects[object_id], object_id, used, allowed)
        else:
            normalized = {
                "object_id": object_id,
                "role": allowed_role["role"],
                "name": _clean_text(role.get("name"), 40),
                "behaviour": allowed_role.get("behaviour", "neutral"),
            }
            if not normalized["name"]:
                normalized["name"] = allowed_role["role"].replace("_", " ").title()
        normalized["name"] = _clean_text(normalized.get("name"), 40)
        normalized["behaviour"] = normalized.get("behaviour", "neutral")
        roles.append(normalized)
        used.append(normalized["role"])

    for object_id, obj in objects.items():
        if object_id not in seen:
            roles.append(_fallback(world, obj, object_id, used, allowed))
            used.append(roles[-1]["role"])
    world["roles"] = roles

    errors = validate_world(world)
    return None if errors else world