# SPEC v0.2.5 — KG 根技术追溯能力

> **唯一目标**: 从任意知识点追溯到根技术，并形成完整的因果链
> **架构原则**: 增量优先，重用已有模块，谨慎新增，API 为单一事实来源，双消费者兼容

---

## 变更概览（4个文件修改 + 1个新脚本）

| 文件 | 操作 | 说明 |
|------|------|------|
| `core/knowledge_graph.py` | 修改 | 追加 parent 写入 + trace 读取 + root_pool 管理 |
| `core/curious_api.py` | 修改 | 追加 `/api/kg/trace/`, `/api/kg/roots`, `/api/kg/overview` |
| `core/event_bus_persistent.py` | 修改 | 追加 `root_candidate_elevated` 事件类型 |
| `scripts/sync_kg_to_r1d3.py` | 新增 | R1D3 消费脚本（唯一新文件）|
| `scripts/migrate_kg_parents.py` | 新增 | 旧数据迁移脚本 |

**新增模块数：0 个**。所有逻辑复用现有模块。

---

## 一、Topic Schema 扩展

**文件**: `core/knowledge_graph.py`

在 `topics[topic_name]` 中追加以下字段（不删除已有字段）：

```python
topics[topic_name] = {
    # === 已有字段（保持不变）===
    "known": bool,
    "depth": int,
    "status": "...",
    "children": [],
    "explored_children": [],
    "summary": "",
    "sources": [],
    "quality": float,

    # === 新增字段（向上关系）===
    "parents": [],          # List[str]，谁派生了这个 topic
    "explains": [],         # List[dict]，这个 topic 解释了哪些 topic
                             # 格式: [{"target": "topic_name", "relation": "derived_from", "confidence": 0.85}]

    # === 新增字段（溯源元数据）===
    "cross_domain_count": 0,  # 跨多少个探索分支
    "is_root_candidate": False,
    "root_score": 0.0,      # 根评分，仅 is_root_candidate=True 时有效

    # === 元数据（已有则保留）===
    "first_observed": timestamp,  # 新增，初始化时写入
    "last_updated": timestamp
}
```

**root_technology_pool**（新增于 state 根级别）：

```python
state["root_technology_pool"] = {
    "candidates": [],  # List[dict]
    "last_updated": None
}

# candidates 元素格式：
{
    "name": "transformer attention",
    "root_score": 9.2,
    "cross_domain_count": 7,
    "explains_count": 23,
    "domains": ["LLM", "CV", "NLP", "RL"],
    "confidence": 0.91,
    "sources": ["cross_subgraph_detection", "manual_seed"]
}
```

---

## 二、knowledge_graph.py 修改详解

### 2.1 新增常量（文件顶部）

```python
ROOT_SCORE_WEIGHT_DOMAIN = 0.4
ROOT_SCORE_WEIGHT_EXPLAINS = 0.6
CROSS_DOMAIN_THRESHOLD = 3  # cross_domain_count >= 3 时升为根候选
ROOT_POOL_KEY = "root_technology_pool"
```

### 2.2 `_ensure_meta_cognitive()` 修改

在函数末尾追加，确保新字段存在：

```python
# 确保 root_technology_pool 存在
if ROOT_POOL_KEY not in state:
    state[ROOT_POOL_KEY] = {"candidates": [], "last_updated": None}
```

### 2.3 `add_exploration_result()` 修改

**现有签名**（不改变）：
```python
def add_exploration_result(topic: str, result: dict, quality: float) -> None:
```

**新增逻辑**：在该函数末尾（保存 state 之前），追加 parent 写入：

```python
# === v0.2.5 新增：parent 写入 ===
# 获取当前正在探索的 parent topic（从 curiosity_queue 获取 status=exploring 的条目）
state = _load_state()
for queue_item in state.get("curiosity_queue", []):
    if queue_item.get("status") == "exploring":
        parent_topic = queue_item.get("topic")
        if parent_topic and parent_topic != topic:
            _update_parent_relation(parent_topic, topic)
            break
# === v0.2.5 新增结束 ===
```

