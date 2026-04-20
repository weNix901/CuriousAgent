#!/usr/bin/env python3
"""
knowledge-query script for OpenClaw Skill.

Usage: python3 query.py "topic here"

Returns JSON with confidence, level, and guidance.
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


def query(topic: str) -> dict:
    url = f"{CA_API_URL}/api/knowledge/confidence?topic={urllib.parse.quote(topic)}"
    try:
        req = urllib.request.Request(url, headers={
            "X-OpenClaw-Agent-Id": "r1d3",
            "X-OpenClaw-Skill-Name": "knowledge-query",
        })
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            conf = data.get("result", {}).get("confidence", 0)
            gaps = data.get("result", {}).get("gaps", [])
            level = classify(conf)
            g = guidance(level)
            output = (
                f"[KG Context — {level.title()} ({conf:.0%})]\n"
                f"话题: {topic}\n"
                f"置信度: {conf:.2f}\n"
                f"{g}"
            )
            if gaps:
                output += f"\n知识缺口: {', '.join(gaps)}"
            return {
                "success": True,
                "output": output,
                "metadata": {"topic": topic, "confidence": conf, "level": level, "gaps": gaps},
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
