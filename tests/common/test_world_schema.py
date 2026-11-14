import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from server.common.schemas import SCHEMA_DIR, validate_world

REPO = Path(__file__).resolve().parents[2]

# Whitepaper §7.7 example plus `id` and `music_signature` (C4).
EXAMPLE = {
    "id": "w-1a2b3c4d",
    "world": {
        "name": "The Drowned Kingdom",
        "setting": "stormy open ocean",
        "mood": "adventurous",
        "time_of_day": "dusk",
        "weather": "rain",
        "palette": ["deep teal", "storm grey", "lantern gold"],
    },
    "roles": [
        {"object_id": 3, "role": "ship", "name": "The Salt Queen", "behaviour": "neutral"},
        {"object_id": 7, "role": "lighthouse", "name": "Old Beacon", "behaviour": "friendly"},
        {"object_id": 9, "role": "sea_serpent", "name": "The Coil", "behaviour": "threat"},
    ],
    "terrain": {"open_space": "open sea", "under_table": "the deep"},
    "restyle_prompt": "first-person view at sea level in a stormy ocean at dusk, rain, wooden ships, lantern light, painterly",
    "narration": "The storm rolls in as you sail into the Drowned Kingdom. Keep clear of the Coil.",
    "music_signature": {"tempo_bpm": 96.0, "energy": 0.6, "brightness": 0.4, "chroma": [0.1] * 12},
}


def test_schema_is_valid_draft_2020_12():
    schema = json.loads((SCHEMA_DIR / "world.schema.json").read_text())
    assert schema["$schema"].endswith("2020-12/schema")
    Draft202012Validator.check_schema(schema)


def test_whitepaper_example_validates():
    assert validate_world(EXAMPLE) == []


def test_missing_restyle_prompt_is_clear():
    w = copy.deepcopy(EXAMPLE)
    del w["restyle_prompt"]
    errors = validate_world(w)
    assert len(errors) == 1
    assert "restyle_prompt" in errors[0] and "required" in errors[0]


def test_evil_behaviour_is_clear():
    w = copy.deepcopy(EXAMPLE)
    w["roles"][1]["behaviour"] = "evil"
    errors = validate_world(w)
    assert len(errors) == 1
    assert errors[0].startswith("roles[1].behaviour:")
    assert "'evil'" in errors[0]


@pytest.mark.parametrize(
    "mutate, where",
    [
        (lambda w: w["world"].__setitem__("palette", ["a", "b"]), "world.palette"),
        (lambda w: w["music_signature"].__setitem__("chroma", [0.0] * 11), "music_signature.chroma"),
        (lambda w: w["world"].__setitem__("name", "x" * 41), "world.name"),
        (lambda w: w["roles"][0].__setitem__("name", "x" * 41), "roles[0].name"),
        (lambda w: w.__setitem__("narration", "x" * 301), "narration"),
        (lambda w: w.__setitem__("restyle_prompt", "x" * 401), "restyle_prompt"),
        (lambda w: w.__setitem__("id", "world-1"), "id"),
    ],
)
def test_caps_and_shapes(mutate, where):
    w = copy.deepcopy(EXAMPLE)
    mutate(w)
    errors = validate_world(w)
    assert errors and errors[0].startswith(where + ":"), errors


def test_non_object_is_an_error_not_a_crash():
    assert validate_world(None)
    assert validate_world("world")


def test_colours_file_shape():
    colours = json.loads((REPO / "shared" / "colours.json").read_text())["colours"]
    assert len(colours) >= 80
    for word, rgb in colours.items():
        assert word == word.lower().strip()
        assert len(rgb) == 3 and all(isinstance(c, int) and 0 <= c <= 255 for c in rgb), word
    for word in EXAMPLE["world"]["palette"]:
        assert word in colours


NODE_SCRIPT = r"""
import { lookupColour, setColours, NEUTRAL } from "./web/common/colours.js";
const out = {};
setColours({ grey: [1, 2, 3], "deep teal": [4, 5, 6] });
out.stormGrey = lookupColour("storm grey");
out.grey = lookupColour("grey");
out.upper = lookupColour("  Deep  TEAL ");
out.unknown = lookupColour("unobtainium");
out.neutral = NEUTRAL;
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_colour_for_last_word_fallback():
    res = subprocess.run(
        ["node", "--input-type=module", "-e", NODE_SCRIPT],
        cwd=REPO, capture_output=True, text=True, check=True,
    )
    out = json.loads(res.stdout)
    assert out["stormGrey"] == out["grey"] == [1, 2, 3]
    assert out["upper"] == [4, 5, 6]
    assert out["unknown"] == out["neutral"]