**新增内部函数** `_update_parent_relation(parent, child)`：

```python
def _update_parent_relation(parent: str, child: str, relation: str = "derived_from", confidence: float = 0.8):
    """内部函数：双向写入父子关系"""
    state = _load_state()
    topics = state["knowledge"]["topics"]
    now = datetime.now(timezone.utc).isoformat()

    # 确保 child 有 parents 字段
    if "parents" not in topics.setdefault(child, {}):
        topics[child]["parents"] = []
    if parent not in topics[child]["parents"]:
        topics[child]["parents"].append(parent)

    # 确保 parent 有 explains 字段
    if "explains" not in topics.setdefault(parent, {}):
        topics[parent]["explains"] = []
    explains_entry = {"target": child, "relation": relation, "confidence": confidence}
    if explains_entry not in topics[parent]["explains"]:
        topics[parent]["explains"].append(explains_entry)

    _save_state(state)
```

### 2.4 新增函数 `get_trace(topic, max_depth=10)`

```python
def get_trace(topic: str, max_depth: int = 10) -> list[dict]:
    """
    向上追溯 topic 的因果链直到根技术。
    返回格式:
    [
        {"level": 0, "topic": "metacognitive monitoring", "relation": "current", "is_root": False},
        {"level": 1, "topic": "self-reflection", "relation": "derived_from", "is_root": False},
        {"level": 2, "topic": "transformer attention", "relation": "derived_from", "is_root": True, "root_score": 9.2}
    ]
    """
    state = _load_state()
    topics = state["knowledge"]["topics"]
    root_pool = state.get(ROOT_POOL_KEY, {}).get("candidates", [])
    root_names = {r["name"] for r in root_pool}

    trace = []
    current = topic
    visited = set()

    for level in range(max_depth):
        if current in visited:
            break
        visited.add(current)

        node = topics.get(current, {})
        parents = node.get("parents", [])

        # 判断是否为根
        is_root = (
            current in root_names or
            not parents or
            node.get("is_root_candidate", False)
        )

        root_info = {}
        if is_root:
            for r in root_pool:
                if r["name"] == current:
                    root_info = {"root_score": r["root_score"], "cross_domain_count": r["cross_domain_count"]}
                    break
            if not root_info and node.get("is_root_candidate"):
                root_info = {"root_score": node.get("root_score", 0), "cross_domain_count": node.get("cross_domain_count", 0)}

        trace.append({
            "level": level,
            "topic": current,
            "relation": "current" if level == 0 else "derived_from",
            "is_root": is_root,
            **root_info
        })

        if is_root or not parents:
            break

        current = parents[0]  # 只追第一条父链（主链路）

    return trace
```

### 2.5 新增函数 `get_root_technologies()`

```python
def get_root_technologies() -> list[dict]:
    """返回所有根技术，按 root_score 降序"""
    state = _load_state()
    candidates = state.get(ROOT_POOL_KEY, {}).get("candidates", [])
    return sorted(candidates, key=lambda x: x.get("root_score", 0), reverse=True)
```

### 2.6 新增函数 `init_root_pool(seeds: list[str])`

```python
def init_root_pool(seeds: list[str]) -> None:
    """
    从初始种子列表初始化根技术池。
    seeds: e.g. ["transformer attention", "gradient descent", "backpropagation"]
    """
    state = _load_state()
    pool = state.setdefault(ROOT_POOL_KEY, {"candidates": [], "last_updated": None})
    existing_names = {r["name"] for r in pool["candidates"]}

    for seed in seeds:
        if seed not in existing_names:
            pool["candidates"].append({
                "name": seed,
                "root_score": 8.0,  # 初始种子给 8.0
                "cross_domain_count": 1,
                "explains_count": 0,
                "domains": ["seed"],
                "confidence": 0.5,
                "sources": ["manual_seed"]
            })

    pool["last_updated"] = datetime.now(timezone.utc).isoformat()
    _save_state(state)
```

### 2.7 新增函数 `get_kg_overview()`

