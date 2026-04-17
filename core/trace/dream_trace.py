"""Dream Agent Trace Writer."""
import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

_TRACES_DB = os.path.join(os.path.dirname(__file__), "../../knowledge", "traces.db")


class DreamTraceWriter:
    """Writes dream traces to SQLite."""

    def __init__(self):
        self._conn = sqlite3.connect(_TRACES_DB, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        self._conn.execute("""CREATE TABLE IF NOT EXISTS dream_traces (
            trace_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
            status TEXT NOT NULL DEFAULT 'running',
            l1_candidates TEXT, l1_count INTEGER DEFAULT 0, l1_duration_ms INTEGER DEFAULT 0,
            l2_scored TEXT, l2_count INTEGER DEFAULT 0, l2_duration_ms INTEGER DEFAULT 0,
            l3_filtered TEXT, l3_count INTEGER DEFAULT 0, l3_duration_ms INTEGER DEFAULT 0,
            l4_topics TEXT, l4_count INTEGER DEFAULT 0, l4_duration_ms INTEGER DEFAULT 0,
            insights_generated TEXT, total_duration_ms INTEGER DEFAULT 0, error TEXT
        )""")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_dream_traces_status ON dream_traces(status)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_dream_traces_time ON dream_traces(started_at)")
        self._conn.commit()

    def start_trace(self) -> str:
        trace_id = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO dream_traces (trace_id, started_at, status) VALUES (?,?,?)",
            (trace_id, datetime.now(timezone.utc).isoformat(), "running"),
        )
        self._conn.commit()
        return trace_id

    def finish_trace(self, trace_id: str, status: str = "done",
                     l1_candidates: list = None, l1_count: int = 0, l1_duration_ms: int = 0,
                     l2_scored: list = None, l2_count: int = 0, l2_duration_ms: int = 0,
                     l3_filtered: list = None, l3_count: int = 0, l3_duration_ms: int = 0,
                     l4_topics: list = None, l4_count: int = 0, l4_duration_ms: int = 0,
                     insights_generated: list = None, total_duration_ms: int = 0,
                     error: str = None):
        def _to_json(data):
            if data is None:
                return None
            return json.dumps(data, default=str, ensure_ascii=False)

        self._conn.execute("""UPDATE dream_traces SET finished_at=?, status=?,
            l1_candidates=?, l1_count=?, l1_duration_ms=?,
            l2_scored=?, l2_count=?, l2_duration_ms=?,
            l3_filtered=?, l3_count=?, l3_duration_ms=?,
            l4_topics=?, l4_count=?, l4_duration_ms=?,
            insights_generated=?, total_duration_ms=?, error=?
            WHERE trace_id=?""",
            (datetime.now(timezone.utc).isoformat(), status,
             _to_json(l1_candidates), l1_count, l1_duration_ms,
             _to_json(l2_scored), l2_count, l2_duration_ms,
             _to_json(l3_filtered), l3_count, l3_duration_ms,
             _to_json(l4_topics), l4_count, l4_duration_ms,
             _to_json(insights_generated), total_duration_ms, error, trace_id))
        self._conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()