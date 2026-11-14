"""T53 — Terrain words.

Says what the open ground and the area under the table are in the current world,
for the prompt and narration (``world.objects.terrain``).

Contract (C7)::

    analyse(objects, world) -> {"open_space": str, "under_table": str}

The world's own ``terrain`` (from Gemini) wins; otherwise a default is picked from
the world's setting. There is no map of the table any more, so no open regions are
computed; ``objects`` is accepted for the contract and ignored.
"""

from __future__ import annotations

# (setting keywords, open_space, under_table) — used when the world has no terrain.
_DEFAULTS = [
    (("ocean", "sea", "coast", "island", "pirate"), "open sea", "the deep sea"),
    (("wasteland", "volcan", "lava", "ash"), "ash plains", "a lava cave"),
    (("snow", "ice", "frost", "winter"), "snowfields", "a bear's den"),
    (("city", "neon", "cyber", "urban"), "empty streets", "the subway"),
    (("jungle", "rainforest", "tropical"), "a jungle clearing", "a hidden ruin"),
    (("court", "royal", "palace"), "palace gardens", "the catacombs"),
    (("space", "station", "orbit", "galaxy"), "open space", "the engine room"),
    (("desert", "dune", "sand"), "desert", "a buried tomb"),
    (("kingdom", "medieval", "castle"), "green plains", "a dragon's cave"),
]
_FALLBACK = ("open plains", "a deep cave")


def _names(world) -> tuple[str, str]:
    world = world or {}
    terrain = world.get("terrain") or {}
    info = world.get("world", world) if isinstance(world.get("world"), dict) else world
    text = f"{info.get('setting', '')} {info.get('name', '')}".lower()
    open_space, under = _FALLBACK
    for keys, o, u in _DEFAULTS:
        if any(k in text for k in keys):
            open_space, under = o, u
            break
    return terrain.get("open_space") or open_space, terrain.get("under_table") or under


def analyse(objects, world) -> dict:
    open_space, under_table = _names(world)
    return {"open_space": open_space, "under_table": under_table}
