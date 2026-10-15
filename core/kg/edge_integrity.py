"""KG edge integrity check (v0.3.7 A-5, read-only guardrail).

Periodically verify that the KG has no duplicate or key-less relations.
The uniqueness constraint is enforced on a synthetic ``key`` property
(``<from>|<relation>|<to>``); if any write path bypasses it, duplicates
accumulate silently. This module makes that visible.

Usage:
    python3 -m core.kg.edge_integrity            # one-shot check
    from core.kg.edge_integrity import check_edge_integrity  # daemon tick use
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

RELATION_TYPES = ["IS_CHILD_OF", "CITES", "DERIVED_FROM", "RELATED_TO"]


def check_edge_integrity(client: Any, relation_types: Optional[List[str]] = None) -> Dict[str, Any]:
    """Read-only check: every relation has a key, and keys are unique.

    Returns a dict:
        {"ok": bool, "total": int, "missing_key": int,
         "duplicate_keys": int, "per_type": {...}}
    """
    relation_types = relation_types or RELATION_TYPES
    total = 0
    missing = 0
    dupes = 0
    per_type: Dict[str, Dict[str, int]] = {}

    def _run(query: str) -> Any:
        import asyncio
        res = client.execute_write(query)
        if asyncio.iscoroutine(res):
            res = asyncio.get_event_loop().run_until_complete(res)
        return res

    for rel in relation_types:
        t_total = _scalar(_run(
            f"MATCH (:Knowledge)-[r:{rel}]->(:Knowledge) RETURN count(r) AS c"
        ))
        t_missing = _scalar(_run(
            f"MATCH (:Knowledge)-[r:{rel}]->(:Knowledge) "
            f"WHERE r.key IS NULL RETURN count(r) AS c"
        ))
        t_dupes = _scalar(_run(
            f"MATCH (:Knowledge)-[r:{rel}]->(:Knowledge) "
            f"WITH r.key AS k, count(*) AS c WHERE k IS NOT NULL AND c > 1 "
            f"RETURN coalesce(sum(c - 1), 0) AS d"
        ))
        total += t_total
        missing += t_missing
        dupes += t_dupes
        per_type[rel] = {"total": t_total, "missing_key": t_missing, "duplicate_keys": t_dupes}

    ok = missing == 0 and dupes == 0
    if not ok:
        logger.warning(
            f"EDGE INTEGRITY VIOLATION: {missing} edges missing key, "
            f"{dupes} duplicate keys (of {total} total)"
        )
    return {
        "ok": ok,
        "total": total,
        "missing_key": missing,
        "duplicate_keys": dupes,
        "per_type": per_type,
    }


def _scalar(result: Any) -> int:
    """Extract a scalar count from a Neo4j result list/dict/iterator."""
    if result is None:
        return 0
    if isinstance(result, dict):
        return int(result.get("c", result.get("d", 0)) or 0)
    if isinstance(result, list):
        if not result:
            return 0
        row = result[0]
        if isinstance(row, dict):
            return int(row.get("c", row.get("d", 0)) or 0)
        return int(row)
    try:
        row = next(iter(result))
        return int(row.get("c", row.get("d", 0)) or 0)
    except Exception:
        return 0


def main() -> int:
    import os
    from neo4j import GraphDatabase

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USERNAME", "neo4j")
    pwd = os.environ.get("NEO4J_PASSWORD", "")
    driver = GraphDatabase.driver(uri, auth=(user, pwd))

    with driver.session() as s:
        class _SessionClient:
            def execute_write(self, query, **kw):
                return [dict(r) for r in s.run(query, **kw)]

        report = check_edge_integrity(_SessionClient())
    driver.close()

    print(f"total edges: {report['total']}")
    print(f"missing key: {report['missing_key']}")
    print(f"duplicate keys: {report['duplicate_keys']}")
    for rel, st in report["per_type"].items():
        print(f"  {rel}: total={st['total']} missing={st['missing_key']} dup={st['duplicate_keys']}")
    print("OK" if report["ok"] else "FAIL: edge integrity violated")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
