#!/usr/bin/env python3
"""
share_new_discoveries.py
检查未分享的好奇心发现，返回列表并标记为已分享。

用法:
  python3 scripts/share_new_discoveries.py          # dry-run: 只返回，不标记
  python3 scripts/share_new_discoveries.py --share  # 实际执行：返回并标记 shared:true
  python3 scripts/share_new_discoveries.py --list    # 只列出未分享的发现（不标记）

返回格式（JSON）:
  {
    "undiscovered": [...],  # 未分享的发现列表
    "count": N
  }
"""
import json
import os
import re
import sys
from pathlib import Path

INDEX_FILE = os.environ.get(
    "CURIOUS_INDEX",
    "/root/.openclaw/workspace-researcher/memory/curious-discoveries.md"
)


def parse_index():
    """解析索引文件，返回所有条目的 (title, score, shared)"""
    if not os.path.exists(INDEX_FILE):
        return []

    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    entries = []
    for line in content.splitlines():
        # 匹配: - **[score]** Title <!-- shared:false -->
        m = re.match(r'-\s+\*\*\[([\d.]+)\]\*\*\s+(.+?)(<!--\s*shared:false\s*-->)?$', line)
        if m:
            score = m.group(1)
            title = m.group(2).strip()
            shared = m.group(3) is None  # 有 <!-- shared:false --> 则为 False
            entries.append({"title": title, "score": float(score), "shared": shared})
    return entries


def mark_shared(title_prefix):
    """在索引文件中将匹配的条目标记为 shared:true"""
    if not os.path.exists(INDEX_FILE):
        return 0

    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines()
    updated = 0
    new_lines = []
    for line in lines:
        m = re.match(r'(-?\s+\*\*\[[\d.]+\]\*\*\s+)(.+?)(<!--\s*shared:false\s*-->)?$', line)
        if m and title_prefix.lower() in m.group(2).lower():
            line = m.group(1) + m.group(2)  # 去掉 <!-- shared:false -->
            updated += 1
        new_lines.append(line)

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))

    return updated


def main():
    dry_run = "--list" in sys.argv
    do_share = "--share" in sys.argv

    entries = parse_index()
    undiscovered = [e for e in entries if not e["shared"]]

    # 按分数降序
    undiscovered.sort(key=lambda x: -x["score"])

    result = {
        "undiscovered": undiscovered,
        "count": len(undiscovered)
    }

    if dry_run or not do_share:
        # 只返回，不标记
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 标记所有为已分享
        count = 0
        for e in undiscovered:
            marked = mark_shared(e["title"])
            if marked:
                count += 1
        result["marked_shared"] = count
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
