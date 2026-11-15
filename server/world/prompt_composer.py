"""Restyle prompt composer (T29, whitepaper §7.2, §7.10).

Builds the text prompt that tells the video model how to redraw the robot's view:

    <world.restyle_prompt>, <role phrase> in the foreground, <giant phrase>, <fixed tail>

and publishes it on ``video.prompt`` only when the text changes, at most twice a second,
capped at 400 characters. While a ``world.transition`` is running the blender (T30) owns
``video.prompt``, so this module stays silent for that window.

Stable Kingdom mode (``STABLE_KINGDOM_ENABLED``, see ``server/world/stable.py``) replaces all of that
with one fixed prompt: facing objects, giants and transitions never change the text.

Contracts: C3 (``world.current``, ``world.objects``, ``robot.state``, ``world.event``,
``world.transition``, ``video.prompt``, ``system.reset``), C4 (World), C5 (roles.json).
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from server.world import stable

MAX_CHARS = 400
MIN_INTERVAL_S = 0.5  # at most 2 publishes per second
TICK_S = 0.1
TAIL = "first-person, low to the ground, consistent lighting"

ROLES_PATH = Path(__file__).resolve().parents[2] / "shared" / "roles.json"

# Used only until shared/roles.json (T03) exists. Same shape as C5.
_STUB_ROLES = [
    {"role": "castle", "behaviour": "neutral", "prompt": "a stone castle tower"},
    {"role": "ship", "behaviour": "neutral", "prompt": "a wooden sailing ship"},
    {"role": "dragon", "behaviour": "threat", "prompt": "a fearsome dragon"},
]

# Setting keyword -> giant phrase. First match wins, so put the specific ones first.
_GIANTS: list[tuple[tuple[str, ...], str]] = [
    (("sea", "ocean", "water", "island", "harbour", "reef", "coast"),
     "a towering sea god looming over the horizon"),
    (("snow", "ice", "frost", "frozen", "winter", "glacier", "tundra"),
     "a frost giant reaching down from the sky"),
    (("volcan", "lava", "fire", "ash", "wasteland", "desert", "inferno"),
     "a colossal fire giant looming through the smoke"),
    (("neon", "city", "cyber", "future", "space", "metropolis"),
     "a colossal mech towering over the skyline"),
    (("jungle", "forest", "swamp", "grove", "woods"),
     "an ancient forest giant looming above the canopy"),
    (("kingdom", "castle", "royal", "medieval", "court", "village"),
     "a stone titan looming over the land"),
]
_DEFAULT_GIANT = "a towering giant looming down from the sky"


def load_vocab(path: Path = ROLES_PATH) -> dict[str, str]:
    """Return {role: prompt phrase} from roles.json, or the three-role stub if it is missing."""
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        entries = _STUB_ROLES
    return {e["role"]: e.get("prompt") or e["role"].replace("_", " ") for e in entries if "role" in e}


def giant_phrase(world: dict | None) -> str:
    """A colossus suited to the world's setting (whitepaper §7.10)."""
    info = (world or {}).get("world") or {}
    text = " ".join(str(info.get(k, "")) for k in ("setting", "name")).lower()
    for keywords, phrase in _GIANTS:
        if any(k in text for k in keywords):
            return phrase
    return _DEFAULT_GIANT


def role_phrase(role: str | None, vocab: dict[str, str] | None = None) -> str | None:
    if not role:
        return None
    vocab = load_vocab() if vocab is None else vocab
    return f"{vocab.get(role) or role.replace('_', ' ')} in the foreground"


