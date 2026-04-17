#!/usr/bin/env python3
"""
sync_kg_to_r1d3.py — 将 CA 的 KG 数据同步到 R1D3 可读格式
用法:
  python3 scripts/sync_kg_to_r1d3.py --topic "metacognitive monitoring"
  python3 scripts/sync_kg_to_r1d3.py --roots
  python3 scripts/sync_kg_to_r1d3.py --overview
  python3 scripts/sync_kg_to_r1d3.py --all
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.knowledge_graph_compat import get_spreading_activation_trace, get_root_technologies, get_kg_overview, get_state

R1D3_KG_DIR = "/root/.openclaw/workspace-researcher/memory/curious/kg"
TRACE_DIR = os.path.join(R1D3_KG_DIR, "trace")


def _slugify(name: str) -> str:
    return name.lower().replace(" ", "-").replace("/", "-")[:80]


def sync_trace(topic: str) -> str:
    trace = get_spreading_activation_trace(topic)
    state = get_state()
    topics = state.get("knowledge", {}).get("topics", {})
    node = topics.get(topic, {})
    roots = get_root_technologies()

    lines = [
        f"# Trace: {topic}",
        f"- **quality**: {node.get('quality', 0)}",
        "",
        "## 因果链",
    ]
    for step in trace["ordered_trace"]:
        marker = "⭐ ROOT" if step.get("is_root") else ""
        score = f" (root_score: {step.get('root_score', 0):.1f})" if step.get("is_root") else ""
        lines.append(f"{step['distance'] + 1}. {step['topic']} {marker}{score}")

    if roots:
        lines.append("")
        lines.append("## 根技术池")
        for r in roots[:10]:
            lines.append(f"- {r['name']} (root_score: {r['root_score']:.1f}, confidence: {r['confidence']:.2f})")

    md = "\n".join(lines)
    os.makedirs(TRACE_DIR, exist_ok=True)
    out_path = os.path.join(TRACE_DIR, f"{_slugify(topic)}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    return out_path


def sync_roots() -> str:
    roots = get_root_technologies()
    lines = ["# 根技术池", ""]
    for r in roots:
        lines.append(f"## {r['name']}")
        lines.append(f"- root_score: {r.get('root_score', 0):.2f}")
        lines.append(f"- cross_domain_count: {r.get('cross_domain_count', 0)}")
        lines.append(f"- explains_count: {r.get('explains_count', 0)}")
        lines.append(f"- domains: {', '.join(r.get('domains', []))}")
        lines.append(f"- confidence: {r.get('confidence', 0):.2f}")
        lines.append("")

    md = "\n".join(lines)
    os.makedirs(R1D3_KG_DIR, exist_ok=True)
    out_path = os.path.join(R1D3_KG_DIR, "roots.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    return out_path


def sync_overview() -> str:
    overview = get_kg_overview()
    lines = ["# KG 全局视图", "", f"- 总节点数: {overview['total']}", ""]

    roots_in_overview = [n for n in overview["nodes"] if n.get("is_root")]
    if roots_in_overview:
        lines.append("## 根技术")
        for n in roots_in_overview:
            lines.append(f"- {n['id']} (root_score: {n.get('root_score', 0):.1f})")

    lines.append("")
    lines.append(f"## 节点数: {len(overview['nodes'])}")
    lines.append(f"## 边数: {len(overview['edges'])}")

    md = "\n".join(lines)
    os.makedirs(R1D3_KG_DIR, exist_ok=True)
    out_path = os.path.join(R1D3_KG_DIR, "overview.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync CA KG to R1D3 memory")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--topic", type=str, help="同步指定 topic 的 trace")
    group.add_argument("--roots", action="store_true", help="同步根技术池")
    group.add_argument("--overview", action="store_true", help="同步 KG 全局视图")
    group.add_argument("--all", action="store_true", help="全量同步")
    args = parser.parse_args()

    if args.topic:
        path = sync_trace(args.topic)
        print(f"Trace synced: {path}")
    elif args.roots:
        path = sync_roots()
        print(f"Roots synced: {path}")
    elif args.overview:
        path = sync_overview()
        print(f"Overview synced: {path}")
    elif args.all:
        sync_roots()
        sync_overview()
        print("Full sync done")