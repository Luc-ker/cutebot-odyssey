from server.gemini.prompt import build_compose_parts
from server.world.fallback_roles import load_vocab


VOCAB = [
    {"role": "ship", "behaviour": "neutral"},
    {"role": "lighthouse", "behaviour": "friendly"},
    {"role": "sea_serpent", "behaviour": "threat"},
    {"role": "giant", "behaviour": "threat", "system_only": True},
]


def test_prompt_includes_every_object_and_allowed_role_under_limit():
    objects = [{"id": i, "cls": "chair", "pos": [i / 20, 0.5]} for i in range(20)]
    vocab = load_vocab()
    text = build_compose_parts(b"wav", b"jpg", objects, None, vocab)[0]["text"]

    assert len(text) < 6000
    assert all(f"id={i};" in text for i in range(20))
    assert all(entry["role"] in text for entry in vocab if entry.get("role") != "giant" and not entry.get("system_only"))
    assert "- giant:" not in text


def test_prompt_preserves_current_world_and_media_mime_types():
    parts = build_compose_parts(
        b"wav", b"jpg", [],
        {"id": "w-12345678", "world": {"name": "The Salt Sea", "setting": "ocean"}},
        VOCAB,
    )

    assert "keep it unless the music clearly implies a different world" in parts[0]["text"]
    assert "The Salt Sea" in parts[0]["text"]
    assert parts[1]["inline_data"]["mime_type"] == "audio/wav"
    assert parts[2]["inline_data"]["mime_type"] == "image/jpeg"