"""Narration queue (T79, whitepaper §7.8).

Turns any number of ``narration.say`` requests into ``narration.speak`` messages, exactly one at a time:

* priority queue, 3 = most urgent; equal priorities keep arrival order;
* items older than 8 s are dropped (stale news is worse than silence);
* at most 4 items wait; overflow drops the lowest priority (oldest first among equals);
* lines are cut at a sentence boundary to ``NARRATION_MAX_CHARS``;
* identical text within 10 s is ignored;
* after a ``narration.speak`` the queue waits for ``narration.done`` with the same id, or a timeout of
  ``len(text) / 12 + 2`` seconds, before speaking the next line.

Contracts: C3 (``narration.say``, ``narration.speak``, ``narration.done``, ``system.reset``).
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Any

MAX_AGE_S = 8.0
MAX_LEN = 4
DEDUPE_S = 10.0
CHARS_PER_S = 12.0
TIMEOUT_PAD_S = 2.0
DEFAULT_MAX_CHARS = 200
TICK_S = 0.05

_SENTENCE_END = re.compile(r"[.!?…](?=[\"')\]]*(\s|$))")


def truncate(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """Shorten ``text`` to at most ``max_chars``, preferring to end on a whole sentence."""
    text = " ".join(str(text).split())
    if len(text) <= max_chars:
        return text
    if max_chars <= 1:
        return text[:max_chars]
    cut = text[:max_chars]
    ends = [m.end() for m in _SENTENCE_END.finditer(cut)]
    if ends:
        return cut[:ends[-1]].strip()
    # One very long sentence: cut at a word boundary and mark the cut.
    cut = text[:max_chars - 1]
    space = cut.rfind(" ")
    if space > max_chars // 2:
        cut = cut[:space]
    return cut.rstrip(" ,;:-") + "…"


def speak_timeout(text: str) -> float:
    return len(text) / CHARS_PER_S + TIMEOUT_PAD_S


@dataclass
class _Item:
    priority: int
    added: float
    seq: int
    text: str
    voice: str | None


class NarrationQueue:
    """Pure state machine: feed it ``say`` / ``done``, call ``tick(now)`` for the next speak (or None)."""

    def __init__(self, max_chars: int = DEFAULT_MAX_CHARS):
        self.max_chars = max_chars
        self.reset()

    def reset(self) -> None:
        self.items: list[_Item] = []
        self.current: dict | None = None  # {"id", "text", "voice"} being spoken
        self.current_deadline = 0.0
        self.recent: dict[str, float] = {}  # text -> time accepted, for de-duplication
        self._seq = 0

    # ---- inputs -------------------------------------------------------------------------------
    def say(self, data: dict, now: float) -> bool:
        """Queue a ``narration.say``. Returns False if it was ignored (empty, duplicate, overflow)."""
        text = truncate(data.get("text") or "", self.max_chars)
        if not text:
            return False
        self._forget_old(now)
        if text in self.recent:
            return False
        try:
            priority = max(0, min(3, int(data.get("priority", 1))))
        except (TypeError, ValueError):
            priority = 1
        self.recent[text] = now
        self._seq += 1
        item = _Item(priority, now, self._seq, text, data.get("voice"))
        self.items.append(item)
        self._drop_stale(now)
        while len(self.items) > MAX_LEN:
            lowest = min(self.items, key=lambda i: (i.priority, i.seq))
            self.items.remove(lowest)
        return item in self.items

    def done(self, data: dict) -> None:
        if self.current and data.get("id") == self.current["id"]:
            self.current = None

    # ---- output -------------------------------------------------------------------------------
    def tick(self, now: float) -> dict | None:
        """Return the next ``narration.speak`` payload if one should be published now."""
        if self.current and now >= self.current_deadline:
            self.current = None  # TTS never answered; don't stall the narrator
        if self.current:
            return None
        self._drop_stale(now)
        if not self.items:
            return None
        nxt = max(self.items, key=lambda i: (i.priority, -i.seq))
        self.items.remove(nxt)
        self.current = {"id": f"n{nxt.seq}", "text": nxt.text, "voice": nxt.voice}
        self.current_deadline = now + speak_timeout(nxt.text)
        return dict(self.current)

    # ---- helpers ------------------------------------------------------------------------------
    def _drop_stale(self, now: float) -> None:
        self.items = [i for i in self.items if now - i.added <= MAX_AGE_S]

    def _forget_old(self, now: float) -> None:
        self.recent = {t: at for t, at in self.recent.items() if now - at < DEDUPE_S}


async def run(hub: Any, config: dict | None = None, clock=time.monotonic) -> None:
    """Brain entrypoint (C7)."""
    q = NarrationQueue((config or {}).get("NARRATION_MAX_CHARS", DEFAULT_MAX_CHARS))

    async def on_say(env: dict) -> None:
        q.say(env.get("data") or {}, clock())

    async def on_done(env: dict) -> None:
        q.done(env.get("data") or {})

    async def on_reset(_env: dict) -> None:
        q.reset()

    hub.sub("narration.say", on_say)
    hub.sub("narration.done", on_done)
    hub.sub("system.reset", on_reset)
    while True:
        speak = q.tick(clock())
        if speak is not None:
            await hub.pub("narration.speak", speak)
        await asyncio.sleep(TICK_S)
