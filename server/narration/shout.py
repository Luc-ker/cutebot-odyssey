"""Shout button: describe what is ahead (T83, whitepaper §7.1, §7.8).

On ``gamepad.button {button: "shout"}`` (at most once per 1.5 s):

* facing an object (``robot.state.facing_id``) -> "Ahead stands <name>, a <role>." plus
  "It looks dangerous." for threats;
* facing nothing -> the open space of the world: "Only open sea lies ahead.";

then publishes ``narration.say`` (priority 2) and ``world.event {kind: "shout", facing_id}``.

Contracts: C3 (``gamepad.button``, ``robot.state``, ``world.objects``, ``world.current``,
``narration.say``, ``world.event``, ``system.reset``).
"""

from __future__ import annotations

import time
from typing import Any

COOLDOWN_S = 1.5
PRIORITY = 2
DEFAULT_OPEN_SPACE = "open land"


def role_words(role: str | None) -> str:
    return (role or "").replace("_", " ").strip()


def with_article(words: str) -> str:
    return f"{'an' if words[:1].lower() in 'aeiou' else 'a'} {words}"


def cap_first(s: str) -> str:
    return s[:1].upper() + s[1:]


def describe_object(obj: dict) -> str:
    role = role_words(obj.get("role"))
    name = (obj.get("name") or "").strip()
    if name and role:
        line = f"Ahead stands {name}, {with_article(role)}."
    elif name:
        line = f"Ahead stands {name}."
    elif role:
        line = f"Ahead stands {with_article(role)}."
    else:
        line = "Something stands ahead."
    if obj.get("behaviour") == "threat":
        line += " It looks dangerous."
    return line


def describe_open_space(open_space: str | None) -> str:
    space = " ".join(str(open_space or "").split()) or DEFAULT_OPEN_SPACE
    for article in ("the ", "a ", "an "):  # "the open sea" -> "Only open sea lies ahead."
        if space.lower().startswith(article):
            space = space[len(article):]
            break
    return f"Only {space} lies ahead."


class Shout:
    """Pure state: feed hub data in, ``press(now)`` returns the messages to publish."""

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.facing_id: int | None = None
        self.objects: dict[int, dict] = {}
        self.objects_world_id: str | None = None
        self.terrain_open_space: str | None = None
        self.world: dict | None = None
        self.last_press = float("-inf")

    def on_robot_state(self, data: dict) -> None:
        self.facing_id = data.get("facing_id")

    def on_world_objects(self, data: dict) -> None:
        self.objects = {o["id"]: o for o in data.get("objects", []) if "id" in o}
        self.objects_world_id = data.get("world_id")
        terrain = data.get("terrain")
        if isinstance(terrain, dict):
            self.terrain_open_space = terrain.get("open_space") or self.terrain_open_space
        elif isinstance(terrain, str) and terrain:
            self.terrain_open_space = terrain

    def on_world_current(self, data: dict) -> None:
        world = data.get("world")
        if isinstance(world, dict):
            if self.world and world.get("id") != self.world.get("id"):
                self.terrain_open_space = None  # the old world's terrain no longer applies
            self.world = world

    def open_space(self) -> str | None:
        return self.terrain_open_space or ((self.world or {}).get("terrain") or {}).get("open_space")

    def line(self) -> str:
        if self.facing_id is not None:
            obj = self.objects.get(self.facing_id)
            if obj is None:
                # Facing something we have no role for yet; fall back to the world's roles list.
                for r in (self.world or {}).get("roles", []):
                    if r.get("object_id") == self.facing_id:
                        obj = r
                        break
            if obj is not None:
                return describe_object(obj)
            return "Something stands ahead, shrouded in mist."
        return describe_open_space(self.open_space())

    def press(self, now: float) -> list[tuple[str, dict]]:
        if now - self.last_press < COOLDOWN_S:
            return []
        self.last_press = now
        return [("narration.say", {"text": self.line(), "priority": PRIORITY}),
                ("world.event", {"kind": "shout", "facing_id": self.facing_id})]


async def run(hub: Any, config: dict | None = None, clock=time.monotonic) -> None:
    """Brain entrypoint (C7)."""
    s = Shout()

    async def on_button(env: dict) -> None:
        if (env.get("data") or {}).get("button") == "shout":
            for topic, data in s.press(clock()):
                await hub.pub(topic, data)

    def plain(fn):
        async def cb(env: dict) -> None:
            fn(env.get("data") or {})
        return cb

    hub.sub("gamepad.button", on_button)
    hub.sub("robot.state", plain(s.on_robot_state))
    hub.sub("world.objects", plain(s.on_world_objects))
    hub.sub("world.current", plain(s.on_world_current))
    hub.sub("system.reset", plain(lambda _d: s.reset()))
