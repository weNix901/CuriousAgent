"""Backfill the synthetic `key` property onto existing KG relations.

Why: to enforce duplicate-free edges we add a property-based relationship
uniqueness constraint on `r.key` (Neo4j rejects bare `REQUIRE r IS UNIQUE`
in this dialect; only `REQUIRE r.<prop> IS UNIQUE` works). Edges created
before this change have no `key`, so we must populate them first — and while
doing so, drop any duplicate edges so the constraint can be created cleanly.

Usage:
    python3 scripts/backfill_relation_keys.py [--dry-run]
"""
import argparse
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from neo4j import GraphDatabase  # noqa: E402

RELATION_TYPES = ["IS_CHILD_OF", "CITES", "DERIVED_FROM", "RELATED_TO"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USERNAME", "neo4j")
    pwd = os.environ.get("NEO4J_PASSWORD", "")
    driver = GraphDatabase.driver(uri, auth=(user, pwd))

    total_dropped = 0
    total_tagged = 0
    with driver.session() as s:
        for rel in RELATION_TYPES:
            rows = list(s.run(
                f"MATCH (a:Knowledge)-[r:{rel}]->(b:Knowledge) "
                f"RETURN a.topic AS a, b.topic AS b, elementId(r) AS eid"
            ))
            by_key = defaultdict(list)
            for row in rows:
                by_key[f"{row['a']}|{rel}|{row['b']}"].append(row["eid"])

            keep, drop = [], []
            for key, eids in by_key.items():
                keep.append((key, eids[0]))
                drop.extend(eids[1:])

            print(f"{rel}: {len(rows)} edges, {len(by_key)} unique keys, "
                  f"{len(drop)} duplicates")

            if args.dry_run:
                total_tagged += len(keep)
                total_dropped += len(drop)
                continue

            # Drop duplicate edges (keep one per key)
            for i in range(0, len(drop), 1000):
                chunk = drop[i:i + 1000]
                s.run(
                    "MATCH ()-[r]->() WHERE elementId(r) IN $eids DELETE r",
                    eids=chunk,
                )
            # Tag surviving edges with their key
            for i in range(0, len(keep), 1000):
                chunk = [{"eid": eid, "key": key} for key, eid in keep[i:i + 1000]]
                s.run(
                    """
                    UNWIND $rows AS row
                    MATCH ()-[r]->() WHERE elementId(r) = row.eid
                    SET r.key = row.key
                    """,
                    rows=chunk,
                )
            total_tagged += len(keep)
            total_dropped += len(drop)

    driver.close()

    verb = "would drop" if args.dry_run else "dropped"
    print(f"\nDone. {verb} {total_dropped} duplicate edges; "
          f"tagged {total_tagged} edges with `key`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
