import asyncio

from server.gemini import object_role


VOCAB = [
    {"role": "ship", "behaviour": "neutral"},
    {"role": "sea_serpent", "behaviour": "threat"},
    {"role": "giant", "behaviour": "threat", "system_only": True},
]


def test_valid_role_passes_through_and_unknown_role_is_rejected(monkeypatch):
    answers = iter([
        {"role": "ship", "name": "The Salt Queen", "behaviour": "neutral", "announce": "A ship rises from the sea."},
        {"role": "spaceship", "name": "Unknown", "behaviour": "neutral", "announce": "A starship appears."},
    ])

    async def fake_ask_json(parts, schema):
        assert "ship" in schema["properties"]["role"]["enum"]
        return next(answers)

    monkeypatch.setattr(object_role, "load_vocab", lambda: VOCAB)
    monkeypatch.setattr(object_role, "ask_json", fake_ask_json)
    world = {"world": {"name": "Salt Sea", "setting": "ocean"}}
    obj = {"id": 4, "cls": "chair", "pos": [0.4, 0.6]}

    assert asyncio.run(object_role.request_role(world, obj, None))["role"] == "ship"
    assert asyncio.run(object_role.request_role(world, obj, None)) is None