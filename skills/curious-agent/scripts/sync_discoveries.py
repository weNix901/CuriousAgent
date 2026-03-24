#!/usr/bin/env python3
"""
sync_discoveries.py
将 Curious Agent 的探索发现同步到记忆系统（memory_search 兼容格式）

每个发现写入独立的 .md 文件到 memory/curious/ 目录，
包含语义标签供 memory_search 检索。

用法:
  python3 scripts/sync_discoveries.py

共享机制:
  每个同步的发现会在 curious-discoveries.md 索引中标记 shared:false
  由 share_new_discoveries.py 标记为 shared:true
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# 默认路径（可通过环境变量覆盖）
CURIOUS_STATE = os.environ.get("CURIOUS_STATE", "/root/dev/curious-agent/knowledge/state.json")
CURIOUS_DIR = os.environ.get("CURIOUS_DIR", "/root/.openclaw/workspace-researcher/memory/curious")
INDEX_FILE = os.environ.get("CURIOUS_INDEX", "/root/.openclaw/workspace-researcher/memory/curious-discoveries.md")
LAST_SYNC_FILE = os.path.join(os.path.dirname(INDEX_FILE), ".curious_last_sync")
MAX_FILES = 100


def slugify(text):
    s = re.sub(r'[^\w\s\-]', '', text)
    s = re.sub(r'[\s]+', '-', s)
    return s[:60].strip('-')


def infer_tags(topic, findings):
    topic_lower = topic.lower()
    findings_lower = findings.lower()
    tags = set()

    if any(k in topic_lower for k in ['agent', 'agentic', 'multi-agent']):
        tags.add('#agent')
    if any(k in topic_lower for k in ['reflection', 'reflect', 'self-contrast', 'mirror']):
        tags.add('#self-reflection')
    if any(k in topic_lower for k in ['curiosity', 'curious', 'exploration']):
        tags.add('#curiosity')
    if any(k in topic_lower for k in ['memory', 'working memory', 'episodic']):
        tags.add('#memory')
    if any(k in topic_lower for k in ['cognition', 'cognitive', 'metacognition']):
        tags.add('#cognitive')
    if any(k in topic_lower for k in ['planner', 'planning', 'replan', 'reasoning']):
        tags.add('#planning')
    if any(k in topic_lower for k in ['framework', 'architecture', 'stack']):
        tags.add('#framework')
    if any(k in topic_lower for k in ['world model', 'embodied', 'sensory']):
        tags.add('#embodied-ai')
    if any(k in topic_lower for k in ['swe-agent', 'software', 'automation', 'coding']):
        tags.add('#automation')
    if any(k in topic_lower for k in ['openclaw', 'opencode', 'openclaw']):
        tags.add('#openclaw')
    if any(k in topic_lower for k in ['arxiv', 'paper', 'research']):
        tags.add('#arxiv')
    if any(k in topic_lower for k in ['langchain', 'langgraph', 'smolagent']):
        tags.add('#agent-framework')

    tags.add('#curious-discovery')
    tags.add('#exploration')
    return sorted(tags)


def write_discovery_file(topic, score, findings, sources, timestamp, tags):
    date = timestamp[:10] if timestamp else datetime.now().strftime("%Y-%m-%d")
    slug = slugify(topic)
    filename = f"{CURIOUS_DIR}/{date}-{slug}.md"

    sources_md = ""
    if sources:
        for src in sources[:5]:
            if src:
                title = src.split('/')[-1][:60] if '/' in src else src[:60]
                sources_md += f"- [{title}]({src})\n"

    content = f"""# [curious] {topic}

<!-- memory_search_tags: {','.join(tags)} -->
{tags_md(tags)}

**好奇心指数**: {score}
**探索时间**: {date}
**shared**: false

---

## 核心发现

{findings.strip()}

"""

    if sources_md:
        content += f"""## 关键来源

{sources_md}
"""

    os.makedirs(CURIOUS_DIR, exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    return filename


def tags_md(tags):
    return " ".join(tags)


def update_index(new_topics):
    """更新索引文件，加入 shared:false 标记"""
    files = sorted(Path(CURIOUS_DIR).glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return

    lines = [
        "# Curious Agent 发现库",
        "",
        "> 由 sync_discoveries.py 自动同步 | 详情见 memory/curious/ 目录",
        "> 使用 memory_search(\"topic keywords\") 可语义检索",
        "",
        "---",
        "",
        "## 最近发现（按时间倒序）",
        "",
    ]

    for f in files[:20]:
        content = f.read_text(encoding="utf-8")
        title_match = re.search(r'^# \[curious\](.+)$', content, re.MULTILINE)
        score_match = re.search(r'\*\*好奇心指数\*\*:\s*([\d.]+)', content)
        shared_match = re.search(r'\*\*shared\*\*:\s*(true|false)', content)
        if title_match and score_match:
            title = title_match.group(1).strip()
            score = score_match.group(1)
            shared = shared_match.group(1) if shared_match else "false"
            shared_flag = "" if shared == "true" else " <!-- shared:false -->"
            lines.append(f"- **[{score}]** {title}{shared_flag}")

    os.makedirs(os.path.dirname(INDEX_FILE), exist_ok=True)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def load_last_sync():
    if not os.path.exists(LAST_SYNC_FILE):
        return None
    try:
        with open(LAST_SYNC_FILE, "r") as f:
            return f.read().strip()
    except:
        return None


def save_last_sync(ts):
    os.makedirs(os.path.dirname(LAST_SYNC_FILE), exist_ok=True)
    with open(LAST_SYNC_FILE, "w") as f:
        f.write(ts)


def sync():
    if not os.path.exists(CURIOUS_STATE):
        print("SYNC: No curious-agent state found")
        return 0

    with open(CURIOUS_STATE, "r", encoding="utf-8") as f:
        state = json.load(f)

    last_sync = load_last_sync()
    new_count = 0

    topic_scores = {}
    for item in state.get("curiosity_queue", []):
        topic_scores[item["topic"].lower()] = item.get("score", 0)

    logs = state.get("exploration_log", [])
    new_topics = []

    for log in reversed(logs):
        ts = log.get("timestamp", "")
        topic = log.get("topic", "")
        if not topic or not ts:
            continue
        if last_sync and ts <= last_sync:
            break

        score = topic_scores.get(topic.lower(), 0)
        findings = log.get("findings", "")
        sources = log.get("sources", [])

        if not findings:
            continue

        tags = infer_tags(topic, findings)
        filename = write_discovery_file(topic, score, findings, sources, ts, tags)
        print(f"  + {filename}")
        new_topics.append(topic)
        new_count += 1

    if new_count > 0:
        save_last_sync(logs[-1]["timestamp"] if logs else "")
        update_index(new_topics)
        print(f"SYNC: {new_count} discoveries synced")
    else:
        print("SYNC: No new discoveries")

    return new_count


if __name__ == "__main__":
    count = sync()
    sys.exit(0)
