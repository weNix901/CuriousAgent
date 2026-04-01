"""
知识图谱 - 管理 Agent 的已知/未知知识状态
"""
import json
import os
from datetime import datetime, timezone
from typing import Optional

STATE_FILE = os.path.join(os.path.dirname(__file__), "../knowledge/state.json")

# === v0.2.5 根技术追溯常量 ===
ROOT_SCORE_WEIGHT_DOMAIN = 0.4
ROOT_SCORE_WEIGHT_EXPLAINS = 0.6
CROSS_DOMAIN_THRESHOLD = 3  # cross_domain_count >= 3 时升为根候选
ROOT_POOL_KEY = "root_technology_pool"

DEFAULT_STATE = {
    "version": "1.0",
    "last_update": None,
    "knowledge": {"topics": {}},
    "curiosity_queue": [],
    "exploration_log": [],
    "config": {
        "curiosity_top_k": 3,        # 每次探索 Top K 个好奇心
        "max_knowledge_nodes": 100,  # 知识图谱最大节点数
        "notification_threshold": 7.0  # 超过此分数才通知用户
    }
}


def _load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return DEFAULT_STATE.copy()
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return DEFAULT_STATE.copy()


def _save_state(state: dict) -> None:
    state["last_update"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_state() -> dict:
    return _load_state()


def add_knowledge(topic: str, depth: int = 5, summary: str = "", sources: list = None, quality: float = None) -> None:
    """标记某个 topic 为已知，并更新/创建知识节点"""
    state = _load_state()
    topics = state["knowledge"]["topics"]
    now = datetime.now(timezone.utc).isoformat()
    
    if topic in topics:
        topics[topic]["known"] = True
        topics[topic]["depth"] = max(topics[topic].get("depth", 0), depth)
        topics[topic]["last_updated"] = now
        if summary:
            topics[topic]["summary"] = summary
        if sources:
            topics[topic]["sources"] = list(set(topics[topic].get("sources", []) + sources))
        topics[topic]["status"] = "complete"
        if quality is not None:
            topics[topic]["quality"] = quality
        elif "quality" not in topics[topic]:
            topics[topic]["quality"] = 0
        # Ensure new fields exist for existing topics
        if "children" not in topics[topic]:
            topics[topic]["children"] = []
        if "parents" not in topics[topic]:
            topics[topic]["parents"] = []
        if "explains" not in topics[topic]:
            topics[topic]["explains"] = []
        if "cites" not in topics[topic]:
            topics[topic]["cites"] = []
        if "cited_by" not in topics[topic]:
            topics[topic]["cited_by"] = []
    else:
        topics[topic] = {
            "known": True,
            "depth": depth,
            "last_updated": now,
            "summary": summary,
            "sources": sources or [],
            "status": "complete",
            "quality": quality if quality is not None else 0,
            "children": [],
            "parents": [],
            "explains": [],
            "cites": [],
            "cited_by": []
        }
    
    # 限制节点数：保留深度最高的
    if len(topics) > DEFAULT_STATE["config"]["max_knowledge_nodes"]:
        sorted_topics = sorted(topics.items(), key=lambda x: x[1].get("depth", 0), reverse=True)
        topics.clear()
        for k, v in sorted_topics[:DEFAULT_STATE["config"]["max_knowledge_nodes"]]:
            topics[k] = v
    
    _save_state(state)


def add_curiosity(topic: str, reason: str, relevance: float = 5.0, depth: float = 5.0, **extra) -> None:
    """添加一个新的好奇心项到队列
    
    支持 extra 参数（如 original_topic）用于追踪父子关系
    """
    state = _load_state()
    now = datetime.now(timezone.utc).isoformat()
    
    # 去重：如果队列里已存在该 topic（无论什么 status），都跳过
    for item in state["curiosity_queue"]:
        if item["topic"].lower() == topic.lower():
            return
    
    score = min(10.0, relevance * 0.35 + depth * 0.25 + 5.0 * 0.4)
    queue_item = {
        "topic": topic,
        "reason": reason,
        "score": score,
        "relevance": relevance,
        "depth": depth,
        "created_at": now,
        "status": "pending"
    }
    # v0.2.5: 存储额外字段（如 original_topic）
    queue_item.update(extra)

    # v0.2.8: priority 字段 — 按来源设优先级，claim 时高优先级先出
    # 避免低优先级的 decomposition 饿死高优先级的 web_citation
    reason = queue_item.get("reason", "")
    if "Web citation" in reason:
        queue_item["priority"] = 10
    elif "Cited by" in reason:
        queue_item["priority"] = 9
    elif "Dream" in reason:
        queue_item["priority"] = 8
    elif "Decomposed from" in reason:
        queue_item["priority"] = 5  # decomposition 优先级低
    else:
        queue_item["priority"] = 5

    state["curiosity_queue"].append(queue_item)
    _save_state(state)


def update_curiosity_status(topic: str, status: str) -> None:
    """更新好奇心项状态: pending → investigating → done"""
    state = _load_state()
    for item in state["curiosity_queue"]:
        if item["topic"] == topic:
            item["status"] = status
    _save_state(state)


def get_top_curiosities(k: int = None) -> list:
    """获取评分最高的好奇心项"""
    state = _load_state()
    k = k or state["config"]["curiosity_top_k"]
    pending = [item for item in state["curiosity_queue"] if item["status"] == "pending"]
    return sorted(pending, key=lambda x: x["score"], reverse=True)[:k]


def _safe_truncate(text: str, max_chars: int) -> str:
    """安全截断——确保不切割多字节字符"""
    if not text or len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    # 找最后一个安全断点
    for i in range(len(truncated) - 1, max_chars - 20, -1):
        c = truncated[i]
        if c.isascii() and (c.isalnum() or c in "_-.()[]"):
            return truncated[:i + 1]
    return truncated

def log_exploration(topic: str, action: str, findings: str, notified: bool = False) -> None:
    """记录一次探索活动"""
    state = _load_state()
    state["exploration_log"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "topic": topic,
        "action": action,
        "findings": _safe_truncate(findings, 500),
        "notified_user": notified
    })
    # 保留最近100条
    state["exploration_log"] = state["exploration_log"][-100:]
    _save_state(state)


