#!/usr/bin/env python3
"""D-1 deliverable (v0.3.7): read-only audit of the deep_read backlog.

Answers the question the old `queue empty` lie hid: what is *actually* sitting
in the queue? Splits pending items into test residue vs. real papers, and
reports age/priority/source so a cleanup decision can be made on facts.

Read-only by default. Pass --purge-residue to mark suspected residue as failed
(non-destructive: status -> failed, reason recorded; rows are never deleted).

Usage:
    python3 scripts/audit_deep_read_queue.py
    python3 scripts/audit_deep_read_queue.py --purge-residue
"""
from __future__ import annotations

import argparse
import collections
import json
import sqlite3
import sys
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "queue.db"

RESIDUE_MARKERS = (
    "test", "stresstopic", "stress_topic", "force-delete", "structure-test",
    "contract-test", "trim",
)


def is_residue(topic: str) -> bool:
    t = (topic or "").lower()
    return any(m in t for m in RESIDUE_MARKERS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--purge-residue", action="store_true",
                    help="mark suspected residue items as failed (no row deletion)")
    args = ap.parse_args()

    if not DB_PATH.exists():
        print(f"queue.db not found: {DB_PATH}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    now = time.time()

    rows = [dict(r) for r in conn.execute(
        "SELECT id, topic, priority, metadata, status, requeue_count, "
        "created_at FROM queue WHERE status = 'pending'"
    )]

    by_type = collections.Counter()
    for r in rows:
        md = r.get("metadata")
        t = None
        if md:
            try:
                t = json.loads(md).get("task_type")
            except Exception:
                t = "<bad-json>"
        by_type[t] += 1

    residue = [r for r in rows if is_residue(r["topic"])]
    real = [r for r in rows if not is_residue(r["topic"])]

    print(f"=== deep_read queue audit ===")
    print(f"pending total : {len(rows)}")
    print(f"  by task_type: {dict(by_type)}")
    print(f"  suspected residue: {len(residue)}")
    print(f"  real papers      : {len(real)}")
    if real:
        ages = [(now - r["created_at"]) / 3600 for r in real]
        print(f"  real age range   : {min(ages):.1f}h .. {max(ages):.1f}h")

    print("\n-- residue items --")
    for r in residue:
        print(f"  [{r['id']}] P{r['priority']} {r['topic'][:70]!r}")

    src = collections.Counter()
    for r in real:
        try:
            md = json.loads(r.get("metadata") or "{}")
        except Exception:
            md = {}
        host = (md.get("source_url") or "?").split("/")[2] if "://" in (md.get("source_url") or "") else "?"
        src[host] += 1
    print("\n-- real papers by source host (top 12) --")
    for h, n in src.most_common(12):
        print(f"  {n:>3}  {h}")

    if args.purge_residue:
        if not residue:
            print("\nno residue to purge.")
            return 0
        ids = [r["id"] for r in residue]
        conn.executemany(
            "UPDATE queue SET status='failed', failed_reason=?, completed_at=? "
            "WHERE id=? AND status='pending'",
            [("D-1 audit: test residue", now, i) for i in ids],
        )
        conn.commit()
        print(f"\nmarked {len(ids)} residue items as failed (rows preserved).")
    else:
        print("\n(read-only; re-run with --purge-residue to mark residue as failed)")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
