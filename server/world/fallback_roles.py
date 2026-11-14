"""T51 — Local fallback role picker.

Gives an object a sensible role without Gemini (slow or offline), from the role
vocabulary (C5, ``shared/roles.json``), the world's setting and the detector class.

Contract (C7)::

    pick_role(world, cls, taken_roles, *, obj_id=0, vocab=None) -> {"role", "name", "behaviour"}

``world`` is a C4 World (or just its inner ``world`` dict). ``taken_roles`` is the
list of role names already used by other objects in this world.

Scoring per non-system role:
  +2 a role ``worlds`` keyword matches the world's setting/name,
  +1 the role is marked for any world (``"*"``, ``"any"``, ``"all"``, ``"most"``),
  +2 the detector class is in the role's ``classes``,
  +1 the role is not already taken.
Ties break on a stable hash of (object id, role), so the same inputs always
give the same answer. At most one threat per four objects (counted as
``len(taken_roles) + 1``, rounded up) unless the world's mood is dark.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROLES_PATH = Path(__file__).resolve().parents[2] / "shared" / "roles.json"

# Used only until T03 ships shared/roles.json.
DEFAULT_VOCAB = [
    {"role": "castle", "behaviour": "neutral", "sfx": "bell", "worlds": ["kingdom", "court"], "classes": ["chair", "box"]},
    {"role": "fortress", "behaviour": "neutral", "sfx": "drum", "worlds": ["wasteland", "volcanic"], "classes": ["chair", "box"]},
    {"role": "temple", "behaviour": "neutral", "sfx": "gong", "worlds": ["jungle", "rainforest"], "classes": ["chair", "vase"]},
    {"role": "skyscraper", "behaviour": "neutral", "sfx": "hum", "worlds": ["city", "neon"], "classes": ["bottle", "chair"]},
    {"role": "palace", "behaviour": "neutral", "sfx": "fanfare", "worlds": ["court", "royal"], "classes": ["chair"]},
    {"role": "watchtower", "behaviour": "friendly", "sfx": "bell", "worlds": ["snow", "kingdom", "*"], "classes": ["bottle", "chair"]},
    {"role": "lighthouse", "behaviour": "friendly", "sfx": "foghorn", "worlds": ["ocean", "sea", "coast"], "classes": ["bottle", "vase"]},
    {"role": "beacon", "behaviour": "friendly", "sfx": "chime", "worlds": ["*"], "classes": ["bottle", "cup"]},
    {"role": "village", "behaviour": "friendly", "sfx": "chatter", "worlds": ["*"], "classes": ["cup", "bowl"]},
    {"role": "harbour", "behaviour": "friendly", "sfx": "gulls", "worlds": ["ocean", "sea"], "classes": ["bowl", "book"]},
    {"role": "ship", "behaviour": "neutral", "sfx": "creak", "worlds": ["ocean", "sea"], "classes": ["bottle", "shoe", "remote"]},
    {"role": "boat", "behaviour": "neutral", "sfx": "splash", "worlds": ["ocean", "sea", "river"], "classes": ["cup", "phone"]},
    {"role": "forest", "behaviour": "neutral", "sfx": "birds", "worlds": ["kingdom", "jungle"], "classes": ["potted plant"]},
    {"role": "mountain", "behaviour": "neutral", "sfx": "wind", "worlds": ["wasteland", "snow"], "classes": ["backpack", "book"]},
    {"role": "volcano", "behaviour": "neutral", "sfx": "rumble", "worlds": ["wasteland", "volcanic"], "classes": ["cup", "vase"]},
    {"role": "glacier", "behaviour": "neutral", "sfx": "crack", "worlds": ["snow", "ice"], "classes": ["book", "laptop"]},
    {"role": "bridge", "behaviour": "neutral", "sfx": "creak", "worlds": ["*"], "classes": ["book", "keyboard"]},
    {"role": "treasure", "behaviour": "friendly", "sfx": "sparkle", "worlds": ["*"], "classes": ["cup", "clock"]},
    {"role": "crystal", "behaviour": "friendly", "sfx": "sparkle", "worlds": ["space", "snow", "*"], "classes": ["bottle", "wine glass"]},
    {"role": "dragon", "behaviour": "threat", "sfx": "roar", "worlds": ["kingdom", "wasteland"], "classes": ["teddy bear", "shoe"]},
    {"role": "sea_serpent", "behaviour": "threat", "sfx": "hiss", "worlds": ["ocean", "sea"], "classes": ["remote", "scissors"]},
    {"role": "lava_beast", "behaviour": "threat", "sfx": "roar", "worlds": ["wasteland", "volcanic"], "classes": ["teddy bear"]},
    {"role": "yeti", "behaviour": "threat", "sfx": "growl", "worlds": ["snow"], "classes": ["teddy bear"]},
    {"role": "robot_sentinel", "behaviour": "threat", "sfx": "beep", "worlds": ["city", "neon", "space"], "classes": ["phone", "mouse"]},
    {"role": "giant", "behaviour": "neutral", "system_only": True, "worlds": ["*"], "classes": []},
]

GENERIC_WORLDS = {"*", "any", "all", "most"}
DARK_MOODS = ("dark", "ominous", "menacing", "sinister", "grim", "forebod", "eerie", "brooding", "dread", "doom")

# Name parts per setting family; first family whose keyword appears in the setting wins.
_NAME_PARTS = [
    (("ocean", "sea", "coast", "pirate", "island"),
     ["Salt", "Drowned", "Tidal", "Brine", "Coral", "Storm"], ["Tides", "Gulls", "Deep", "Kraken", "Queen"]),
    (("wasteland", "volcan", "lava", "ash", "metal"),
     ["Burning", "Ashen", "Iron", "Molten", "Scorched", "Black"], ["Embers", "Cinders", "Forge", "Skulls", "Warlord"]),
    (("snow", "ice", "frost", "winter", "arctic"),
     ["Frozen", "Silent", "White", "Frost", "Pale", "Hollow"], ["Winter", "Wolves", "Stars", "North", "Lantern"]),
    (("city", "neon", "cyber", "synth", "urban"),
     ["Neon", "Chrome", "Midnight", "Electric", "Glass", "Static"], ["Signals", "Grid", "Wires", "Pulse", "Circuit"]),
    (("jungle", "rainforest", "forest", "tropical"),
     ["Emerald", "Hidden", "Ancient", "Mossy", "Vine", "Golden"], ["Jaguar", "Vines", "Sun", "Rain", "Idols"]),
    (("space", "station", "galaxy", "star", "orbit"),
     ["Orbital", "Silent", "Distant", "Solar", "Void", "Quantum"], ["Stars", "Void", "Comets", "Engine", "Nebula"]),
    (("court", "royal", "palace", "baroque"),
     ["Gilded", "Royal", "Velvet", "Ivory", "Grand", "Crimson"], ["Crown", "Masks", "Roses", "Duchess", "Violins"]),
    ((), ["Old", "Great", "Lonely", "Golden", "Silver", "Whispering"], ["Kings", "Dawn", "Valley", "Ages", "Lady"]),
]
_TEMPLATES = ["{adj} {role}", "The {adj} {role}", "{role} of the {noun}", "The {noun} {role}"]

_vocab_cache: list | None = None


def load_vocab(path: Path | None = None) -> list:
    """The shipped roles.json, or the built-in list until T03 lands."""
    global _vocab_cache
    if path is None and _vocab_cache is not None:
        return _vocab_cache
    p = path or ROLES_PATH
    try:
        vocab = json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        vocab = DEFAULT_VOCAB
    if path is None:
        _vocab_cache = vocab
    return vocab


def _stable(*parts) -> int:
    return int.from_bytes(hashlib.sha1("|".join(map(str, parts)).encode()).digest()[:8], "big")


def _world_info(world: dict | None) -> dict:
    world = world or {}
    return world.get("world", world) if isinstance(world.get("world"), dict) else world


def _setting_text(info: dict) -> str:
    return " ".join(str(info.get(k, "")) for k in ("setting", "name")).lower()


def _role_matches_setting(role: dict, text: str, tokens: set) -> int:
    best = 0
    for kw in role.get("worlds") or []:
        kw = str(kw).lower()
        if kw in GENERIC_WORLDS:
            best = max(best, 1)
        elif kw in tokens or (len(kw) > 3 and kw in text):
            return 2
    return best


def is_dark(info: dict) -> bool:
    mood = str(info.get("mood", "")).lower()
    return any(m in mood for m in DARK_MOODS)


def make_name(role: str, info: dict, seed) -> str:
    text = _setting_text(info)
    adjs, nouns = _NAME_PARTS[-1][1], _NAME_PARTS[-1][2]
    for keys, a, n in _NAME_PARTS:
        if any(k in text for k in keys):
            adjs, nouns = a, n
            break
    h = _stable("name", seed, role)
    role_word = role.replace("_", " ").title()
    tpl = _TEMPLATES[h % len(_TEMPLATES)]
    return tpl.format(adj=adjs[(h >> 8) % len(adjs)], noun=nouns[(h >> 16) % len(nouns)], role=role_word)


def pick_role(world, cls, taken_roles, *, obj_id=0, vocab=None) -> dict:
    vocab = vocab if vocab is not None else load_vocab()
    info = _world_info(world)
    text = _setting_text(info)
    tokens = set(re.findall(r"[a-z]+", text))
    taken = list(taken_roles or [])
    taken_set = set(taken)
    cls = str(cls or "").lower()

    behaviour_of = {r["role"]: r.get("behaviour", "neutral") for r in vocab}
    threats = sum(1 for t in taken if behaviour_of.get(t) == "threat")
    n_objects = len(taken) + 1
    threat_ok = is_dark(info) or threats + 1 <= -(-n_objects // 4)

    candidates = [r for r in vocab if not r.get("system_only") and r.get("role") != "giant"]
    allowed = [r for r in candidates if threat_ok or r.get("behaviour") != "threat"] or candidates
    if not allowed:
        return {"role": "beacon", "name": make_name("beacon", info, obj_id), "behaviour": "friendly"}

    def score(r):
        s = _role_matches_setting(r, text, tokens)
        if cls and cls in [str(c).lower() for c in r.get("classes") or []]:
            s += 2
        if r["role"] not in taken_set:
            s += 1
        return (s, _stable("tie", obj_id, r["role"]))

    best = max(allowed, key=score)
    return {
        "role": best["role"],
        "name": make_name(best["role"], info, f"{obj_id}|{info.get('setting', '')}"),
        "behaviour": best.get("behaviour", "neutral"),
    }
