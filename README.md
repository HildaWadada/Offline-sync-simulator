# Offline-First Sync Simulator (FastAPI)

Simulates how a field tool queues submissions while offline and syncs them safely once connectivity returns. Core logic is plain Python with no framework dependency; FastAPI wraps it as an API for a real dashboard to call.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt
```

## Run

```bash
python demo.py                        # console demo, no server needed
pytest                                 # test suite (11 tests)
uvicorn app.main:app --reload          # API + interactive docs at /docs
```

Expected `demo.py` result: 4 queued -> **3 committed**, 1 duplicate dropped (Mukono Municipality), 0 pending.

## API

| Method | Path             | Purpose                                              |
|--------|------------------|-------------------------------------------------------|
| POST   | `/submissions`   | Cache/queue a batch of raw records (no validation yet) |
| POST   | `/sync?online=`  | Validate, dedupe, and commit the queue                |
| GET    | `/queue`         | What's currently pending                               |
| GET    | `/records`       | Committed records                                       |
| GET    | `/rejected`      | Records that failed validation                          |

Example:

```bash
curl -X POST localhost:8000/submissions -H "Content-Type: application/json" -d @data/payload.json
curl -X POST "localhost:8000/sync?online=false"   # simulates offline: nothing commits
curl -X POST "localhost:8000/sync?online=true"    # 3 committed, 1 dropped
curl localhost:8000/records
```

## How it works

`app/sync.py` -> `sync(queue, store, online=True)`

1. **Cache/queue**: `OfflineQueue` (`app/storage.py`) persists submissions to a JSON file under `.state/` (stand-in for SQLite on a device). While `online=False`, `sync` is a no-op and everything stays queued.
2. **Validate**: `app/validate.py` checks UUID format, non-empty council, `pdp_status` in `Active | Expiring | Missing`, an ISO-8601 timestamp, and a cross-field rule: `expiry_year` is required for Active/Expiring and must be `null` for Missing (so the Gulu record is valid). Invalid records go to a reject log and are never committed.
3. **Dedupe**: by `submission_uuid`, first occurrence wins. Also checked against records committed in earlier syncs, so retries and re-submissions are idempotent. A same-UUID record whose content differs is still dropped but flagged `conflict: true`.
4. **Commit**: valid unique records are written in a single store write, then the queue is acknowledged. If the commit raises, the queue is untouched, so nothing is lost and a retry is safe.

## Design notes and trade-offs

- Commit to the store *before* clearing the queue: at-least-once delivery plus UUID dedupe gives effectively-once commits.
- Client-generated UUIDs are the idempotency key. The same pattern works with a unique constraint on `submission_uuid` in a real database (Postgres, SQLite).
- First-write-wins is the simplest conflict policy. A production system might compare `field_officer_timestamp`, or surface conflicts to a reviewer instead of silently dropping them.
- Not included (out of scope for a 2-3h exercise): auth, retry/backoff, a persistent DB instead of JSON files, a UI. `sync()` is storage-agnostic — swap `OfflineQueue`/`RecordStore` for SQLAlchemy models and nothing else changes.

## Layout

```
app/validate.py    record validation
app/storage.py     OfflineQueue + RecordStore (JSON-file persistence)
app/sync.py        queue -> validate -> dedupe -> commit
app/main.py        FastAPI endpoints
demo.py             standalone console demo (no server)
tests/test_sync.py  core logic tests
tests/test_api.py   API smoke test
data/payload.json   the sample queued payload
```
