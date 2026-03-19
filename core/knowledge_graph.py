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
    else:
        topics[topic] = {
            "known": True,
            "depth": depth,
            "last_updated": now,
            "summary": summary,
            "sources": sources or []
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
    
    score = relevance * depth
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
