#!/usr/bin/env python3
"""
knowledge-query script for OpenClaw Skill.

Usage: python3 query.py "topic here"

Returns JSON with confidence, level, and guidance.

C1-C-4 (v0.3.5): now parses the four-state `coverage` field
(known | partial | unknown | void) emitted by the confidence endpoint and
leads its guidance with the state, falling back to the legacy confidence
threshold ladder when the field is absent (backward compatible).
"""

import os
import sys
import json
import urllib.request
import urllib.parse

CA_API_URL = os.environ.get("CA_API_URL", "http://localhost:4848")


def classify(confidence: float) -> str:
    if confidence >= 0.85: return "expert"
    if confidence >= 0.6: return "intermediate"
    if confidence >= 0.3: return "beginner"
    return "novice"


def guidance(level: str) -> str:
    return {
        "expert": "【建议】KG 已掌握此话题，可直接引用 KG 知识回答，注明来源。",
        "intermediate": "【建议】KG 有相关知识但不够完整，建议补充搜索后再回答。",
        "beginner": "【建议】KG 知识有限，请先搜索获取信息，再结合 KG 知识回答。",
        "novice": "【建议】KG 无此话题记录，请使用 LLM 知识回答。可考虑注入 CA 探索。",
    }[level]


# C1-C-4 (v0.3.5): four-state guidance — conclusion-first.
COVERAGE_GUIDANCE = {
    "known":   "【建议】系统覆盖：known —— KG 有完整知识，直接引用并注明来源。",
    "partial": "【建议】系统覆盖：partial —— KG 有部分知识，需标注不确定性，建议补充搜索。",
    "unknown": "【建议】系统覆盖：unknown —— KG 无此话题，请先搜索再回答；CA 会异步探索补全。",
    "void":    "【建议】系统覆盖：void —— 系统层面无依据（无节点 + 既往探索失败），明确声明\"暂无系统依据\"。",
}


def query_related_discoveries(topic: str, k: int = 3) -> list:
    """C3D-R2 (v0.3.6): 同方向已结案发现（消费提示）。

    重定向后的 C3-D：让 CA 探出的成果真正被用（**扩大消费面**）。
    失败返回空列表（纪律：消费提示是注解，绝不阻断主查询）。
    """
    try:
        url = (f"{CA_API_URL}/api/kg/related_discoveries/"
               f"{urllib.parse.quote(topic)}?k={int(k)}")
        req = urllib.request.Request(url, headers={
            "X-OpenClaw-Agent-Id": "r1d3",
            "X-OpenClaw-Skill-Name": "knowledge-query",
        })
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            items = data.get("discoveries", [])
            return items if isinstance(items, list) else []
    except Exception:
        return []


def query(topic: str) -> dict:
    # C1-C (v0.3.5, Plan A): single consolidated confidence route.
    # Was `/api/knowledge/confidence?topic=`; that route was deleted as a
    # duplicate of `/api/kg/confidence/<topic>`, which now serves both the
    # knowledge-gate hook and this skill.
    url = f"{CA_API_URL}/api/kg/confidence/{urllib.parse.quote(topic)}"
    try:
        req = urllib.request.Request(url, headers={
            "X-OpenClaw-Agent-Id": "r1d3",
            "X-OpenClaw-Skill-Name": "knowledge-query",
        })
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            result = data.get("result", {})
            conf = result.get("confidence", 0)
            gaps = result.get("gaps", [])
            coverage = result.get("coverage")
            coverage_reason = result.get("coverage_reason", "")
            source_count = result.get("source_count", 0)

            # Four-state leads when present; else fall back to legacy ladder.
            if coverage:
                g = COVERAGE_GUIDANCE.get(coverage, "")
                header = f"[KG Context — {coverage}]"
            else:
                level = classify(conf)
                g = guidance(level)
                header = f"[KG Context — {level.title()} ({conf:.0%})]"

            output = (
                f"{header}\n"
                f"话题: {topic}\n"
                f"置信度: {conf:.2f}"
            )
            if coverage:
                output += f"\n覆盖状态: {coverage}（来源 {source_count} 条）"
                if coverage_reason:
                    output += f"\n判定依据: {coverage_reason}"
            output += f"\n{g}"
            if gaps:
                output += f"\n知识缺口: {', '.join(gaps)}"

            # C3D-R2: 同方向已结案发现（消费提示）。
            discoveries = query_related_discoveries(topic, k=3)
            if discoveries:
                lines = "\n".join(
                    f"  - {d.get('topic')}（相似度 {float(d.get('similarity', 0)):.0%}）"
                    for d in discoveries
                )
                output += (
                    f"\n[相关发现 — 系统探过的同方向知识]\n"
                    f"可按需引用以下系统已探索、有质量的内容：\n{lines}"
                )

            return {
                "success": True,
                "output": output,
                "metadata": {
                    "topic": topic,
                    "confidence": conf,
                    "coverage": coverage,
                    "source_count": source_count,
                    "gaps": gaps,
                    "related_discoveries": discoveries,
                },
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "output": f"[KG Context — 不可用] CA API 无响应，跳过知识查询。"
        }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "Usage: query.py <topic>"}))
        sys.exit(1)
    topic = sys.argv[1]
    result = query(topic)
    print(json.dumps(result, ensure_ascii=False))
