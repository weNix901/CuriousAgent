"""C2-B (v0.3.6): Learning needs store — 显式学习需求。

CA2.0 §4.2 相关性三信号：
    1. 共现频率（KG 路径距离）      —— CA 侧，待建
    2. 任务触发（会话触发 seen）    —— 已实现（gap_store.real_seen）
    3. 显式需求（learning_needs）   —— 本模块

## 决策（weNix 2026-10-08）

**由 R1D3 主动写**，理由：用户只与 R1D3 交互，不会直接与 CA 交互。
CA 不应"从对话推断"需求（那是读心，违反 C1 公理：决策权归外部测量）。

## 目录约定

    shared_knowledge/r1d3/learning_needs/<slug>.md

每个文件 = 一条显式需求。格式（YAML front-matter + 正文）：

    ---
    topic: FlashAttention
    priority: high       # high | normal | low
    created_at: 2026-10-08T21:43:00+00:00
    ---
    为什么想学：用户连续问了 3 次注意力优化，系统无对应知识。

## CA 侧用法

    explicit_topics() → {topic: priority}
    ranks 作为相关性加成（gap_calculator）。

失败一律返回空（纪律：需求是注解，绝不破坏主流程）。
"""
import logging
import os
import re
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# 显式需求目录（与共享知识库对齐）。
# 本文件在 core/api/ → 上溯三级到项目根（同 gap_store 的路径约定，
# 防历史 bug 复发：上溯级数错会导致落到 core/shared_knowledge/）。
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
DEFAULT_DIR = os.path.join(_PROJECT_ROOT, "shared_knowledge", "r1d3", "learning_needs")

# priority → 相关性加成倍率（显式需求优先于会话触发）。
PRIORITY_WEIGHT = {"high": 1.0, "normal": 0.7, "low": 0.4}

_SLUG_RE = re.compile(r"[^0-9a-zA-Z\u4e00-\u9fff]+")


def _parse_front_matter(text: str) -> Dict[str, str]:
    """极简 front-matter 解析（不引入 yaml 依赖）。"""
    out: Dict[str, str] = {}
    if not text.startswith("---"):
        return out
    end = text.find("\n---", 3)
    if end < 0:
        return out
    for line in text[3:end].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


def explicit_topics(needs_dir: Optional[str] = None) -> Dict[str, str]:
    """读取所有显式需求 → {topic: priority}。

    失败/目录不存在 → 返回空 dict（纪律）。
    """
    d = needs_dir or DEFAULT_DIR
    try:
        if not os.path.isdir(d):
            return {}
        out: Dict[str, str] = {}
        for fn in os.listdir(d):
            if not fn.endswith(".md"):
                continue
            if fn.startswith("_") or fn.lower() == "readme.md":
                continue  # 跳过模板/说明
            path = os.path.join(d, fn)
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
            except OSError:
                continue
            fm = _parse_front_matter(text)
            topic = (fm.get("topic") or "").strip()
            if not topic:
                # 回退：用文件名（去 .md）当 topic
                topic = fn[:-3].replace("_", " ").strip()
            if not topic:
                continue
            prio = (fm.get("priority") or "normal").strip().lower()
            if prio not in PRIORITY_WEIGHT:
                prio = "normal"
            out[topic] = prio
        return out
    except Exception as e:
        logger.warning(f"[learning_needs] explicit_topics failed: {e}")
        return {}


def explicit_weight(topic: str, lookup: Optional[Dict[str, str]] = None,
                    needs_dir: Optional[str] = None) -> float:
    """某 topic 的显式需求权重；无需求 → 0.0。

    匹配：精确优先，其次忽略大小写的包含匹配（topic 是需求词的一部分或反之）。
    """
    if not topic:
        return 0.0
    lk = lookup if lookup is not None else explicit_topics(needs_dir)
    if not lk:
        return 0.0
    if topic in lk:
        return PRIORITY_WEIGHT.get(lk[topic], 0.7)
    low = topic.lower()
    for t, prio in lk.items():
        tl = t.lower()
        if tl and (tl in low or low in tl):
            return PRIORITY_WEIGHT.get(prio, 0.7)
    return 0.0


def make_slug(topic: str) -> str:
    """topic → 文件名 slug（保留中英文，其余折叠为下划线）。"""
    s = _SLUG_RE.sub("_", (topic or "").strip()).strip("_")
    return s or "unnamed"


def write_need(topic: str, priority: str = "normal", reason: str = "",
               needs_dir: Optional[str] = None) -> Optional[str]:
    """R1D3 侧写入口：创建/更新一条显式需求。返回文件路径，失败 None。

    （本函数供 R1D3 调用；CA 侧一般只用读接口。）
    """
    try:
        topic = (topic or "").strip()
        if not topic:
            return None
        prio = (priority or "normal").strip().lower()
        if prio not in PRIORITY_WEIGHT:
            prio = "normal"
        d = needs_dir or DEFAULT_DIR
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"{make_slug(topic)}.md")
        if os.path.exists(path):
            fm = _parse_front_matter(open(path, encoding="utf-8").read())
            if "created_at" not in fm:
                fm["created_at"] = datetime.now(timezone.utc).isoformat()
        else:
            fm = {"created_at": datetime.now(timezone.utc).isoformat()}
        fm["topic"] = topic
        fm["priority"] = prio
        fm["updated_at"] = datetime.now(timezone.utc).isoformat()
        body = reason.strip() or "（无备注）"
        content = (
            "---\n"
            + "\n".join(f"{k}: {v}" for k, v in fm.items())
            + "\n---\n"
            + f"{body}\n"
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path
    except Exception as e:
        logger.warning(f"[learning_needs] write_need failed for '{topic}': {e}")
        return None
