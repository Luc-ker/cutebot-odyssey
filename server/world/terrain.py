"""T53 — Free-space terrain analysis.

Finds the big empty areas of the table (open sea, plains, desert on the map)
and says what the open space and the area under the table are.

Contract (C7)::

    analyse(objects, world) -> {"open_regions": [{x, y, w, h}], "open_space": str, "under_table": str}

Method: a ``grid``×``grid`` occupancy grid from object footprints, then the
largest empty rectangle is taken repeatedly (marking it used) to give up to
``top`` non-overlapping regions, largest first, in table units.
"""

from __future__ import annotations

GRID = 20
TOP = 3
MIN_CELLS = 4

# (setting keywords, open_space, under_table) — used when the world has no terrain.
_DEFAULTS = [
    (("ocean", "sea", "coast", "island", "pirate"), "open sea", "the deep sea"),
    (("wasteland", "volcan", "lava", "ash"), "ash plains", "a lava cave"),
    (("snow", "ice", "frost", "winter"), "snowfields", "a bear's den"),
    (("city", "neon", "cyber", "urban"), "empty streets", "the subway"),
    (("jungle", "rainforest", "tropical"), "a jungle clearing", "a hidden ruin"),
    (("court", "royal", "palace"), "palace gardens", "the catacombs"),
    (("space", "station", "orbit", "galaxy"), "open space", "the engine room"),
    (("desert", "dune", "sand"), "desert", "a buried tomb"),
    (("kingdom", "medieval", "castle"), "green plains", "a dragon's cave"),
]
_FALLBACK = ("open plains", "a deep cave")


def _get(o, key, default=None):
    return o.get(key, default) if isinstance(o, dict) else getattr(o, key, default)


def occupancy(objects, grid: int = GRID) -> list[list[bool]]:
    occ = [[False] * grid for _ in range(grid)]
    for o in objects or []:
        pos = _get(o, "pos")
        if pos is None:
            continue
        w, h = (_get(o, "size") or [0, 0])[:2]
        x0, x1 = pos[0] - w / 2, pos[0] + w / 2
        y0, y1 = pos[1] - h / 2, pos[1] + h / 2
        c0 = max(0, min(grid - 1, int(x0 * grid)))
        c1 = max(0, min(grid - 1, int(x1 * grid)))
        r0 = max(0, min(grid - 1, int(y0 * grid)))
        r1 = max(0, min(grid - 1, int(y1 * grid)))
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                occ[r][c] = True
    return occ


def largest_empty(occ) -> tuple[int, int, int, int, int]:
    """(area, col, row, width, height) of the largest all-False rectangle."""
    rows, cols = len(occ), len(occ[0]) if occ else 0
    heights = [0] * cols
    best = (0, 0, 0, 0, 0)
    for r in range(rows):
        for c in range(cols):
            heights[c] = 0 if occ[r][c] else heights[c] + 1
        stack: list[int] = []
        for c in range(cols + 1):
            h = heights[c] if c < cols else 0
            while stack and heights[stack[-1]] >= h:
                top = stack.pop()
                height = heights[top]
                left = stack[-1] + 1 if stack else 0
                width = c - left
                if height * width > best[0]:
                    best = (height * width, left, r - height + 1, width, height)
            stack.append(c)
    return best


def open_regions(objects, grid: int = GRID, top: int = TOP) -> list[dict]:
    occ = occupancy(objects, grid)
    regions = []
    for _ in range(top):
        area, c, r, w, h = largest_empty(occ)
        if area < MIN_CELLS:
            break
        regions.append({"x": c / grid, "y": r / grid, "w": w / grid, "h": h / grid})
        for rr in range(r, r + h):
            for cc in range(c, c + w):
                occ[rr][cc] = True
    return regions


def _names(world) -> tuple[str, str]:
    world = world or {}
    terrain = world.get("terrain") or {}
    info = world.get("world", world) if isinstance(world.get("world"), dict) else world
    text = f"{info.get('setting', '')} {info.get('name', '')}".lower()
    open_space, under = _FALLBACK
    for keys, o, u in _DEFAULTS:
        if any(k in text for k in keys):
            open_space, under = o, u
            break
    return terrain.get("open_space") or open_space, terrain.get("under_table") or under


def analyse(objects, world, grid: int = GRID, top: int = TOP) -> dict:
    open_space, under_table = _names(world)
    return {"open_regions": open_regions(objects, grid, top),
            "open_space": open_space, "under_table": under_table}
