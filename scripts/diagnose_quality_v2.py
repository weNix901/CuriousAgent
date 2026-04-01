#!/usr/bin/env python3
"""
诊断 QualityV2 评估器。

执行方式：
  cd /root/dev/curious-agent && python3 scripts/diagnose_quality_v2.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import knowledge_graph as kg
from core.quality_v2 import QualityV2Assessor
from core.llm_client import LLMClient

llm = LLMClient()
assessor = QualityV2Assessor(llm)

state = kg.get_state()
topics = state.get("knowledge", {}).get("topics", {})

# Step 1: 检查 KG 节点 content 分布
print("=== Step 1: KG 节点 content 分布 ===")
no_summary = [t for t, v in topics.items() if not v.get("summary")]
stub_kw = ["推理分析", "相关已有知识", "初步推断", "该领域"]
stub_topics = [t for t, v in topics.items() if any(kw in v.get("summary", "") for kw in stub_kw)]
with_content = [t for t, v in topics.items() if v.get("summary") and not any(kw in v.get("summary", "") for kw in stub_kw)]
print(f"  总节点: {len(topics)}")
print(f"  无 summary: {len(no_summary)}")
print(f"  Stub 节点: {len(stub_topics)}")
print(f"  有实质 content: {len(with_content)}")

# Step 2: 测试 QualityV2 对有 content 节点
print("\n=== Step 2: QualityV2 评估测试 ===")
if not with_content:
    print("  没有实质 content 的节点可测试（先跑一些探索）")
else:
    test_topic = with_content[0]
    v = topics[test_topic]
    findings = {"summary": v["summary"], "sources": v.get("sources", [])}
    print(f"  测试 topic: {test_topic}")
    print(f"  summary length: {len(findings['summary'])}")

    try:
        quality = assessor.assess_quality(test_topic, findings, kg)
        print(f"  QualityV2 返回: {quality}")
        if quality == 0:
            print("  ⚠️ 返回 0，评分逻辑有问题")
        elif quality > 0:
            print(f"  ✅ 正常，质量分 {quality}")
    except Exception as e:
        print(f"  ⚠️ QualityV2 异常: {e}")

# Step 3: quality 分布
print("\n=== Step 3: KG quality 分布 ===")
quality_buckets = {"0": 0, "0.1-5": 0, "5.1-8": 0, ">8": 0, "NONE": 0}
for t, v in topics.items():
    q = v.get("quality")
    if q is None or q == 0:
        quality_buckets["0"] += 1
    elif q <= 5:
        quality_buckets["0.1-5"] += 1
    elif q <= 8:
        quality_buckets["5.1-8"] += 1
    else:
        quality_buckets[">8"] += 1
for k, v in quality_buckets.items():
    print(f"  {k}: {v}")

# Step 4: 队列状态分布
print("\n=== Step 4: curiosity_queue 状态分布 ===")
queue = state.get("curiosity_queue", [])
pending = sum(1 for i in queue if i.get("status") == "pending")
exploring = sum(1 for i in queue if i.get("status") == "exploring")
done = sum(1 for i in queue if i.get("status") == "done")
paused = sum(1 for i in queue if i.get("status") == "paused")
print(f"  总队列项: {len(queue)}")
print(f"  pending: {pending}")
print(f"  exploring: {exploring}")
print(f"  done: {done}")
print(f"  paused: {paused}")
