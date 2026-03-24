"""
知识图谱 - 管理 Agent 的已知/未知知识状态
"""
import json
import os
from datetime import datetime, timezone
from typing import Optional

STATE_FILE = os.path.join(os.path.dirname(__file__), "../knowledge/state.json")

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


def add_knowledge(topic: str, depth: int = 5, summary: str = "", sources: list = None) -> None:
    """标记某个 topic 为已知，并更新/创建知识节点"""
    state = _load_state()
    topics = state["knowledge"]["topics"]
    now = datetime.now(timezone.utc).isoformat()
    
    if topic in topics:
        topics[topic]["known"] = True
        topics[topic]["depth"] = max(topics[topic]["depth"], depth)
        topics[topic]["last_updated"] = now
        if summary:
            topics[topic]["summary"] = summary
        if sources:
            topics[topic]["sources"] = list(set(topics[topic].get("sources", []) + sources))
        topics[topic]["status"] = "complete"
    else:
        topics[topic] = {
            "known": True,
            "depth": depth,
            "last_updated": now,
            "summary": summary,
            "sources": sources or [],
            "status": "complete"
        }
    
    # 限制节点数：保留深度最高的
    if len(topics) > DEFAULT_STATE["config"]["max_knowledge_nodes"]:
        sorted_topics = sorted(topics.items(), key=lambda x: x[1]["depth"], reverse=True)
        topics.clear()
        for k, v in sorted_topics[:DEFAULT_STATE["config"]["max_knowledge_nodes"]]:
            topics[k] = v
    
    _save_state(state)


def add_curiosity(topic: str, reason: str, relevance: float = 5.0, depth: float = 5.0) -> None:
    """添加一个新的好奇心项到队列"""
    state = _load_state()
    now = datetime.now(timezone.utc).isoformat()
    
    # 去重：如果已存在且未完成，跳过
    for item in state["curiosity_queue"]:
        if item["topic"].lower() == topic.lower() and item["status"] != "done":
            return
    
    score = min(10.0, relevance * 0.35 + depth * 0.25 + 5.0 * 0.4)
    state["curiosity_queue"].append({
        "topic": topic,
        "reason": reason,
        "score": score,
        "relevance": relevance,
        "depth": depth,
        "created_at": now,
        "status": "pending"
    })
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


# === Meta-cognitive tracking functions ===

def _ensure_meta_cognitive(state: dict) -> dict:
    """Ensure state.json contains meta_cognitive field"""
    if "meta_cognitive" not in state:
        state["meta_cognitive"] = {
            "explore_counts": {},
            "marginal_returns": {},
            "last_quality": {},
            "exploration_log": [],
            "completed_topics": {}
        }
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
            "status": "partial"
        }
    
    if "children" not in topics[parent]:
        topics[parent]["children"] = []
    
    if child not in topics[parent]["children"]:
        topics[parent]["children"].append(child)
    
    topics[parent]["status"] = "partial"
    
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
