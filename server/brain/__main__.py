"""Run the game brain: ``python -m server.brain [--only audio,world] [--skip bridge] [--hub URL]`` (T104).

Groups: audio, lights, world, gemini, video, narration, bridge (module names work too, e.g. ``--only beat``).
The launcher (``scripts/launch.py``) runs ``--skip bridge`` here and ``--only bridge`` in a second process.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from server.brain.wiring import GROUPS, MODULES, Brain, build_shared, select_modules
from server.common.config import load_config


def _set(arg: str | None) -> set[str]:
    return {s.strip() for s in (arg or "").split(",") if s.strip()}


def default_hub_url(config: dict) -> str:
    scheme = "wss" if config.get("TLS_CERT") and config.get("TLS_KEY") else "ws"
    return f"{scheme}://127.0.0.1:{config['HUB_PORT']}/hub"  # not "localhost": Windows tries ::1 first


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="python -m server.brain", description="Genrator game brain.")
    p.add_argument("--only", help=f"comma-separated groups or modules to run ({', '.join(GROUPS)})")
    p.add_argument("--skip", help="comma-separated groups or modules to leave out")
    p.add_argument("--hub", help="hub URL (default: 127.0.0.1 and HUB_PORT from shared/config.json)")
    p.add_argument("--list", action="store_true", help="list modules and exit")
    return p.parse_args(argv)


async def amain(args) -> int:
    from server.common.hub_client import HubClient

    config = load_config()
    modules = select_modules(_set(args.only), _set(args.skip))
    if not modules:
        print("no modules selected", file=sys.stderr)
        return 2
    url = args.hub or default_hub_url(config)
    # wss:// needs the certificate trusted by Python: make_cert.sh adds 127.0.0.1 to it, and mkcert's
    # CA is in the system store (or point SSL_CERT_FILE at "$(mkcert -CAROOT)/rootCA.pem").
    logging.getLogger("brain").info("connecting to %s with %d modules", url, len(modules))
    hub = await HubClient.connect(url, "brain" if not args.only else f"brain.{args.only}")
    brain = Brain(hub, config, modules, build_shared(config, modules))
    try:
        await brain.run()
    finally:
        await hub.close()
    return 0


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=os.environ.get("GENRATOR_LOG_LEVEL", "INFO").upper(),
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if args.list:
        for m in MODULES:
            print(f"{m.group:10} {m.name:20} {m.path}{'  (optional)' if m.optional else ''}")
        return 0
    try:
        return asyncio.run(amain(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
