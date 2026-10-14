#!/usr/bin/env python3
"""v0.3.7-D1c: purge test/stress artifacts from the Neo4j knowledge graph.

Same root disease as the queue/gap pollution: stress tests and e2e tests wrote
synthetic nodes straight into the KG (stress_topic_*, test *, *_XYZ123, ...).
These pollute DreamAgent's dream material and OrphanScan's candidate set.

Non-destructive options:
    (default)  dry-run report
    --apply    delete matching nodes (and their relations, via DETACH DELETE)

Matching uses the SHARED predicate in core.knowledge_graph_compat
(_is_residue_topic) plus an explicit stress_topic_* pattern.

Usage:
    python3 scripts/scrub_test_kg_nodes.py
    python3 scripts/scrub_test_kg_nodes.py --apply
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.kg.repository_factory import get_kg_factory  # noqa: E402
from core.knowledge_graph_compat import _is_residue_topic  # noqa: E402

STRESS_RE = re.compile(r"^stress_topic_", re.I)


def is_pollution(topic: str) -> bool:
    if STRESS_RE.search(topic or ""):
        return True
    return _is_residue_topic(topic)


async def _delete(client, topics: list[str]) -> int:
    deleted = 0
    q = "MATCH (n:Knowledge {topic:$t}) DETACH DELETE n"
    for t in topics:
        try:
            await client.execute_write(q, t=t)
            deleted += 1
        except Exception as e:
            print(f"  failed to delete {t!r}: {e}", file=sys.stderr)
    return deleted


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=5000)
    args = ap.parse_args()

    f = get_kg_factory()
    nodes = f.get_all_nodes_sync(limit=args.limit)
    targets = [n.get("topic", "") for n in nodes if is_pollution(n.get("topic", ""))]

    print(f"total nodes : {len(nodes)}")
    print(f"pollution   : {len(targets)}")
    for t in targets[:20]:
        print(f"  - {t[:70]!r}")
    if len(targets) > 20:
        print(f"  ... and {len(targets) - 20} more")

    if not args.apply:
        print("\n(dry-run; re-run with --apply to delete)")
        return 0

    repo = asyncio.run(f._ensure_connected())
    client = f._client
    deleted = asyncio.run(_delete(client, targets))
    print(f"\ndeleted {deleted}/{len(targets)} pollution nodes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
