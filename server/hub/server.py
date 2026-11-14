"""The hub: WebSocket pub/sub at `/hub` plus static files, on one port (T07, contract C2).

- `{"op": "sub", "topics": [...]}` adds subscription patterns (a trailing `*` is a prefix match).
- `{"op": "pub", "topic", "ts", "src", "data"}` fans the envelope out to every matching subscriber,
  including the sender only if it subscribed. `data` is never changed.
- `web/` is served at `/`, `shared/` at `/shared/`.
- Every client has its own outbound queue and writer task, so a slow client never blocks the others.
  High-rate topics (`vision.*`, `audio.*`, `camera.*`, `robot.state`, `world.objects`) drop the oldest queued
  message when that client falls behind; everything else (`world.event`, `narration.*`, ...) is never dropped.
- Bulk topics (`camera.*`, the phone's frames as JPEG) only reach clients that subscribe to them by a
  pattern naming them, such as `camera.frame` or `camera.*`. A catch-all like `*` does not get them, so the
  status page doesn't download video it never shows.
  A client whose reliable backlog exceeds `RELIABLE_MAX` is considered dead and disconnected.
"""
from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import ssl
import time
from collections import deque
from email.utils import formatdate
from pathlib import Path
from urllib.parse import unquote

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

log = logging.getLogger("hub")

REPO_ROOT = Path(__file__).resolve().parents[2]
HUB_PATH = "/hub"
LOSSY_PREFIXES = ("vision.", "audio.", "camera.")
BULK_PREFIXES = ("camera.",)
LOSSY_TOPICS = {"robot.state", "world.objects"}
LOSSY_MAX = 32          # queued high-rate messages per client before the oldest is dropped
RELIABLE_MAX = 5000     # queued never-drop messages per client before the client is disconnected
HEALTH_INTERVAL_S = 2.0


def is_lossy(topic: str) -> bool:
    return topic in LOSSY_TOPICS or topic.startswith(LOSSY_PREFIXES)


def topic_matches(pattern: str, topic: str) -> bool:
    if pattern.endswith("*"):
        prefix = pattern[:-1]
        if not topic.startswith(prefix):
            return False
        # Bulk topics need a pattern that names their prefix: "camera.*" yes, "*" or "c*" no.
        return not any(topic.startswith(b) and not prefix.startswith(b) for b in BULK_PREFIXES)
    return pattern == topic


class Client:
    """One connected socket: its subscriptions and its outbound queue."""

    def __init__(self, ws: ServerConnection):
        self.ws = ws
        self.patterns: set[str] = set()
        self.queue: deque[tuple[bool, str]] = deque()  # (lossy, text)
        self.lossy_count = 0
        self.dropped = 0
        self.wake = asyncio.Event()
        self.closed = False

    def wants(self, topic: str) -> bool:
        return any(topic_matches(p, topic) for p in self.patterns)

    def enqueue(self, topic: str, text: str) -> bool:
        """Queue a message. Returns False if the client should be disconnected."""
        lossy = is_lossy(topic)
        if lossy:
            if self.lossy_count >= LOSSY_MAX:
                for i, (was_lossy, _) in enumerate(self.queue):
                    if was_lossy:
                        del self.queue[i]
                        self.lossy_count -= 1
                        self.dropped += 1
                        break
            self.lossy_count += 1
        elif len(self.queue) - self.lossy_count >= RELIABLE_MAX:
            return False
        self.queue.append((lossy, text))
        self.wake.set()
        return True

    async def writer(self) -> None:
        try:
            while not self.closed:
                if not self.queue:
                    self.wake.clear()
                    await self.wake.wait()
                    continue
                lossy, text = self.queue.popleft()
                if lossy:
                    self.lossy_count -= 1
                await self.ws.send(text)
        except ConnectionClosed:
            pass


