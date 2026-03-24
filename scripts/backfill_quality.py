#!/usr/bin/env python3
"""
Backfill last_quality for historical topics that have known=True but no quality score.
运行一次即可，重复运行幂等。
"""
import sys
sys.path.insert(0, '/root/dev/curious-agent')

from core import knowledge_graph as kg
from core.meta_cognitive_monitor import MetaCognitiveMonitor
from core.llm_manager import LLMManager

def main():
    state = kg.get_state()
    topics = state.get("knowledge", {}).get("topics", {})

    # 初始化 LLM（质量评估需要）
    try:
        llm = LLMManager.get_instance()
        monitor = MetaCognitiveMonitor(llm_client=llm)
        use_llm = True
        print("LLM 初始化成功，将使用真实质量评估")
    except Exception as e:
        print(f"LLM 初始化失败 ({e})，使用默认质量 6.0")
        use_llm = False
        monitor = None

    mc = state.get("meta_cognitive", {})
    lq = mc.get("last_quality", {})

    filled = []
    skipped = []

    for topic, v in topics.items():
        if not v.get("known"):
            skipped.append(topic)
            continue
        if topic in lq:
            # 已有 quality，跳过
            continue

        summary = v.get("summary", "")
        if not summary:
            # 有 known=True 但无内容，默认 5.0
            quality = 5.0
        elif use_llm and monitor:
            try:
                findings = {"summary": summary, "sources": v.get("sources", [])}
                quality = monitor.assess_exploration_quality(topic, findings)
                quality = round(quality, 1)
            except Exception as e:
                print(f"  评估失败 {topic}: {e}，用 6.0")
                quality = 6.0
        else:
            quality = 6.0

        lq[topic] = quality
        filled.append((topic, quality))
        print(f"  补录: {topic} -> Q={quality}")

    mc["last_quality"] = lq
    state["meta_cognitive"] = mc

    import json, os
    # 使用 kg 模块的路径（与 _save_state 一致）
    import os as _os
    state_path = _os.path.join(_os.path.dirname(__file__), '..', 'knowledge', 'state.json')
    state_path = _os.path.normpath(state_path)
    with open(state_path, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    print(f"\n完成：补录 {len(filled)} 个，跳过 {len(skipped)} 个（无内容）")
    for topic, q in filled:
        print(f"  {topic}: Q={q}")

if __name__ == "__main__":
    main()
