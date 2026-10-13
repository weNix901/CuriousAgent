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
    consumed_at  TEXT      -- 唯一消费真源：NULL=未消费，时间戳=已消费+何时
                           -- （2026-10-12 设计归一：删除冗余布尔列 consumed，
                           --   它曾与 consumed_at 漂移导致 C2 死锁，见 reset_stale_consumed）
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
    last_seen    TEXT NOT NULL
)
"""

# v0.3.6-C2 (2026-10-08) 新增列。用独立 ALTER 而非改 _SCHEMA，
# 以便对已存在的表做幂等迁移（SQLite 无 ADD COLUMN IF NOT EXISTS）。
#   observed_by : 观测来源(user|hook|test) — 让相关性只认真实会话触发
#   real_seen   : 真实观测计数（只累计 observed_by=user/hook）
#   consumed_at : 入队消费时间 — 唯一消费真源（NULL=未消费）
#
# 2026-10-12 设计归一：废弃冗余布尔列 consumed。
#   旧 schema 有 consumed INTEGER + consumed_at TEXT 两列，而 consumed 是
#   consumed_at 的派生（consumed = consumed_at IS NOT NULL）。两列可互相漂移，
#   历史上产生过 consumed=1 + consumed_at=NULL 的不一致态，导致
#   reset_stale_consumed 永久跳过 → C2 回路死锁。删除冗余列后，不一致态
#   在物理上无法表达。旧库的 consumed 列保留（SQLite 不易 DROP），但代码不再读写。
_MIGRATIONS = [
    "ALTER TABLE gaps ADD COLUMN observed_by TEXT NOT NULL DEFAULT 'unknown'",
    "ALTER TABLE gaps ADD COLUMN real_seen INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE gaps ADD COLUMN consumed_at TEXT",
]

# 只有这两态算"缺口"（CA2.0 §3.2）。known/partial 有知识，不是缺口。
GAP_STATES = ("unknown", "void")

# 视为"真实会话触发"的观测来源。test/probe 类打点不计入相关性。
# 视为"真实会话触发"的观测来源。只有这些计入 real_seen（相关性因子）。
# 2026-10-12 修复：原实现用字面量精确匹配 ("user","hook")，但真实 hook
# 调用传的是自己的 hook 名（如 'knowledge-gate'），不等于字面量 'hook' → is_real=0
# → 真实观测不计入相关性 → rank_gaps 的 rel=0 → 缺口价值恒 0 → C2 仍不工作。
# 改为"排除法"：凡非 test/probe/unknown 的来源一律视为真实观测。
NON_REAL_SOURCES = ("test", "probe", "unknown", "")


def _is_real_source(src: str) -> int:
    """观测来源是否计入 real_seen：非 test/probe/unknown 即真实。"""
    return 0 if (src or "").strip().lower() in NON_REAL_SOURCES else 1


# 向后兼容：旧代码/测试可能引用 REAL_SOURCES 做成员判断。保留并含类别名。
REAL_SOURCES = ("user", "hook")

# consumed 时间衰减：入队后超过此秒数且队列已消化 → 允许重评估（consumed 重置）。
# 默认 6 小时，可通过环境变量覆盖。
DEFAULT_CONSUME_TTL_S = 6 * 3600


def _consume_ttl_s() -> int:
    try:
        import os as _os
        return int(_os.environ.get("CA_GAP_CONSUME_TTL_S", DEFAULT_CONSUME_TTL_S))
    except Exception:
        return DEFAULT_CONSUME_TTL_S


def _get_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or _DEFAULT_DB
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    for stmt in _MIGRATIONS:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass  # 列已存在 → 幂等跳过
    # 回填历史行：real_seen 只认 user/hook；其余保持 0。
    try:
        conn.execute(
            "UPDATE gaps SET real_seen = seen_count "
            "WHERE observed_by IN ('user','hook') AND real_seen = 0"
        )
    except sqlite3.OperationalError:
        pass
    # 2026-10-12 数据自愈：旧库可能存在 consumed=1 但 consumed_at IS NULL 的
    # 不一致行（冗余列时代的产物）。设计归一后 consumed 列不再被信任，
    # 此处把这些行的 consumed 清回 0（未消费），让它们重新进入候选。
    try:
        conn.execute(
            "UPDATE gaps SET consumed = 0 "
            "WHERE consumed = 1 AND (consumed_at IS NULL OR consumed_at = '')"
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass  # 新库无 consumed 列 → 无需自愈
    return conn


def record_gap(
    topic: str,
    coverage: str,
    quality: float = 0.0,
    source_count: int = 0,
    observed_by: str = "unknown",
    db_path: Optional[str] = None,
) -> bool:
    """记录/更新一个缺口（幂等）。

    只有 coverage ∈ {unknown, void} 才落库；其余状态直接返回 False（不是缺口）。
    失败绝不抛异常（同批1 纪律）—— 缺口感测不得破坏主查询/回复路径。

    Args:
        observed_by: 观测来源。REAL_SOURCES('user'/'hook') 计入 real_seen
            （相关性因子只认真实会话触发）；'test'/'probe'/'unknown' 只累加
            seen_count，不污染 real_seen。

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

        src = (observed_by or "unknown").strip().lower()
        is_real = _is_real_source(src)

        ts = datetime.now(timezone.utc).isoformat()
        conn = _get_conn(db_path)
        try:
            with conn:
                row = conn.execute(
                    "SELECT seen_count, real_seen, first_seen, "
                    "consumed_at, observed_by "
                    "FROM gaps WHERE topic = ?", (topic,)
                ).fetchone()
                if row is None:
                    conn.execute(
                        "INSERT INTO gaps (topic, status, quality, source_count, "
                        "seen_count, first_seen, last_seen, "
                        "observed_by, real_seen, consumed_at) "
                        "VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, NULL)",
                        (topic, cov, float(quality or 0.0), int(source_count or 0),
                         ts, ts, src, is_real),
                    )
                else:
                    # 真实观测优先记录其来源，避免被后续 test 打点覆盖语义。
                    # 保留语义优先级：真实观测覆盖非真实来源，反之不覆盖。
                    new_src = src if (is_real or _is_real_source(row["observed_by"]) == 0) \
                        else row["observed_by"]
                    new_real = int(row["real_seen"] or 0) + is_real
                    # 重新观测到 → 清空 consumed_at（出现新证据 = 重新变为未消费）。
                    conn.execute(
                        "UPDATE gaps SET status = ?, quality = ?, source_count = ?, "
                        "seen_count = seen_count + 1, real_seen = ?, last_seen = ?, "
                        "observed_by = ?, consumed_at = NULL "
                        "WHERE topic = ?",
                        (cov, float(quality or 0.0), int(source_count or 0),
                         new_real, ts, new_src, topic),
                    )
            # 2026-10-12 抗静默：成功路径也留痕。以前只在失败时打 warning，
            # 导致"缺口订阅断线"8 天无任何信号（成功=沉默，断线=也沉默）。
            logger.debug(
                f"[gaps] record_gap: {topic!r} status={cov} "
                f"observed_by={src} real={is_real}"
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
                # 设计归一：未消费 = consumed_at IS NULL（不再读冗余布尔列）。
                q += " AND consumed_at IS NULL"
            q += " ORDER BY seen_count DESC, last_seen DESC"
            rows = conn.execute(q, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"[gaps] list_gaps failed: {e}")
        return []


def mark_consumed(topic: str, db_path: Optional[str] = None) -> None:
    """标记缺口已被入队消费（4c 调用），避免重复入队。

    记录 consumed_at 时间戳，供 reset_stale_consumed() 做时间衰减重置。
    """
    try:
        ts = datetime.now(timezone.utc).isoformat()
        conn = _get_conn(db_path)
        try:
            with conn:
                conn.execute(
                    "UPDATE gaps SET consumed_at = ? WHERE topic = ?",
                    (ts, topic),
                )
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"[gaps] mark_consumed failed for {topic!r}: {e}")


