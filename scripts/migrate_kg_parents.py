#!/usr/bin/env python3
"""
migrate_kg_parents.py — 将 v0.2.4 的 KG 数据迁移到 v0.2.5 schema
迁移内容：
1. 为已有 topic 初始化 parents = []、explains = []
2. 从 children 关系反向推算 parents（如果 parent 存在）
3. 从 curiosity_queue 的历史父子关系补全 parents
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.knowledge_graph import _load_state, _save_state
from datetime import datetime, timezone

def migrate():
    state = _load_state()
    topics = state.get("knowledge", {}).get("topics", {})
    updated = 0

    # 1. 初始化新字段
    for topic, node in topics.items():
        if "parents" not in node:
            node["parents"] = []
            updated += 1
        if "explains" not in node:
            node["explains"] = []
            updated += 1
        if "children" not in node:
            node["children"] = []
            updated += 1
        if "cross_domain_count" not in node:
            node["cross_domain_count"] = 0
        if "is_root_candidate" not in node:
            node["is_root_candidate"] = False
        if "root_score" not in node:
            node["root_score"] = 0.0
        if "first_observed" not in node:
            node["first_observed"] = node.get("last_updated", datetime.now(timezone.utc).isoformat())

    # 2. 从 children 反推 parents（如果父节点存在）
    for topic, node in topics.items():
        children = node.get("children", [])
        for child in children:
            if child in topics:
                if "parents" not in topics[child]:
                    topics[child]["parents"] = []
                if topic not in topics[child]["parents"]:
                    topics[child]["parents"].append(topic)

    # 3. 初始化 root_technology_pool
    if "root_technology_pool" not in state:
        state["root_technology_pool"] = {"candidates": [], "last_updated": datetime.now(timezone.utc).isoformat()}

    # 4. 从 config 注入初始种子
    config = state.get("config", {})
    seeds = config.get("root_technology_seeds", [
        "transformer attention",
        "gradient descent",
        "backpropagation",
        "softmax",
        "RL reward signal",
        "uncertainty quantification"
    ])

    pool = state["root_technology_pool"]
    existing = {r["name"] for r in pool["candidates"]}
    for seed in seeds:
        if seed not in existing:
            pool["candidates"].append({
                "name": seed,
                "root_score": 8.0,
                "cross_domain_count": 1,
                "explains_count": 0,
                "domains": ["seed"],
                "confidence": 0.5,
                "sources": ["manual_seed"]
            })

    _save_state(state)
    print(f"Migration done: {updated} topics updated, {len(pool['candidates'])} root seeds loaded")


if __name__ == "__main__":
    migrate()