```python
def get_kg_overview() -> dict:
    """返回 KG 全局视图数据"""
    state = _load_state()
    topics = state["knowledge"]["topics"]
    pool = state.get(ROOT_POOL_KEY, {}).get("candidates", [])
    root_names = {r["name"] for r in pool}

    nodes = []
    edges = []

    for name, node in topics.items():
        is_root = name in root_names or node.get("is_root_candidate", False)
        nodes.append({
            "id": name,
            "quality": node.get("quality", 0),
            "root_score": next((r["root_score"] for r in pool if r["name"] == name), 0),
            "is_root": is_root,
            "status": node.get("status", "unexplored"),
            "children_count": len(node.get("children", [])),
            "parents_count": len(node.get("parents", [])),
            "explains_count": len(node.get("explains", [])),
            "cross_domain_count": node.get("cross_domain_count", 0)
        })

        for child in node.get("children", []):
            edges.append({"from": name, "to": child, "type": "child_of"})
        for explain in node.get("explains", []):
            edges.append({"from": name, "to": explain["target"], "type": "explains"})

    return {"nodes": nodes, "edges": edges, "total": len(nodes)}
```

### 2.8 新增函数 `promote_to_root_candidate(topic: str, domains: list[str])`

```python
def promote_to_root_candidate(topic: str, domains: list[str]) -> None:
    """
    将 topic 升为根技术候选。
    由 Cross-Subgraph Detector 或手动调用。
    """
    state = _load_state()
    pool = state.setdefault(ROOT_POOL_KEY, {"candidates": [], "last_updated": None})
    topics = state["knowledge"]["topics"]

    # 计算 explains_count
    explains_count = len(topics.get(topic, {}).get("explains", []))
    cross_domain_count = len(domains)

    root_score = (
        cross_domain_count * ROOT_SCORE_WEIGHT_DOMAIN +
        explains_count * ROOT_SCORE_WEIGHT_EXPLAINS
    )

    # 写入或更新 pool
    for r in pool["candidates"]:
        if r["name"] == topic:
            r["root_score"] = root_score
            r["cross_domain_count"] = cross_domain_count
            r["explains_count"] = explains_count
            r["domains"] = domains
            r["confidence"] = min(0.95, 0.5 + explains_count * 0.05)
            break
    else:
        pool["candidates"].append({
            "name": topic,
            "root_score": root_score,
            "cross_domain_count": cross_domain_count,
            "explains_count": explains_count,
            "domains": domains,
            "confidence": min(0.95, 0.5 + explains_count * 0.05),
            "sources": ["cross_subgraph_detection"]
        })

    # 标记 topic 为候选
    if topic in topics:
        topics[topic]["is_root_candidate"] = True
        topics[topic]["root_score"] = root_score
        topics[topic]["cross_domain_count"] = cross_domain_count

    pool["last_updated"] = datetime.now(timezone.utc).isoformat()
    _save_state(state)
```

---

## 三、event_bus_persistent.py 修改详解

### 3.1 新增事件类型常量（文件顶部）

```python
# === v0.2.5 root tracing events ===
EVENT_ROOT_CANDIDATE_ELEVATED = "root_candidate_elevated"
```

### 3.2 在 `PersistentEventBus.__init__()` 之后追加默认订阅（如果需要）

如已有 `subscribe` 机制可用则复用，无需修改。如果需要初始化根候选处理器：

```python
# 默认订阅（如果 bus 被明确初始化）
def _on_root_candidate_elevated(event: Event):
    from core.knowledge_graph import promote_to_root_candidate
    data = event.data
    promote_to_root_candidate(data["topic"], data.get("domains", []))

# 在 __init__ 中（如果尚未订阅）:
# self.subscribe(EVENT_ROOT_CANDIDATE_ELEVATED, _on_root_candidate_elevated)
```

---

## 四、curious_api.py 修改详解

在现有路由注册区域之后，追加：

