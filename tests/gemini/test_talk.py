import asyncio

from server.gemini.talk import TalkingObjects


def test_second_visit_count_is_in_the_request():
    prompts = []

    async def fake_ask(parts, _schema):
        prompts.append(parts[0]["text"])
        return {"line": "The ship bells ring again."}

    class Hub:
        def __init__(self):
            self.messages = []

        async def pub(self, topic, data):
            self.messages.append((topic, data))

    hub = Hub()
    talking = TalkingObjects(hub, ask=fake_ask)
    obj = {"id": 8, "role": "ship", "name": "Salt Queen", "behaviour": "neutral"}

    async def scenario():
        await talking.on_world_objects({"objects": [obj]})
        await talking.on_robot_state({"facing_id": 8, "distance_cm": 20}, now=0)
        await talking.on_robot_state({"facing_id": 8, "distance_cm": 20}, now=2)
        await talking.task
        await talking.on_robot_state({"facing_id": 8, "distance_cm": 20}, now=23)
        await talking.task

    asyncio.run(scenario())

    assert len(prompts) == 2
    assert "visit number 2" in prompts[1]
    assert all(topic == "narration.say" for topic, _ in hub.messages)
    assert hub.messages[0][1]["voice"] == "ship"