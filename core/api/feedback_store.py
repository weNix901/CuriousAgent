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

# 真实发现的门槛：KG 节点 quality ≥ 此值才算"有价值的发现"。
DISCOVERY_MIN_QUALITY = 7.0


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

def resolved_topics(
    db_path: Optional[str] = None,
    include_kg_known: bool = True,
) -> Set[str]:
    """返回「已结案发现」的 topic 集合（探索奏效的成果）。

    C3D-R (2026-10-08) 口径修正：
      原口径只取「曾出现在 retrieval_events 且最近 coverage=known/partial」
      → 语料被 R1D3 检索行为垄断，且大量是测试词（x/test_topic），
        真正的探索成果根本不在里面。

      新口径 = seed 集（检索命中的真实 topic）
             ∪ KG 真实发现集（quality≥DISCOVERY_MIN_QUALITY）
      这样「已结案发现」= 系统真探出来且有质量的东西，不再被检索历史垄断。

    证据形态（真实数据）：FlashAttention: unknown→unknown→known→known...
    """
    try:
        out: Set[str] = set()
        # ① 检索命中过的真实 topic（种子）
        conn = _get_conn(db_path)
        try:
            rows = conn.execute(
                "SELECT query_topic, coverage FROM retrieval_events re "
                "WHERE id = (SELECT MAX(id) FROM retrieval_events "
                "            WHERE query_topic = re.query_topic)"
            ).fetchall()
            out |= {
                r["query_topic"]
                for r in rows
                if (r["coverage"] or "").lower() in HIT_STATES
            }
        finally:
            conn.close()
        # ② KG 真实发现集（不被检索历史垄断）
        if include_kg_known:
            out |= _real_discoveries(db_path)
        return out
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

# ---------------------------------------------------------------------------
# 6. 短 TTL 缓存（C3D-R2 接入优化，2026-10-08）
# ---------------------------------------------------------------------------
#
# 问题：related_discoveries 每次调用都要 _load_embeddings(806 节点)→2.25s，
# 超过 hook/skill 的 2s 预算（实测端点 2.7s → 消费方超时拿到空）。
#
# 方案：进程内缓存「resolved 集合 + 其 embedding + 向量矩阵」，30s TTL。
# 首个请求预热（可能略超 2s），后续请求命中缓存 <10ms。
# 不引入新真源：缓存只是加速器，失效后重算（真源仍是 Neo4j）。
_CACHE_TTL_S = 30.0
_cache: Dict[str, Any] = {"ts": 0.0, "resolved": None, "embs": None, "vectors": None}


def _get_cached_corpus() -> Dict[str, Any]:
    """返回缓存的 {resolved, embs}；过期则重算。失败返回空缓存。"""
    import time as _t
    now = _t.time()
    if _cache.get("resolved") is not None and (now - _cache["ts"]) < _CACHE_TTL_S:
        return _cache
    try:
        resolved = resolved_topics()
        embs = _load_embeddings(resolved) if resolved else {}
        # 预归一化向量，避免每次查询重算 norm
        vectors = {}
        for t, v in embs.items():
            if not v:
                continue
            n = math.sqrt(sum(x * x for x in v))
            if n:
                vectors[t] = [x / n for x in v]
        _cache.update({"ts": now, "resolved": resolved, "embs": embs, "vectors": vectors})
    except Exception as e:
        logger.warning(f"[feedback] _get_cached_corpus failed: {e}")
    return _cache


def _cosine_norm(a_norm: List[float], b_norm: List[float]) -> float:
    """两个已归一化向量的余弦 = 点积。"""
    if not a_norm or not b_norm:
        return 0.0
    return sum(x * y for x, y in zip(a_norm, b_norm))


