"""Evaluate Gemini world composition against local, uncommitted media (T78)."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.gemini.client import compose_world
from server.gemini.guard import guard_world
from server.world.fallback_roles import load_vocab

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "eval" / "cases.json"


def render_report(rows: list[dict], runs: int) -> str:
    settings_by_song: dict[str, set[str]] = {}
    for row in rows:
        observed = {setting for setting in row.get("settings", set()) if not setting.startswith("ERROR:")}
        if row.get("setting"):
            observed.add(row["setting"])
        if observed:
            settings_by_song.setdefault(row["song_id"], set()).update(observed)
    lines = [
        f"# Gemini evaluation report ({date.today().isoformat()})",
        "",
        f"Runs per clip/photo pair: {runs}",
        "",
        "| Song | Photo | Latency (ms) | Guard pass rate | Settings | Roles |",
        "|---|---|---:|---:|---|---|",
    ]
    for row in rows:
        settings = ", ".join(sorted(row["settings"])) or "(none)"
        roles = ", ".join(row["roles"]) or "(none)"
        lines.append(f"| {row['song']} | {row['photo']} | {row['latency_ms']} | {row['pass_rate']}% | {settings} | {roles} |")
    inconsistent = [song_id for song_id, settings in settings_by_song.items() if len(settings) > 1]
    lines.extend(("", "## Consistency flags", ""))
    if inconsistent:
        lines.extend(f"- {song_id}: varied settings ({', '.join(sorted(settings_by_song[song_id]))})"
                     for song_id in sorted(inconsistent))
    else:
        lines.append("No song produced more than one guarded setting.")
    return "\n".join(lines) + "\n"


async def evaluate(cases_path: Path, report_dir: Path, limit: int | None = None, runs: int = 3,
                   composer=compose_world, guard=guard_world, vocab=None) -> Path:
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    songs = cases["songs"][:limit] if limit else cases["songs"]
    photos = cases["table_photos"]
    vocab = vocab if vocab is not None else load_vocab()
    rows = []
    for song in songs:
        clip_path = ROOT / song["clip"]
        for photo_name in photos:
            photo_path = ROOT / photo_name
            outcomes = []
            latencies = []
            settings = set()
            roles = set()
            for _ in range(runs):
                started = time.monotonic()
                try:
                    audio = clip_path.read_bytes()
                    image = photo_path.read_bytes()
                    raw = await composer(audio, image, [], None)
                    world = guard(raw, [], vocab)
                    if world is None:
                        raise ValueError("guard rejected response")
                    outcomes.append(True)
                    settings.add((world.get("world") or {}).get("setting", "unknown"))
                    roles.update(role.get("role", "") for role in world.get("roles", []))
                except Exception as exc:
                    outcomes.append(False)
                    settings.add(f"ERROR: {type(exc).__name__}")
                latencies.append(round((time.monotonic() - started) * 1000))
            rows.append({
                "song_id": song["id"], "song": song["title"], "photo": Path(photo_name).name,
                "latency_ms": round(statistics.mean(latencies)),
                "pass_rate": round(100 * sum(outcomes) / len(outcomes)),
                "settings": settings, "setting": next(iter(settings)) if len(settings) == 1 and not next(iter(settings)).startswith("ERROR:") else None,
                "roles": sorted(role for role in roles if role),
            })
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"report-{date.today().isoformat()}.md"
    report_path.write_text(render_report(rows, runs), encoding="utf-8")
    return report_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the Gemini composition evaluation on local media.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--report-dir", type=Path, default=ROOT / "eval")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args(argv)
    if args.runs < 1:
        parser.error("--runs must be at least one")
    report = asyncio.run(evaluate(args.cases, args.report_dir, args.limit, args.runs))
    print(report)


if __name__ == "__main__":
    main()