```python
# === v0.2.5 KG Root Tracing APIs ===

@app.route("/api/kg/trace/<path:topic>")
def api_kg_trace(topic: str):
    """向上追溯 topic 的因果链到根技术"""
    from core.knowledge_graph import get_trace, get_root_technologies, get_state

    topic = topic.strip()
    state = get_state()
    topics = state.get("knowledge", {}).get("topics", {})

    if topic not in topics:
        return jsonify({"error": f"Topic '{topic}' not found in KG"}), 404

    node = topics[topic]
    trace = get_trace(topic)
    root_technologies = get_root_technologies()

    return jsonify({
        "topic": topic,
        "quality": node.get("quality", 0),
        "trace": trace,
        "root_technologies": [
            {"name": r["name"], "root_score": r["root_score"], "confidence": r["confidence"]}
            for r in root_technologies
        ],
        "cross_subgraph_connections": [
            {"connected_topic": e["target"], "shared_concept": "shared concept", "branch": "inferred"}
            for e in node.get("explains", [])
        ]
    })


@app.route("/api/kg/roots")
def api_kg_roots():
    """返回所有根技术，按 root_score 降序"""
    from core.knowledge_graph import get_root_technologies

    roots = get_root_technologies()
    return jsonify({
        "roots": roots,
        "total": len(roots)
    })


@app.route("/api/kg/overview")
def api_kg_overview():
    """返回 KG 全局视图数据（节点+边）"""
    from core.knowledge_graph import get_kg_overview

    return jsonify(get_kg_overview())


@app.route("/api/kg/promote", methods=["POST"])
def api_kg_promote():
    """手动将 topic 升为根候选（R1D3 或人工调用）"""
    from core.knowledge_graph import promote_to_root_candidate

    data = request.get_json()
    topic = data.get("topic", "").strip()
    domains = data.get("domains", [])

    if not topic:
        return jsonify({"error": "topic is required"}), 400

    promote_to_root_candidate(topic, domains)
    return jsonify({"status": "ok", "topic": topic})
```

---

## 五、新增脚本

### 5.1 scripts/sync_kg_to_r1d3.py（唯一新文件）

```python
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

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.knowledge_graph import get_trace, get_root_technologies, get_kg_overview, get_state

R1D3_KG_DIR = "/root/.openclaw/workspace-researcher/memory/curious/kg"
TRACE_DIR = os.path.join(R1D3_KG_DIR, "trace")


def _slugify(name: str) -> str:
    return name.lower().replace(" ", "-").replace("/", "-")[:80]


def sync_trace(topic: str) -> str:
    trace = get_trace(topic)
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
    for step in trace:
        marker = "⭐ ROOT" if step.get("is_root") else ""
        score = f" (root_score: {step.get('root_score', 0):.1f})" if step.get("is_root") else ""
        lines.append(f"{step['level'] + 1}. {step['topic']} {marker}{score}")

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
```

### 5.2 scripts/migrate_kg_parents.py

```python
#!/usr/bin/env python3
"""
migrate_kg_parents.py — 将 v0.2.4 的 KG 数据迁移到 v0.2.5 schema
迁移内容：
1. 为已有 topic 初始化 parents = []、explains = []
2. 从 children 关系反向推算 parents（如果 parent 存在）
3. 从 curiosity_queue 的历史父子关系补全 parents
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.knowledge_graph import get_state, _save_state, _load_state
from datetime import datetime, timezone

def migrate():
    state = _load_state()
    topics = state.get("knowledge", {}).get("topics", {})
    updated = 0

    # 1. 初始化新字段
    for topic, node in topics.items():
        if "parents" not in node:
            node["parents"] = []
            updated += 1
        if "explains" not in node:
            node["explains"] = []
            updated += 1
        if "cross_domain_count" not in node:
            node["cross_domain_count"] = 0
        if "is_root_candidate" not in node:
            node["is_root_candidate"] = False
        if "root_score" not in node:
            node["root_score"] = 0.0
        if "first_observed" not in node:
            node["first_observed"] = node.get("last_updated", datetime.now(timezone.utc).isoformat())

    # 2. 从 children 反推 parents（如果父节点存在）
    for topic, node in topics.items():
        children = node.get("children", [])
        for child in children:
            if child in topics:
                if "parents" not in topics[child]:
                    topics[child]["parents"] = []
                if topic not in topics[child]["parents"]:
                    topics[child]["parents"].append(topic)

    # 3. 初始化 root_technology_pool
    if "root_technology_pool" not in state:
        state["root_technology_pool"] = {"candidates": [], "last_updated": datetime.now(timezone.utc).isoformat()}

    # 4. 从 config 注入初始种子
    config = state.get("config", {})
    seeds = config.get("root_technology_seeds", [
        "transformer attention",
        "gradient descent",
        "backpropagation",
        "softmax",
        "RL reward signal",
        "uncertainty quantification"
    ])

    pool = state["root_technology_pool"]
    existing = {r["name"] for r in pool["candidates"]}
    for seed in seeds:
        if seed not in existing:
            pool["candidates"].append({
                "name": seed,
                "root_score": 8.0,
                "cross_domain_count": 1,
                "explains_count": 0,
                "domains": ["seed"],
                "confidence": 0.5,
                "sources": ["manual_seed"]
            })

    _save_state(state)
    print(f"Migration done: {updated} topics updated, {len(pool['candidates'])} root seeds loaded")


if __name__ == "__main__":
    migrate()
```

