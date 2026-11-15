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
    "Restyle the whole scene into a sunlit miniature medieval kingdom seen by a tiny explorer at ground level, "
    "and replace bottles with tall stone watchtowers and laptops with castle fortress walls. "
    "The output will show one continuous painterly fantasy landscape: the desk is a green meadow, "
    "the dark space under the desk is a vast cave, and a gigantic castle rises in the far distance."
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
