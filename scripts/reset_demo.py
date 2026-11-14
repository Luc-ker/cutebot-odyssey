"""T63 — One-command demo reset.

    python scripts/reset_demo.py [--url wss://laptop:8765/hub]

Publishes ``system.reset`` on the hub. Every stateful module clears itself on
that topic, and the brain's reset module (server/world/reset.py) then
re-selects the default ``kingdom`` world.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def default_url(config: dict) -> str:
    scheme = "wss" if config.get("TLS_CERT") else "ws"
    return f"{scheme}://localhost:{config.get('HUB_PORT', 8765)}/hub"


async def reset_demo(hub) -> None:
    await hub.pub("system.reset", {})


async def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Reset the Genrator demo to a clean start.")
    parser.add_argument("--url", help="hub URL (default from shared/config.json)")
    args = parser.parse_args(argv)

    from server.common.config import load_config  # T01
    from server.common.hub_client import HubClient  # T09

    config = load_config()
    hub = await HubClient.connect(args.url or default_url(config), "reset_demo")
    await reset_demo(hub)
    await asyncio.sleep(0.3)  # let the message flush before we exit
    close = getattr(hub, "close", None)
    if close:
        await close()
    print("system.reset sent")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
