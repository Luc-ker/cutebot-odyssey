"""Prompt blending during world changes (T30, whitepaper §7.12).

On ``world.transition`` this module publishes a short sequence of ``video.prompt`` messages
spread over ``duration_ms``:

    old prompt -> "X with hints of Y" -> "X turning into Y" -> "Y with fading traces of X" -> new prompt

It owns ``video.prompt`` for exactly the transition window; the composer (T29) stays quiet
then by itself and takes over again afterwards.

Prompt weights: the ``video.prompt`` contract (C3) carries a single ``{prompt}`` string, so
blending is textual. If the chosen provider supports weighted prompts (see
``docs/restyle-provider.md``), add a weights field through a contract change first.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

MAX_CHARS = 400
TICK_S = 0.05


def short_desc(world: dict | None, fallback_prompt: str = "") -> str:
    """A short phrase for a world: "stormy open ocean at dusk"."""
    info = (world or {}).get("world") or {}
    setting = str(info.get("setting") or "").strip()
    if setting:
        tod = str(info.get("time_of_day") or "").strip()
        return f"{setting} at {tod}" if tod and tod not in setting else setting
    first = (world or {}).get("restyle_prompt") or fallback_prompt
    return first.split(",")[0].strip()


def _cap(text: str) -> str:
    if len(text) <= MAX_CHARS:
        return text
    cut = text[:MAX_CHARS]
    return cut[: cut.rfind(" ")].rstrip(" ,") if " " in cut else cut


def blend_steps(old_prompt: str, new_prompt: str, old_short: str, new_short: str) -> list[str]:
    """Five prompts: old, three mixes, new. Pure function."""
    steps = [
        old_prompt,
        f"{old_prompt}, with first hints of {new_short}",
        f"{old_short} turning into {new_short}, {new_prompt}",
        f"{new_prompt}, with fading traces of {old_short}",
        new_prompt,
    ]
    out: list[str] = []
    for s in (_cap(s) for s in steps):
        if s and (not out or out[-1] != s):
            out.append(s)
    return out


class PromptBlender:
    """Schedules blend prompts. :meth:`tick` returns the prompts due by ``now``, in order."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.last_prompt: str | None = None  # last video.prompt seen from anyone
        self.schedule: list[tuple[float, str]] = []
        self.target_short: str | None = None

    @property
    def blending(self) -> bool:
        return bool(self.schedule)

    def on_video_prompt(self, data: dict) -> None:
        if isinstance(data.get("prompt"), str):
            self.last_prompt = data["prompt"]

    def start(self, transition: dict, now: float) -> None:
        to = transition.get("to") or {}
        new_prompt = to.get("restyle_prompt") or ""
        if not new_prompt:
            return
        frm = transition.get("from")
        duration = max(0.0, float(transition.get("duration_ms", 0)) / 1000.0)
        started = transition.get("started")
        if not isinstance(started, (int, float)) or abs(started - now) > 60:
            started = now

        if self.blending and self.target_short:
            # Mid-blend: start from what is on screen now and mix from where we were heading.
            old_prompt, old_short = self.last_prompt or new_prompt, self.target_short
        else:
            old_prompt = self.last_prompt or (frm or {}).get("restyle_prompt") or new_prompt
            old_short = short_desc(frm, old_prompt)
        new_short = short_desc(to, new_prompt)

        steps = blend_steps(old_prompt, new_prompt, old_short, new_short)
        # Evenly spaced inside the window: step i at started + i * duration / n, so the final
        # prompt lands before the composer takes over at started + duration.
        n = len(steps)
        self.schedule = [(started + i * duration / n, s) for i, s in enumerate(steps)]
        self.target_short = new_short

    def tick(self, now: float) -> list[str]:
        due = [s for t, s in self.schedule if t <= now]
        self.schedule = [(t, s) for t, s in self.schedule if t > now]
        if due:
            self.last_prompt = due[-1]
        if not self.schedule:
            self.target_short = None
        return due


async def run(hub: Any, config: dict | None = None, clock=time.time) -> None:
    """Brain entrypoint (C7)."""
    blender = PromptBlender()

    async def on_prompt(env: dict) -> None:
        blender.on_video_prompt(env.get("data") or {})

    async def on_transition(env: dict) -> None:
        blender.start(env.get("data") or {}, clock())

    async def on_reset(_env: dict) -> None:
        blender.reset()

    hub.sub("video.prompt", on_prompt)
    hub.sub("world.transition", on_transition)
    hub.sub("system.reset", on_reset)

    while True:
        for text in blender.tick(clock()):
            await hub.pub("video.prompt", {"prompt": text})
        await asyncio.sleep(TICK_S)
