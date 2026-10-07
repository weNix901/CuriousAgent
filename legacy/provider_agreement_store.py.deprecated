"""Provider Agreement Store — 批1（v0.3.6）: 接通 provider 一致性死管道。

问题（v0.3.6 计划 §批1）：
    `curiosity_decomposer._verify_with_providers()` 产出 `provider_results`
    （{provider: result_count}），但只在内存里用一次就丢。
    `/api/providers/record` 端点存在、逻辑完整，却无任何调用方。
    `provider_heatmap.json` 从未生成 → 信号5（provider 一致性）为死数据。

修法（本模块）：
    验证完成后，把每个候选子话题的 provider 结果落库到 `ops.db.provider_agreement`。
    · 真值源 = SQLite（v0.3.4 数据治理：运行状态进 SQLite），非旧的文件副本模式。
    · 幂等：同一 (topic) 重复验证覆盖，不累积（避免热图失真）。

表结构：
    provider_agreement(topic, provider, result_count, agreed, ts)
    - agreed: 该 provider 是否"找到"（result_count > 0）→ 供 C1-B 冲突检测直接消费
"""
import logging
import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ops.db 单一真源 = <project_root>/knowledge/ops.db。
# 本文件在 core/ 下，上溯一级到项目根（原本已正确，加注释防回退）。
_DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge", "ops.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS provider_agreement (
    topic        TEXT NOT NULL,
    provider     TEXT NOT NULL,
    result_count INTEGER NOT NULL DEFAULT 0,
    agreed       INTEGER NOT NULL DEFAULT 0,
    ts           TEXT NOT NULL,
    PRIMARY KEY (topic, provider)
)
"""


def _get_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or _DEFAULT_DB
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.execute(_SCHEMA)
    return conn


def record_agreement(
    topic: str,
    provider_results: dict,
    providers_queried: Optional[list] = None,
    db_path: Optional[str] = None,
) -> int:
    """落库单个 topic 的 provider 验证结果（幂等覆盖）。

    Args:
        topic: 被验证的子话题
        provider_results: {provider_name: result_count}（仅含找到结果的 provider）
        providers_queried: 参与查询的全部 provider 名（用于标记"未找到"的 provider）
        db_path: 测试用覆盖

    Returns:
        写入行数
    """
    if not topic:
        return 0

    ts = datetime.now(timezone.utc).isoformat()
    rows = {}

    # 找到结果的 provider
    for provider, count in (provider_results or {}).items():
        rows[provider] = (int(count), 1 if int(count) > 0 else 0)

    # 参与查询但无结果的 provider → agreed=0（冲突检测需要"谁没找到"）
    for provider in (providers_queried or []):
        if provider not in rows:
            rows[provider] = (0, 0)

    if not rows:
        return 0

    conn = _get_conn(db_path)
    try:
        with conn:  # 事务：先删该 topic 旧记录，再写（幂等，不累积）
            conn.execute("DELETE FROM provider_agreement WHERE topic = ?", (topic,))
            conn.executemany(
                "INSERT INTO provider_agreement (topic, provider, result_count, agreed, ts) "
                "VALUES (?, ?, ?, ?, ?)",
                [(topic, p, rc, ag, ts) for p, (rc, ag) in rows.items()],
            )
        return len(rows)
    except Exception as e:
        logger.warning(f"[provider_agreement] record failed for {topic}: {e}")
        return 0
    finally:
        conn.close()


def get_agreement(topic: str, db_path: Optional[str] = None) -> dict:
    """读取某 topic 的 provider 一致性信号（供 C1-B 冲突检测消费）。

    Returns:
        {
          "topic": str,
          "providers": {provider: result_count},
          "provider_count": int,     # 参与查询的 provider 数
          "agreed_count": int,       # 找到结果的 provider 数
          "disagreement": bool,      # 部分找到部分没找到 → True
        }
    """
    conn = _get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT provider, result_count, agreed FROM provider_agreement WHERE topic = ?",
            (topic,),
        ).fetchall()
    finally:
        conn.close()

    providers = {r[0]: r[1] for r in rows}
    agreed_count = sum(1 for r in rows if r[2] == 1)
    provider_count = len(rows)

    return {
        "topic": topic,
        "providers": providers,
        "provider_count": provider_count,
        "agreed_count": agreed_count,
        # 分歧 = 有 provider 找到 且 有 provider 没找到
        "disagreement": 0 < agreed_count < provider_count,
    }
