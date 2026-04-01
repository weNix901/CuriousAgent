#!/usr/bin/env python3
"""
Backfill quality scores for KG nodes with quality=0 or quality=NONE.

运行方式：
  cd /root/dev/curious-agent && python3 scripts/backfill_quality.py

依赖：Phase 1 修复后（QualityV2 能返回 > 0 的分）
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import knowledge_graph as kg
from core.quality_v2 import QualityV2Assessor
from core.llm_client import LLMClient

llm = LLMClient()
assessor = QualityV2Assessor(llm)

state = kg.get_state()
topics = state.get("knowledge", {}).get("topics", {})

stub_kw = ["推理分析", "相关已有知识", "初步推断", "该领域"]

need_backfill = []
skipped_stub = []
skipped_no_content = []

for topic, node in topics.items():
    q = node.get("quality")
    summary = node.get("summary", "")

    if not summary or len(summary) < 50:
        skipped_no_content.append(topic)
        continue

    if any(kw in summary for kw in stub_kw):
        skipped_stub.append(topic)
        continue

    if q is None or q == 0:
        need_backfill.append(topic)

print(f"需要 backfill: {len(need_backfill)} 个节点")
print(f"跳过（无 content）: {len(skipped_no_content)} 个节点")
print(f"跳过（stub）: {len(skipped_stub)} 个节点")

updated = 0
errors = 0
for topic in need_backfill:
    node = topics[topic]
    summary = node.get("summary", "")
    findings = {"summary": summary, "sources": node.get("sources", [])}

    try:
        quality = assessor.assess_quality(topic, findings, kg)
        if quality > 0:
            kg.update_topic_quality(topic, quality)
            updated += 1
            print(f"  [OK] {topic[:50]}: Q={quality:.1f}")
        else:
            print(f"  [WARN] {topic[:50]}: Q={quality} (still 0)")
    except Exception as e:
        errors += 1
        print(f"  [ERROR] {topic[:50]}: {e}")

print(f"\n完成: {updated}/{len(need_backfill)} 节点更新了正质量分，{errors} 个错误")
