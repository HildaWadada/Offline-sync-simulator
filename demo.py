"""Run the sync simulator end-to-end against data/payload.json and
print what happened -- no server required.

    python demo.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.storage import OfflineQueue, RecordStore
from app.sync import sync

BASE_DIR = Path(__file__).resolve().parent
STATE_DIR = BASE_DIR / ".state"
shutil.rmtree(STATE_DIR, ignore_errors=True)  # fresh demo run

payload = json.loads((BASE_DIR / "data" / "payload.json").read_text(encoding="utf-8"))
queue = OfflineQueue(str(STATE_DIR / "queue.json"))
store = RecordStore(str(STATE_DIR / "store.json"))

print(f"[device] offline. caching {len(payload)} submissions...")
queue.enqueue(payload)
print(f"[device] queued: {queue.size}")

attempt = sync(queue, store, online=False)
print(f"[sync]   attempt while offline -> skipped ({attempt['reason']}), still pending: {attempt['pending']}\n")

print("[device] connectivity restored. syncing...")
result = sync(queue, store, online=True)

for d in result["duplicates"]:
    conflict = " [content conflict]" if d["conflict"] else ""
    print(f"[sync]   DROPPED duplicate #{d['index']}: {d['urban_council']} ({d['submission_uuid']}){conflict}")
for r in result["rejected"]:
    print(f"[sync]   REJECTED #{r['index']}: {'; '.join(r['errors'])}")

print(
    f"\n[sync]   committed {len(result['committed'])}, "
    f"dropped {len(result['duplicates'])}, "
    f"rejected {len(result['rejected'])}, "
    f"pending {result['pending']}"
)

rows = [
    (r["submission_uuid"], r["urban_council"], r["pdp_status"], r["expiry_year"])
    for r in store.records
]
headers = ("submission_uuid", "urban_council", "pdp_status", "expiry_year")
widths = [max(len(str(x)) for x in [h, *[row[i] for row in rows]]) for i, h in enumerate(headers)]
line = "-+-".join("-" * w for w in widths)
print("\n" + " | ".join(h.ljust(w) for h, w in zip(headers, widths)))
print(line)
for row in rows:
    print(" | ".join(str(v).ljust(w) for v, w in zip(row, widths)))