def get_recent_knowledge(hours: int = 24) -> list:
    """获取最近更新的知识节点"""
    state = _load_state()
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_str = cutoff.isoformat()
    return [
        {"topic": k, **v} for k, v in state["knowledge"]["topics"].items()
        if v.get("last_updated", "") > cutoff_str
    ]


def get_knowledge_summary() -> dict:
    """获取知识图谱概览"""
    state = _load_state()
    topics = state["knowledge"]["topics"]
    return {
        "total_topics": len(topics),
        "known_count": sum(1 for v in topics.values() if v.get("known")),
        "pending_curiosities": sum(1 for i in state["curiosity_queue"] if i["status"] == "pending"),
        "recent_explorations": len(state["exploration_log"])
    }


def remove_curiosity(topic: str, force: bool = False) -> bool:
    """
    删除好奇心队列条目

    Args:
        topic: 话题名称
        force: 是否强制删除（忽略状态）

    Returns:
        bool: 是否成功删除
    """
    state = _load_state()
    queue = state.get("curiosity_queue", [])

    for i, item in enumerate(queue):
        if item.get("topic") == topic:
            # 检查状态
            if not force and item.get("status") in ["exploring", "done"]:
                return False

            # 删除
            queue.pop(i)
            state["curiosity_queue"] = queue
            _save_state(state)
            return True

    return False


def list_pending() -> list:
    """列出所有待探索条目"""
    state = _load_state()
    return [item for item in state.get("curiosity_queue", []) if item.get("status") == "pending"]


def claim_pending_item() -> Optional[dict]:
    """
    原子地 claim 一个 pending 项。
    只有 status=pending 的项才能被 claim。
    已 claiming 的项（status=exploring）会被跳过。

    注意：本函数不修改 DreamInbox，只修改 curiosity_queue 的 status。

    Returns:
        被 claim 的 item dict（status 已改为 exploring），或 None（队列为空）
    """
    state = _load_state()
    queue = state.get("curiosity_queue", [])
    # v0.2.8: 优先 claim priority 最高的 pending 项
    pending_items = [(i, item) for i, item in enumerate(queue) if item.get("status") == "pending"]
    if not pending_items:
        _save_state(state)
        return None
    # priority 最高的排前面；priority 相等时按入队时间（越早优先）
    pending_items.sort(key=lambda x: (x[1].get("priority", 5), x[1].get("created_at", "")), reverse=True)
    idx, item = pending_items[0]
    item["status"] = "exploring"
    _save_state(state)
    return item.copy()


# === Meta-cognitive tracking functions ===

def _ensure_meta_cognitive(state: dict) -> dict:
    """Ensure state.json contains meta_cognitive field with correct types"""
    if "meta_cognitive" not in state:
        state["meta_cognitive"] = {
            "explore_counts": {},
            "marginal_returns": {},
            "last_quality": {},
            "exploration_log": [],
            "completed_topics": {}
        }

    # === v0.2.5 新增: 确保 root_technology_pool 存在 ===
    if ROOT_POOL_KEY not in state:
        state[ROOT_POOL_KEY] = {"candidates": [], "last_updated": None}
    # === v0.2.5 新增结束 ===

    mc = state["meta_cognitive"]

    mc = state["meta_cognitive"]

    # Bug #29 fix: Migrate completed_topics from list to dict format
    if "completed_topics" in mc and isinstance(mc["completed_topics"], list):
        old_list = mc["completed_topics"]
        mc["completed_topics"] = {}
        for topic in old_list:
            if topic:
                mc["completed_topics"][topic] = {
                    "reason": "migrated from list format",
                    "timestamp": None
                }

    # Ensure all required keys exist
    for key, default in [
        ("explore_counts", {}),
        ("marginal_returns", {}),
        ("last_quality", {}),
        ("exploration_log", []),
        ("completed_topics", {})
    ]:
        if key not in mc:
            mc[key] = default

    return state


def remove_ghost_nodes() -> list:
    state = _load_state()
    queue_topics = {
        item["topic"]: item["status"]
        for item in state.get("curiosity_queue", [])
    }

    topics = state["knowledge"]["topics"]
    removed = []

    for topic in list(topics.keys()):
        node = topics[topic]
        queue_status = queue_topics.get(topic)

        if (node.get("known") is False
                and node.get("status") == "partial"
                and queue_status == "done"):
            del topics[topic]
            removed.append(topic)

    if removed:
        _save_state(state)

    return removed


