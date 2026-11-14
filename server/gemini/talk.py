"""Talking-object stretch feature (T77, contract C3)."""

from __future__ import annotations

import asyncio
import json
import time

from server.gemini.client import ask_json

DWELL_S = 2.0
COOLDOWN_S = 20.0
CLOSE_RANGE_CM = 35.0
TALK_TIMEOUT_S = 4.0


class TalkingObjects:
    def __init__(self, hub, *, ask=ask_json, clock=time.monotonic):
        self.hub = hub
        self.ask = ask
        self.clock = clock
        self.reset()

    def reset(self) -> None:
        task = getattr(self, "task", None)
        if task and not task.done():
            task.cancel()
        self.objects: dict[int, dict] = {}
        self.facing_id: int | None = None
        self.facing_since: float | None = None
        self.distance_cm: float | None = None
        self.last_spoken: dict[int, float] = {}
        self.visits: dict[int, int] = {}
        self.in_flight = False
        self.task: asyncio.Task | None = None

    async def on_world_objects(self, data: dict) -> None:
        self.objects = {int(obj["id"]): obj for obj in data.get("objects", []) if "id" in obj}
        await self._maybe_talk(self.clock())

    async def on_robot_state(self, data: dict, now: float | None = None) -> None:
        now = self.clock() if now is None else now
        try:
            facing_id = int(data["facing_id"]) if data.get("facing_id") is not None else None
            distance_cm = float(data["distance_cm"]) if data.get("distance_cm") is not None else None
        except (TypeError, ValueError):
            facing_id, distance_cm = None, None
        if facing_id is None or distance_cm is None or distance_cm > CLOSE_RANGE_CM:
            self.facing_id = None
            self.facing_since = None
            self.distance_cm = distance_cm
            return
        if facing_id != self.facing_id:
            self.facing_id = facing_id
            self.facing_since = now
        self.distance_cm = distance_cm
        await self._maybe_talk(now)

    async def _maybe_talk(self, now: float) -> None:
        object_id = self.facing_id
        if self.in_flight or object_id is None or self.facing_since is None:
            return
        if now - self.facing_since < DWELL_S or now - self.last_spoken.get(object_id, float("-inf")) < COOLDOWN_S:
            return
        obj = self.objects.get(object_id)
        if not obj:
            return
        visit_count = self.visits.get(object_id, 0) + 1
        self.visits[object_id] = visit_count
        self.last_spoken[object_id] = now
        self.in_flight = True
        self.task = asyncio.create_task(self._request_line(obj, visit_count))

    async def _request_line(self, obj: dict, visit_count: int) -> None:
        prompt = "\n".join((
            "Write one short in-character line for a fantasy object the player is visiting. Return JSON only.",
            f"Object role: {obj.get('role', 'unknown')}",
            f"Object name: {obj.get('name', 'unnamed')}",
            f"Behaviour: {obj.get('behaviour', 'neutral')}",
            f"This is visit number {visit_count}; use the count naturally if it is greater than one.",
        ))
        schema = {"type": "object", "required": ["line"],
                  "properties": {"line": {"type": "string", "maxLength": 160}}}
        try:
            result = await asyncio.wait_for(self.ask([{"text": prompt}], schema), timeout=TALK_TIMEOUT_S)
            line = " ".join(str(result.get("line", "")).split())[:160]
            if line:
                await self.hub.pub("narration.say", {
                    "text": line, "priority": 1,
                    "voice": str(obj.get("role", "object")).replace("_", " "),
                })
        except Exception:
            pass
        finally:
            self.in_flight = False


async def run(hub, config=None) -> TalkingObjects:
    talking = TalkingObjects(hub)

    async def on_robot(env: dict) -> None:
        await talking.on_robot_state(env.get("data") or {})

    async def on_objects(env: dict) -> None:
        await talking.on_world_objects(env.get("data") or {})

    async def on_reset(_env: dict) -> None:
        talking.reset()

    hub.sub("robot.state", on_robot)
    hub.sub("world.objects", on_objects)
    hub.sub("system.reset", on_reset)
    return talking