---

## 六、实现顺序

```
Step 1: 修改 knowledge_graph.py
  - 追加常量（ROOT_SCORE_WEIGHT_*、CROSS_DOMAIN_THRESHOLD、ROOT_POOL_KEY）
  - 修改 _ensure_meta_cognitive() — 初始化 root_technology_pool
  - 修改 add_child() — 在函数末尾追加 _update_parent_relation(parent, child) 调用
  - 修改 mark_topic_done() — 在函数末尾追加 _update_parent_relation() 调用（追踪所有已完成 topic 的 parent）
  - 追加 _update_parent_relation(parent, child, relation, confidence)
  - 追加 get_trace(topic, max_depth)
  - 追加 get_root_technologies()
  - 追加 init_root_pool(seeds)
  - 追加 get_kg_overview()
  - 追加 promote_to_root_candidate(topic, domains)

Step 2: 修改 curious_agent.py — run_one_cycle()
  无需修改！parent 追踪已由 mark_topic_done() 内部自动处理（Step 1 修改）
  仅需确认 add_child() 调用处有 _update_parent_relation（已在 Step 1 add_child 内部处理）

Step 3: 修改 curious_api.py
  - 追加 /api/kg/trace/<path:topic>
  - 追加 /api/kg/roots
  - 追加 /api/kg/overview
  - 追加 /api/kg/promote (POST)

Step 4: 修改 event_bus_persistent.py
  - 追加 EVENT_ROOT_CANDIDATE_ELEVATED 常量（仅常量，无逻辑变更）

Step 5: 新增 scripts/sync_kg_to_r1d3.py
  - 实现 sync_trace(), sync_roots(), sync_overview()

Step 6: 新增 scripts/migrate_kg_parents.py
  - 实现 migrate() 并立即运行

Step 7: 修改 config.json
  - 追加 root_technology_seeds 列表

Step 8: 修改 curious_agent.py — main() 或 daemon_mode()
  在 daemon 循环开始前追加：
  - 调用 init_root_pool(config.root_technology_seeds)

Step 9: 验证
  - 跑 migrate 脚本
  - 调用 /api/kg/roots 确认种子在池中
  - 调用 /api/kg/overview 确认节点和边返回正常
  - 调用 /api/kg/trace/<任意已有topic> 确认链路返回
  - 调用 sync_kg_to_r1d3.py --roots 确认 markdown 输出
```

---

## 七、主流程集成点（必须逐个确认的位置）

这是每次都遗漏的部分。以下是 v0.2.5 所有新增逻辑的调用位置，必须逐个确认。

### 7.1 `curious_agent.py` — `run_one_cycle()` 函数

**无需修改**。parent 追踪已在 `mark_topic_done()` 内部自动处理（Step 1 修改）。

- 所有已探索 topic（无论是否 decomposed）都会调用 `mark_topic_done()`
- `mark_topic_done()` 内部自动从 curiosity_queue 查找 parent 并写入
- `add_child()` 内部也会调用 `_update_parent_relation()`（双重保险）

