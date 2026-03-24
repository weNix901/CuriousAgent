#!/usr/bin/env python3
"""
清理 v0.2.3 开发期间注入的测试数据和幽灵节点。
运行一次即可，重复运行幂等。
"""
import sys
sys.path.insert(0, '/root/dev/curious-agent')

from core import knowledge_graph as kg

def main():
    state = kg.get_state()
    topics = state.get("knowledge", {}).get("topics", {})
    queue = state.get("curiosity_queue", [])

    # =========================================================
    # 1. KG 测试数据清理
    # =========================================================
    test_topics_kg = [
        "test", "test topic", "test medium", "test deep",
        "test_new_topic_xyz123", "test_bw_trigger",
        "old_topic", "recent_topic"
    ]
    removed_kg = []
    for t in test_topics_kg:
        if t in topics:
            topics.pop(t)
            removed_kg.append(t)

    # =========================================================
    # 2. 队列清理
    # =========================================================
    # 27 个 ghost done 节点（known=False 但 queue status=done）
    ghost_done = [
        "curiosity-driven reinforcement learning",
        "knowledge graph completion AI",
        "ReAct Reflexion agent frameworks",
        "autonomous agent planning and replanning",
        "dual process theory AI",
        "working memory AI agent",
        "OMO multi-agent orchestration",
        "item2",
        "Fine Agentic Workflows",
        "Curiosity",
        "Incremental Contingency Planning",
        "Visual Working Memory",
        "ModelingContinuousRepresentationsVisualWorkingMemoryJohannesLohmann",
        "Working Memory Representations",
        "Agent Planning",
        "Agentic Reasoning",
        "Streamlined Framework",
        "Enhancing LLM Reasoning",
        "Agentic Tools",
        "Extending Classical Planning",
        "__test_sync_topic__",
        "During Working Memory",
        "Computational Cognitive Modeling",
        "Working Memory Guides",
        "Introduction Dynamic Memory",
        "Memory Overhead  Download",
        "Detectedmemoryleaks",
    ]

    # investigating 状态中的幽灵（known=False）
    investigating_ghosts = [
        "LLM self-reflection mechanisms",
        "openclaw agent framework capabilities",
    ]

    # pending 测试占位符
    pending_test_patterns = ["test", "item2", "__test_sync_topic__", "fake", "dummy"]

    cleaned_queue = []
    removed_queue_ghosts = []
    removed_queue_test = []

    for item in queue:
        topic = item["topic"]
        status = item["status"]

        # ghost done → 移除
        if status == "done" and topic in ghost_done:
            removed_queue_ghosts.append(topic)
            continue

        # investigating 幽灵 → 移除
        if status == "investigating" and topic in investigating_ghosts:
            removed_queue_ghosts.append(topic)
            continue

        # pending 测试数据 → 移除
        if status == "pending":
            is_test = any(p.lower() in topic.lower() for p in pending_test_patterns)
            if is_test:
                removed_queue_test.append(topic)
                continue

        cleaned_queue.append(item)

    # =========================================================
    # 3. 清理 knowledge.topics 中的幽灵节点
    #    known=False + status=partial 且不在 cleaned_queue 中
    # =========================================================
    queue_topics = {item["topic"] for item in cleaned_queue}
    ghost_kg_removed = []
    for topic in list(topics.keys()):
        node = topics[topic]
        if not node.get("known") and node.get("status") == "partial" and topic not in queue_topics:
            del topics[topic]
            ghost_kg_removed.append(topic)

    # =========================================================
    # 4. 保存
    # =========================================================
    state["knowledge"]["topics"] = topics
    state["curiosity_queue"] = cleaned_queue
    kg._save_state(state)

    print(f"清理完成:")
    print(f"  KG 测试数据: {len(removed_kg)} 个 - {removed_kg}")
    print(f"  队列 ghost done: {len(removed_queue_ghosts)} 个")
    print(f"  队列 pending 测试: {len(removed_queue_test)} 个")
    print(f"  KG 幽灵节点: {len(ghost_kg_removed)} 个")
    print(f"  保留队列条目: {len(cleaned_queue)} 个")
    if removed_queue_test:
        print(f"  移除的 pending 测试: {removed_queue_test}")

    # 验证
    remaining_test = [t for t in topics if "test" in t.lower()]
    print(f"\n验证: KG 剩余测试数据: {remaining_test or '无'}")

if __name__ == "__main__":
    main()
