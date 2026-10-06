"""批5 C3-C (v0.3.6): Retrieval hit log — 检索命中追踪。

CA2.0 §4.3 C3「发现回流」的第三环：记录 discovery 是否被检索/引用。

    缺口 ID → 探索 → discovery → 行为库 → 进入 context → R1D3 可检索 → 输出变化
                                                              ▲
                                                    本模块记录这一环

追踪证据（文件级，不读 LLM 内部状态）：
    「进入 context」= 文件被加载（extraPaths + 检索命中日志）
    「行为变化」   = R1D3 输出引用了该发现

本模块落库每次检索的事件：查询话题、命中的话题、相似度、四态判定。
这样"某个缺口 → 某条 R1D3 输出变化"的追溯链才有第一环可观测证据。

真值源 = SQLite（knowledge/ops.db），同批1/4a 纪律（运行状态进 SQLite）。
纪律：绝不抛异常（失败静默返回）—— 命中日志绝不破坏主查询/回复路径。

表 retrieval_events:
    id           INTEGER PK AUTOINCREMENT
    query_topic  TEXT      -- 查询话题（R1D3 问的）
    matched_topic TEXT     -- 语义检索命中的话题（None = 未命中）
    similarity   REAL      -- 命中相似度（未命中 = 0）
    coverage     TEXT      -- 四态：known | partial | unknown | void
    quality      REAL      -- 命中节点的 quality
    source_count INTEGER   -- 命中节点的来源数
    matched      INTEGER   -- 是否真命中（known/partial=1，unknown/void=0）
    created_at   TEXT      -- ISO8601 UTC
"""
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ops.db 单一真源 = <project_root>/knowledge/ops.db（本文件在 core/api/，上溯三级）。
_DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "knowledge", "ops.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS retrieval_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    query_topic   TEXT NOT NULL,
    matched_topic TEXT,
    similarity    REAL NOT NULL DEFAULT 0.0,
    coverage      TEXT NOT NULL DEFAULT 'unknown',
    quality       REAL NOT NULL DEFAULT 0.0,
    source_count  INTEGER NOT NULL DEFAULT 0,
    matched       INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
)
"""

_SCHEMA_INDEX = """
CREATE INDEX IF NOT EXISTS idx_retrieval_query ON retrieval_events(query_topic);
CREATE INDEX IF NOT EXISTS idx_retrieval_matched_topic ON retrieval_events(matched_topic);
CREATE INDEX IF NOT EXISTS idx_retrieval_created ON retrieval_events(created_at);
"""

# 真命中 = 这两态（有可用知识）。unknown/void 是未命中。
HIT_STATES = ("known", "partial")


def _get_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or _DEFAULT_DB
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    for stmt in _SCHEMA_INDEX.strip().split(";"):
        if stmt.strip():
            conn.execute(stmt)
    return conn


def record_retrieval(
    query_topic: str,
    coverage: str,
    matched_topic: Optional[str] = None,
    similarity: float = 0.0,
    quality: float = 0.0,
    source_count: int = 0,
    db_path: Optional[str] = None,
) -> bool:
    """记录一次检索命中事件（C3-C）。

    在四态唯一出口（/api/knowledge/check 或 check_confidence）调用。
    失败绝不抛异常 —— 命中日志不得破坏主查询路径。

    Returns:
        True 表示已落库；False 表示落库失败（静默）。
    """
    try:
        qt = (query_topic or "").strip()
        if not qt:
            return False
        cov = (coverage or "unknown").strip().lower()
        is_hit = 1 if cov in HIT_STATES and matched_topic else 0
        ts = datetime.now(timezone.utc).isoformat()
        conn = _get_conn(db_path)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO retrieval_events "
                    "(query_topic, matched_topic, similarity, coverage, quality, "
                    "source_count, matched, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        qt,
                        matched_topic,
                        float(similarity or 0.0),
                        cov,
                        float(quality or 0.0),
                        int(source_count or 0),
                        is_hit,
                        ts,
                    ),
                )
            return True
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"[retrieval] record_retrieval failed for {query_topic!r}: {e}")
        return False


def list_retrievals(
    query_topic: Optional[str] = None,
    matched_topic: Optional[str] = None,
    only_hits: bool = False,
    limit: int = 100,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """列出检索事件（供 C3-D 反馈回好奇消费）。失败返回空列表。"""
    try:
        conn = _get_conn(db_path)
        try:
            q = "SELECT * FROM retrieval_events WHERE 1=1"
            params: List[Any] = []
            if query_topic:
                q += " AND query_topic = ?"
                params.append(query_topic)
            if matched_topic:
                q += " AND matched_topic = ?"
                params.append(matched_topic)
            if only_hits:
                q += " AND matched = 1"
            q += " ORDER BY id DESC LIMIT ?"
            params.append(int(limit))
            rows = conn.execute(q, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"[retrieval] list_retrievals failed: {e}")
        return []


def hit_stats(db_path: Optional[str] = None) -> Dict[str, Any]:
    """命中统计（供监控/C3-D 用）。失败返回空统计。"""
    try:
        conn = _get_conn(db_path)
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM retrieval_events"
            ).fetchone()[0]
            hits = conn.execute(
                "SELECT COUNT(*) FROM retrieval_events WHERE matched = 1"
            ).fetchone()[0]
            by_coverage = {}
            for row in conn.execute(
                "SELECT coverage, COUNT(*) as cnt FROM retrieval_events "
                "GROUP BY coverage"
            ).fetchall():
                by_coverage[row["coverage"]] = row["cnt"]
            return {
                "total": total,
                "hits": hits,
                "misses": total - hits,
                "hit_rate": round(hits / total, 4) if total else 0.0,
                "by_coverage": by_coverage,
            }
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"[retrieval] hit_stats failed: {e}")
        return {"total": 0, "hits": 0, "misses": 0, "hit_rate": 0.0, "by_coverage": {}}
