#!/usr/bin/env python3
"""
Clean Dream Insights — 去重 + 质量过滤 + 清理

策略：
1. 按 trigger topic 分组
2. 每组内按内容前 100 字符去重（相似度 > 0.7 = 重复）
3. 质量评分：信息密度、是否实质性内容 vs 空类比
4. 每组最多保留 N 条高质量 insight
5. 删除低质量/重复文件
6. 生成清理报告
"""
import json
import os
import glob
import sys
import hashlib
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from datetime import datetime

INSIGHTS_DIR = "/root/dev/curious-agent/knowledge/dream_insights"
BACKUP_DIR = "/root/dev/curious-agent/knowledge/dream_insights_backup"
REPORT_PATH = "/root/dev/curious-agent/knowledge/dream_insight_cleanup_report.json"

# 每个 topic 最多保留的条数
MAX_PER_TOPIC = 3

# 内容相似度阈值（超过视为重复）
SIMILARITY_THRESHOLD = 0.7

# 低质量关键词模式（空类比的标志）
LOW_QUALITY_PATTERNS = [
    r'^Just as ',
    r'^If we map ',
    r'^We can frame ',
    r'^We can reframe ',
    r'^Combining the ',
    r'^The .* framework.*can be',
]

def is_analogy_only(content):
    """判断是否纯类比（无实质信息）"""
    if not content:
        return True
    content = content.strip()
    for pattern in LOW_QUALITY_PATTERNS:
        if re.match(pattern, content, re.IGNORECASE):
            return True
    return False

def content_signature(content, length=80):
    """提取内容前 N 字符的签名"""
    return content[:length].strip().lower()

def similarity(a, b):
    """计算两个字符串的相似度"""
    if not a or not b:
        return 0
    return SequenceMatcher(None, a, b).ratio()

def information_density(content):
    """信息密度评分（0-1）"""
    if not content:
        return 0
    
    words = content.split()
    if len(words) < 5:
        return 0
    
    # 实质性指标
    score = 0
    
    # 1. 长度适中（太长可能是废话，太短没信息）
    length = len(content)
    if 100 <= length <= 800:
        score += 0.2
    elif length > 800:
        score += 0.15
    
    # 2. 包含技术术语或具体名称
    technical_indicators = [
        'algorithm', 'framework', 'model', 'network', 'parameter',
        'vector', 'embedding', 'attention', 'token', 'layer',
        'performance', 'accuracy', 'latency', 'optimization',
        'SQLite', 'Neo4j', 'asyncio', 'ReAct', 'LLM', 'API',
        'context', 'memory', 'agent', 'knowledge', 'graph',
    ]
    content_lower = content.lower()
    tech_matches = sum(1 for t in technical_indicators if t.lower() in content_lower)
    score += min(tech_matches * 0.05, 0.3)
    
    # 3. 包含具体数据或引用
    if re.search(r'\d+%', content) or re.search(r'\d+\.\d+', content):
        score += 0.15
    
    # 4. 不包含空类比前缀
    if not is_analogy_only(content):
        score += 0.2
    
    # 5. 包含因果关系或结论
    if any(k in content_lower for k in ['because', 'therefore', 'thus', 'leads to', 'results in', 'enables', 'improves']):
        score += 0.15
    
    return min(score, 1.0)

def deduplicate_group(insights):
    """对一组 insight 去重，返回保留的列表（每个元素是 (f, data, score) 三元组）"""
    # 按质量排序
    scored = []
    for f, data in insights:
        content = data.get('content', '')
        score = information_density(content)
        scored.append((f, data, score))
    
    if len(scored) <= MAX_PER_TOPIC:
        return scored
    
    scored.sort(key=lambda x: x[2], reverse=True)
    
    kept = []
    kept_sigs = []
    
    for item in scored:
        f, data = item[0], item[1]
        if len(kept) >= MAX_PER_TOPIC:
            break
        
        sig = content_signature(data.get('content', ''))
        is_dup = False
        for existing_sig in kept_sigs:
            if similarity(sig, existing_sig) > SIMILARITY_THRESHOLD:
                is_dup = True
                break
        
        if not is_dup:
            kept.append((f, data, score))
            kept_sigs.append(sig)
    
    return kept

