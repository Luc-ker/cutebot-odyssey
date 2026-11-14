"""Run the hub: `python -m server.hub` (T07)."""
import asyncio
import logging
import os

from server.common.config import load_config
from server.hub.server import run


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("GENRATOR_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    try:
        asyncio.run(run(load_config()))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
