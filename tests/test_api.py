import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app, queue, store

client = TestClient(app)
PAYLOAD = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "payload.json").read_text(encoding="utf-8")
)


def test_full_flow_via_api():
    # Reset shared state so this test is order-independent.
    queue.ack(queue.size)
    for _ in store.records:
        pass  # RecordStore has no clear(); a fresh .state/ is used per test run instead.

    resp = client.post("/submissions", json=PAYLOAD)
    assert resp.status_code == 200
    assert resp.json()["queued"] == 4

    resp = client.post("/sync", params={"online": False})
    assert resp.json()["skipped"] is True

    resp = client.post("/sync", params={"online": True})
    body = resp.json()
    assert len(body["committed"]) == 3
    assert len(body["duplicates"]) == 1

    resp = client.get("/records")
    assert resp.json()["count"] >= 3
