"""Hub client for Python services (T09, contract C2). Depends only on `websockets`, so it runs on the Jetson.

    hub = await HubClient.connect("ws://laptop:8765/hub", "jetson")
    hub.sub("system.reset", on_reset)          # async (or plain) callback taking the envelope
    await hub.pub("vision.state", {...})        # fills ts and src; dropped (returns False) while disconnected
    await hub.close()

Reconnects with backoff (0.5 s doubling to 5 s) and re-subscribes after every reconnect. Callbacks run in
arrival order; one that raises is logged and does not stop delivery to the others.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
from typing import Any, Awaitable, Callable

import websockets
from websockets.exceptions import ConnectionClosed

log = logging.getLogger("hub_client")

Callback = Callable[[dict], Awaitable[None] | None]


def topic_matches(pattern: str, topic: str) -> bool:
    if pattern.endswith("*"):
        return topic.startswith(pattern[:-1])
    return pattern == topic


class HubClient:
    def __init__(self, url: str, src: str, min_delay: float = 0.5, max_delay: float = 5.0):
        self.url = url
        self.src = src
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._handlers: dict[str, list[Callback]] = {}
        self._ws = None
        self._connected = asyncio.Event()
        self._closing = False
        self._task: asyncio.Task | None = None
        self.reconnects = 0

    # ------------------------------------------------------------------ public API

    @classmethod
    async def connect(cls, url: str, src: str, timeout: float | None = None, **kw) -> "HubClient":
        """Create a client and wait until the first connection is open (retrying with backoff)."""
        client = cls(url, src, **kw)
        client._task = asyncio.create_task(client._run(), name=f"hub-client-{src}")
        try:
            await asyncio.wait_for(client._connected.wait(), timeout)
        except BaseException:
            await client.close()
            raise
        return client

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    async def pub(self, topic: str, data: Any = None) -> bool:
        """Publish `data` on `topic`. Returns False (message dropped) when not connected."""
        ws = self._ws
        if ws is None or not self.connected:
            return False
        env = {"op": "pub", "topic": topic, "ts": time.time(), "src": self.src,
               "data": {} if data is None else data}
        try:
            await ws.send(json.dumps(env, separators=(",", ":")))
            return True
        except ConnectionClosed:
            return False

    def sub(self, pattern: str, callback: Callback) -> Callable[[], None]:
        """Register a callback for `pattern` (trailing `*` = prefix). Returns a function that removes it."""
        cbs = self._handlers.setdefault(pattern, [])
        new_pattern = not cbs
        cbs.append(callback)
        if new_pattern and self.connected:
            asyncio.ensure_future(self._send_sub([pattern]))

        def unsubscribe() -> None:
            if callback in cbs:
                cbs.remove(callback)

        return unsubscribe

    async def close(self) -> None:
        self._closing = True
        if self._ws is not None:
            await self._ws.close()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

    async def wait_connected(self, timeout: float | None = None) -> None:
        await asyncio.wait_for(self._connected.wait(), timeout)

    # ------------------------------------------------------------------ internals

    async def _send_sub(self, patterns: list[str]) -> None:
        ws = self._ws
        if ws is None or not patterns:
            return
        try:
            await ws.send(json.dumps({"op": "sub", "topics": patterns}))
        except ConnectionClosed:
            pass

    async def _dispatch(self, env: dict) -> None:
        topic = env.get("topic")
        if not isinstance(topic, str):
            return
        for pattern, cbs in list(self._handlers.items()):
            if not topic_matches(pattern, topic):
                continue
            for cb in list(cbs):
                try:
                    res = cb(env)
                    if inspect.isawaitable(res):
                        await res
                except Exception:
                    log.exception("hub callback for %r failed on %r", pattern, topic)

    async def _run(self) -> None:
        delay = self.min_delay
        first = True
        while not self._closing:
            try:
                async with websockets.connect(self.url, max_size=8 * 1024 * 1024) as ws:
                    self._ws = ws
                    delay = self.min_delay
                    await self._send_sub(list(self._handlers))
                    if not first:
                        self.reconnects += 1
                        log.info("reconnected to %s", self.url)
                    first = False
                    self._connected.set()
                    async for raw in ws:
                        try:
                            env = json.loads(raw)
                        except ValueError:
                            continue
                        if isinstance(env, dict):
                            await self._dispatch(env)
            except asyncio.CancelledError:
                raise
            except (OSError, ConnectionClosed, websockets.InvalidHandshake, asyncio.TimeoutError) as exc:
                log.debug("hub connection to %s failed: %s", self.url, exc)
            finally:
                self._ws = None
                self._connected.clear()
            if self._closing:
                break
            await asyncio.sleep(delay)
            delay = min(delay * 2, self.max_delay)
