import json
from pathlib import Path

import pytest

from app.storage import OfflineQueue, RecordStore
from app.sync import sync
from app.validate import validate_record

PAYLOAD = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "payload.json").read_text(encoding="utf-8")
)


def fresh():
    return OfflineQueue(), RecordStore()


def test_commits_three_unique_drops_mukono_duplicate():
    queue, store = fresh()
    queue.enqueue(PAYLOAD)
    res = sync(queue, store)

    assert len(res["committed"]) == 3
    assert len(res["duplicates"]) == 1
    assert res["duplicates"][0]["urban_council"] == "Mukono Municipality"
    assert res["duplicates"][0]["index"] == 2
    assert res["duplicates"][0]["conflict"] is False
    assert [r["urban_council"] for r in store.records] == [
        "Mukono Municipality",
        "Entebbe Municipal Council",
        "Gulu City Council",
    ]
    assert queue.size == 0


def test_offline_nothing_committed_queue_retained():
    queue, store = fresh()
    queue.enqueue(PAYLOAD)
    res = sync(queue, store, online=False)

    assert res["skipped"] is True
    assert len(store.records) == 0
    assert queue.size == 4


def test_idempotent_across_syncs():
    queue, store = fresh()
    queue.enqueue(PAYLOAD)
    sync(queue, store)
    queue.enqueue(PAYLOAD)
    res = sync(queue, store)

    assert len(res["committed"]) == 0
    assert len(res["duplicates"]) == 4
    assert len(store.records) == 3


def test_invalid_records_rejected_not_committed():
    queue, store = fresh()
    queue.enqueue(
        [
            {**PAYLOAD[0], "pdp_status": "Bogus"},
            {**PAYLOAD[1], "expiry_year": None},
        ]
    )
    res = sync(queue, store)

    assert len(res["committed"]) == 0
    assert len(res["rejected"]) == 2
    assert len(store.rejected) == 2


def test_same_uuid_different_content_flagged_conflict():
    queue, store = fresh()
    queue.enqueue([PAYLOAD[0], {**PAYLOAD[0], "expiry_year": 2030}])
    res = sync(queue, store)

    assert len(res["committed"]) == 1
    assert res["duplicates"][0]["conflict"] is True


@pytest.mark.parametrize("record", PAYLOAD)
def test_all_sample_records_valid(record):
    assert validate_record(record) == []


def test_missing_status_requires_null_year():
    bad = {**PAYLOAD[3], "expiry_year": 2030}
    assert validate_record(bad) != []
