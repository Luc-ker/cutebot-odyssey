from server.gemini.guard import guard_world

VOCAB = [
    {"role": "ship", "behaviour": "neutral", "worlds": ["ocean"], "classes": ["chair"]},
    {"role": "lighthouse", "behaviour": "friendly", "worlds": ["ocean"], "classes": ["bottle"]},
    {"role": "giant", "behaviour": "threat", "system_only": True},
]


def response():
    return {
        "id": "w-1234abcd",
        "world": {"name": "Salt Sea", "setting": "ocean", "mood": "bright", "time_of_day": "dusk",
                  "weather": "clear", "palette": ["deep teal", "storm grey", "gold"]},
        "roles": [{"object_id": 1, "role": "spaceship", "name": "[The Ship](https://example.test)",
                   "behaviour": "threat"}, {"object_id": 999, "role": "ship", "name": "Ghost",
                                                    "behaviour": "neutral"}],
        "terrain": {"open_space": "open sea", "under_table": "deep water"},
        "restyle_prompt": "First-person sea-level view https://example.test",
        "narration": "Welcome to the sea.",
        "music_signature": {"tempo_bpm": 120, "energy": 0.5, "brightness": 0.4, "chroma": [0] * 12},
    }


def test_guard_replaces_unknown_role_drops_unknown_id_and_fills_missing():
    guarded = guard_world(response(), [{"id": 1, "cls": "chair"}, {"id": 2, "cls": "bottle"}], VOCAB)

    assert guarded is not None
    assert [role["object_id"] for role in guarded["roles"]] == [1, 2]
    assert guarded["roles"][0]["role"] == "ship"
    assert guarded["roles"][0]["behaviour"] == "neutral"
    assert guarded["roles"][1]["role"] == "lighthouse"
    assert "https://" not in guarded["restyle_prompt"]
    assert "https://" not in guarded["roles"][0]["name"]


def test_non_json_garbage_is_rejected():
    assert guard_world("not json", [], VOCAB) is None