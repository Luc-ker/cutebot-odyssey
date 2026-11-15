"""Stable demo mode (shared config ``STABLE_KINGDOM_ENABLED``; the key keeps its old name).

One place that answers "is the scene locked?", "which world is it locked to?" and "what is the
locked prompt?", so the composer, blender, giant events, world scheduler, object arrivals and the
eye page all agree.

When stable mode is on:

* the ``STABLE_WORLD`` fallback world (default ``kingdom``) is adopted at start and stays selected
  (no music worlds, no ``world.select`` switches);
* ``video.prompt`` is always that world's ``stable_prompt`` (or ``STABLE_KINGDOM_PROMPT`` when it is
  set, as an override): no per-object, giant or transition phrases;
* hands and people never become ``giant_enter`` events;
* an object gets a role only after ``OBJECT_SETTLE_S`` of continuous view, and the role is chosen
  locally from its detector class alone, so the same kind of object always becomes the same thing.
"""

from __future__ import annotations

import json
import logging

from server.world.fallback_worlds import WORLDS_DIR

log = logging.getLogger(__name__)

DEFAULT_PROMPT = (
    "Transform the entire view into an enchanted fairy-tale kingdom from a cinematic fantasy "
    "film, seen through a handheld camera walking through it. Everything in view becomes part of "
    "the kingdom in the same place and size: tall shapes become slender watchtowers with pointed "
    "blue spires and banners, wide or boxy shapes become ivy-covered castle fortress walls, thin "
    "legs and poles become gnarled trees, flat surfaces become flower meadows and cobblestone "
    "paths, dark gaps become glowing caves. The output will show weathered stone, moss and "
    "wildflowers in golden light with soft mist, a castle on a far hill, and a solid 3D world "
    "whose view pans and turns with every camera movement while the buildings stay anchored, with "
    "nothing modern."
)
DEFAULT_WORLD = "kingdom"
DEFAULT_SETTLE_S = 1.0
MAX_CHARS = 750  # Decart Lucy 2.6 prompt guidance: up to ~750 characters


def enabled(config: dict | None) -> bool:
    """Off unless the config says so; shared/config.json turns it on for the demo."""
    return bool((config or {}).get("STABLE_KINGDOM_ENABLED", False))


def world_key(config: dict | None) -> str:
    """The fallback world stable mode locks to, as its file stem ("Neon City" -> "neon_city")."""
    raw = str((config or {}).get("STABLE_WORLD") or "").strip().lower()
    return raw.replace(" ", "_").replace("-", "_") or DEFAULT_WORLD


def world_prompt(key: str) -> str | None:
    """The ``stable_prompt`` stored in ``shared/worlds/<key>.json``, or None."""
    try:
        world = json.loads((WORLDS_DIR / f"{key}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return str(world.get("stable_prompt") or "").strip() or None


def world_name(config: dict | None) -> str:
    """Display name of the locked world ("Neon City"), for the eye page's status label."""
    key = world_key(config)
    try:
        world = json.loads((WORLDS_DIR / f"{key}.json").read_text(encoding="utf-8"))
        return str(world["world"]["name"])
    except (OSError, ValueError, KeyError, TypeError):
        return key.replace("_", " ").title()


def prompt(config: dict | None) -> str:
    """Override first, then the locked world's own stable prompt, then the built-in Kingdom one."""
    text = str((config or {}).get("STABLE_KINGDOM_PROMPT") or "").strip()
    if not text:
        key = world_key(config)
        text = world_prompt(key) or ""
        if not text:
            log.warning("stable world %r has no stable_prompt; using the Kingdom prompt", key)
            text = DEFAULT_PROMPT
    return text[:MAX_CHARS]


def settle_s(config: dict | None) -> float:
    try:
        return max(0.0, float((config or {}).get("OBJECT_SETTLE_S", DEFAULT_SETTLE_S)))
    except (TypeError, ValueError):
        return DEFAULT_SETTLE_S