def related_discoveries(
    topic: str,
    db_path: Optional[str] = None,
    threshold: float = None,
    k: int = 5,
    emb_fn=None,
) -> List[Dict[str, Any]]:
    """C3D-R (2026-10-08): 给定 topic → 返回同方向的「已结案发现」。

    这是重定向后的 C3-D 唯一作用：**发现 → 消费提示**（扩大消费面），
    而非旧的「被检索 → 缺口提权」（收窄探索面，因果反了）。

    用法：R1D3 回答某 topic 时，可附上「我探过的相关内容」——
    让已探出的成果真正进入消费，而不是被动等用户撞到。

    Args:
        topic: 用户正在问 / 正在处理的 topic。
        db_path: ops.db 路径（测试用）。
        threshold: 方向聚类阈值；None → DIRECTION_THRESHOLD。
        k: 最多返回几条。
        emb_fn: 注入的 embedding 加载函数（测试用）。

    Returns:
        [{topic, similarity, direction_source?}]，按相似度降序。失败返回 []。
    """
    try:
        if not topic:
            return []
        thr = DIRECTION_THRESHOLD if threshold is None else float(threshold)

        # 测试注入路径：显式 emb_fn 时不做缓存（保证单测可注入）
        if emb_fn is not None:
            resolved = resolved_topics(db_path)
            neighbors = direction_neighbors({topic}, resolved, threshold, emb_fn)
            peers = [p for p in neighbors.get(topic, []) if p != topic]
            embs = emb_fn({topic} | set(peers))
            tv = embs.get(topic)
            out = [{"topic": p,
                    "similarity": round(_cosine(tv, embs.get(p)), 4)}
                   for p in peers]
            out.sort(key=lambda x: -x["similarity"])
            return out[: max(1, int(k))]

        # 生产路径：走缓存语料（30s TTL）
        corpus = _get_cached_corpus()
        vectors = corpus.get("vectors") or {}
        resolved = corpus.get("resolved") or set()
        if not vectors or not resolved or topic not in vectors:
            return []
        tv = vectors[topic]
        out = []
        for p in resolved:
            if p == topic:
                continue
            pv = vectors.get(p)
            if not pv:
                continue
            sim = _cosine_norm(tv, pv)
            if sim >= thr:
                out.append({"topic": p, "similarity": round(sim, 4)})
        out.sort(key=lambda x: -x["similarity"])
        return out[: max(1, int(k))]
    except Exception as e:
        logger.warning(f"[feedback] related_discoveries failed: {e}")
        return []


def _real_discoveries(db_path: Optional[str] = None) -> Set[str]:
    """C3D-R：真实发现集 —— KG 中 quality ≥ DISCOVERY_MIN_QUALITY 的节点 topic。

    取代旧口径（行为库 360 条）—— 后者混入爬虫网页标题/失败条目（噪声分母）。
    失败返回空 set。
    """
    try:
        from core.kg.repository_factory import get_kg_factory
        f = get_kg_factory()
        nodes = f.get_all_nodes_sync(limit=5000) or []
        return {
            n.get("topic")
            for n in nodes
            if n.get("topic")
            and float(n.get("quality", 0) or 0) >= DISCOVERY_MIN_QUALITY
        }
    except Exception as e:
        logger.warning(f"[feedback] _real_discoveries failed: {e}")
        return set()


def discovery_reference_rate_v2(db_path: Optional[str] = None) -> Dict[str, Any]:
    """发现引用率 v2（CA2.0 §十，C3D-R 修正口径）。

    分子 = 真实发现中被检索过的数（KG quality≥7 且出现在 retrieval_events）
    分母 = 真实发现总数（KG quality≥7）

    对比旧口径：分母曾是行为库 360 条（混入爬虫垃圾 → 引用率被稀释至 0.92%，
    不是"用户没用"，是"分母不是发现"）。
    """
    try:
        real = _real_discoveries(db_path)
        retrieved = retrieved_topics(db_path)
        referenced = real & retrieved
        total = len(real)
        return {
            "discovered_total": total,
            "referenced": len(referenced),
            "reference_rate": round(len(referenced) / total, 4) if total else 0.0,
            "referenced_topics": sorted(referenced)[:50],
            "denominator": "kg_quality_ge_7",
        }
    except Exception as e:
        logger.warning(f"[feedback] discovery_reference_rate_v2 failed: {e}")
        return {
            "discovered_total": 0,
            "referenced": 0,
            "reference_rate": 0.0,
            "referenced_topics": [],
            "denominator": "kg_quality_ge_7",
        }
