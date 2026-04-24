"""Explorer Agent Trace Writer."""
import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

_TRACES_DB = os.path.join(os.path.dirname(__file__), "../../knowledge", "traces.db")


class TraceWriter:
    """Writes explorer traces to SQLite."""

    def __init__(self):
        self._conn = sqlite3.connect(_TRACES_DB, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        self._conn.execute("""CREATE TABLE IF NOT EXISTS explorer_traces (
            trace_id TEXT PRIMARY KEY, topic TEXT NOT NULL, queue_item_id INTEGER,
            started_at TEXT NOT NULL, finished_at TEXT,
            status TEXT NOT NULL DEFAULT 'running',
            total_steps INTEGER DEFAULT 0, tools_used TEXT,
            kg_nodes_created TEXT, quality_score REAL,
            error TEXT, llm_total_tokens INTEGER, duration_ms INTEGER,
            notified INTEGER DEFAULT 0
        )""")
        self._conn.execute("""CREATE TABLE IF NOT EXISTS trace_steps (
            step_id TEXT PRIMARY KEY, trace_id TEXT NOT NULL, step_num INTEGER NOT NULL,
            timestamp TEXT NOT NULL, action TEXT NOT NULL, action_input TEXT,
            output_summary TEXT, output_size INTEGER DEFAULT 0,
            duration_ms INTEGER DEFAULT 0, is_llm_step INTEGER DEFAULT 0, llm_tokens INTEGER,
            FOREIGN KEY (trace_id) REFERENCES explorer_traces(trace_id)
        )""")
        self._conn.execute("""CREATE INDEX IF NOT EXISTS idx_trace_steps_trace
            ON trace_steps(trace_id, step_num)""")
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
        self._migrate_llm_call_to_is_llm_step()
        self._conn.commit()

    def _migrate_llm_call_to_is_llm_step(self):
        """Migrate legacy llm_call column to is_llm_step if needed."""
        try:
            cols = [row[1] for row in self._conn.execute("PRAGMA table_info(trace_steps)").fetchall()]
            if "llm_call" in cols and "is_llm_step" not in cols:
                self._conn.execute("ALTER TABLE trace_steps RENAME COLUMN llm_call TO is_llm_step")
        except sqlite3.OperationalError:
            pass

    def start_trace(self, topic: str, queue_item_id: Optional[int] = None) -> str:
        trace_id = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO explorer_traces (trace_id, topic, queue_item_id, started_at, status) VALUES (?,?,?,?,?)",
            (trace_id, topic, queue_item_id, datetime.now(timezone.utc).isoformat(), "running"),
        )
        self._conn.commit()
        return trace_id

    def record_step(self, trace_id: str, step_num: int, action: str,
                    action_input: str = "", is_llm_step: bool = False) -> str:
        step_id = str(uuid.uuid4())
        self._conn.execute(
            """INSERT INTO trace_steps (step_id, trace_id, step_num, timestamp, action,
               action_input, output_summary, output_size, duration_ms, is_llm_step, llm_tokens)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (step_id, trace_id, step_num, datetime.now(timezone.utc).isoformat(),
             action, action_input[:500] if action_input else None, "", 0, 0,
             1 if is_llm_step else 0, None),
        )
        self._conn.commit()
        return step_id

    def update_step(self, step_id: str, output_summary: str = "", output_size: int = 0,
                    duration_ms: int = 0, llm_tokens: int = None):
        self._conn.execute(
            """UPDATE trace_steps SET output_summary=?, output_size=?, duration_ms=?, llm_tokens=?
               WHERE step_id=?""",
            (output_summary[:300] if output_summary else "", output_size, duration_ms, llm_tokens, step_id),
        )
        self._conn.commit()

    def finish_trace(self, trace_id: str, status: str = "done",
                     total_steps: int = 0, tools_used: list = None,
                     kg_nodes_created: list = None, quality_score: float = None,
                     error: str = None, llm_total_tokens: int = None,
                     duration_ms: int = None, notified: bool = False):
        self._conn.execute(
            """UPDATE explorer_traces SET finished_at=?, status=?, total_steps=?,
               tools_used=?, kg_nodes_created=?, quality_score=?, error=?,
               llm_total_tokens=?, duration_ms=?, notified=? WHERE trace_id=?""",
            (datetime.now(timezone.utc).isoformat(), status, total_steps,
             json.dumps(tools_used or [], ensure_ascii=False),
             json.dumps(kg_nodes_created or [], ensure_ascii=False),
             quality_score, error, llm_total_tokens, duration_ms,
             1 if notified else 0, trace_id),
        )
        self._conn.commit()

    def update_notified(self, trace_id: str, notified: bool) -> None:
        """Update notified field for an existing trace."""
        self._conn.execute(
            "UPDATE explorer_traces SET notified=? WHERE trace_id=?",
            (1 if notified else 0, trace_id),
        )
        self._conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()