def _clip(text: str, limit: int) -> str:
    """Cut at a word boundary so the result is at most ``limit`` characters."""
    text = text.strip().rstrip(",").strip()
    if len(text) <= limit:
        return text
    if limit <= 0:
        return ""
    cut = text[:limit]
    space = cut.rfind(" ")
    return (cut[:space] if space > limit // 2 else cut).rstrip(" ,")


def compose(world: dict | None, facing_role: str | None, giant_present: bool,
            vocab: dict[str, str] | None = None) -> str:
    """Pure prompt builder. ``world`` is a C4 World (or None), ``facing_role`` a role name.

    The world's base prompt is the part that gets shortened when the 400-character cap bites,
    so the facing object, the giant and the consistency tail always survive.

    A built-in scene with a ``stable_prompt`` (Kingdom at start, before any song) is sent as that
    full scene prompt instead, with no object or giant phrases: it already says how everything in
    view becomes part of the scene.
    """
    fixed = ((world or {}).get("stable_prompt") or "").strip()
    if fixed:
        return fixed[:stable.MAX_CHARS]
    base = ((world or {}).get("restyle_prompt") or "").strip()
    extras = [p for p in (role_phrase(facing_role, vocab),
                          giant_phrase(world) if giant_present else None) if p]
    extras.append(TAIL)
    suffix = ", ".join(extras)
    if not base:
        return _clip(suffix, MAX_CHARS)
    room = MAX_CHARS - len(suffix) - 2  # ", "
    base = _clip(base, room)
    return f"{base}, {suffix}" if base else _clip(suffix, MAX_CHARS)


class PromptComposer:
    """State machine around :func:`compose`. Feed it hub data, call :meth:`tick` with the time.

    ``tick`` returns the prompt to publish, or None. Kept free of I/O so tests drive it with a
    fake clock; :func:`run` wires it to the hub.
    """

    def __init__(self, vocab: dict[str, str] | None = None, fixed_prompt: str | None = None):
        self.vocab = load_vocab() if vocab is None else vocab
        # Stable mode: this exact text is the only prompt ever published.
        self.fixed_prompt = fixed_prompt
        self.reset()

    def reset(self) -> None:
        self.world: dict | None = None
        self.roles: dict[int, str] = {}  # object id -> role, from world.objects
        self.facing_id: int | None = None
        self.giants: set[str] = set()
        self.transition_until = 0.0
        self.last_text: str | None = None
        self.last_pub_at = float("-inf")

    # ---- inputs -----------------------------------------------------------------
    def on_world_current(self, data: dict) -> None:
        world = data.get("world")
        if isinstance(world, dict):
            if self.world and world.get("id") != self.world.get("id"):
                self.roles = {}  # roles belong to the old world until world.objects catches up
            self.world = world

    def on_world_objects(self, data: dict) -> None:
        if self.world and data.get("world_id") not in (None, self.world.get("id")):
            return  # stale objects from the previous world
        self.roles = {o["id"]: o.get("role") for o in data.get("objects", []) if "id" in o}

    def on_robot_state(self, data: dict) -> None:
        self.facing_id = data.get("facing_id")

    def on_world_event(self, data: dict) -> None:
        kind = data.get("kind")
        if kind == "giant_enter":
            self.giants.add(str(data.get("id")))
        elif kind == "giant_leave":
            self.giants.discard(str(data.get("id")))

    def on_transition(self, data: dict, now: float) -> None:
        started = data.get("started")
        if not isinstance(started, (int, float)) or abs(started - now) > 60:
            started = now  # missing or wildly skewed clock: trust our own
        self.transition_until = max(self.transition_until,
                                    started + float(data.get("duration_ms", 0)) / 1000.0)
        if isinstance(data.get("to"), dict):
            self.world = data["to"]
            self.roles = {}
        # The blender's last prompt replaces ours on screen, so republish once the window ends.
        # (Stable mode has no blender, so the fixed prompt is still on screen.)
        if not self.fixed_prompt:
            self.last_text = None

    # ---- output -----------------------------------------------------------------
    def current_text(self) -> str | None:
        if self.fixed_prompt:
            return self.fixed_prompt
        if not self.world:
            return None
        facing_role = self.roles.get(self.facing_id) if self.facing_id is not None else None
        return compose(self.world, facing_role, bool(self.giants), self.vocab)

    def tick(self, now: float) -> str | None:
        if now < self.transition_until and not self.fixed_prompt:
            return None
        text = self.current_text()
        if text is None or text == self.last_text:
            return None
        if now - self.last_pub_at < MIN_INTERVAL_S:
            return None  # still changed on the next tick, so it goes out then
        self.last_text, self.last_pub_at = text, now
        return text


async def run(hub: Any, config: dict | None = None, clock=time.time) -> None:
    """Brain entrypoint (C7): subscribe, then publish ``video.prompt`` as inputs change."""
    composer = PromptComposer(fixed_prompt=stable.prompt(config) if stable.enabled(config) else None)

    def handler(fn, with_time=False):
        async def cb(env: dict) -> None:
            data = env.get("data") or {}
            fn(data, clock()) if with_time else fn(data)
        return cb

    hub.sub("world.current", handler(composer.on_world_current))
    hub.sub("world.objects", handler(composer.on_world_objects))
    hub.sub("robot.state", handler(composer.on_robot_state))
    hub.sub("world.event", handler(composer.on_world_event))
    hub.sub("world.transition", handler(composer.on_transition, with_time=True))
    hub.sub("system.reset", handler(lambda _d: composer.reset()))

    while True:
        text = composer.tick(clock())
        if text is not None:
            await hub.pub("video.prompt", {"prompt": text})
        await asyncio.sleep(TICK_S)
