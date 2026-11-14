"""Tests against a minimal in-test hub (not the real T07 server)."""
import asyncio
import json
import logging

import pytest
from websockets.asyncio.server import serve

from server.common.hub_client import HubClient, topic_matches


def run(coro):
    return asyncio.run(asyncio.wait_for(coro, 20))


class MiniHub:
    """Just enough of C2: sub with prefix patterns, pub fan-out to subscribers."""

    def __init__(self):
        self.clients = {}
        self.server = None
        self.sub_msgs = []

    async def handler(self, ws):
        self.clients[ws] = set()
        try:
            async for raw in ws:
                msg = json.loads(raw)
                if msg["op"] == "sub":
                    self.sub_msgs.append(msg["topics"])
                    self.clients[ws].update(msg["topics"])
                elif msg["op"] == "pub":
                    env = {k: msg[k] for k in ("topic", "ts", "src", "data")}
                    for c, pats in list(self.clients.items()):
                        if any(topic_matches(p, env["topic"]) for p in pats):
                            await c.send(json.dumps(env))
        finally:
            self.clients.pop(ws, None)

    async def start(self, port=0):
        self.server = await serve(self.handler, "127.0.0.1", port)
        self.port = next(iter(self.server.sockets)).getsockname()[1]
        return self

    async def stop(self):
        self.server.close()
        await self.server.wait_closed()

    async def wait_subs(self, n):
        for _ in range(200):
            if sum(len(p) for p in self.clients.values()) >= n:
                return
            await asyncio.sleep(0.01)
        raise AssertionError("subscriptions never arrived")


def test_pub_sub_round_trip():
    async def main():
        hub = await MiniHub().start()
        url = f"ws://127.0.0.1:{hub.port}/hub"
        a = await HubClient.connect(url, "a")
        b = await HubClient.connect(url, "b")
        got = asyncio.Queue()

        async def on_vision(env):
            await got.put(env)

        a.sub("vision.*", on_vision)
        await hub.wait_subs(1)
        assert await b.pub("world.current", {"x": 1})
        assert await b.pub("vision.state", {"frame_ts": 1.0})
        env = await asyncio.wait_for(got.get(), 2)
        assert env["topic"] == "vision.state" and env["src"] == "b" and env["data"] == {"frame_ts": 1.0}
        assert isinstance(env["ts"], float)
        await asyncio.sleep(0.1)
        assert got.empty()
        await a.close()
        await b.close()
        await hub.stop()
    run(main())


def test_resubscribes_after_server_restart():
    async def main():
        hub = await MiniHub().start()
        port = hub.port
        url = f"ws://127.0.0.1:{port}/hub"
        a = await HubClient.connect(url, "a", min_delay=0.05, max_delay=0.2)
        got = asyncio.Queue()
        a.sub("audio.beat", got.put)  # a coroutine function works directly
        await hub.wait_subs(1)

        await hub.stop()
        for _ in range(100):
            if not a.connected:
                break
            await asyncio.sleep(0.01)
        assert not a.connected
        assert await a.pub("audio.beat", {}) is False  # dropped while down

        hub2 = await MiniHub().start(port)
        await a.wait_connected(5)
        await hub2.wait_subs(1)
        assert hub2.sub_msgs == [["audio.beat"]]
        b = await HubClient.connect(url, "b")
        await b.pub("audio.beat", {"tempo_bpm": 120, "strength": 0.5})
        env = await asyncio.wait_for(got.get(), 2)
        assert env["data"]["tempo_bpm"] == 120
        assert a.reconnects == 1
        await a.close()
        await b.close()
        await hub2.stop()
    run(main())


def test_raising_callback_is_logged_and_delivery_continues(caplog):
    async def main():
        hub = await MiniHub().start()
        url = f"ws://127.0.0.1:{hub.port}/hub"
        a = await HubClient.connect(url, "a")
        got = []

        async def bad(env):
            raise RuntimeError("boom")

        def good(env):  # plain functions are accepted too
            got.append(env["data"]["n"])

        a.sub("t.*", bad)
        a.sub("t.*", good)
        await hub.wait_subs(1)
        await a.pub("t.x", {"n": 1})
        await a.pub("t.x", {"n": 2})
        for _ in range(100):
            if len(got) == 2:
                break
            await asyncio.sleep(0.01)
        assert got == [1, 2]
        await a.close()
        await hub.stop()

    with caplog.at_level(logging.ERROR, logger="hub_client"):
        run(main())
    failures = [r for r in caplog.records if r.exc_info and "boom" in str(r.exc_info[1])]
    assert len(failures) == 2


def test_connect_timeout_when_no_hub():
    async def main():
        with pytest.raises(asyncio.TimeoutError):
            await HubClient.connect("ws://127.0.0.1:9/hub", "x", timeout=0.3, min_delay=0.05)
    run(main())


def test_unsubscribe():
    async def main():
        hub = await MiniHub().start()
        url = f"ws://127.0.0.1:{hub.port}/hub"
        a = await HubClient.connect(url, "a")
        got = []
        off = a.sub("t", lambda e: got.append(1))
        await hub.wait_subs(1)
        await a.pub("t", {})
        await asyncio.sleep(0.1)
        off()
        await a.pub("t", {})
        await asyncio.sleep(0.1)
        assert got == [1]
        await a.close()
        await hub.stop()
    run(main())
