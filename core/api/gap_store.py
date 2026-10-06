"""批4a (v0.3.6): Gap store — C1 unknown/void 订阅落库。

CA2.0 §3.2 数据流原文：
    [用户问题] → C1 覆盖状态 → 若 unknown/void → 缺口计算器 (C2) → 探索队列

缺口的一等公民来源 = C1 判定的 `unknown`/`void` 话题（用户问了我没有 = 差值）。
本模块把四态判为 unknown/void 的话题落为缺口记录，供批4b 计算器消费。

真值源 = SQLite（knowledge/ops.db），同批1 纪律（运行状态进 SQLite）。
幂等：同 topic 重复观测 → 累加 seen_count、更新 last_seen，不产生重复行。

表 gaps:
    topic        TEXT PK
    status       TEXT      -- unknown | void
    quality      REAL      -- 观测时刻的 KG quality（unknown/void 恒为 0）
    source_count INTEGER
    seen_count   INTEGER   -- 被观测到"缺"的次数（相关性代理之一）
    first_seen   TEXT
    last_seen    TEXT
    consumed     INTEGER   -- 是否已被 4c 入队（0/1）
"""
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ops.db 单一真源 = <project_root>/knowledge/ops.db。
# 本文件位于 core/api/，需上溯三级到项目根后再进 knowledge/。
# （历史 bug：曾用 dirname(dirname(...)) = core/，导致落到 core/knowledge/ops.db，
#   与 knowledge/ops.db 分裂。2026-10-07 合并修复。）
_DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "knowledge", "ops.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gaps (
    topic        TEXT PRIMARY KEY,
    status       TEXT NOT NULL,
    quality      REAL NOT NULL DEFAULT 0.0,
    source_count INTEGER NOT NULL DEFAULT 0,
    seen_count   INTEGER NOT NULL DEFAULT 1,
    first_seen   TEXT NOT NULL,
    last_seen    TEXT NOT NULL,
    consumed     INTEGER NOT NULL DEFAULT 0
)
"""

# 只有这两态算"缺口"（CA2.0 §3.2）。known/partial 有知识，不是缺口。
GAP_STATES = ("unknown", "void")


def _get_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or _DEFAULT_DB
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    return conn


def record_gap(
    topic: str,
    coverage: str,
    quality: float = 0.0,
    source_count: int = 0,
    db_path: Optional[str] = None,
) -> bool:
    """记录/更新一个缺口（幂等）。

    只有 coverage ∈ {unknown, void} 才落库；其余状态直接返回 False（不是缺口）。
    失败绝不抛异常（同批1 纪律）—— 缺口感测不得破坏主查询/回复路径。

    Returns:
        True 表示该 topic 是一个缺口（已落库）；False 表示不是缺口或落库失败。
    """
    try:
        cov = (coverage or "").strip().lower()
        if cov not in GAP_STATES:
            return False
        topic = (topic or "").strip()
        if not topic:
            return False

        ts = datetime.now(timezone.utc).isoformat()
        conn = _get_conn(db_path)
        try:
            with conn:
                row = conn.execute(
                    "SELECT seen_count, first_seen FROM gaps WHERE topic = ?", (topic,)
                ).fetchone()
                if row is None:
                    conn.execute(
                        "INSERT INTO gaps (topic, status, quality, source_count, "
                        "seen_count, first_seen, last_seen, consumed) "
                        "VALUES (?, ?, ?, ?, 1, ?, ?, 0)",
                        (topic, cov, float(quality or 0.0), int(source_count or 0), ts, ts),
                    )
                else:
                    conn.execute(
                        "UPDATE gaps SET status = ?, quality = ?, source_count = ?, "
                        "seen_count = seen_count + 1, last_seen = ? WHERE topic = ?",
                        (cov, float(quality or 0.0), int(source_count or 0), ts, topic),
                    )
            return True
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"[gaps] record_gap failed for {topic!r}: {e}")
        return False


def list_gaps(
    only_unconsumed: bool = False,
    min_seen: int = 1,
    db_path: Optional[str] = None,
) -> list:
    """列出缺口（供 4b 计算器消费）。失败返回空列表。"""
    try:
        conn = _get_conn(db_path)
        try:
            q = "SELECT * FROM gaps WHERE seen_count >= ?"
            params = [int(min_seen)]
            if only_unconsumed:
                q += " AND consumed = 0"
            q += " ORDER BY seen_count DESC, last_seen DESC"
            rows = conn.execute(q, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"[gaps] list_gaps failed: {e}")
        return []


def mark_consumed(topic: str, db_path: Optional[str] = None) -> None:
    """标记缺口已被入队消费（4c 调用），避免重复入队。"""
    try:
        conn = _get_conn(db_path)
        try:
            with conn:
                conn.execute("UPDATE gaps SET consumed = 1 WHERE topic = ?", (topic,))
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"[gaps] mark_consumed failed for {topic!r}: {e}")
