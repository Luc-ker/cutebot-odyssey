"""Gemini model designer: a unique 3D miniature for every object in the world (docs/local-renderer.md).

When an object gets a role (``world.objects``), Gemini is asked to design a miniature for it as a
*recipe*: a list of simple parts (boxes, cones, domes...) with sizes, positions, colours and materials
(``shared/schemas/model.schema.json``). The eye page builds and animates that recipe live in three.js.
Gemini sees the world, the role, the real object's class, its on-screen proportions and (when the vision
snapshot is available) a crop of the real object, so each model echoes the thing it replaces.

Publishes ``world.models`` once a second::

    {world_id, models: [{id, role, name, source: "gemini", recipe}]}

* One request at a time, at most ``MODEL_DESIGN_PER_MIN`` a minute; the eye page shows a seeded
  procedural model until Gemini's arrives, so nothing waits on the network.
* Stable Kingdom mode designs one model per detector class (every bottle is the same tower);
  otherwise one per object.
* Designs are cached on disk per world setting and role (``logs/model_cache.json``). Once
  ``MODEL_VARIANTS_PER_ROLE`` designs exist for a role, new objects reuse one of them instead of
  calling Gemini again, which keeps the cost bounded during long demos.
* Every answer goes through ``normalise_recipe``: numbers are clamped, unknown shapes/materials dropped,
  colours checked, parts capped, so a bad answer can never break the renderer.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
import urllib.request
from pathlib import Path
from typing import Any, Awaitable, Callable

from server.world import stable

log = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "shared" / "schemas" / "model.schema.json"
CACHE_PATH = Path(__file__).resolve().parents[2] / "logs" / "model_cache.json"
PUBLISH_S = 1.0
REQUEST_TIMEOUT_S = 20.0
RETRY_AFTER_S = 30.0
MAX_ATTEMPTS = 2

SHAPES = {"box", "cylinder", "cone", "sphere", "dome", "pyramid", "torus", "wedge", "capsule"}
MATERIALS = {"stone", "wood", "metal", "gold", "cloth", "leaf", "scale", "crystal", "water", "glow"}
PART_ANIMS = {"none", "spin", "bob", "sway", "flicker", "flap", "pulse"}
MODEL_ANIMS = {"none", "bob", "spin", "sway", "breathe"}
MAX_PARTS = 32
MAX_EXPANDED_PARTS = 120  # after repeats
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

EXAMPLE = {
    "name": "mossy watchtower",
    "animation": "none",
    "parts": [
        {"shape": "cylinder", "size": [0.9, 0.06, 0.9], "pos": [0, 0, 0], "colour": "#5f8f3a", "material": "leaf"},
        {"shape": "cylinder", "size": [0.4, 0.7, 0.4], "pos": [0, 0.05, 0], "colour": "#b8a98c", "material": "stone"},
        {"shape": "box", "size": [0.1, 0.1, 0.1], "pos": [0.2, 0.75, 0], "colour": "#b8a98c", "material": "stone",
         "repeat": {"count": 8, "mode": "ring", "radius": 0.22}},
        {"shape": "cone", "size": [0.55, 0.35, 0.55], "pos": [0, 0.78, 0], "colour": "#c8452e", "material": "wood"},
        {"shape": "box", "size": [0.08, 0.12, 0.02], "pos": [0, 0.4, 0.2], "colour": "#ffd36b", "material": "glow"},
        {"shape": "box", "size": [0.14, 0.08, 0.01], "pos": [0.07, 1.16, 0], "colour": "#e1b337", "material": "cloth",
         "anim": "sway"},
    ],
}


# ------------------------------------------------------------------------------------- the recipe guard

def _num(v: Any, lo: float, hi: float, default: float) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f:  # NaN
        return default
    return round(min(hi, max(lo, f)), 4)


def _vec(v: Any, lo: float, hi: float, default: list[float]) -> list[float]:
    if not isinstance(v, (list, tuple)) or len(v) != 3:
        return list(default)
    return [_num(x, lo, hi, d) for x, d in zip(v, default)]


def normalise_recipe(raw: Any) -> dict | None:
    """Return a safe, renderable recipe, or None when nothing usable is left."""
    if not isinstance(raw, dict):
        return None
    parts = []
    expanded = 0
    for p in (raw.get("parts") or [])[:MAX_PARTS]:
        if not isinstance(p, dict) or p.get("shape") not in SHAPES:
            continue
        colour = p.get("colour") if isinstance(p.get("colour"), str) and _HEX.match(p.get("colour", "")) else None
        if colour is None:
            continue
        part = {
            "shape": p["shape"],
            "size": _vec(p.get("size"), 0.02, 1.2, [0.2, 0.2, 0.2]),
            "pos": [0.0, 0.0, 0.0],
            "colour": colour.lower(),
            "material": p.get("material") if p.get("material") in MATERIALS else "stone",
        }
        x, y, z = _vec(p.get("pos"), -10, 10, [0, 0, 0])
        part["pos"] = [_num(x, -0.8, 0.8, 0), _num(y, 0, 1.4, 0), _num(z, -0.8, 0.8, 0)]
        if p.get("rot") is not None:
            part["rot"] = _vec(p.get("rot"), -180, 180, [0, 0, 0])
        if p.get("anim") in PART_ANIMS and p.get("anim") != "none":
            part["anim"] = p["anim"]
        copies = 1
        rep = p.get("repeat")
        if isinstance(rep, dict) and rep.get("mode") in ("ring", "line"):
            count = int(_num(rep.get("count"), 2, 12, 2))
            r = {"count": count, "mode": rep["mode"]}
            if rep["mode"] == "ring":
                r["radius"] = _num(rep.get("radius"), 0.02, 0.8, 0.3)
            else:
                r["spacing"] = _num(rep.get("spacing"), 0.02, 0.6, 0.15)
            part["repeat"] = r
            copies = count
        if expanded + copies > MAX_EXPANDED_PARTS:
            break
        expanded += copies
        parts.append(part)
    if not parts:
        return None
    name = " ".join(str(raw.get("name") or "").split())[:60] or "miniature"
    anim = raw.get("animation") if raw.get("animation") in MODEL_ANIMS else "none"
    return {"name": name, "animation": anim, "parts": parts}


# ------------------------------------------------------------------------------------- asking Gemini

def design_prompt(world: dict | None, obj: dict, role: dict, role_info: dict | None) -> str:
    info = (world or {}).get("world", {}) if isinstance(world, dict) else {}
    summary = {k: info.get(k) for k in ("name", "setting", "mood", "time_of_day", "weather", "palette") if info.get(k)}
    size = obj.get("size") or [0.2, 0.2]
    try:
        aspect = round(float(size[0]) / max(float(size[1]), 1e-3), 2)
    except (TypeError, ValueError, IndexError):
        aspect = 1.0
    hint = (role_info or {}).get("prompt")
    return "\n".join([
        "Design a miniature 3D model, built from simple parts, for a game in which a palm-sized robot drives "
        "across a real table and every real object it finds becomes part of a fantasy world. Return JSON only.",
        f"World: {json.dumps(summary, ensure_ascii=True)}",
        f"The real object is a {obj.get('cls', 'object')}. In this world it is the {role.get('role')}"
        + (f" called {role.get('name')!r}" if role.get("name") else "")
        + (f" ({hint})" if hint else "") + f"; behaviour: {role.get('behaviour') or 'neutral'}.",
        f"On screen it is {aspect} times as wide as it is tall. The model is drawn over it, so keep roughly that "
        "proportion. If a photo crop of the real object is attached, echo its main colour and overall shape.",
        "Style: a chunky, hand-painted tabletop miniature; low-poly; bold readable silhouette; 8 to 24 parts; "
        "colours that suit the world's palette. Give it a few small details (windows, banners, moss, eyes, "
        "crenellations) so it reads well up close.",
        "Coordinates: the model stands on the ground at y = 0 and is about 1 unit tall (never above 1.4). "
        "x is left-right and z is front-back, both within -0.8..0.8; the camera looks from +z. "
        "pos is the centre of the BOTTOM of each part, so stack parts by raising y. Sizes are width, height, depth. "
        "Use repeat (ring or line) for battlements, windows, fence posts, legs or a ring of trees. "
        "Use the glow material for flames, lit windows and magic; anim flicker for flames, flap for wings, "
        "sway for flags. Creatures need a body, head, legs, eyes (glow) and usually a tail; give them animation "
        "breathe or bob. Rotations are optional, in degrees, and turn a part about its own centre. "
        "For flat triangles (wings, fins, sails) use a cone with a tiny depth; for bodies use a stretched sphere.",
        "Example of the format (a small watchtower): " + json.dumps(EXAMPLE, separators=(",", ":")),
    ])


def _crop(image_jpeg: bytes | None, obj: dict) -> bytes | None:
    try:
        from server.gemini.object_role import _crop_snapshot
    except ImportError:
        return None
    return _crop_snapshot(image_jpeg, obj) if image_jpeg else None


async def request_model(world: dict | None, obj: dict, role: dict, image_jpeg: bytes | None,
                        role_info: dict | None = None, ask=None) -> dict | None:
    """One Gemini design call. Returns a normalised recipe or None."""
    if ask is None:
        from server.gemini.client import ask_json as ask
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    parts: list[dict] = [{"text": design_prompt(world, obj, role, role_info)}]
    crop = _crop(image_jpeg, obj)
    if crop:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": crop}})
    raw = await asyncio.wait_for(ask(parts, schema), timeout=REQUEST_TIMEOUT_S)
    return normalise_recipe(raw)


# ------------------------------------------------------------------------------------- the service

def _setting(world: dict | None) -> str:
    info = (world or {}).get("world", {}) if isinstance(world, dict) else {}
    return str(info.get("setting") or info.get("name") or "world").lower()


def _pick(variants: list, key: str):
    h = int(hashlib.sha1(key.encode()).hexdigest()[:8], 16)
    return variants[h % len(variants)]


class ModelDesigner:
    def __init__(self, hub, config: dict | None = None, *, request=None,
                 fetch_snapshot: Callable[[], Awaitable[bytes | None]] | None = None,
                 cache_path: Path | None = CACHE_PATH, clock=time.monotonic, vocab: list | None = None):
        self.hub = hub
        self.config = config or {}
        self.request = request or request_model
        self.fetch_snapshot = fetch_snapshot or self._default_snapshot
        self.cache_path = cache_path
        self.clock = clock
        self.enabled = bool(self.config.get("MODEL_DESIGN_ENABLED", True))
        self.min_gap_s = 60.0 / max(1.0, float(self.config.get("MODEL_DESIGN_PER_MIN", 10)))
        self.variants_per_role = max(1, int(self.config.get("MODEL_VARIANTS_PER_ROLE", 3)))
        self.stable = stable.enabled(self.config)
        self.world: dict | None = None
        self.world_id: str | None = None
        self.objects: dict[int, dict] = {}         # latest world.objects entries with a role
        self.designs: dict[str, dict] = {}         # design key -> {recipe, role, name}
        self.failures: dict[str, tuple[int, float]] = {}  # key -> (attempts, last try)
        self.cache: dict[str, list[dict]] = self._load_cache()  # "setting|role" -> [recipe, ...]
        self.last_request = -float("inf")
        self.in_flight: str | None = None
        self._vocab = vocab

    # -- keys and lookups
    def key_for(self, obj: dict) -> str:
        if self.stable:
            return f"{self.world_id}|cls:{obj.get('cls')}|{obj.get('role')}"
        return f"{self.world_id}|id:{obj.get('id')}|{obj.get('role')}"

    def role_info(self, role: str) -> dict | None:
        if self._vocab is None:
            try:
                from server.world.fallback_roles import load_vocab
                self._vocab = load_vocab()
            except Exception:
                self._vocab = []
        return next((r for r in self._vocab if r.get("role") == role), None)

    # -- cache on disk
    def _load_cache(self) -> dict:
        if not self.cache_path or not self.cache_path.exists():
            return {}
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            return {k: [r for r in map(normalise_recipe, v) if r] for k, v in data.items() if isinstance(v, list)}
        except (OSError, ValueError, AttributeError):
            return {}

    def _save_cache(self) -> None:
        if not self.cache_path:
            return
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self.cache), encoding="utf-8")
        except OSError as exc:
            log.info("model cache not saved: %s", exc)

    # -- hub
    def attach(self):
        self.hub.sub("world.current", self._on_world)
        self.hub.sub("world.objects", self._on_objects)
        self.hub.sub("system.reset", self._on_reset)
        return self

    async def _on_world(self, env: dict) -> None:
        world = (env.get("data") or {}).get("world")
        if isinstance(world, dict):
            self.world = world

    async def _on_objects(self, env: dict) -> None:
        data = env.get("data") or {}
        self.world_id = data.get("world_id")
        self.objects = {o["id"]: o for o in data.get("objects") or []
                        if isinstance(o, dict) and isinstance(o.get("id"), int) and o.get("role")}

    async def _on_reset(self, env: dict) -> None:
        self.objects.clear()
        self.designs.clear()
        self.failures.clear()

    # -- work
    def next_job(self, now: float) -> dict | None:
        """The object most worth designing now: visible ones first, never a key already done or failing."""
        best = None
        for obj in self.objects.values():
            key = self.key_for(obj)
            if key in self.designs or key == self.in_flight:
                continue
            tries, last = self.failures.get(key, (0, -float("inf")))
            if tries >= MAX_ATTEMPTS or now - last < RETRY_AFTER_S:
                continue
            if best is None or (obj.get("visible") and not best.get("visible")):
                best = obj
        return best

    def reuse(self, obj: dict) -> dict | None:
        variants = self.cache.get(f"{_setting(self.world)}|{obj.get('role')}") or []
        if len(variants) >= self.variants_per_role:
            return _pick(variants, self.key_for(obj))
        return None

    async def step(self) -> bool:
        """Design (or reuse) one model if one is due. Returns True when it did something."""
        now = self.clock()
        obj = self.next_job(now)
        if obj is None:
            return False
        key = self.key_for(obj)
        cached = self.reuse(obj)
        if cached is not None:
            self.designs[key] = {"recipe": cached, "role": obj["role"], "name": cached.get("name")}
            return True
        if not self.enabled or now - self.last_request < self.min_gap_s:
            return False
        self.last_request = now
        self.in_flight = key
        try:
            image = await self.fetch_snapshot() if obj.get("visible") else None
            recipe = await self.request(self.world, obj, {"role": obj.get("role"), "name": obj.get("name"),
                                                          "behaviour": obj.get("behaviour")},
                                        image, self.role_info(obj.get("role")))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # timeout, no key, network, bad JSON
            log.info("model design failed for %s: %r", key, exc)
            recipe = None
        finally:
            self.in_flight = None
        if not recipe:
            tries, _ = self.failures.get(key, (0, 0.0))
            self.failures[key] = (tries + 1, self.clock())
            return True
        self.designs[key] = {"recipe": recipe, "role": obj["role"], "name": recipe.get("name")}
        bucket = self.cache.setdefault(f"{_setting(self.world)}|{obj['role']}", [])
        if len(bucket) < self.variants_per_role:
            bucket.append(recipe)
            self._save_cache()
        log.info("designed %s: %s (%d parts)", key, recipe["name"], len(recipe["parts"]))
        return True

    def snapshot(self) -> dict:
        models = []
        for obj in self.objects.values():
            d = self.designs.get(self.key_for(obj))
            if d:
                models.append({"id": obj["id"], "role": d["role"], "name": d["name"], "source": "gemini",
                               "recipe": d["recipe"]})
        return {"world_id": self.world_id, "models": models}

    async def _default_snapshot(self) -> bytes | None:
        host, port = self.config.get("VISION_HOST"), self.config.get("VISION_HTTP_PORT")
        if not host or not port:
            return None

        def fetch():
            with urllib.request.urlopen(f"http://{host}:{port}/snapshot.jpg", timeout=1.5) as resp:
                return resp.read()

        try:
            return await asyncio.to_thread(fetch)
        except Exception:
            return None

    async def loop(self) -> None:
        next_pub = 0.0
        while True:
            worked = await self.step()
            now = self.clock()
            if now >= next_pub:
                next_pub = now + PUBLISH_S
                await self.hub.pub("world.models", self.snapshot())
            await asyncio.sleep(0.05 if worked else 0.25)


async def run(hub, config):
    designer = ModelDesigner(hub, config).attach()
    if not designer.enabled:
        log.info("model designer disabled (MODEL_DESIGN_ENABLED false); the eye page uses procedural models")
    await designer.loop()
