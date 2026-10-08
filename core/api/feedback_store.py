"""批6 C3-D (v0.3.6): Feedback to curiosity — 反馈回好奇（方向级）。

CA2.0 §4.3「发现回流」闭环的最后一环。

    缺口ID → CA探索 → discovery → 行为库 → 进入 context → R1D3 可检索 → 输出变化
       ▲                                                                        │
       └────────── 本模块：被检索的 discovery 反馈回「同方向」缺口优先级 ◄──────┘

## CA2.0 §4.3 原文反馈环

    回填：该 discovery 被查询过 → 提高同类缺口优先级

## 设计（外部可观测，不读心 —— 遵守 C1 公理）

### 「发现」的真身（2026-10-07 核实）

「发现」= **行为库条目**（`curious-agent-behaviors.md`，343 条），非 KG 节点。
其 topic 命名空间与 `retrieval_events.matched_topic` 一致，可直接对照。

### 「方向」的聚类依据（2026-10-07 核实，经过数据质量验证）

用 **KG 节点的 content embedding**（1024 维，3927/3927 全覆盖）算余弦相似度。

> ⚠️ **曾误用 `IS_CHILD_OF` 关系做聚类，已证伪**：该关系 34,124 条边去重后
> 仅 900 个不同子节点（单对重复最多 484 次，是日志堆积非图结构），且真实
> 待探索话题（FlashAttention / 知识图谱）根本不在图里。教训：**数量大 ≠ 质量好**。

### 反馈逻辑

    已结案的发现（曾为缺口 → 现为 known/partial）
        │  用 embedding 找同方向（cos ≥ DIRECTION_THRESHOLD）
        ▼
    同方向中「仍在缺口表」的 topic → 提权（同类缺口优先级上升）
        │
        ▼
    进入 C2 队列 → CA 探索（闭环回到好奇）

纪律：
    1. 聚类走外部可观测 embedding，不 LLM 臆断（C1 公理）
    2. 失败静默，不破坏缺口计算主流程（同批1/4a/批5）
    3. 阈值固定可解释，不调参（同批0 纪律）
"""
import logging
import math
import os
import sqlite3
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# ops.db 单一真源 = <project_root>/knowledge/ops.db（本文件在 core/api/，上溯三级）。
_DEFAULT_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "knowledge", "ops.db"
)

# 行为库（C3-B 产物）
BEHAVIOR_FILE = "/root/.openclaw/workspace-researcher/curious-agent-behaviors.md"

# 真命中 = 有可用知识（缺口已消解）
HIT_STATES = ("known", "partial")

# 方向聚类阈值（余弦相似度）。固定值，可解释，不调参。
# 依据实测：KD×LLM=0.607（同向）、FlashAttention×知识图谱=0.443（异向）。
DIRECTION_THRESHOLD = 0.6

# 同类缺口提权上限（避免单方向淹没）
DIRECTION_BOOST = 1.5


def _get_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or _DEFAULT_DB
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# 1. 发现集合（行为库）
# ---------------------------------------------------------------------------

def discovered_topics(behavior_file: str = None) -> Set[str]:
    """从行为库提取发现集合（topic）。

    行为库条目格式：`### 📌 <topic>（日期）`
    失败返回空 set（纪律）。
    """
    path = behavior_file or BEHAVIOR_FILE
    try:
        topics: Set[str] = set()
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("### 📌"):
                    # 剥掉 "### 📌 " 前缀与末尾 "（日期）"
                    t = line[len("### 📌"):].strip()
                    if t.endswith("）"):
                        i = t.rfind("（")
                        if i > 0:
                            t = t[:i].strip()
                    if t:
                        topics.add(t)
        return topics
    except Exception as e:
        logger.warning(f"[feedback] discovered_topics failed: {e}")
        return set()


# ---------------------------------------------------------------------------
# 2. 发现引用率（CA2.0 §十 指标）
# ---------------------------------------------------------------------------

def retrieved_topics(db_path: Optional[str] = None) -> Set[str]:
    """从 retrieval_events 找出被检索过的 topic（发现引用信号）。

    判定：query_topic 出现在检索日志中 = R1D3 真的查过它。
    失败返回空 set。
    """
    try:
        conn = _get_conn(db_path)
        try:
            rows = conn.execute(
                "SELECT DISTINCT query_topic FROM retrieval_events"
            ).fetchall()
            return {r["query_topic"] for r in rows if r["query_topic"]}
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"[feedback] retrieved_topics failed: {e}")
        return set()


def discovery_reference_rate(db_path: Optional[str] = None) -> Dict[str, Any]:
    """发现引用率 = 被检索过的发现 / 发现总数（CA2.0 §十）。

    这是 C3 的核心度量：探出的成果有多少真正进入了系统行为。

    失败返回零值统计（纪律）。
    """
    try:
        discovered = discovered_topics()
        retrieved = retrieved_topics(db_path)
        referenced = discovered & retrieved
        total = len(discovered)
        return {
            "discovered_total": total,
            "referenced": len(referenced),
            "reference_rate": round(len(referenced) / total, 4) if total else 0.0,
            "referenced_topics": sorted(referenced),
        }
    except Exception as e:
        logger.warning(f"[feedback] discovery_reference_rate failed: {e}")
        return {
            "discovered_total": 0,
            "referenced": 0,
            "reference_rate": 0.0,
            "referenced_topics": [],
        }


