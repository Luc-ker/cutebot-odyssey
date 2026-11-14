"""Google Gen AI client wrapper (T71, contracts C7 and C10)."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from server.common.config import load_config
from server.gemini.prompt import build_compose_parts

log = logging.getLogger(__name__)
_client = None
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "shared" / "schemas" / "world.schema.json"


class GeminiTimeout(TimeoutError):
    """The Gemini request exceeded its configured deadline after retrying."""


class GeminiConfigurationError(RuntimeError):
    """The Gemini SDK or API key is unavailable."""


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise GeminiConfigurationError("GEMINI_API_KEY is not set")
        try:
            from google import genai
        except ImportError as exc:
            raise GeminiConfigurationError("Install the official google-genai package to call Gemini") from exc
        _client = genai.Client(api_key=api_key)
    return _client


def _status_code(error: Exception) -> int | None:
    for candidate in (getattr(error, "status_code", None), getattr(error, "code", None),
                      getattr(getattr(error, "response", None), "status_code", None)):
        try:
            if candidate is not None:
                return int(candidate)
        except (TypeError, ValueError):
            continue
    return None


def _schema_dict(schema: dict) -> dict:
    return {key: value for key, value in schema.items() if key not in {"$schema", "$id", "title", "description"}}


async def ask_json(parts: list, schema: dict) -> dict:
    """Send multimodal parts and return parsed JSON, retrying one timeout or 5xx."""
    config = load_config()
    timeout_s = float(config.get("GEMINI_TIMEOUT_S", 12.0))
    model = str(config.get("GEMINI_MODEL", "gemini-2.5-flash"))
    client = _get_client()
    request_config = {
        "response_mime_type": "application/json",
        "response_schema": _schema_dict(schema),
    }
    started = time.monotonic()
    for attempt in range(2):
        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=model, contents=parts, config=request_config,
                ),
                timeout=timeout_s,
            )
            text = getattr(response, "text", None)
            if not isinstance(text, str):
                raise ValueError("Gemini returned no JSON text")
            result = json.loads(text)
            if not isinstance(result, dict):
                raise ValueError("Gemini JSON response must be an object")
            usage = getattr(response, "usage_metadata", None)
            log.info(
                "Gemini request completed latency_ms=%d prompt_tokens=%s output_tokens=%s",
                round((time.monotonic() - started) * 1000),
                getattr(usage, "prompt_token_count", None),
                getattr(usage, "candidates_token_count", None),
            )
            return result
        except (asyncio.TimeoutError, TimeoutError) as exc:
            if attempt == 0:
                continue
            raise GeminiTimeout(f"Gemini request timed out after {timeout_s:g} seconds") from exc
        except Exception as exc:
            status = _status_code(exc)
            if attempt == 0 and status is not None and 500 <= status < 600:
                continue
            raise


async def compose_world(audio_wav: bytes, image_jpeg: bytes, objects: list,
                        current_world: dict | None) -> dict:
    """Compose a raw world response from the audio clip, robot's-view image and discovered objects."""
    from server.world.fallback_roles import load_vocab

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    parts = build_compose_parts(audio_wav, image_jpeg, objects, current_world, load_vocab())
    return await ask_json(parts, schema)


async def _main(wav_path: str, image_path: str) -> None:
    result = await compose_world(Path(wav_path).read_bytes(), Path(image_path).read_bytes(), [], None)
    print(json.dumps(result, indent=2))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Compose a world from a WAV clip and JPEG snapshot.")
    parser.add_argument("--wav", required=True)
    parser.add_argument("--jpg", required=True)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main(args.wav, args.jpg))


if __name__ == "__main__":
    main()