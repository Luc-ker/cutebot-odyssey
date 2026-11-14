"""T96 — start the whole laptop side of Genrator with one command, stop it with Ctrl-C.

    python scripts/launch.py                              # hub + brain + serial bridge, live microphone
    python scripts/launch.py --replay robot_loop          # + recorded vision scene instead of the Jetson
    python scripts/launch.py --audio-file song.wav        # play a file into the audio pipeline (no mic)
    python scripts/launch.py --no-bridge                  # no USB micro:bit plugged in
    python scripts/launch.py --jetson                     # also start the Jetson vision service over SSH

Every service runs as a subprocess with its output prefixed (``[hub]``, ``[brain]`` ...). The launcher
waits up to 20 s for each one to report ``system.health ok`` (vision counts as healthy once a
``vision.state`` arrives), prints the page URLs, then keeps running until Ctrl-C, which stops everything.
See docs/running.md.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import socket
import ssl
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HEALTH_TIMEOUT_S = 20.0
PAGES = ["eye", "map", "sound", "status", "phone"]
COLOURS = {"hub": "36", "brain": "35", "bridge": "33", "vision": "32", "jetson": "32"}
WIN = os.name == "nt"


def lan_ip() -> str:
    """The laptop's address on the local network (the one the phone and Jetson should use)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is sent; this only picks the outgoing interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def page_urls(config: dict, host: str) -> dict[str, str]:
    scheme = "https" if config.get("TLS_CERT") and config.get("TLS_KEY") else "http"
    return {p: f"{scheme}://{host}:{config['HUB_PORT']}/{p}/" for p in PAGES}


def hub_url(config: dict, host: str = "127.0.0.1") -> str:
    scheme = "wss" if config.get("TLS_CERT") and config.get("TLS_KEY") else "ws"
    return f"{scheme}://{host}:{config['HUB_PORT']}/hub"


def resolve_scene(name: str) -> Path:
    """`robot_loop`, `robot_loop.json` or a path all work."""
    for cand in (Path(name), ROOT / "scripts" / "scenes" / name, ROOT / "scripts" / "scenes" / f"{name}.json"):
        if cand.is_file():
            return cand.resolve()
    raise SystemExit(f"replay scene not found: {name} (looked in scripts/scenes/)")


def plan_services(args, config: dict) -> list[tuple[str, list[str], dict]]:
    """(name, argv, extra_env) for every subprocess, in start order."""
    py = sys.executable
    brain_env = {"GENRATOR_AUDIO_FILE": str(Path(args.audio_file).resolve())} if args.audio_file else {}
    services = [("hub", [py, "-m", "server.hub"], {}),
                ("brain", [py, "-m", "server.brain", "--skip", "bridge"], brain_env)]
    if not args.no_bridge:
        services.append(("bridge", [py, "-m", "server.brain", "--only", "bridge"], {}))
    if args.replay:
        replay = ROOT / "scripts" / "vision_replay.py"
        if not replay.is_file():
            raise SystemExit("--replay needs scripts/vision_replay.py (ticket T47), which is not in this checkout")
        services.append(("vision", [py, str(replay), str(resolve_scene(args.replay)), "--loop"], {}))
    if args.jetson:
        url = hub_url(config, lan_ip())
        remote = (f"cd {args.jetson_dir} && python3 jetson/main.py --hub {url}")
        services.append(("jetson", ["ssh", "-tt", args.jetson_user + "@" + config["JETSON_HOST"]
                                    if args.jetson_user else config["JETSON_HOST"], remote], {}))
    return services


def expected_health(names: list[str]) -> dict[str, str]:
    """service name in system.health -> launcher service it belongs to."""
    want = {"hub": "hub", "brain": "brain"}
    if "bridge" in names:
        want["serial_bridge"] = "bridge"
    if "vision" in names or "jetson" in names:
        want["vision"] = "vision"   # satisfied by any vision.state message
    return want


# --------------------------------------------------------------------------------------- processes

