import json

from fastapi.testclient import TestClient
from lotus_api.main import app

client = TestClient(app)


def test_stream_orders_planner_tools_result_and_answer() -> None:
    response = client.post(
        "/v1/chat/stream",
        json={
            "message": "Show the checkout retry architecture document",
            "project_id": "payments",
            "session_id": "session-test",
        },
    )
    assert response.status_code == 200
    frames = [frame for frame in response.text.split("\n\n") if "data:" in frame]
    events = [json.loads(frame.split("data: ", 1)[1]) for frame in frames]
    kinds = [event["event_type"] for event in events]
    assert kinds[0] == "run.started"
    assert kinds[-1] == "answer.completed"
    planner_done = next(
        index
        for index, event in enumerate(events)
        if event["event_type"] == "node.completed" and event["node_id"] == "planner"
    )
    data_started = next(
        index
        for index, event in enumerate(events)
        if event["event_type"] == "node.started" and event["node_id"] == "data"
    )
    result_started = next(
        index
        for index, event in enumerate(events)
        if event["event_type"] == "node.started" and event["node_id"] == "result"
    )
    data_done = next(
        index
        for index, event in enumerate(events)
        if event["event_type"] == "node.completed" and event["node_id"] == "data"
    )
    assert planner_done < data_started < data_done < result_started
    assert events[-1]["response"]["execution_id"] == events[0]["execution_id"]