class HubServer:
    def __init__(self, web_dir: Path | str | None = None, shared_dir: Path | str | None = None,
                 health_interval: float = HEALTH_INTERVAL_S):
        self.web_dir = Path(web_dir or REPO_ROOT / "web").resolve()
        self.shared_dir = Path(shared_dir or REPO_ROOT / "shared").resolve()
        self.health_interval = health_interval
        self.clients: set[Client] = set()
        self.server: Server | None = None
        self._health_task: asyncio.Task | None = None

    # ------------------------------------------------------------------ pub/sub

    def publish(self, envelope: dict) -> int:
        """Fan an envelope out to matching subscribers. Returns how many clients it was queued for."""
        topic = envelope["topic"]
        targets = [c for c in self.clients if not c.closed and c.wants(topic)]
        if not targets:
            return 0
        text = json.dumps(envelope, separators=(",", ":"))
        for c in targets:
            if not c.enqueue(topic, text):
                log.warning("client %s fell too far behind; disconnecting", c.ws.remote_address)
                c.closed = True
                c.wake.set()
                asyncio.ensure_future(c.ws.close(code=1013, reason="too slow"))
        return len(targets)

    def _handle_message(self, client: Client, raw: str | bytes) -> None:
        try:
            msg = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            log.warning("dropping non-JSON message from %s", client.ws.remote_address)
            return
        if not isinstance(msg, dict):
            return
        op = msg.get("op")
        if op == "sub":
            topics = msg.get("topics")
            if isinstance(topics, str):
                topics = [topics]
            if isinstance(topics, list):
                client.patterns.update(t for t in topics if isinstance(t, str) and t)
        elif op == "unsub":
            topics = msg.get("topics") or []
            client.patterns.difference_update(topics if isinstance(topics, list) else [topics])
        elif op == "pub":
            topic = msg.get("topic")
            if not isinstance(topic, str) or not topic:
                log.warning("dropping pub without topic from %s", client.ws.remote_address)
                return
            ts = msg.get("ts")
            envelope = {
                "topic": topic,
                "ts": ts if isinstance(ts, (int, float)) and not isinstance(ts, bool) else time.time(),
                "src": msg.get("src") if isinstance(msg.get("src"), str) else "",
                "data": msg.get("data") if "data" in msg else {},
            }
            self.publish(envelope)
        else:
            log.debug("ignoring message with op=%r", op)

    async def _handler(self, ws: ServerConnection) -> None:
        client = Client(ws)
        self.clients.add(client)
        writer = asyncio.create_task(client.writer())
        log.info("client connected %s (%d total)", ws.remote_address, len(self.clients))
        try:
            async for raw in ws:
                self._handle_message(client, raw)
        except ConnectionClosed:
            pass
        finally:
            client.closed = True
            client.wake.set()
            self.clients.discard(client)
            writer.cancel()
            log.info("client left %s (%d total)", ws.remote_address, len(self.clients))

    # ------------------------------------------------------------------ static files

    def _resolve_static(self, url_path: str) -> Path | None:
        path = url_path.split("?", 1)[0].split("#", 1)[0]
        if path.startswith("/shared/") or path == "/shared":
            base, rel = self.shared_dir, path[len("/shared"):]
        else:
            base, rel = self.web_dir, path
        target = (base / unquote(rel).lstrip("/")).resolve()
        if target != base and base not in target.parents:
            return None  # path traversal
        if target.is_dir():
            target = target / "index.html"
        return target if target.is_file() else None

    def _process_request(self, connection: ServerConnection, request: Request) -> Response | None:
        if request.path.split("?", 1)[0] == HUB_PATH:
            return None  # proceed with the WebSocket handshake
        target = self._resolve_static(request.path)
        if target is None:
            return self._response(404, "Not Found", b"Not Found\n", "text/plain; charset=utf-8")
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        return self._response(200, "OK", target.read_bytes(), ctype)

    @staticmethod
    def _response(status: int, reason: str, body: bytes, ctype: str) -> Response:
        headers = Headers()
        headers["Date"] = formatdate(usegmt=True)
        headers["Content-Type"] = ctype
        headers["Content-Length"] = str(len(body))
        headers["Cache-Control"] = "no-cache"
        headers["Connection"] = "close"
        return Response(status, reason, headers, body)

    # ------------------------------------------------------------------ lifecycle

    async def _health_loop(self) -> None:
        while True:
            await asyncio.sleep(self.health_interval)
            self.publish({
                "topic": "system.health", "ts": time.time(), "src": "hub",
                "data": {"service": "hub", "ok": True, "detail": f"{len(self.clients)} clients"},
            })

    async def start(self, host: str = "0.0.0.0", port: int = 8765, ssl_context: ssl.SSLContext | None = None) -> Server:
        self.server = await serve(
            self._handler, host, port, ssl=ssl_context, process_request=self._process_request,
            max_size=8 * 1024 * 1024, ping_interval=20, ping_timeout=20,
        )
        self._health_task = asyncio.create_task(self._health_loop())
        return self.server

    @property
    def port(self) -> int:
        assert self.server is not None
        return next(iter(self.server.sockets)).getsockname()[1]

    async def stop(self) -> None:
        if self._health_task:
            self._health_task.cancel()
        if self.server:
            self.server.close()
            await self.server.wait_closed()


def make_ssl_context(cert: str, key: str) -> ssl.SSLContext | None:
    """An SSL context when both paths are set (relative paths resolve from the repo root)."""
    if not cert or not key:
        return None
    resolve = lambda p: str(p if Path(p).is_absolute() else REPO_ROOT / p)  # noqa: E731
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(resolve(cert), resolve(key))
    return ctx


async def run(config: dict, host: str = "0.0.0.0", stop: asyncio.Future | None = None) -> None:
    """Run the hub until `stop` resolves (forever if None)."""
    ctx = make_ssl_context(config.get("TLS_CERT", ""), config.get("TLS_KEY", ""))
    hub = HubServer()
    await hub.start(host, int(config["HUB_PORT"]), ctx)
    scheme = "https" if ctx else "http"
    log.info("hub on %s://%s:%d  (WebSocket %s)", scheme, host, hub.port, HUB_PATH)
    try:
        await (stop if stop is not None else asyncio.get_running_loop().create_future())
    finally:
        await hub.stop()