class Service:
    def __init__(self, name: str, argv: list[str], env: dict):
        self.name, self.argv, self.env = name, argv, env
        self.proc: asyncio.subprocess.Process | None = None
        self.pump: asyncio.Task | None = None

    def prefix(self) -> str:
        tag = f"[{self.name}]".ljust(9)
        if sys.stdout.isatty():
            return f"\033[{COLOURS.get(self.name, '37')}m{tag}\033[0m "
        return tag + " "

    async def start(self) -> None:
        env = {**os.environ, **self.env, "PYTHONUNBUFFERED": "1",
               "PYTHONPATH": str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")}
        kw = {}
        if WIN:
            kw["creationflags"] = 0x00000200  # CREATE_NEW_PROCESS_GROUP: Ctrl-C reaches only the launcher
        else:
            kw["start_new_session"] = True
        self.proc = await asyncio.create_subprocess_exec(
            *self.argv, cwd=ROOT, env=env, stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, **kw)
        self.pump = asyncio.create_task(self._pump())

    async def _pump(self) -> None:
        assert self.proc and self.proc.stdout
        pre = self.prefix()
        async for raw in self.proc.stdout:
            line = raw.decode("utf-8", "replace").rstrip()
            print(pre + line, flush=True)
        code = await self.proc.wait()
        print(f"{pre}exited with code {code}", flush=True)

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.returncode is None

    async def stop(self, grace: float = 3.0) -> None:
        if not self.running:
            return
        assert self.proc
        try:
            if WIN:
                self.proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(self.proc.pid, signal.SIGINT)
        except (ProcessLookupError, OSError, ValueError):
            pass
        try:
            await asyncio.wait_for(self.proc.wait(), grace)
        except asyncio.TimeoutError:
            self.proc.kill()
            await self.proc.wait()
        if self.pump:
            await asyncio.gather(self.pump, return_exceptions=True)


# --------------------------------------------------------------------------------------- health

async def wait_healthy(url: str, want: dict[str, str], timeout: float = HEALTH_TIMEOUT_S) -> dict[str, tuple[bool, str]]:
    """Listen to the hub until every wanted service reported ok, or timeout. Returns last status per service."""
    import websockets

    seen: dict[str, tuple[bool, str]] = {}
    deadline = time.monotonic() + timeout
    ctx = None
    if url.startswith("wss://"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False          # our own certificate, on this machine
        ctx.verify_mode = ssl.CERT_NONE
    while time.monotonic() < deadline:
        try:
            async with websockets.connect(url, ssl=ctx, open_timeout=2) as ws:
                await ws.send(json.dumps({"op": "sub", "topics": ["system.health", "vision.state"]}))
                while time.monotonic() < deadline:
                    if all(seen.get(s, (False, ""))[0] for s in want):
                        return seen
                    try:
                        raw = await asyncio.wait_for(ws.recv(), max(0.1, deadline - time.monotonic()))
                    except asyncio.TimeoutError:
                        break
                    env = json.loads(raw)
                    if env.get("topic") == "vision.state":
                        seen["vision"] = (True, "vision.state arriving")
                    else:
                        d = env.get("data") or {}
                        svc = d.get("service")
                        if isinstance(svc, str):
                            seen[svc] = (bool(d.get("ok")), str(d.get("detail", "")))
                            if svc.startswith(("jetson", "vision")) and d.get("ok"):
                                seen["vision"] = (True, d.get("detail", ""))
        except (OSError, asyncio.TimeoutError, Exception):  # hub not up yet
            await asyncio.sleep(0.5)
    return seen


def report(want: dict[str, str], seen: dict[str, tuple[bool, str]], elapsed: float) -> bool:
    all_ok = True
    print()
    for svc in want:
        ok, detail = seen.get(svc, (False, "no report yet"))
        all_ok &= ok
        print(f"  {'OK  ' if ok else 'WAIT'}  {svc:14} {detail}")
    brain_mods = sorted(s for s in seen if s.startswith("brain."))
    bad = [s for s in brain_mods if not seen[s][0]]
    if brain_mods:
        print(f"        brain modules: {len(brain_mods) - len(bad)}/{len(brain_mods)} ok"
              + (f"; not ok: {', '.join(b[6:] for b in bad)}" if bad else ""))
    print(f"\n  {'All services healthy' if all_ok else 'Not everything is healthy'} after {elapsed:.1f} s"
          + ("" if all_ok else " (see the status page for details)"))
    return all_ok


async def amain(args) -> int:
    from server.common.config import load_config

    config = load_config()
    services = [Service(n, a, e) for n, a, e in plan_services(args, config)]
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    if not WIN:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

    t0 = time.monotonic()
    try:
        for svc in services:
            await svc.start()
            if svc.name == "hub":
                await asyncio.sleep(0.5)  # let the hub bind before clients connect
        want = expected_health([s.name for s in services])
        seen = await wait_healthy(hub_url(config), want, args.timeout)
        report(want, seen, time.monotonic() - t0)
        print("\n  Pages (open on any device on the same network):")
        for page, url in page_urls(config, lan_ip()).items():
            print(f"    {page:7} {url}")
        print("\n  Ctrl-C stops everything.\n", flush=True)

        async def watch():
            while not stop.is_set():
                if not services[0].running:
                    print("[launch]  the hub stopped; shutting down", flush=True)
                    stop.set()
                await asyncio.sleep(0.5)

        watcher = asyncio.create_task(watch())
        try:
            await stop.wait()
        finally:
            watcher.cancel()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        print("\n[launch]  stopping...", flush=True)
        for svc in reversed(services):
            await svc.stop()
        print("[launch]  all stopped.", flush=True)
    return 0


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Start the laptop side of Genrator.")
    p.add_argument("--replay", metavar="SCENE", help="replay a recorded vision scene (scripts/scenes/<SCENE>.json)")
    p.add_argument("--audio-file", metavar="WAV", help="feed this audio file to the pipeline instead of the mic")
    p.add_argument("--no-bridge", action="store_true", help="don't start the USB micro:bit serial bridge")
    p.add_argument("--jetson", action="store_true", help="also start the Jetson vision service over SSH")
    p.add_argument("--jetson-user", default=os.environ.get("GENRATOR_JETSON_USER", ""), help="SSH user on the Jetson")
    p.add_argument("--jetson-dir", default="~/sonar-bot-tune", help="repo folder on the Jetson")
    p.add_argument("--timeout", type=float, default=HEALTH_TIMEOUT_S, help="seconds to wait for health (default 20)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        return asyncio.run(amain(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
