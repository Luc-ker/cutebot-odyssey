"""Local renderer configuration and short-lived Decart credentials."""
import asyncio
import json
import os
import urllib.error
import urllib.request


def renderer_config():
    from server.common.config import load_config
    from server.world import stable

    config = load_config()
    return {"RESTYLE_PROVIDER": os.environ.get("GENRATOR_RESTYLE_PROVIDER", "fake"),
            "DECART_MODEL": os.environ.get("GENRATOR_DECART_MODEL", "lucy-2.6"),
            # Effective (env-overridden) stable mode, so the eye page agrees with the brain.
            "STABLE_KINGDOM_ENABLED": stable.enabled(config),
            "STABLE_KINGDOM_PROMPT": stable.prompt(config)}


def _mint(key, model, origin):
    request = urllib.request.Request(
        "https://api.decart.ai/v1/client/tokens",
        data=json.dumps({"expiresIn": 300, "allowedModels": [model],
                         "allowedOrigins": [origin]}).encode(),
        headers={"X-API-KEY": key, "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.load(response)
    # Never return the account key or unrelated provider response fields.
    if not data.get("apiKey") or data["apiKey"] == key:
        raise ValueError("invalid token response")
    return {"apiKey": data["apiKey"], "expiresAt": data.get("expiresAt")}


async def mint_token(origin):
    key = os.environ.get("DECART_API_KEY", "")
    if not key:
        return 503, {"error": "DECART_API_KEY is missing on the laptop server"}
    try:
        token = await asyncio.to_thread(_mint, key, renderer_config()["DECART_MODEL"], origin)
        return 200, token
    except urllib.error.HTTPError as exc:
        # Provider bodies can contain credentials; expose only the status.
        return 502, {"error": f"Decart rejected token request (HTTP {exc.code})"}
    except Exception:
        return 502, {"error": "Decart token service unavailable"}