**无需在 curious_agent.py 中追加任何代码。**

---

### 7.2 `curious_agent.py` — `daemon_mode()` 函数（初始化根技术池）

**新增代码**：在 daemon 循环开始前，初始化根技术池：

```python
# === v0.2.5 集成: 初始化根技术池（仅在 daemon 启动时执行一次）===
from core.config import get_config
cfg = get_config()
seeds = getattr(cfg, 'root_technology_seeds', [
    "transformer attention",
    "gradient descent",
    "backpropagation",
    "softmax",
    "RL reward signal",
    "uncertainty quantification"
])
kg.init_root_pool(seeds)
print(f"[v0.2.5] Root pool initialized with {len(seeds)} seeds")
# === v0.2.5 集成结束 ===
```

---

### 7.3 `async_explorer.py` — `_explore_in_thread()` 函数

**无需修改**。`add_exploration_result()` 内部已追加 parent 写入（Step 1 修改），所有异步探索自动获得 parent 追踪。

---

### 7.4 同步/异步探索写入路径汇总

| 调用位置 | 调用的写入函数 | parent 追踪方式 |
|---------|-------------|--------------|
| `async_explorer._explore_in_thread()` | `add_exploration_result()` | ✅ 自动（Step 1 修改该函数内部） |
| `curious_agent.run_one_cycle()` | `kg.mark_topic_done()` | ✅ 自动（Step 1 修改该函数内部） |
| `curious_agent.run_one_cycle()` | `kg.add_child()` | ✅ 自动（Step 1 修改该函数内部） |

**结论**：3 个写入路径均已自动获得 parent 追踪，无需在 `curious_agent.py` 中追加任何代码。

---

### 7.5 API 路由注册

**位置**：`curious_api.py` 文件末尾

追加 4 个新路由，无需修改任何现有路由。

---

### 7.6 R1D3 消费脚本

**位置**：`scripts/sync_kg_to_r1d3.py`（新增文件）

**不在 CA 主流程中调用**，由 R1D3 心跳或 cron 触发。

---

## 八、验收标准（OpenCode 可独立验证）

```bash
# 1. 迁移后 schema 正确
python3 scripts/migrate_kg_parents.py
python3 -c "from core.knowledge_graph import get_state; s=get_state(); print('parents' in list(s['knowledge']['topics'].values())[0])"  # 应输出 True

# 2. /api/kg/roots 返回根技术池
curl http://localhost:4848/api/kg/roots | python3 -m json.tool  # 应包含 transformer attention

# 3. /api/kg/overview 返回图数据
curl http://localhost:4848/api/kg/overview | python3 -m json.tool  # 应包含 nodes 和 edges

# 4. /api/kg/trace/<topic> 返回链路
curl "http://localhost:4848/api/kg/trace/agent" | python3 -m json.tool  # 应返回 trace 列表

# 5. sync 脚本输出正确格式
python3 scripts/sync_kg_to_r1d3.py --roots
cat /root/.openclaw/workspace-researcher/memory/curious/kg/roots.md  # 应为 markdown

# 6. 初始种子在 pool 中
python3 -c "from core.knowledge_graph import get_root_technologies; roots=get_root_technologies(); print([r['name'] for r in roots])"  # 应列出初始种子

# 7. 集成点确认
# 位置A：grep 确认 curious_agent.py 的 run_one_cycle() 中有 _update_parent_relation 调用
grep -n "_update_parent_relation" /root/dev/curious-agent/curious_agent.py

# 8. add_child 自动触发 parent 追踪
grep -n "_update_parent_relation" /root/dev/curious-agent/core/knowledge_graph.py
# 应在 add_child() 函数内部出现
```

---

## 九、config.json 修改

在 `config.json` 中追加：

```json
{
  "root_technology_seeds": [
    "transformer attention",
    "gradient descent",
    "backpropagation",
    "softmax",
    "RL reward signal",
    "uncertainty quantification"
  ]
}
```

---

_Last updated: 2026-03-27 by R1D3_
_v0.2.5: 4 files modified, 1 new script, 0 new modules_