def mark_topic_done(topic: str, reason: str) -> None:
    """Mark topic as completed, preventing further exploration"""
    state = _load_state()
    state = _ensure_meta_cognitive(state)

    mc = state["meta_cognitive"]
    if "completed_topics" not in mc:
        mc["completed_topics"] = {}

    mc["completed_topics"][topic] = {
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    for item in state.get("curiosity_queue", []):
        if item["topic"] == topic and item.get("status") != "done":
            item["status"] = "done"

    _save_state(state)

    state = _load_state()

    parent_topic = None
    for item in state.get("curiosity_queue", []):
        if item.get("topic") == topic:
            parent_topic = item.get("original_topic")
            break

    if parent_topic:
        _update_parent_relation(parent_topic, topic)

    topics = state["knowledge"]["topics"]
    if topic in topics:
        node = topics[topic]
        queue_status = next(
            (item["status"] for item in state.get("curiosity_queue", [])
             if item["topic"] == topic), None
        )
        if (node.get("known") is False
                and node.get("status") == "partial"
                and queue_status == "done"):
            del topics[topic]

    _save_state(state)


# === v0.2.5 新增: 内部函数 - 双向写入父子关系 ===
def _update_parent_relation(parent: str, child: str, relation: str = "derived_from", confidence: float = 0.8):
    """内部函数：双向写入父子关系"""
    state = _load_state()
    topics = state["knowledge"]["topics"]
    now = datetime.now(timezone.utc).isoformat()

    # Bug #8 fix: 确保 child 存在且有完整结构
    if child not in topics:
        topics[child] = {
            "known": False,
            "depth": 0,
            "parents": [],
            "explains": [],
            "children": [],
            "explored_children": [],
            "cross_domain_count": 0,
            "is_root_candidate": False,
            "root_score": 0.0,
            "first_observed": now,
            "last_updated": now,
            "status": "partial"
        }
    else:
        # 补全缺失的字段
        if "parents" not in topics[child]:
            topics[child]["parents"] = []
        if "explains" not in topics[child]:
            topics[child]["explains"] = []
        if "children" not in topics[child]:
            topics[child]["children"] = []

    # 确保 parent 存在且有完整结构
    if parent not in topics:
        topics[parent] = {
            "known": False,
            "depth": 0,
            "parents": [],
            "explains": [],
            "children": [],
            "explored_children": [],
            "cross_domain_count": 0,
            "is_root_candidate": False,
            "root_score": 0.0,
            "first_observed": now,
            "last_updated": now,
            "status": "partial"
        }
    else:
        # 补全缺失的字段
        if "explains" not in topics[parent]:
            topics[parent]["explains"] = []
        if "children" not in topics[parent]:
            topics[parent]["children"] = []

    # 写入父子关系
    if parent not in topics[child]["parents"]:
        topics[child]["parents"].append(parent)

    explains_entry = {"target": child, "relation": relation, "confidence": confidence}
    if explains_entry not in topics[parent]["explains"]:
        topics[parent]["explains"].append(explains_entry)

    # 确保溯源元数据字段存在
    for t in [parent, child]:
        if t in topics:
            if "cross_domain_count" not in topics[t]:
                topics[t]["cross_domain_count"] = 0
            if "is_root_candidate" not in topics[t]:
                topics[t]["is_root_candidate"] = False
            if "root_score" not in topics[t]:
                topics[t]["root_score"] = 0.0
            if "first_observed" not in topics[t]:
                topics[t]["first_observed"] = now
            if "last_updated" not in topics[t]:
                topics[t]["last_updated"] = now

    _save_state(state)
# === v0.2.5 新增结束 ===


def update_last_exploration_notified(topic: str, notified: bool) -> None:
    """Update last exploration notified flag"""
    state = _load_state()
    state = _ensure_meta_cognitive(state)

    mc = state["meta_cognitive"]
    if "last_notified" not in mc:
        mc["last_notified"] = {}

    mc["last_notified"][topic] = {
        "notified": notified,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    _save_state(state)


def get_topic_keywords(topic: str) -> list:
    """Get existing keywords for topic"""
    state = _load_state()
    topics = state.get("knowledge", {}).get("topics", {})
    if topic in topics:
        return topics[topic].get("keywords", [])
    return []


def get_topic_depth(topic: str) -> float:
    """Get current depth for topic"""
    state = _load_state()
    topics = state.get("knowledge", {}).get("topics", {})
    if topic in topics:
        return topics[topic].get("depth", 0)
    return 0.0


def is_topic_completed(topic: str) -> bool:
    """Check if topic is completed (marked as no longer explore)"""
    state = _load_state()
    state = _ensure_meta_cognitive(state)
    mc = state.get("meta_cognitive", {})
    completed = mc.get("completed_topics", {})
    return topic in completed


def update_meta_exploration(topic: str, quality: float, marginal_return: float, notified: bool) -> None:
    """Update exploration meta-cognitive data"""
    state = _load_state()
    state = _ensure_meta_cognitive(state)

    mc = state["meta_cognitive"]

    if "explore_counts" not in mc:
        mc["explore_counts"] = {}
    mc["explore_counts"][topic] = mc["explore_counts"].get(topic, 0) + 1

    if "marginal_returns" not in mc:
        mc["marginal_returns"] = {}
    if topic not in mc["marginal_returns"]:
        mc["marginal_returns"][topic] = []
    mc["marginal_returns"][topic].append(marginal_return)

    if "last_quality" not in mc:
        mc["last_quality"] = {}
    mc["last_quality"][topic] = quality

    if "exploration_log" not in mc:
        mc["exploration_log"] = []
    mc["exploration_log"].append({
        "topic": topic,
        "quality": quality,
        "marginal_return": marginal_return,
        "notified": notified,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    _save_state(state)


def get_meta_cognitive_state() -> dict:
    """Get complete meta-cognitive state"""
    state = _load_state()
    state = _ensure_meta_cognitive(state)
    return state.get("meta_cognitive", {})


def get_topic_explore_count(topic: str) -> int:
    """Get exploration count for topic"""
    state = _load_state()
    state = _ensure_meta_cognitive(state)
    mc = state.get("meta_cognitive", {})
    return mc.get("explore_counts", {}).get(topic, 0)


def get_topic_marginal_returns(topic: str) -> list:
    """Get marginal return history for topic"""
    state = _load_state()
    state = _ensure_meta_cognitive(state)
    mc = state.get("meta_cognitive", {})
    return mc.get("marginal_returns", {}).get(topic, [])


def add_child(parent: str, child: str) -> None:
    """Add parent-child relationship between topics"""
    state = _load_state()
    topics = state["knowledge"]["topics"]
    now = datetime.now(timezone.utc).isoformat()
    
    if parent not in topics:
        topics[parent] = {
            "known": False,
            "depth": 0,
            "children": [],
            "explored_children": [],
            "created_at": now,
            "status": "partial",
            "cites": [],
            "cited_by": []
        }
    
    if not topics[parent].get("children"):
        topics[parent]["children"] = []
    
    if child not in topics[parent]["children"]:
        topics[parent]["children"].append(child)
    
    topics[parent]["status"] = "partial"
    
    _save_state(state)
    
    _update_parent_relation(parent, child)


def add_citation(citing_topic: str, cited_topic: str) -> None:
    """
    添加论文引用关系。

    citing_topic cites cited_topic（citing_topic 引用了 cited_topic）。
    双向写入 cites 和 cited_by 字段。

    引用关系和分解关系（children/parents）是独立的：
    - children: 分解的子领域（sub-domain/sub-concept）
    - cites:    论文引用关系（paper citation）
    """
    state = _load_state()
    topics = state["knowledge"]["topics"]
    now = datetime.now(timezone.utc).isoformat()

    # 确保 citing_topic 存在
    if citing_topic not in topics:
        topics[citing_topic] = {
            "known": False,
            "depth": 0,
            "children": [],
            "parents": [],
            "explains": [],
            "cites": [],
            "cited_by": [],
            "explored_children": [],
            "cross_domain_count": 0,
            "is_root_candidate": False,
            "root_score": 0.0,
            "first_observed": now,
            "last_updated": now,
            "status": "partial"
        }

    # 确保 cited_topic 存在
    if cited_topic not in topics:
        topics[cited_topic] = {
            "known": False,
            "depth": 0,
            "children": [],
            "parents": [],
            "explains": [],
            "cites": [],
            "cited_by": [],
            "explored_children": [],
            "cross_domain_count": 0,
            "is_root_candidate": False,
            "root_score": 0.0,
            "first_observed": now,
            "last_updated": now,
            "status": "partial"
        }

    # 写入 cites（正向：citing 指向 cited）
    cites_list = topics[citing_topic].get("cites") or []
    if cited_topic not in cites_list:
        cites_list.append(cited_topic)
        topics[citing_topic]["cites"] = cites_list

    # 写入 cited_by（反向：cited 被 citing 引用）
    cited_by_list = topics[cited_topic].get("cited_by") or []
    if citing_topic not in cited_by_list:
        cited_by_list.append(citing_topic)
        topics[cited_topic]["cited_by"] = cited_by_list

    topics[citing_topic]["last_updated"] = now
    topics[cited_topic]["last_updated"] = now

    _save_state(state)


def get_children(topic: str) -> list:
    """Get child topics for a given topic"""
    state = _load_state()
    topic_data = state.get("knowledge", {}).get("topics", {}).get(topic, {})
    return topic_data.get("children", [])


def mark_child_explored(parent: str, child: str) -> None:
    """Mark a child topic as explored"""
    state = _load_state()
    topics = state["knowledge"]["topics"]
    
    if parent not in topics:
        return
    
    if "explored_children" not in topics[parent]:
        topics[parent]["explored_children"] = []
    
    if child not in topics[parent]["explored_children"]:
        topics[parent]["explored_children"].append(child)
    
    children = topics[parent].get("children", [])
    explored = topics[parent].get("explored_children", [])
    if children and len(explored) >= len(children):
        topics[parent]["status"] = "complete"
    
    _save_state(state)


def get_exploration_status(topic: str) -> str:
    """Get exploration status: unexplored | partial | complete"""
    state = _load_state()
    topic_data = state.get("knowledge", {}).get("topics", {}).get(topic, {})
    
    return topic_data.get("status", "unexplored")


# ===== T-6/T-9/T-10 补充函数 =====

def update_topic_quality(topic: str, quality: float) -> None:
    """Update quality score for a topic (T-2/T-10)"""
    state = _load_state()
    topics = state.get("knowledge", {}).setdefault("topics", {})
    if topic not in topics:
        topics[topic] = {}
    topics[topic]["quality"] = quality
    _save_state(state)


def update_curiosity_score(topic: str, score: float) -> None:
    """Update curiosity score for a topic (T-9 priority boost)"""
    state = _load_state()
    curiosity_queue = state.get("curiosity_queue", [])
    for item in curiosity_queue:
        if item.get("topic") == topic:
            item["score"] = score
            break
    _save_state(state)


def add_exploration_result(topic: str, result: dict, quality: float) -> None:
    """Record exploration result with quality score (T-10)"""
    state = _load_state()
    topics = state.get("knowledge", {}).setdefault("topics", {})

    # Build findings dict (Explorer returns findings as string, also accept dict)
    findings_data = result.get("findings", {})
    findings_str = findings_data.get("summary", "") if isinstance(findings_data, dict) else (findings_data or "")
    findings_for_writer = {
        "summary": findings_str,
        "sources": result.get("sources", []),
        "papers": result.get("papers", [])
    }

    if topic not in topics:
        topics[topic] = {}
    topics[topic].update({
        "quality": quality,
        "summary": findings_str,
        "sources": result.get("sources", []),
        "findings": findings_data,
        "status": "explored"
    })

    # Fix Bug #2: Also write to meta_cognitive.last_quality (what the API reads)
    state = _ensure_meta_cognitive(state)
    mc = state["meta_cognitive"]
    if "last_quality" not in mc:
        mc["last_quality"] = {}
    mc["last_quality"][topic] = quality

    _save_state(state)

    # Fix Bug #1: Also write to shared_knowledge/curious/ via AgentBehaviorWriter
    try:
        from core.agent_behavior_writer import AgentBehaviorWriter
        writer = AgentBehaviorWriter()
        writer.process(topic, findings_for_writer, quality, result.get("sources", []))
    except Exception as e:
        print(f"[KG] AgentBehaviorWriter failed: {e}")

    # v0.2.7 Phase 4: parent link 已在 api_inject() 入口处通过 add_child() 写入 KG，
    # 不需要再从队列推断。此段逻辑删除以避免 Bug 3+4（queue_item.get("topic")
    # 拿到的是当前探索完成的 topic，不是 parent，逻辑颠倒）。
    pass

# v0.2.5 Root Tracing Functions

def get_spreading_activation_trace(
    topic: str,
    max_depth: int = 10,
    decay: float = 0.5,
    threshold: float = 0.1
) -> dict:
    """
    使用扩散激活算法（Collins & Loftus, 1975）从任意 topic 追溯根技术。

    机制：
    - 从起点 topic 开始，激活值 = 1.0
    - 激活沿所有边（parents + explains）并行扩散
    - 每跳衰减系数 = decay（默认 0.5）
    - 多条路径汇聚时，激活值累加（跨子图连接自然体现）
    - 激活值低于 threshold 时停止扩散
    - 按激活值降序排列，paths >= 2 的节点为候选根技术
    """
    state = _load_state()
    topics = state["knowledge"]["topics"]
    root_pool = state.get(ROOT_POOL_KEY, {}).get("candidates", [])
    root_names = {r["name"] for r in root_pool}

    activation_map = {}
    activation_map[topic] = {"activation": 1.0, "distance": 0, "paths": 1}

    queue = [(topic, 1.0, 0)]
    visited = {topic}

    while queue:
        current, current_activation, current_distance = queue.pop(0)

        if current_distance >= max_depth or current_activation < threshold:
            continue

        node = topics.get(current, {})
        next_activation = current_activation * decay

        # 从 parents（谁派生了我）和 explains（我解释了谁）两个方向扩散
        connected = []
        for parent in node.get("parents", []):
            connected.append(parent)
        for explain in node.get("explains", []):
            target = explain.get("target", "") if isinstance(explain, dict) else explain
            if target:
                connected.append(target)

        for next_topic in connected:
            if not next_topic or next_topic in visited:
                continue

            if next_topic not in activation_map:
                activation_map[next_topic] = {"activation": 0.0, "distance": current_distance + 1, "paths": 0}

            activation_map[next_topic]["activation"] += next_activation
            activation_map[next_topic]["distance"] = min(
                activation_map[next_topic]["distance"], current_distance + 1
            )
            activation_map[next_topic]["paths"] += 1

            if next_topic not in visited:
                visited.add(next_topic)
                queue.append((next_topic, next_activation, current_distance + 1))

    # 构建有序 trace（按激活值降序）
    ordered_trace = []
    for t, info in activation_map.items():
        # 根技术判断：来自 root_pool 或 多路径汇聚（paths >= 2）
        is_root = t in root_names or info["paths"] >= 2
        ordered_trace.append({
            "topic": t,
            "activation": round(info["activation"], 4),
            "distance": info["distance"],
            "paths": info["paths"],
            "is_root": is_root
        })

    ordered_trace.sort(key=lambda x: (-x["activation"], x["distance"]))

    root_technologies = [
        {"topic": t["topic"], "activation": t["activation"], "paths_converged": t["paths"]}
        for t in ordered_trace if t["is_root"]
    ]

    cross_subgraph_connections = []
    origin_node = topics.get(topic, {})
    for explain in origin_node.get("explains", []):
        if isinstance(explain, dict):
            target = explain.get("target", "")
            cross_subgraph_connections.append({
                "from": topic,
                "to": target,
                "shared_concept": explain.get("relation", "shared concept"),
                "activation": activation_map.get(target, {}).get("activation", 0)
            })

    return {
        "origin": topic,
        "activation_map": activation_map,
        "ordered_trace": ordered_trace,
        "root_technologies": root_technologies,
        "cross_subgraph_connections": cross_subgraph_connections
    }


def get_root_technologies() -> list:
    """返回所有根技术，按 root_score 降序"""
    state = _load_state()
    candidates = state.get(ROOT_POOL_KEY, {}).get("candidates", [])
    return sorted(candidates, key=lambda x: x.get("root_score", 0), reverse=True)


def init_root_pool(seeds: list) -> None:
    """
    从初始种子列表初始化根技术池。
    seeds: e.g. ["transformer attention", "gradient descent", "backpropagation"]
    """
    state = _load_state()
    pool = state.setdefault(ROOT_POOL_KEY, {"candidates": [], "last_updated": None})
    existing_names = {r["name"] for r in pool["candidates"]}

    for seed in seeds:
        if seed not in existing_names:
            pool["candidates"].append({
                "name": seed,
                "root_score": 8.0,  # 初始种子给 8.0
                "cross_domain_count": 1,
                "explains_count": 0,
                "domains": ["seed"],
                "confidence": 0.5,
                "sources": ["manual_seed"]
            })

    pool["last_updated"] = datetime.now(timezone.utc).isoformat()
    _save_state(state)


def get_kg_overview() -> dict:
    """返回 KG 全局视图数据"""
    state = _load_state()
    topics = state["knowledge"]["topics"]
    pool = state.get(ROOT_POOL_KEY, {}).get("candidates", [])
    root_names = {r["name"] for r in pool}

    nodes = []
    edges = []

    for name, node in topics.items():
        is_root = name in root_names or node.get("is_root_candidate", False)
        nodes.append({
            "id": name,
            "quality": node.get("quality", 0),
            "root_score": next((r["root_score"] for r in pool if r["name"] == name), 0),
            "is_root": is_root,
            "status": node.get("status", "unexplored"),
            "children_count": len(node.get("children", [])),
            "parents_count": len(node.get("parents", [])),
            "explains_count": len(node.get("explains", [])),
            "cites_count": len(node.get("cites", [])),
            "cited_by_count": len(node.get("cited_by", [])),
            "cross_domain_count": node.get("cross_domain_count", 0)
        })

        for child in node.get("children", []):
            edges.append({"from": name, "to": child, "type": "child_of"})
        for explain in node.get("explains", []):
            edges.append({"from": name, "to": explain["target"], "type": "explains"})
        for cited in node.get("cites", []):
            edges.append({"from": name, "to": cited, "type": "cites"})

    return {"nodes": nodes, "edges": edges, "total": len(nodes)}


def promote_to_root_candidate(topic: str, domains: list) -> None:
    """
    将 topic 升为根技术候选。
    由 Cross-Subgraph Detector 或手动调用。
    """
    state = _load_state()
    pool = state.setdefault(ROOT_POOL_KEY, {"candidates": [], "last_updated": None})
    topics = state["knowledge"]["topics"]

    # 计算 explains_count
    explains_count = len(topics.get(topic, {}).get("explains", []))
    cross_domain_count = len(domains)

    root_score = (
        cross_domain_count * ROOT_SCORE_WEIGHT_DOMAIN +
        explains_count * ROOT_SCORE_WEIGHT_EXPLAINS
    )

    # 写入或更新 pool
    for r in pool["candidates"]:
        if r["name"] == topic:
            r["root_score"] = root_score
            r["cross_domain_count"] = cross_domain_count
            r["explains_count"] = explains_count
            r["domains"] = domains
            r["confidence"] = min(0.95, 0.5 + explains_count * 0.05)
            break
    else:
        pool["candidates"].append({
            "name": topic,
            "root_score": root_score,
            "cross_domain_count": cross_domain_count,
            "explains_count": explains_count,
            "domains": domains,
            "confidence": min(0.95, 0.5 + explains_count * 0.05),
            "sources": ["cross_subgraph_detection"]
        })

    # 标记 topic 为候选
    if topic in topics:
        topics[topic]["is_root_candidate"] = True
        topics[topic]["root_score"] = root_score
        topics[topic]["cross_domain_count"] = cross_domain_count

    pool["last_updated"] = datetime.now(timezone.utc).isoformat()
    _save_state(state)


# === v0.2.6 Dream Insights Functions ===

def add_dream_insight(
    content: str,
    insight_type: str,
    source_topics: list[str],
    surprise: float,
    novelty: float,
    trigger_topic: str | None
) -> str:
    """Create a dream insight node."""
    from core.node_lock_registry import NodeLockRegistry

    node_id = f"insight_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"

    entry = {
        "node_id": node_id,
        "content": content,
        "insight_type": insight_type,
        "source_topics": source_topics,
        "surprise": surprise,
        "novelty": novelty,
        "trigger_topic": trigger_topic,
        "weight": 0.5,
        "verified": False,
        "quality": 0.0,
        "stale": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    with NodeLockRegistry.global_write_lock():
        insight_dir = os.path.join(os.path.dirname(STATE_FILE), "dream_insights")
        os.makedirs(insight_dir, exist_ok=True)

        filepath = os.path.join(insight_dir, f"{node_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)

    return node_id


def get_dream_insights(topic: str | None = None) -> list[dict]:
    """Get all dream insights or insights related to a specific topic."""
    from core.node_lock_registry import NodeLockRegistry

    insights = []

    with NodeLockRegistry.global_write_lock():
        insight_dir = os.path.join(os.path.dirname(STATE_FILE), "dream_insights")

        if not os.path.exists(insight_dir):
            return insights

        for filename in os.listdir(insight_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(insight_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    if topic is None:
                        insights.append(data)
                    elif topic in data.get("source_topics", []):
                        insights.append(data)
                except (json.JSONDecodeError, IOError):
                    continue

    return insights


def get_all_dream_insights() -> list[dict]:
    """Get all dream insights (wrapper around get_dream_insights)."""
    return get_dream_insights(topic=None)


def remove_dream_insight(node_id: str) -> None:
    """Remove a dream insight file."""
    from core.node_lock_registry import NodeLockRegistry

    with NodeLockRegistry.global_write_lock():
        insight_dir = os.path.join(os.path.dirname(STATE_FILE), "dream_insights")
        filepath = os.path.join(insight_dir, f"{node_id}.json")

        if os.path.exists(filepath):
            os.remove(filepath)


def is_insight_stale(node_id: str) -> bool:
    """Check if insight is stale (> 7 days old and never verified)."""
    from core.node_lock_registry import NodeLockRegistry

    with NodeLockRegistry.global_write_lock():
        insight_dir = os.path.join(os.path.dirname(STATE_FILE), "dream_insights")
        filepath = os.path.join(insight_dir, f"{node_id}.json")

        if not os.path.exists(filepath):
            return False

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return False

        if data.get("verified", False):
            return False

        created_at_str = data.get("created_at")
        if not created_at_str:
            return False

        try:
            created_at = datetime.fromisoformat(created_at_str)
            age = datetime.now(timezone.utc) - created_at
            return age.days > 7
        except (ValueError, TypeError):
            return False


def update_insight_weight(node_id: str, delta: float) -> None:
    """Update insight weight by delta."""
    from core.node_lock_registry import NodeLockRegistry

    with NodeLockRegistry.global_write_lock():
        insight_dir = os.path.join(os.path.dirname(STATE_FILE), "dream_insights")
        filepath = os.path.join(insight_dir, f"{node_id}.json")

        if not os.path.exists(filepath):
            return

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            data["weight"] = data.get("weight", 0.5) + delta

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except (json.JSONDecodeError, IOError):
            return


def update_insight_quality(node_id: str, delta: float) -> None:
    """Update insight quality by delta."""
    from core.node_lock_registry import NodeLockRegistry

    with NodeLockRegistry.global_write_lock():
        insight_dir = os.path.join(os.path.dirname(STATE_FILE), "dream_insights")
        filepath = os.path.join(insight_dir, f"{node_id}.json")

        if not os.path.exists(filepath):
            return

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            data["quality"] = data.get("quality", 0.0) + delta

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except (json.JSONDecodeError, IOError):
            return


# === v0.2.6 Node Lifecycle Functions ===

def mark_dormant(topic: str) -> None:
    """Mark topic as dormant (status = 'dormant')."""
    from core.node_lock_registry import NodeLockRegistry
    with NodeLockRegistry.global_write_lock():
        lock = NodeLockRegistry.get_lock(topic)
        with lock:
            state = _load_state()
            if topic in state["knowledge"]["topics"]:
                state["knowledge"]["topics"][topic]["status"] = "dormant"
                _save_state(state)


def reactivate(topic: str) -> None:
    """Reactivate a dormant topic (status = 'complete')."""
    from core.node_lock_registry import NodeLockRegistry
    with NodeLockRegistry.global_write_lock():
        lock = NodeLockRegistry.get_lock(topic)
        with lock:
            state = _load_state()
            if topic in state["knowledge"]["topics"]:
                state["knowledge"]["topics"][topic]["status"] = "complete"
                _save_state(state)


def mark_dreamed(topic: str) -> None:
    """Mark topic as having been processed by DreamAgent (sets dreamed_at timestamp)."""
    from core.node_lock_registry import NodeLockRegistry
    with NodeLockRegistry.global_write_lock():
        lock = NodeLockRegistry.get_lock(topic)
        with lock:
            state = _load_state()
            if topic in state["knowledge"]["topics"]:
                state["knowledge"]["topics"][topic]["dreamed_at"] = datetime.now(timezone.utc).isoformat()
                _save_state(state)


def set_consolidated(topic: str) -> None:
    """Mark topic as consolidated (sets last_consolidated timestamp)."""
    from core.node_lock_registry import NodeLockRegistry
    with NodeLockRegistry.global_write_lock():
        lock = NodeLockRegistry.get_lock(topic)
        with lock:
            state = _load_state()
            if topic in state["knowledge"]["topics"]:
                state["knowledge"]["topics"][topic]["last_consolidated"] = datetime.now(timezone.utc).isoformat()
                _save_state(state)


def get_dormant_nodes() -> list[str]:
    """Get all dormant nodes."""
    from core.node_lock_registry import NodeLockRegistry
    with NodeLockRegistry.global_write_lock():
        state = _load_state()
        topics = state["knowledge"]["topics"]
        return [name for name, data in topics.items() if data.get("status") == "dormant"]


def has_recent_dreams(topic: str, within_days: int) -> bool:
    """Check if topic has been dreamed recently."""
    from core.node_lock_registry import NodeLockRegistry
    from datetime import timedelta
    with NodeLockRegistry.global_write_lock():
        state = _load_state()
        topics = state["knowledge"]["topics"]
        if topic not in topics:
            return False
        topic_data = topics[topic]
        dreamed_at_str = topic_data.get("dreamed_at")
        if not dreamed_at_str:
            return False
        try:
            dreamed_at = datetime.fromisoformat(dreamed_at_str)
            age = datetime.now(timezone.utc) - dreamed_at
            return age.days < within_days
        except (ValueError, TypeError):
            return False


def get_recently_dreamed(within_days: int) -> set[str]:
    """Get all topics dreamed within time window."""
    from core.node_lock_registry import NodeLockRegistry
    from datetime import timedelta
    with NodeLockRegistry.global_write_lock():
        state = _load_state()
        topics = state["knowledge"]["topics"]
        result = set()
        cutoff = datetime.now(timezone.utc) - timedelta(days=within_days)
        for name, data in topics.items():
            dreamed_at_str = data.get("dreamed_at")
            if dreamed_at_str:
                try:
                    dreamed_at = datetime.fromisoformat(dreamed_at_str)
                    if dreamed_at > cutoff:
                        result.add(name)
                except (ValueError, TypeError):
                    continue
        return result


# === v0.2.6 Connection Functions ===

def strengthen_connection(topic_a: str, topic_b: str, delta: float = 0.1):
    """Strengthen connection between two topics by delta (default 0.1)."""
    from core.node_lock_registry import NodeLockRegistry
    
    with NodeLockRegistry.global_write_lock():
        lock_a = NodeLockRegistry.get_lock(topic_a)
        lock_b = NodeLockRegistry.get_lock(topic_b)
        locks = tuple(sorted([lock_a, lock_b], key=lambda l: id(l)))
        
        with locks[0], locks[1]:
            state = _load_state()
            topics = state["knowledge"]["topics"]
            
            for topic in [topic_a, topic_b]:
                if topic not in topics:
                    topics[topic] = {"known": False, "depth": 0, "parents": [], 
                                   "explains": [], "children": [], "status": "partial"}
                if "connections" not in topics[topic]:
                    topics[topic]["connections"] = {}
            
            for a, b in [(topic_a, topic_b), (topic_b, topic_a)]:
                if b not in topics[a]["connections"]:
                    topics[a]["connections"][b] = {"weight": 0.0}
                topics[a]["connections"][b]["weight"] = min(
                    1.0, topics[a]["connections"][b]["weight"] + delta
                )
            
            _save_state(state)


def get_directly_connected(topic: str) -> set[str]:
    """Get all nodes directly connected to topic (parents + children)."""
    from core.node_lock_registry import NodeLockRegistry
    
    with NodeLockRegistry.global_write_lock():
        state = _load_state()
        topics = state["knowledge"]["topics"]
        
        if topic not in topics:
            return set()
        
        node = topics[topic]
        connected = set()
        
        for parent in node.get("parents", []):
            connected.add(parent)
        
        for child in node.get("children", []):
            connected.add(child)
        
        return connected


def get_shortest_path_length(topic_a: str, topic_b: str) -> int | float:
    """Get shortest path length between topics using BFS. Returns inf if no path."""
    from core.node_lock_registry import NodeLockRegistry
    from collections import deque
    import math
    
    with NodeLockRegistry.global_write_lock():
        state = _load_state()
        topics = state["knowledge"]["topics"]
        
        if topic_a == topic_b:
            return 0
        
        if topic_a not in topics or topic_b not in topics:
            return math.inf
        
        visited = {topic_a}
        queue = deque([(topic_a, 0)])
        
        while queue:
            current, distance = queue.popleft()
            
            if current == topic_b:
                return distance
            
            node = topics.get(current, {})
            neighbors = set()
            
            for parent in node.get("parents", []):
                neighbors.add(parent)
            for child in node.get("children", []):
                neighbors.add(child)
            
            for neighbor in neighbors:
                if neighbor not in visited and neighbor in topics:
                    visited.add(neighbor)
                    queue.append((neighbor, distance + 1))
        
        return math.inf


def get_all_nodes(active_only: bool = False) -> list[tuple[str, dict]]:
    """Get all nodes, optionally filtering to active only (non-dormant)."""
    from core.node_lock_registry import NodeLockRegistry
    
    with NodeLockRegistry.global_write_lock():
        state = _load_state()
        topics = state["knowledge"]["topics"]
        
        if active_only:
            return [(name, data) for name, data in topics.items() 
                    if data.get("status") != "dormant"]
        
        return list(topics.items())


def get_root_pool_names() -> set[str]:
    """Get all names in root technology pool."""
    from core.node_lock_registry import NodeLockRegistry
    
    with NodeLockRegistry.global_write_lock():
        state = _load_state()
        pool = state.get(ROOT_POOL_KEY, {}).get("candidates", [])
        return {r.get("name") for r in pool if r.get("name")}


# === v0.2.6 SharedInbox Functions (Commit 4) ===

def add_to_dream_inbox(topic: str, source_insight: str):
    """Add topic to dream inbox for SpiderAgent."""
    from core.node_lock_registry import NodeLockRegistry
    
    inbox_path = os.path.join(os.path.dirname(STATE_FILE), "dream_topic_inbox.json")
    
    with NodeLockRegistry.global_write_lock():
        inbox = {"inbox": []}
        if os.path.exists(inbox_path):
            try:
                with open(inbox_path, "r", encoding="utf-8") as f:
                    inbox = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        inbox["inbox"].append({
            "topic": topic,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_insight": source_insight
        })
        
        with open(inbox_path, "w", encoding="utf-8") as f:
            json.dump(inbox, f, ensure_ascii=False, indent=2)


def fetch_and_clear_dream_inbox() -> list[dict]:
    """Fetch and clear dream inbox. Called by SpiderAgent."""
    from core.node_lock_registry import NodeLockRegistry
    
    inbox_path = os.path.join(os.path.dirname(STATE_FILE), "dream_topic_inbox.json")
    
    with NodeLockRegistry.global_write_lock():
        inbox = {"inbox": []}
        if os.path.exists(inbox_path):
            try:
                with open(inbox_path, "r", encoding="utf-8") as f:
                    inbox = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        items = inbox.get("inbox", [])
        
        inbox["inbox"] = []
        with open(inbox_path, "w", encoding="utf-8") as f:
            json.dump(inbox, f, ensure_ascii=False, indent=2)
        
        return items


# === v0.2.6 Utility Functions (Commit 5) ===

def mark_insight_triggered(insight_node_id: str):
    """Mark an insight as having triggered follow-up exploration."""
    from core.node_lock_registry import NodeLockRegistry
    
    with NodeLockRegistry.global_write_lock():
        state = _load_state()
        if "insight_generation" not in state:
            state["insight_generation"] = {}
        if insight_node_id not in state["insight_generation"]:
            state["insight_generation"][insight_node_id] = {}
        state["insight_generation"][insight_node_id]["triggered"] = True
        _save_state(state)


def get_recent_explorations(within_hours: int) -> list:
    """Get explorations within time window."""
    from core.node_lock_registry import NodeLockRegistry
    from datetime import timedelta
    
    with NodeLockRegistry.global_write_lock():
        state = _load_state()
        exploration_log = state.get("exploration_log", [])
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=within_hours)
        cutoff_str = cutoff.isoformat()
        
        return [
            entry for entry in exploration_log
            if entry.get("timestamp", "") > cutoff_str
        ]


def get_node_lifecycle(topic: str) -> dict:
    """Get lifecycle information for a node (status, timestamps, etc.).
    
    Returns:
        dict with: status, created_at, dreamed_at, last_consolidated, etc.
        Returns empty dict if topic not found.
    """
    from core.node_lock_registry import NodeLockRegistry
    
    with NodeLockRegistry.global_write_lock():
        state = _load_state()
        topics = state["knowledge"]["topics"]
        
        if topic not in topics:
            return {}
        
        node = topics[topic]
        return {
            "status": node.get("status", "partial"),
            "known": node.get("known", False),
            "created_at": node.get("last_updated"),  # Use last_updated as proxy
            "dreamed_at": node.get("dreamed_at"),
            "last_consolidated": node.get("last_consolidated"),
            "depth": node.get("depth", 0),
        }


def get_connection_strength(topic_a: str, topic_b: str) -> float:
    """Get connection strength between two topics (0.0 to 1.0).
    
    Returns 0.0 if no direct connection exists.
    """
    from core.node_lock_registry import NodeLockRegistry
    
    with NodeLockRegistry.global_write_lock():
        state = _load_state()
        topics = state["knowledge"]["topics"]
        
        if topic_a not in topics:
            return 0.0
        
        node = topics[topic_a]
        connections = node.get("connections", {})
        
        if topic_b in connections:
            return connections[topic_b].get("weight", 0.0)
        
        # Check reverse direction (connections are stored bidirectionally)
        if topic_b in topics:
            reverse_connections = topics[topic_b].get("connections", {})
            if topic_a in reverse_connections:
                return reverse_connections[topic_a].get("weight", 0.0)
        
        return 0.0