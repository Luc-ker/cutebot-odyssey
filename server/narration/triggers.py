"""Narration triggers (T82, whitepaper §7.8, §7.10, §7.11, §7.12).

Turns ``world.event`` into ``narration.say``:

    world_changed  -> the world's own narration (priority 3); a returning world gets "You return to <name>."
    object_added   -> its ``announce`` text, or a setting template if empty (priority 2)
    giant_enter    -> a setting template ("A sea god's hand breaks the waves!") (priority 2)
    danger_enter   -> "Beware! <name> stirs." (priority 3)
    blocked        -> "<Obstacle> bars your way." (priority 1)

Templates live in ``shared/narration_templates.json``, chosen by setting keyword, with a default.
Each line also carries the setting's ``voice`` hint for the TTS (T80).

Contracts: C3 (``world.event``, ``world.current``, ``narration.say``, ``system.reset``), C4 (World).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

TEMPLATES_PATH = Path(__file__).resolve().parents[2] / "shared" / "narration_templates.json"
PENDING_WORLD_S = 10.0  # how long a world_changed waits for its world.current to arrive

P_WORLD, P_OBJECT, P_GIANT, P_DANGER, P_BLOCKED = 3, 2, 2, 3, 1

# Used only if shared/narration_templates.json is missing or broken.
_STUB_TEMPLATES = {
    "default": {
        "voice": "",
        "world_changed": "You arrive in {world}.",
        "returning": "You return to {world}.",
        "object_added": "{Name} appears.",
        "object_added_from_sky": "{Name} falls from the sky!",
        "giant_enter": "A giant's hand reaches down from the sky!",
        "danger_enter": "Beware! {Name} stirs.",
        "blocked": "{Obstacle} bars your way.",
    },
    "settings": [],
}


def load_templates(path: Path = TEMPLATES_PATH) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data.get("default"), dict):
            data.setdefault("settings", [])
            return data
    except (OSError, ValueError, AttributeError):
        pass
    return _STUB_TEMPLATES


def role_words(role: str | None) -> str:
    return (role or "").replace("_", " ").strip()


def with_article(words: str) -> str:
    if not words:
        return "something"
    return f"{'an' if words[0].lower() in 'aeiou' else 'a'} {words}"


def cap_first(s: str) -> str:
    return s[:1].upper() + s[1:]


def setting_entry(world: dict | None, templates: dict) -> dict:
    """The settings entry whose keyword appears in the world's setting (checked first) or name."""
    info = (world or {}).get("world") or {}
    for field in ("setting", "name"):
        text = str(info.get(field) or "").lower()
        if not text:
            continue
        for entry in templates.get("settings", []):
            if any(k in text for k in entry.get("match", [])):
                return entry
    return {}


def template(world: dict | None, templates: dict, key: str) -> str:
    entry = setting_entry(world, templates)
    if key in entry:
        return entry[key]
    return templates["default"].get(key) or _STUB_TEMPLATES["default"].get(key, "")


def voice_for(world: dict | None, templates: dict) -> str:
    return setting_entry(world, templates).get("voice") or templates["default"].get("voice") or ""


def fill(tpl: str, **values: str) -> str:
    """Format with {x} and {X} (first letter capitalised) for every value; unknown keys stay blank."""
    full: dict[str, str] = {}
    for k, v in values.items():
        v = v or ""
        full[k] = v
        full[cap_first(k)] = cap_first(v)

    class _Blank(dict):
        def __missing__(self, _key):
            return ""

    return " ".join(tpl.format_map(_Blank(full)).split())


