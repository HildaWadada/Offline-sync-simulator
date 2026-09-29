"""FastAPI app for the offline-first sync simulator.

Endpoints:
    POST /submissions  -- cache/queue a batch of raw submissions (no
                           validation yet; a field tool queues first,
                           validates on sync)
    POST /sync          -- validate, dedupe, and commit whatever is
                            queued. `?online=false` simulates being
                            offline: nothing is committed, the queue
                            is retained.
    GET  /queue          -- what's currently pending
    GET  /records         -- committed records
    GET  /rejected        -- records that failed validation
    GET  /health           -- liveness check
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query

from app.storage import OfflineQueue, RecordStore
from app.sync import sync as run_sync

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / ".state"

app = FastAPI(
    title="Offline-First Sync Simulator",
    description="Queue field submissions, dedupe by submission_uuid, validate, and commit.",
    version="1.0.0",
)

# Module-level singletons, persisted to .state/ so the app survives a
# restart -- a stand-in for a device's local cache and a remote server.
queue = OfflineQueue(str(STATE_DIR / "queue.json"))
store = RecordStore(str(STATE_DIR / "store.json"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/submissions")
def submit(records: list[dict[str, Any]]) -> dict[str, int]:
    """Cache/queue records. Field tools call this while offline; nothing
    is validated or committed until /sync runs."""
    queue.enqueue(records)
    return {"queued": len(records), "pending": queue.size}


@app.post("/sync")
def sync_endpoint(online: bool = Query(True, description="Simulate connectivity")) -> dict:
    return run_sync(queue, store, online=online)


@app.get("/queue")
def get_queue() -> dict:
    return {"pending": queue.size, "items": queue.peek()}


@app.get("/records")
def get_records() -> dict:
    return {"count": len(store.records), "records": store.records}


@app.get("/rejected")
def get_rejected() -> dict:
    return {"count": len(store.rejected), "rejected": store.rejected}
