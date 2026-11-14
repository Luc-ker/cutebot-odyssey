"""Validated pre-composed fallback worlds (T75, contract C7)."""

from __future__ import annotations

import json
from pathlib import Path

from server.common.schemas import validate_world

WORLDS_DIR = Path(__file__).resolve().parents[2] / "shared" / "worlds"
COLOURS_PATH = Path(__file__).resolve().parents[2] / "shared" / "colours.json"
FALLBACK_WORLD_ORDER = (
    "ocean", "wasteland", "snowy_village", "kingdom",
    "neon_city", "rainforest", "royal_court", "space_station",
)


def load_fallback_worlds(path: str | Path | None = None) -> list[dict]:
    """Load fallback world JSON in a fixed order and reject invalid bundled data."""
    directory = Path(path) if path is not None else WORLDS_DIR
    colour_data = json.loads(COLOURS_PATH.read_text(encoding="utf-8"))
    colours = colour_data.get("colours", colour_data)
    worlds = []
    names = set()
    for key in FALLBACK_WORLD_ORDER:
        world_path = directory / f"{key}.json"
        world = json.loads(world_path.read_text(encoding="utf-8"))
        errors = validate_world(world)
        if errors:
            raise ValueError(f"Invalid fallback world {world_path.name}: {'; '.join(errors)}")
        name = world["world"]["name"].casefold()
        if name in names:
            raise ValueError(f"Duplicate fallback world name: {world['world']['name']}")
        names.add(name)
        missing = [colour for colour in world["world"]["palette"] if colour.casefold() not in colours]
        if missing:
            raise ValueError(f"Unknown palette colours in {world_path.name}: {', '.join(missing)}")
        world.setdefault("key", key)
        worlds.append(world)
    return worlds