class NarrationTriggers:
    """Pure: ``on_world_current(data)`` and ``on_event(data, now)`` return a list of ``narration.say`` payloads."""

    def __init__(self, templates: dict | None = None):
        self.templates = load_templates() if templates is None else templates
        self.reset()

    def reset(self) -> None:
        self.world: dict | None = None
        self.pending: tuple[str, bool, float] | None = None  # (world_id, returning, when)

    # ---- inputs -------------------------------------------------------------------------------
    def on_world_current(self, data: dict, now: float = 0.0) -> list[dict]:
        world = data.get("world")
        if isinstance(world, dict):
            self.world = world
        if self.pending and self.world and self.world.get("id") == self.pending[0]:
            _, returning, when = self.pending
            self.pending = None
            if now - when <= PENDING_WORLD_S:
                return [self._arrival(returning)]
        return []

    def on_event(self, data: dict, now: float = 0.0) -> list[dict]:
        kind = data.get("kind")
        handler = getattr(self, f"_on_{kind}", None)
        return handler(data, now) if handler else []

    # ---- event kinds --------------------------------------------------------------------------
    def _on_world_changed(self, data: dict, now: float) -> list[dict]:
        returning = bool(data.get("returning"))
        if self.world and self.world.get("id") == data.get("world_id"):
            return [self._arrival(returning)]
        self.pending = (data.get("world_id"), returning, now)  # world.current not here yet
        return []

    def _on_object_added(self, data: dict, now: float) -> list[dict]:
        text = (data.get("announce") or "").strip()
        if not text:
            role = role_words(data.get("role"))
            name = (data.get("name") or "").strip() or (f"the {role}" if role else "something")
            key = "object_added_from_sky" if data.get("from_sky") else "object_added"
            text = fill(template(self.world, self.templates, key),
                        name=name, role=role, a_role=with_article(role), world=self._world_name())
        return [self._say(text, P_OBJECT)]

    def _on_giant_enter(self, data: dict, now: float) -> list[dict]:
        # C3's giant_enter payload also has a `kind` (hand/person) that collides with the event kind,
        # so one template covers both.
        text = fill(template(self.world, self.templates, "giant_enter"), world=self._world_name())
        return [self._say(text, P_GIANT)]

    def _on_danger_enter(self, data: dict, now: float) -> list[dict]:
        role = role_words(data.get("role"))
        name = (data.get("name") or "").strip() or (f"the {role}" if role else "something")
        text = fill(template(self.world, self.templates, "danger_enter"),
                    name=name, role=role, a_role=with_article(role), world=self._world_name())
        return [self._say(text, P_DANGER)]

    def _on_blocked(self, data: dict, now: float) -> list[dict]:
        obstacle = (str(data.get("obstacle") or "")).strip() or "something"
        text = fill(template(self.world, self.templates, "blocked"), obstacle=obstacle,
                    world=self._world_name())
        return [self._say(text, P_BLOCKED)]

    # ---- helpers ------------------------------------------------------------------------------
    def _world_name(self) -> str:
        return str(((self.world or {}).get("world") or {}).get("name") or "a new world")

    def _arrival(self, returning: bool) -> dict:
        own = str((self.world or {}).get("narration") or "").strip()
        name = self._world_name()
        if returning:
            prefix = fill(template(self.world, self.templates, "returning"), world=name)
            text = f"{prefix} {own}".strip()
        else:
            text = own or fill(template(self.world, self.templates, "world_changed"), world=name)
        return self._say(text, P_WORLD)

    def _say(self, text: str, priority: int) -> dict:
        out = {"text": text, "priority": priority}
        voice = voice_for(self.world, self.templates)
        if voice:
            out["voice"] = voice
        return out


async def run(hub: Any, config: dict | None = None, clock=time.monotonic) -> None:
    """Brain entrypoint (C7)."""
    t = NarrationTriggers()

    async def publish(says: list[dict]) -> None:
        for s in says:
            await hub.pub("narration.say", s)

    async def on_current(env: dict) -> None:
        await publish(t.on_world_current(env.get("data") or {}, clock()))

    async def on_event(env: dict) -> None:
        await publish(t.on_event(env.get("data") or {}, clock()))

    async def on_reset(_env: dict) -> None:
        t.reset()

    hub.sub("world.current", on_current)
    hub.sub("world.event", on_event)
    hub.sub("system.reset", on_reset)