def main():
    files = glob.glob(os.path.join(INSIGHTS_DIR, "insight_*.json"))
    print(f"Found {len(files)} insight files")
    
    if not files:
        print("No insights to clean")
        return
    
    # 1. 按 trigger topic 分组
    groups = defaultdict(list)
    parse_errors = 0
    
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            trigger = data.get('trigger_topic', 'unknown').strip()
            groups[trigger].append((f, data))
        except Exception as e:
            parse_errors += 1
    
    print(f"Grouped into {len(groups)} topics ({parse_errors} parse errors)")
    
    # 2. 统计原始分布
    topic_counts = Counter({k: len(v) for k, v in groups.items()})
    print(f"\nOriginal distribution:")
    print(f"  Topics with 100+ insights: {sum(1 for c in topic_counts.values() if c >= 100)}")
    print(f"  Topics with 1 insight: {sum(1 for c in topic_counts.values() if c == 1)}")
    print(f"  Max per topic: {topic_counts.most_common(1)[0]}")
    
    # 3. 备份
    print(f"\nBacking up to {BACKUP_DIR}...")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if not os.listdir(BACKUP_DIR):
        for f in files:
            basename = os.path.basename(f)
            dest = os.path.join(BACKUP_DIR, basename)
            os.symlink(f, dest)  # 软链，不占额外空间
    print("Backup done")
    
    # 4. 去重 + 质量过滤
    total_before = len(files)
    files_to_delete = []
    files_to_keep = []
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_before": total_before,
        "topics": {},
        "deleted_count": 0,
        "kept_count": 0,
    }
    
    for topic, insights in sorted(groups.items(), key=lambda x: len(x[1]), reverse=True):
        kept = deduplicate_group(insights)
        
        # 记录
        report["topics"][topic] = {
            "original_count": len(insights),
            "kept_count": len(kept),
            "deleted_count": len(insights) - len(kept),
        }
        
        kept_files = set(f for f, _, _ in kept)
        for f, data in insights:
            if f in kept_files:
                files_to_keep.append((f, data))
            else:
                files_to_delete.append(f)
    
    # 5. 执行删除
    print(f"\n{'='*60}")
    print(f"Total before: {total_before}")
    print(f"Files to delete: {len(files_to_delete)}")
    print(f"Files to keep: {len(files_to_keep)}")
    print(f"{'='*60}")
    
    # 先干跑模式，列出要删除的 topic 统计
    print("\nPer-topic cleanup summary (top 20):")
    topic_cleanup = sorted(report["topics"].items(), key=lambda x: x[1]["deleted_count"], reverse=True)
    for topic, stats in topic_cleanup[:20]:
        if stats["deleted_count"] > 0:
            print(f"  {topic:60s} {stats['original_count']:5d} → {stats['kept_count']:2d} (delete {stats['deleted_count']})")
    
    # 询问确认
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--yes', action='store_true', help='Skip confirmation')
    args = parser.parse_args()
    
    if not args.yes:
        confirm = input(f"\nDelete {len(files_to_delete)} files? (y/N): ").strip().lower()
        if confirm not in ('y', 'yes'):
            print("Cancelled")
            return
    
    deleted = 0
    for f in files_to_delete:
        try:
            os.remove(f)
            deleted += 1
        except Exception as e:
            print(f"  Failed to delete {f}: {e}")
    
    print(f"\nDeleted {deleted} files")
    print(f"Remaining: {total_before - deleted} files")
    
    # 6. 写报告
    report["total_after"] = total_before - deleted
    report["deleted_count"] = deleted
    report["kept_count"] = total_before - deleted
    
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"Report saved to {REPORT_PATH}")
    
    # 7. 清理空目录
    remaining = glob.glob(os.path.join(INSIGHTS_DIR, "insight_*.json"))
    print(f"Final count: {len(remaining)} files")

if __name__ == "__main__":
    main()
