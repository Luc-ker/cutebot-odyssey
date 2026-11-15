"""Stable Kingdom demo mode (shared config ``STABLE_KINGDOM_ENABLED``).

One place that answers "is the scene locked?" and "what is the locked prompt?", so the composer,
blender, giant events, world scheduler, object arrivals and the eye page all agree.

When stable mode is on:

* ``video.prompt`` is always ``STABLE_KINGDOM_PROMPT``: no per-object, giant or transition phrases;
* the Kingdom world stays selected (no music worlds, no ``world.select`` switches);
* hands and people never become ``giant_enter`` events;
* an object gets a role only after ``OBJECT_SETTLE_S`` of continuous view, and the role is chosen
  locally from its detector class alone, so the same kind of object always becomes the same thing.
"""

from __future__ import annotations

DEFAULT_PROMPT = (
    "Transform the real scene into a sunlit miniature medieval kingdom filmed by a handheld "
    "camera walking through it at ground level, and permanently replace every bottle with a tall "
    "stone watchtower and every laptop with castle fortress walls, each built exactly where the "
    "real object stands with the same position, size and outline. The output will show one solid, "
    "physically real 3D world with true depth and parallax: the desk is a green meadow, the dark "
    "space under the desk is a vast cave, a gigantic castle rises in the far distance, and every "
    "building stays fixed in place and fully transformed, never reverting to the original object, "
    "as the camera moves, turns and walks closer. Consistent lighting, textures and style in "
    "every frame."
)
DEFAULT_SETTLE_S = 1.0
MAX_CHARS = 750  # Decart Lucy 2.6 prompt guidance: up to ~750 characters


def enabled(config: dict | None) -> bool:
    """Off unless the config says so; shared/config.json turns it on for the demo."""
    return bool((config or {}).get("STABLE_KINGDOM_ENABLED", False))


def prompt(config: dict | None) -> str:
    text = str((config or {}).get("STABLE_KINGDOM_PROMPT") or "").strip() or DEFAULT_PROMPT
    return text[:MAX_CHARS]


def settle_s(config: dict | None) -> float:
    try:
        return max(0.0, float((config or {}).get("OBJECT_SETTLE_S", DEFAULT_SETTLE_S)))
    except (TypeError, ValueError):
        return DEFAULT_SETTLE_S
