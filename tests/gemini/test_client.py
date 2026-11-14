import asyncio
from types import SimpleNamespace

import pytest

from server.gemini import client as gemini


class FakeModels:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def test_ask_json_sends_audio_and_image_mime_types(monkeypatch):
    models = FakeModels(SimpleNamespace(text='{"ok":true}', usage_metadata=None))
    fake = SimpleNamespace(aio=SimpleNamespace(models=models))
    monkeypatch.setattr(gemini, "_get_client", lambda: fake)
    monkeypatch.setattr(gemini, "load_config", lambda: {"GEMINI_TIMEOUT_S": 1, "GEMINI_MODEL": "test-model"})
    parts = [
        {"text": "compose"},
        {"inline_data": {"mime_type": "audio/wav", "data": b"wav"}},
        {"inline_data": {"mime_type": "image/jpeg", "data": b"jpg"}},
    ]

    assert asyncio.run(gemini.ask_json(parts, {"type": "object"})) == {"ok": True}
    sent = models.calls[0]["contents"]
    assert [part["inline_data"]["mime_type"] for part in sent[1:]] == ["audio/wav", "image/jpeg"]


def test_timeout_retries_once_then_raises_clear_error(monkeypatch):
    class SlowModels:
        calls = 0

        async def generate_content(self, **_kwargs):
            self.calls += 1
            await asyncio.sleep(0.02)

    models = SlowModels()
    monkeypatch.setattr(gemini, "_get_client", lambda: SimpleNamespace(aio=SimpleNamespace(models=models)))
    monkeypatch.setattr(gemini, "load_config", lambda: {"GEMINI_TIMEOUT_S": 0.001})

    with pytest.raises(gemini.GeminiTimeout, match="timed out"):
        asyncio.run(gemini.ask_json([], {}))
    assert models.calls == 2


def test_client_error_is_not_retried(monkeypatch):
    class ClientError(Exception):
        status_code = 400

    models = FakeModels(error=ClientError("bad request"))
    monkeypatch.setattr(gemini, "_get_client", lambda: SimpleNamespace(aio=SimpleNamespace(models=models)))
    monkeypatch.setattr(gemini, "load_config", lambda: {"GEMINI_TIMEOUT_S": 1})
    with pytest.raises(ClientError):
        asyncio.run(gemini.ask_json([], {}))
    assert len(models.calls) == 1

def test_current_flash_model_uses_low_thinking_and_bounded_json_output(monkeypatch):
    models = FakeModels(SimpleNamespace(text='{"ok":true}', usage_metadata=None))
    monkeypatch.setattr(gemini, "_get_client", lambda: SimpleNamespace(aio=SimpleNamespace(models=models)))
    monkeypatch.setattr(gemini, "load_config", lambda: {"GEMINI_MODEL": "gemini-3.8-flash"})
    assert asyncio.run(gemini.ask_json([], {"type": "object"})) == {"ok": True}
    config = models.calls[0]["config"]
    assert config["thinking_config"] == {"thinking_level": "low"}
    assert config["max_output_tokens"] == 4096