def reset_stale_consumed(db_path: Optional[str] = None, ttl_s: Optional[int] = None) -> int:
    """时间衰减：入队超过 TTL 的缺口，重置 consumed=0，允许重评估。

    让 C2 从"一次性管道"变为"循环"：缺口入队 → 探索 → 若知识仍缺，
    且静置超过 TTL，则重新进入候选，供 4c 再次入队。

    仅在对应队列项**已不在 pending**（已消化/失败）时才重置——避免同一条
    缺口在探索进行中反复入队。

    Returns:
        被重置的缺口数。失败返回 0（纪律）。
    """
    try:
        ttl = _consume_ttl_s() if ttl_s is None else int(ttl_s)
        cutoff = datetime.now(timezone.utc).timestamp() - ttl
        conn = _get_conn(db_path)
        try:
            # 设计归一：已消费 = consumed_at IS NOT NULL。
            rows = conn.execute(
                "SELECT topic, consumed_at FROM gaps WHERE consumed_at IS NOT NULL"
            ).fetchall()
            if not rows:
                return 0

            # 队列 pending 话题集合（探索进行中/待探索的不重置）。
            pending_topics = set()
            try:
                import sqlite3 as _sq
                qdb = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    "knowledge", "queue.db",
                )
                qc = _sq.connect(qdb, timeout=10)
                try:
                    for r in qc.execute(
                        "SELECT topic FROM queue WHERE status IN ('pending','claimed')"
                    ):
                        pending_topics.add(r[0])
                finally:
                    qc.close()
            except Exception:
                pass

            reset = 0
            with conn:
                for r in rows:
                    topic = r["topic"]
                    if topic in pending_topics:
                        continue  # 探索进行中
                    ca = r["consumed_at"]
                    if not ca:
                        # 设计归一 + 自愈：走到这里必然不可能（WHERE 已过滤 NULL），
                        # 但若历史库有不一致行（旧冗余列时代遗留），视其为"最陈旧的
                        # 消费"，直接重置为未消费。绝不静默跳过（旧 bug 根因）。
                        conn.execute(
                            "UPDATE gaps SET consumed_at = NULL WHERE topic = ?",
                            (topic,),
                        )
                        reset += 1
                        continue
                    try:
                        age = datetime.now(timezone.utc).timestamp() - \
                            datetime.fromisoformat(ca).timestamp()
                    except (ValueError, TypeError):
                        # 时间戳不可解析 = 脏数据 → 重置（同无时间戳处理）。
                        conn.execute(
                            "UPDATE gaps SET consumed_at = NULL WHERE topic = ?",
                            (topic,),
                        )
                        reset += 1
                        continue
                    if age >= ttl:
                        conn.execute(
                            "UPDATE gaps SET consumed_at = NULL "
                            "WHERE topic = ?", (topic,)
                        )
                        reset += 1
            if reset:
                logger.info(f"[gaps] reset_stale_consumed: {reset} gap(s) re-opened (ttl={ttl}s)")
            return reset
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"[gaps] reset_stale_consumed failed: {e}")
        return 0