# ---------------------------------------------------------------------------
# 3. 结案发现（曾为缺口 → 现命中）
# ---------------------------------------------------------------------------

def resolved_topics(db_path: Optional[str] = None) -> Set[str]:
    """返回「已从缺口变为命中」的 topic 集合。

    判定：该 query_topic 最近一次检索 coverage 已是 known/partial。
    证据形态（真实数据）：FlashAttention: unknown→unknown→known→known...
    这类 topic 的探索「奏效了」，其方向值得继续探。
    """
    try:
        conn = _get_conn(db_path)
        try:
            rows = conn.execute(
                "SELECT query_topic, coverage FROM retrieval_events re "
                "WHERE id = (SELECT MAX(id) FROM retrieval_events "
                "            WHERE query_topic = re.query_topic)"
            ).fetchall()
            return {
                r["query_topic"]
                for r in rows
                if (r["coverage"] or "").lower() in HIT_STATES
            }
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"[feedback] resolved_topics failed: {e}")
        return set()


# ---------------------------------------------------------------------------
# 4. 方向聚类（embedding）
# ---------------------------------------------------------------------------

def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _load_embeddings(topics: Set[str]) -> Dict[str, List[float]]:
    """从 Neo4j 批量拉取指定 topics 的 embedding。失败返回空 dict。"""
    try:
        from core.kg.repository_factory import get_kg_factory
        import asyncio

        f = get_kg_factory()

        async def _fetch():
            repo = await f._ensure_connected()
            # 分批查询，避免 IN 列表过大
            out: Dict[str, List[float]] = {}
            topic_list = list(topics)
            for i in range(0, len(topic_list), 200):
                batch = topic_list[i:i + 200]
                q = (
                    "MATCH (n:Knowledge) WHERE n.topic IN $ts "
                    "AND n.embedding IS NOT NULL "
                    "RETURN n.topic as topic, n.embedding as emb"
                )
                for row in await repo._client.execute_query(q, ts=batch):
                    if row.get("emb"):
                        out[row["topic"]] = row["emb"]
            return out

        return asyncio.run(_fetch())
    except Exception as e:
        logger.warning(f"[feedback] _load_embeddings failed: {e}")
        return {}


def direction_neighbors(
    resolved: Set[str],
    candidates: Set[str],
    threshold: float = None,
    emb_fn=None,
) -> Dict[str, List[str]]:
    """对每个已结案发现，找出「同方向」的候选 topic（embedding 相似 ≥ 阈值）。

    Args:
        resolved: 已结案的发现 topic（探索奏效的方向源头）。
        candidates: 候选 topic（通常 = 仍在缺口表的 topic）。
        threshold: 余弦相似度阈值；None → DIRECTION_THRESHOLD。
        emb_fn: 注入的 embedding 加载函数（测试用）；None → _load_embeddings。

    Returns:
        {resolved_topic: [同方向的候选 topic, ...]}

    失败返回空 dict（纪律）。
    """
    try:
        thr = DIRECTION_THRESHOLD if threshold is None else float(threshold)
        if not resolved or not candidates:
            return {}
        loader = emb_fn or _load_embeddings
        embs = loader(set(resolved) | set(candidates))
        if not embs:
            return {}

        out: Dict[str, List[str]] = {}
        for src in resolved:
            sv = embs.get(src)
            if not sv:
                continue
            neighbors = []
            for cand in candidates:
                if cand == src:
                    continue
                cv = embs.get(cand)
                if not cv:
                    continue
                if _cosine(sv, cv) >= thr:
                    neighbors.append(cand)
            if neighbors:
                out[src] = sorted(neighbors)
        return out
    except Exception as e:
        logger.warning(f"[feedback] direction_neighbors failed: {e}")
        return {}


# ---------------------------------------------------------------------------
# 5. 反馈查找表（供 rank_gaps 消费）
# ---------------------------------------------------------------------------

def feedback_lookup(
    db_path: Optional[str] = None,
    threshold: float = None,
    boost: float = None,
    emb_fn=None,
) -> Dict[str, Dict[str, Any]]:
    """构建 {topic: {boost, reason}} 反馈查找表。

    对「与已结案发现同方向、且仍在缺口表」的 topic 给相关性加成。

    Args:
        db_path: ops.db 路径（测试用）。
        threshold: 方向聚类阈值。
        boost: 提权倍率；None → DIRECTION_BOOST。
        emb_fn: 注入的 embedding 加载函数（测试用）。

    失败返回空 dict（纪律：反馈是注解，绝不破坏主流程）。
    """
    try:
        resolved = resolved_topics(db_path)
        if not resolved:
            return {}

        # 候选 = 仍在缺口表的 topic
        from core.api.gap_store import list_gaps
        gaps = list_gaps(only_unconsumed=False)
        candidates = {g["topic"] for g in gaps if g.get("topic")}
        if not candidates:
            return {}

        neighbors = direction_neighbors(resolved, candidates, threshold, emb_fn)
        b = DIRECTION_BOOST if boost is None else float(boost)

        out: Dict[str, Dict[str, Any]] = {}
        for src, cands in neighbors.items():
            for cand in cands:
                # 同一候选可能被多个源指到 → 取首个（避免叠加）
                if cand not in out:
                    out[cand] = {
                        "boost": b,
                        "reason": f"同方向于已结案发现「{src}」",
                        "source_discovery": src,
                    }
        return out
    except Exception as e:
        logger.warning(f"[feedback] feedback_lookup failed: {e}")
        return {}
