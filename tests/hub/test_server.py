import asyncio
import base64
import json
import os
import socket
import time
import urllib.request
from pathlib import Path

import pytest
from websockets.asyncio.client import connect

from server.hub import server as hubmod
from server.hub.server import Client, HubServer, topic_matches

REPO = Path(__file__).resolve().parents[2]


def run(coro):
    return asyncio.run(asyncio.wait_for(coro, 20))


class Running:
    def __init__(self, **kw):
        self.hub = HubServer(**kw)

    async def __aenter__(self):
        await self.hub.start("127.0.0.1", 0)
        self.url = f"ws://127.0.0.1:{self.hub.port}/hub"
        return self

    async def __aexit__(self, *exc):
        await self.hub.stop()


async def sub(ws, *topics):
    await ws.send(json.dumps({"op": "sub", "topics": list(topics)}))


async def pub(ws, topic, data, src="test"):
    await ws.send(json.dumps({"op": "pub", "topic": topic, "ts": time.time(), "src": src, "data": data}))


async def recv(ws, timeout=2.0):
    return json.loads(await asyncio.wait_for(ws.recv(), timeout))


async def nothing(ws, timeout=0.3):
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(ws.recv(), timeout)


VISION = {"frame_ts": 1.0, "objects": [{"id": 3, "cls": "cup", "pos": [0.25, 0.5], "size": [0.1, 0.1], "conf": 0.9}],
          "giants": []}


def test_topic_matching():
    assert topic_matches("vision.*", "vision.state")
    assert not topic_matches("vision.*", "world.current")
    assert topic_matches("*", "anything")
    assert topic_matches("audio.beat", "audio.beat")
    assert not topic_matches("audio.beat", "audio.beats")


def test_camera_frames_only_reach_clients_that_ask_for_them():
    assert topic_matches("camera.frame", "camera.frame")
    assert topic_matches("camera.*", "camera.frame")
    assert not topic_matches("*", "camera.frame")
    assert not topic_matches("cam*", "camera.frame")
    assert topic_matches("*", "vision.state")


def test_pub_sub_unchanged_and_filtered():
    async def main():
        async with Running(health_interval=3600) as h:
            async with connect(h.url) as a, connect(h.url) as b:
                await sub(a, "vision.*")
                await asyncio.sleep(0.05)
                await pub(b, "world.current", {"world": {}, "previous_id": None})
                await pub(b, "vision.state", VISION, src="vision")
                env = await recv(a)
                assert env["topic"] == "vision.state"
                assert env["src"] == "vision"
                assert env["data"] == VISION
                assert set(env) == {"topic", "ts", "src", "data"}
                await nothing(a)  # world.current was not delivered
                await nothing(b)  # B did not subscribe, so no echo
    run(main())


def test_sender_receives_own_message_only_if_subscribed():
    async def main():
        async with Running(health_interval=3600) as h:
            async with connect(h.url) as a:
                await sub(a, "audio.beat")
                await asyncio.sleep(0.05)
                await pub(a, "audio.beat", {"tempo_bpm": 120, "strength": 1})
                assert (await recv(a))["topic"] == "audio.beat"
    run(main())


async def raw_stalled_client(port, topics):
    """A WebSocket client that handshakes, subscribes, then never reads (tiny receive buffer)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2048)
    sock.setblocking(False)
    loop = asyncio.get_running_loop()
    await loop.sock_connect(sock, ("127.0.0.1", port))
    key = base64.b64encode(os.urandom(16)).decode()
    await loop.sock_sendall(sock, (
        f"GET /hub HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
    head = b""
    while b"\r\n\r\n" not in head:
        head += await loop.sock_recv(sock, 1)
    assert head.startswith(b"HTTP/1.1 101")
    payload = json.dumps({"op": "sub", "topics": topics}).encode()
    mask = os.urandom(4)
    assert len(payload) < 126
    frame = bytes([0x81, 0x80 | len(payload)]) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    await loop.sock_sendall(sock, frame)
    return sock


def test_stalled_client_does_not_delay_others():
    async def main():
        async with Running(health_interval=3600) as h:
            stalled = await raw_stalled_client(h.hub.port, ["*"])
            async with connect(h.url, max_size=None) as good, connect(h.url) as producer:
                await sub(good, "world.event")
                await asyncio.sleep(0.1)
                blob = "x" * 200_000
                for i in range(60):  # ~12 MB, far more than socket buffers
                    await pub(producer, "world.event", {"kind": "horn", "i": i, "pad": blob})
                t0 = time.monotonic()
                for i in range(60):
                    assert (await recv(good, timeout=5))["data"]["i"] == i
                assert time.monotonic() - t0 < 5
                stalled_client = next(c for c in h.hub.clients if "*" in c.patterns)
                assert len(stalled_client.queue) > 0  # it really is backed up
            stalled.close()
    run(main())


def test_slow_client_drops_oldest_lossy_but_never_world_event(monkeypatch):
    monkeypatch.setattr(hubmod, "LOSSY_MAX", 3)

    class FakeWs:
        remote_address = ("x", 1)

    async def main():
        c = Client(FakeWs())
        c.patterns.add("*")
        c.enqueue("world.event", "E0")
        for i in range(10):
            c.enqueue("vision.state", f"V{i}")
        c.enqueue("narration.say", "N0")
        texts = [t for _, t in c.queue]
        assert texts == ["E0", "V7", "V8", "V9", "N0"]
        assert c.dropped == 7
    run(main())


def test_static_files_and_traversal():
    async def main():
        async with Running(health_interval=3600) as h:
            base = f"http://127.0.0.1:{h.hub.port}"
            loop = asyncio.get_running_loop()

            def get(path):
                try:
                    with urllib.request.urlopen(base + path, timeout=5) as r:
                        return r.status, r.headers.get("Content-Type"), r.read()
                except urllib.error.HTTPError as e:
                    return e.code, None, b""

            status, ctype, body = await loop.run_in_executor(None, get, "/shared/config.json")
            assert status == 200 and ctype.startswith("application/json")
            assert body == (REPO / "shared" / "config.json").read_bytes()
            status, ctype, _ = await loop.run_in_executor(None, get, "/common/config.js")
            assert status == 200 and "javascript" in ctype
            assert (await loop.run_in_executor(None, get, "/shared/../server/hub/server.py"))[0] == 404
            assert (await loop.run_in_executor(None, get, "/shared/%2e%2e/server/hub/server.py"))[0] == 404
            assert (await loop.run_in_executor(None, get, "/nope.txt"))[0] == 404
    run(main())


def test_hub_publishes_health():
    async def main():
        async with Running(health_interval=0.1) as h:
            async with connect(h.url) as a:
                await sub(a, "system.*")
                env = await recv(a)
                assert env["topic"] == "system.health"
                assert env["src"] == "hub"
                assert env["data"]["service"] == "hub" and env["data"]["ok"] is True
    run(main())


def test_bad_messages_are_ignored():
    async def main():
        async with Running(health_interval=3600) as h:
            async with connect(h.url) as a:
                await a.send("not json")
                await a.send(json.dumps([1, 2]))
                await a.send(json.dumps({"op": "pub", "data": {}}))
                await sub(a, "ok.*")
                await asyncio.sleep(0.05)
                await pub(a, "ok.test", {"v": 1})
                assert (await recv(a))["data"] == {"v": 1}
    run(main())
