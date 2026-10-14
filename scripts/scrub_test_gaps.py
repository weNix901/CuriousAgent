#!/usr/bin/env python3
"""v0.3.7-D1c: one-shot cleanup of test pollution that entered ops.db.gaps
BEFORE the test-mode guard existed.

Only touches rows whose observed_by is 'hook'/'unknown' AND whose topic matches
a known synthetic/test pattern. Legitimate topics (e.g. '知识图谱',
'FlashAttention') are preserved. Non-destructive: real_seen is zeroed and
observed_by set to 'test' (rows kept for audit).

Usage:
    python3 scripts/scrub_test_gaps.py          # dry-run (default)
    python3 scripts/scrub_test_gaps.py --apply
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "knowledge" / "ops.db"

# 明确的测试/合成话题（由 v0.3.7 实测的污染清单 + 通用合成命名模式）
TEST_TOPICS = {
    "BrandNewTopicXYZ123", "UnknownTopic123", "never-worked",
    "量子计算xyz", "FreshSyntheticCheckXYZ999", "YetAnotherFreshQ99",
    "TestTopicE2E", "TestTopic", "test_topic",
}
# 合成命名模式（XYZ123 / ABC / Qnn / 'never-worked' 等）
import re
SYNTH_PATTERNS = [
    re.compile(r"XYZ\d+"),
    re.compile(r"Test\w*(Topic|ABC)"),
    re.compile(r"Q\d{2}$"),
    re.compile(r"Gamma|Delta$"),
]


def is_test(topic: str) -> bool:
    if topic in TEST_TOPICS:
        return True
    return any(p.search(topic) for p in SYNTH_PATTERNS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "SELECT topic, observed_by, real_seen FROM gaps"
    )]

    targets = [r for r in rows if is_test(r["topic"]) and r["observed_by"] != "test"]
    print(f"gaps total: {len(rows)}")
    print(f"test pollution detected: {len(targets)}")
    for r in targets:
        print(f"  {r['topic']!r}  observed_by={r['observed_by']} real_seen={r['real_seen']}")

    if not args.apply:
        print("\n(dry-run; re-run with --apply to scrub)")
        return 0

    for r in targets:
        conn.execute(
            "UPDATE gaps SET observed_by='test', real_seen=0 WHERE topic=?",
            (r["topic"],),
        )
    conn.commit()
    print(f"\nscrubbed {len(targets)} rows (observed_by='test', real_seen=0).")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
