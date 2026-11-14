"""Fast one-object role assignment (T76, contract C7)."""

from __future__ import annotations

import asyncio
import io
import json

from server.gemini.client import ask_json
from server.world.fallback_roles import load_vocab

ROLE_TIMEOUT_S = 4.0


def _crop_snapshot(image_jpeg: bytes | None, obj: dict) -> bytes | None:
    if not image_jpeg:
        return None
    try:
        from PIL import Image

        image = Image.open(io.BytesIO(image_jpeg)).convert("RGB")
        pos = obj.get("pos", obj.get("position"))
        size = obj.get("size")
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            return image_jpeg
        width, height = image.size
        cx, cy = float(pos[0]) * width, float(pos[1]) * height
        if isinstance(size, (list, tuple)) and len(size) >= 2:
            half_w = max(width * float(size[0]), width * 0.06)
            half_h = max(height * float(size[1]), height * 0.06)
        else:
            half_w, half_h = width * 0.12, height * 0.12
        crop = image.crop((int(max(0, cx - half_w)), int(max(0, cy - half_h)),
                   int(min(width, cx + half_w)), int(min(height, cy + half_h))))
        output = io.BytesIO()
        crop.save(output, format="JPEG", quality=85)
        return output.getvalue()
    except (ImportError, OSError, TypeError, ValueError):
        return image_jpeg


async def request_role(world: dict, obj: dict, image_jpeg: bytes | None) -> dict | None:
    """Return a validated role/narration for one object, or ``None`` for any bad answer."""
    vocab = [entry for entry in load_vocab() if entry.get("role") != "giant" and not entry.get("system_only")]
    allowed = {entry["role"]: entry.get("behaviour", "neutral") for entry in vocab}
    if not allowed:
        return None
    world_info = world.get("world", world) if isinstance(world, dict) else {}
    summary = {key: world_info.get(key) for key in ("name", "setting", "mood") if world_info.get(key)}
    prompt = "\n".join((
        "Assign this one new table object a role in the current fantasy world. Return JSON only.",
        f"World: {json.dumps(summary, ensure_ascii=True)}",
        f"Object: {json.dumps({key: obj.get(key) for key in ('id', 'cls', 'class', 'pos', 'size') if key in obj}, ensure_ascii=True)}",
        "Allowed roles and default behaviours: " + json.dumps(allowed, ensure_ascii=True),
        "Use the object's crop if supplied. Keep the name concise and the in-world announcement to 15 words.",
    ))
    parts = [{"text": prompt}]
    crop = _crop_snapshot(image_jpeg, obj)
    if crop is not None:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": crop}})
    schema = {
        "type": "object",
        "required": ["role", "name", "behaviour", "announce"],
        "properties": {
            "role": {"type": "string", "enum": list(allowed)},
            "name": {"type": "string"},
            "behaviour": {"type": "string", "enum": ["friendly", "neutral", "threat"]},
            "announce": {"type": "string"},
        },
    }
    try:
        answer = await asyncio.wait_for(ask_json(parts, schema), timeout=ROLE_TIMEOUT_S)
    except Exception:
        return None
    role = allowed.get(answer.get("role"))
    if role is None or answer.get("behaviour") != role:
        return None
    name = " ".join(str(answer.get("name", "")).split())[:40]
    announce = " ".join(str(answer.get("announce", "")).split()).split()
    if not name or not announce:
        return None
    return {"role": answer["role"], "name": name, "behaviour": role,
            "announce": " ".join(announce[:15])}