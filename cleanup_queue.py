#!/usr/bin/env python3
"""
cleanup_queue.py — 精简 curiosity queue

策略：
1. 移除已在 KG 的 items（去重）
2. 每个 original_topic 的 web_citation 上限 20 个
3. 保留所有无类型 items（用户原始好奇心）
4. 保留 citation 类型（学术引用，质量高）
5. 保留 relevance >= 7 的 items
"""

import json
import sys

STATE_FILE = "knowledge/state.json"
BACKUP_FILE = "knowledge/state.json.bak_cleanup"

def load_state():
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def cleanup_queue(state, dry_run=True):
    q = state["curiosity_queue"]
    kg = state["knowledge"]["topics"]
    original_len = len(q)

    # 分类
    in_kg_dup = []       # 已在 KG 的重复 items
    web_citation_items = []  # web_citation items（需要按 source cap）
    no_type_items = []    # 无类型 items（保留）
    citation_items = []    # citation 类型（保留）
    other = []            # 其他类型（保留）

    for item in q:
        topic = item["topic"]
        topic_type = item.get("topic_type")
        original = item.get("original_topic", "")
        relevance = item.get("relevance", 0)

        # 已在 KG → 移除
        if topic in kg:
            in_kg_dup.append(item)
            continue

        if topic_type == "web_citation":
            web_citation_items.append(item)
        elif topic_type is None:
            no_type_items.append(item)
        elif topic_type == "citation":
            citation_items.append(item)
        else:
            other.append(item)

    # 按 original_topic 分组 web_citation，每个 source 最多保留 MAX_PER_SOURCE 个
    MAX_PER_SOURCE = 10
    from collections import defaultdict
    by_source = defaultdict(list)
    for item in web_citation_items:
        by_source[item.get("original_topic", "")].append(item)

    kept_web_citation = []
    removed_by_cap = 0
    for source, items in by_source.items():
        if len(items) > MAX_PER_SOURCE:
            # 按 relevance 降序，保留 top N
            items.sort(key=lambda x: x.get("relevance", 0), reverse=True)
            kept_web_citation.extend(items[:MAX_PER_SOURCE])
            removed_by_cap += len(items) - MAX_PER_SOURCE
        else:
            kept_web_citation.extend(items)

    # 统计
    print(f"=== 清理报告 ===")
    print(f"原始队列: {original_len}")
    print(f"  ├── 已在 KG（重复）: {len(in_kg_dup)} ← 移除")
    print(f"  ├── web_citation: {len(web_citation_items)}")
    print(f"  │     └── 来源数: {len(by_source)} 个 original_topic")
    print(f"  │     └── 超限移除: {removed_by_cap} (每 source 上限 {MAX_PER_SOURCE})")
    print(f"  │     └── 保留: {len(kept_web_citation)}")
    print(f"  ├── 无类型（保留）: {len(no_type_items)}")
    print(f"  ├── citation（保留）: {len(citation_items)}")
    print(f"  └── 其他（保留）: {len(other)}")

    new_total = len(kept_web_citation) + len(no_type_items) + len(citation_items) + len(other)
    print(f"\n清理后队列: {new_total} (减少 {original_len - new_total})")

    if dry_run:
        print(f"\n🟡 DRY RUN — 加上 --no-dry-run 实际执行")
        return

    # 执行清理
    new_q = kept_web_citation + no_type_items + citation_items + other
    state["curiosity_queue"] = new_q

    # 备份
    import shutil
    shutil.copy(STATE_FILE, BACKUP_FILE)
    print(f"备份: {BACKUP_FILE}")

    save_state(state)
    print(f"✅ 已保存，队列 {original_len} → {len(new_q)}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    parser.set_defaults(dry_run=True)
    args = parser.parse_args()

    state = load_state()
    cleanup_queue(state, dry_run=args.dry_run)
