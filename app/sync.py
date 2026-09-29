"""Flush the queue: validate -> drop duplicates (by submission_uuid) -> commit.

Idempotent: UUIDs already committed in earlier syncs are treated as
duplicates too. The first occurrence in a batch wins. Does nothing
while offline, so records stay cached for the next attempt.
"""
from __future__ import annotations

import json

from app.storage import OfflineQueue, RecordStore
from app.validate import validate_record


def _fingerprint(record: dict) -> str:
    # Stable comparison so key order doesn't matter.
    return json.dumps(record, sort_keys=True)


def sync(queue: OfflineQueue, store: RecordStore, online: bool = True) -> dict:
    if not online:
        return {
            "skipped": True,
            "reason": "offline",
            "pending": queue.size,
            "committed": [],
            "duplicates": [],
            "rejected": [],
        }

    batch = queue.peek()
    seen: dict[str, str] = {}  # uuid -> fingerprint of first accepted record
    committed: list[dict] = []
    duplicates: list[dict] = []
    rejected: list[dict] = []

    for index, record in enumerate(batch):
        errors = validate_record(record)
        if errors:
            rejected.append({"index": index, "record": record, "errors": errors})
            continue

        submission_uuid = record["submission_uuid"]
        if submission_uuid in seen or store.has(submission_uuid):
            duplicates.append(
                {
                    "index": index,
                    "submission_uuid": submission_uuid,
                    "urban_council": record.get("urban_council"),
                    # A same-UUID record with different content is
                    # suspicious; surface it, still drop it.
                    "conflict": submission_uuid in seen
                    and seen[submission_uuid] != _fingerprint(record),
                }
            )
            continue

        seen[submission_uuid] = _fingerprint(record)
        committed.append(record)

    store.commit(committed, rejected)  # persist first...
    queue.ack(len(batch))  # ...then clear the queue

    return {
        "skipped": False,
        "pending": queue.size,
        "committed": committed,
        "duplicates": duplicates,
        "rejected": rejected,
    }
