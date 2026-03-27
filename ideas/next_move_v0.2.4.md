# Curious Agent v0.2.4 — 蜘蛛引擎 + KG 图谱

> **文档状态**: 完整设计，待 OpenCode 实现
> **版本**: v0.2.4
> **日期**: 2026-03-25
> **设计者**: R1D3 + weNix
> **实现者**: OpenCode
> **前置依赖**: v0.2.3（好奇心分解引擎 + Bug 修复）
> **配套文档**: `ARCHITECTURE.md`（已有）、各 `RELEASE_NOTE_v0.2.x.md`（已有）

---

## 版本叠加关系

```
v0.2   — 分层探索 (shallow/medium/deep)               ← 复用
v0.2.1 — ICM 融合评分                                  ← 复用
v0.2.2 — 元认知监控器 + MGV + EventBus + 多LLM路由     ← 复用
         └── should_continue(topic) → tuple[bool, str]
         └── monitor.get_marginal_returns(topic) → list[float]
         └── monitor.assess_exploration_quality(topic, findings) → float
v0.2.3 — 好奇心分解引擎 (CuriosityDecomposer)           ← 复用
v0.2.4 — 蜘蛛引擎 + KG 图谱基础  ← 本文定义
v0.2.5 — R1D3 KG Search Skill（未来）
```

---

## 一、目标

| 编号 | 目标 | 描述 |
|------|------|------|
| O1 | 自主探索 | CA 能自主决定探索方向，不依赖 R1D3 的具体指令 |
| O2 | 持续运行 | CA 能持续探索，不间断、不迷路 |
| O3 | KG 图谱 | 探索结果形成结构化 KG 图谱，R1D3 可查询 |
| O4 | 命题驱动 | R1D3 只需给出大命题，CA 自动完成探索 |

---

## 二、核心原理

### 2.1 边际收益驱动自主性

```
探索节点 A → findings
    ↓
monitor.assess_quality(A, findings) → quality分数
    ↓
controller.should_continue(A) 内部：
    marginal = current_quality - avg(历史returns)
    ↓
marginal > 0.3 → 继续深入
marginal ≤ 0.3 → 跳转
```

**重要**：不要把边际收益判断理解成"比较两次 findings"。真正的计算是：
- 从 monitor 拿到历史 marginal_returns 列表
- 取最近几次的平均值
- 当前 quality 减去该平均值

### 2.2 图结构 vs 树结构

树：每个节点只能有一个父节点 → 同一知识点被不同路径发现时，重复探索

图：节点可以有多个父节点 → 共享同一个节点，只探索一次

```
树结构：
    A ──→ C
    B ──→ C   ← C 被发现两次，但树无法合并

图结构：
    A ──→ C ←── B   ← C 只探索一次，A 和 B 都是 C 的父节点
```

### 2.3 蜘蛛引擎循环

```
observe → reason → act → reflect → checkpoint
    ↑                                    ↓
    ←──────── 边际收益判断 ←←←←←←←←←←←←←←←←
```

---

## 三、文件结构（OpenCode 开发清单）

### 3.1 新建文件

| 文件路径 | 描述 | 对应特性 |
|---------|------|---------|
| `spider_engine.py` | 蜘蛛引擎主入口 | F1 |
| `core/kg_graph.py` | KG 图谱管理 | F2 |
| `core/surprise_detector.py` | 惊异检测 | F4 |
| `core/r1d3_watcher.py` | R1D3 命题感知 | F5 |
| `state/checkpoint.py` | 状态持久化 | F6 |
| `state/spider_state.json` | 蜘蛛运行状态 | F6 |

### 3.2 复用文件（只读，不修改）

| 文件路径 | 复用方式 |
|---------|---------|
| `core/explorer.py` | `Explorer().explore({"topic":..., "score":..., "depth":...})` |
| `core/meta_cognitive_controller.py` | `controller.should_continue(topic)` |
| `core/meta_cognitive_monitor.py` | `monitor.assess_quality(topic, findings)`, `monitor.get_marginal_returns(topic)` |
| `core/curiosity_decomposer.py` | `decomposer.decompose(topic)` (async) |
| `curious_agent.py` | 启动入口，可选调用 spider_engine |

### 3.3 共享知识路径

| 路径 | 用途 |
|------|------|
| `shared_knowledge/r1d3/propositions/` | R1D3 写入命题，spider 读取 |
| `shared_knowledge/ca/kg/kg_graph.json` | KG 图谱，R1D3 和 CA 共享 |
| `shared_knowledge/ca/discoveries/` | CA 写入发现，R1D3 感知 |

---

## 四、特性开发顺序与依赖拓扑

### 4.1 依赖拓扑

```
F2 (KG Graph)          ← 无依赖，基础中的基础
    ↓
F6 (Checkpoint)        ← 依赖 F2（需要知道 kg_path）
    ↓
F1 (Spider Engine)      ← 依赖 F2、F6
    ↓
F3 (边际收益)           ← 复用 v0.2.2，已在 F1 中集成
    ↓
F5 (R1D3 Watcher)      ← 独立，可与 F1 并行
    ↓
F7 (Discv. Write)      ← 依赖 F1（探索完成后写）
    ↓
F4 (Surprise Detect)   ← 依赖 F1（探索前后 hook）
    ↓
F8 (KG 共享)           ← 依赖 F2，基础设施
```

### 4.2 推荐开发顺序

```
Phase 1: 基础设施
  ① F2 — KG 图结构（无依赖，最先做）
  
Phase 2: 持久化
  ② F6 — Checkpoint（依赖 F2）

Phase 3: 核心引擎
  ③ F1 — Spider Engine（依赖 F2、F6）
  ④ F3 — 边际收益（复用 v0.2.2，在 F1 中验证）

Phase 4: 感知层（可并行）
  ⑤ F5 — R1D3 Watcher（独立模块）
  ⑥ F7 — Discoveries Write（依赖 F1）

Phase 5: 增强功能
  ⑦ F4 — Surprise Detector（依赖 F1 的 act/reflect 钩子）
  
Phase 6: 共享
  ⑧ F8 — KG 共享（依赖 F2，基础设施）
```

**理由**：
- F2 是所有功能的基础，先做
- F1 需要 F2 和 F6，所以它们先做
- F5 和 F1 可并行：F5 只感知命题文件，不依赖引擎
- F4 需要 F1 的 act/reflect hook，最后做

---

## 五、F2: KG 图结构（P0）

### 5.1 需求描述

将 KG 从树改为图，支持多父节点，避免重复探索。

### 5.2 设计目的

解决树结构中同一节点被多次发现时重复探索的问题。

### 5.3 节点数据结构

```json
{
  "nodes": {
    "节点名": {
      "parents": ["父节点A", "父节点B"],
      "children": ["子节点C"],
      "explored": true,
      "fully_explored": false,
      "explored_at": "2026-03-25T18:00:00",
      "explored_by": ["父节点A"],
      "findings_summary": "...",
      "created_at": "2026-03-25T17:00:00"
    }
  },
  "edges": [
    {"from": "节点A", "to": "节点B", "relation": "associated"}
  ]
}
```

### 5.4 实现逻辑（core/kg_graph.py）

```python
import json
import os
from typing import Optional

def timestamp():
    import datetime
    return datetime.datetime.now().isoformat()

class KGGraph:
    """
    KG 图谱管理器。
    图结构：节点可有多父节点，边记录关联关系。
    """

    def __init__(self, path: str = "shared_knowledge/ca/kg/kg_graph.json"):
        self.path = path
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []
        self.load()

    # ── 核心判断 ───────────────────────────────────────

    def should_explore(self, node: str, from_parent: Optional[str]) -> tuple[bool, str]:
        """
        判断是否需要探索该节点。

        三种返回值：
        - (True,  "first_visit")          → 新节点，需要探索
        - (True,  "not_yet_explored")      → 已存在但未探索，需要探索
        - (False, "linked_only")           → 已探索，只更新关联
        - (False, "already_explored")      → 已探索且已知此父节点，跳过
        """
        if node not in self.nodes:
            return True, "first_visit"

        nd = self.nodes[node]

        if not nd.get("explored"):
            return True, "not_yet_explored"

        # 已探索，但这个父节点还没关联过 → 只建立关联，不重复探索
        if from_parent and from_parent not in nd.get("explored_by", []):
            nd.setdefault("parents", []).append(from_parent)
            nd.setdefault("explored_by", []).append(from_parent)
            self._add_edge(from_parent, node, "associated")
            return False, "linked_only"

        return False, "already_explored"

    # ── 增删改 ─────────────────────────────────────────

    def add_node(self, node: str, from_parent: Optional[str] = None) -> None:
        """添加节点（如果不存在）"""
        if node in self.nodes:
            return
        self.nodes[node] = {
            "parents": [from_parent] if from_parent else [],
            "children": [],
            "explored": False,
            "fully_explored": False,
            "explored_by": [from_parent] if from_parent else [],
            "findings_summary": "",
            "created_at": timestamp()
        }

    def mark_explored(self, node: str, findings: str = "") -> None:
        """标记节点已探索"""
        if node not in self.nodes:
            self.add_node(node)
        self.nodes[node]["explored"] = True
        self.nodes[node]["explored_at"] = timestamp()
        if findings:
            self.nodes[node]["findings_summary"] = findings

    def mark_fully_explored(self, node: str) -> None:
        """标记节点为充分探索（不再跳转回来）"""
        if node in self.nodes:
            self.nodes[node]["fully_explored"] = True
            self.nodes[node]["fully_explored_at"] = timestamp()

    def _add_edge(self, from_node: str, to_node: str, relation: str = "associated") -> None:
        """添加边（内部用，不做去重检查）"""
        edge = {"from": from_node, "to": to_node, "relation": relation}
        if edge not in self.edges:
            self.edges.append(edge)

        if to_node not in self.nodes.get(from_node, {}).get("children", []):
            self.nodes.setdefault(from_node, {}).setdefault("children", []).append(to_node)
        if from_node not in self.nodes.get(to_node, {}).get("parents", []):
            self.nodes.setdefault(to_node, {}).setdefault("parents", []).append(from_node)

    def add_relation(self, from_node: str, to_node: str, relation: str = "associated") -> None:
        """从探索结果中提取关联节点并添加边"""
        self.add_node(to_node, from_node)
        self._add_edge(from_node, to_node, relation)

    # ── 查询 ───────────────────────────────────────────

    def get_high_degree_unexplored(self) -> Optional[str]:
        """获取度（入+出）最高且未 fully_explored 的节点"""
        candidates = []
        for node, data in self.nodes.items():
            if data.get("fully_explored"):
                continue
            degree = len(data.get("parents", [])) + len(data.get("children", []))
            candidates.append((degree, node))
        if not candidates:
            return None
        candidates.sort(reverse=True)
        return candidates[0][1]

    def get_unexplored_nodes(self) -> list[str]:
        """获取所有未探索的节点名"""
        return [n for n, d in self.nodes.items() if not d.get("explored")]

    def is_empty(self) -> bool:
        return len(self.nodes) == 0

    # ── 持久化 ────────────────────────────────────────

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"nodes": self.nodes, "edges": self.edges}, f,
                      ensure_ascii=False, indent=2)

    def load(self) -> "KGGraph":
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
                self.nodes = data.get("nodes", {})
                self.edges = data.get("edges", [])
        return self
```

### 5.5 复用已有模块

无（全新模块）。

### 5.6 主流程集成点

```
SpiderEngine 初始化时：
    self.kg = KGGraph()

SpiderEngine.run_once() 中：
    # 探索前判断
    should, reason = self.kg.should_explore(node, parent)
    if should:
        self.explorer.explore(...)

    # 探索后更新
    self.kg.mark_explored(node, findings)
    for subtopic in subtopics:
        self.kg.add_relation(node, subtopic)
    self.kg.save()
```

### 5.7 测试方式

```python
import pytest, os, tempfile
from core.kg_graph import KGGraph

@pytest.fixture
def kg():
    path = tempfile.mktemp(suffix=".json")
    yield KGGraph(path)
    if os.path.exists(path):
        os.remove(path)

def test_first_visit(kg):
    should, reason = kg.should_explore("new_topic", None)
    assert should == True
    assert reason == "first_visit"

def test_already_explored_same_parent(kg):
    kg.add_node("C", "A")
    kg.mark_explored("C")
    should, reason = kg.should_explore("C", "A")
    assert should == False
    assert reason == "already_explored"

def test_linked_only_new_parent(kg):
    kg.add_node("C", "A")
    kg.mark_explored("C")
    should, reason = kg.should_explore("C", "B")
    assert should == False
    assert reason == "linked_only"
    assert "A" in kg.nodes["C"]["parents"]
    assert "B" in kg.nodes["C"]["parents"]
    assert kg.nodes["C"]["explored"] == True  # 探索状态不变

def test_multi_parent_three_parents(kg):
    kg.add_node("C", "A")
    kg.mark_explored("C")
    kg.should_explore("C", "B")
    kg.should_explore("C", "D")
    assert set(kg.nodes["C"]["parents"]) == {"A", "B", "D"}
    assert kg.nodes["C"]["explored"] == True  # 不重复探索

def test_high_degree_unexplored(kg):
    kg.add_node("A", None)
    kg.add_node("B", None)
    kg.add_node("C", None)
    kg.add_relation("A", "B")
    kg.add_relation("A", "C")
    # A 的度=2（2条出边），B和C的度=1
    assert kg.get_high_degree_unexplored() == "A"

def test_save_and_load(kg):
    kg.add_node("X", None)
    kg.add_relation("X", "Y")
    kg.save()

    kg2 = KGGraph(kg.path).load()
    assert "X" in kg2.nodes
    assert len(kg2.edges) == 1
```

### 5.8 验收标准

| 编号 | 标准 | 验证方式 |
|------|------|---------|
| V2.1 | `should_explore` 对新节点返回 `(True, "first_visit")` | 单元测试 |
| V2.2 | 同一节点被 A、B 关联，只探索一次 | 单元测试 `test_multi_parent_three_parents` |
| V2.3 | `add_relation` 后节点 children/parents 双向更新 | 单元测试 |
| V2.4 | `get_high_degree_unexplored` 返回度最高的未充分探索节点 | 单元测试 |
| V2.5 | `save()`/`load()` 正确持久化图结构 | 单元测试 `test_save_and_load` |

### 5.9 已知限制

- `get_high_degree_unexplored` 按度排序，度相同时按字母顺序选第一个（确定性但不保证最优）

---

## 六、F6: 状态持久化（P0）

### 6.1 需求描述

蜘蛛状态定期持久化，支持 kill -9 后重启恢复。

### 6.2 设计目的

确保探索过程不因进程中断而丢失，实现"断点续探"。

### 6.3 实现逻辑（state/checkpoint.py）

```python
import json
import os
from datetime import datetime

class Checkpoint:
    """
    蜘蛛状态持久化。
    保存：当前节点、frontier、visited、连续低收益计数、步数、kg路径。
    """

    CHECKPOINT_DIR = "state"
    CHECKPOINT_FILE = "state/spider_checkpoint.json"

    def __init__(self, path: str = None):
        self.path = path or self.CHECKPOINT_FILE

    def save(self, spider_state: dict) -> None:
        """
        spider_state 格式：
        {
            "current_node": str | None,
            "frontier": list[str],
            "visited": list[str],         # set 在这里转 list
            "consecutive_low_gain": int,
            "step_count": int,
            "kg_path": str,
            "previous_findings": dict,    # 可选，用于边际收益计算
        }
        """
        data = {
            "last_loop_time": datetime.now().isoformat(),
            **spider_state
        }
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self) -> dict | None:
        """返回 None 表示没有 checkpoint"""
        if not os.path.exists(self.path):
            return None
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def clear(self) -> None:
        if os.path.exists(self.path):
            os.remove(self.path)
```

### 6.4 复用已有模块

无（全新模块）。

### 6.5 主流程集成点

```
SpiderEngine.__init__():
    self.checkpoint = Checkpoint()

SpiderEngine.run_once() 末尾：
    self.checkpoint.save({
        "current_node": self.current_node,
        "frontier": self.frontier,
        "visited": list(self.visited),        # set → list
        "consecutive_low_gain": self.consecutive_low_gain,
        "step_count": self.step_count,
        "kg_path": self.kg.path,
    })

SpiderEngine.__init__() 恢复路径：
    saved = self.checkpoint.load()
    if saved:
        self.current_node = saved.get("current_node")
        self.frontier = saved.get("frontier", [])
        self.visited = set(saved.get("visited", []))
        self.consecutive_low_gain = saved.get("consecutive_low_gain", 0)
        self.step_count = saved.get("step_count", 0)
```

### 6.6 测试方式

```python
import pytest, tempfile, os
from state.checkpoint import Checkpoint

def test_save_and_load():
    ck = Checkpoint(tempfile.mktemp(suffix=".json"))

    state = {
        "current_node": "node_a",
        "frontier": ["b", "c"],
        "visited": ["x", "y"],          # list[str]
        "consecutive_low_gain": 2,
        "step_count": 10,
        "kg_path": "shared_knowledge/ca/kg/kg_graph.json"
    }

    ck.save(state)
    loaded = ck.load()

    assert loaded["current_node"] == "node_a"
    assert loaded["frontier"] == ["b", "c"]
    assert set(loaded["visited"]) == {"x", "y"}
    assert loaded["consecutive_low_gain"] == 2
    assert loaded["step_count"] == 10

def test_load_returns_none_when_missing():
    ck = Checkpoint("/nonexistent/path.json")
    assert ck.load() is None

def test_clear():
    path = tempfile.mktemp(suffix=".json")
    ck = Checkpoint(path)
    ck.save({"step_count": 1})
    assert os.path.exists(path)
    ck.clear()
    assert not os.path.exists(path)
```

### 6.7 验收标准

| 编号 | 标准 | 验证方式 |
|------|------|---------|
| V6.1 | kill -TERM 后 checkpoint 文件存在且格式正确 | 发送信号，cat 文件 |
| V6.2 | 重启后 `checkpoint.load()` 返回正确状态 | 单元测试 |
| V6.3 | `visited` 字段 set→list→set 互转正确 | 单元测试 |
| V6.4 | checkpoint 不存在时 `load()` 返回 None | 单元测试 |

### 6.8 已知限制

- 只保存蜘蛛引擎状态，不保存 KG 图谱（KG 图谱自己通过 `kg.save()` 持久化）

---

## 七、F1: 蜘蛛引擎（P0）

### 7.1 需求描述

不知疲倦的蜘蛛，在 KG 图上自主探索，自主决定探索方向和深度。

### 7.2 设计目的

实现 CA 从"被动响应"到"自驱动探索"的转变。

### 7.3 关键设计决策

**决策1：Explorer.explore() 的正确调用方式**

```python
# ❌ 错误（文档旧版）
findings = self.explorer.explore(self.current_node, DEFAULT_DEPTH)

# ✅ 正确（实际 API）
findings = self.explorer.explore({
    "topic": self.current_node,
    "score": 0.5,
    "depth": 2  # 对应 medium
})
```

**决策2：should_continue() 的正确调用方式**

```python
# ❌ 错误（旧版理解：传入 findings 和 previous_findings）
should = controller.should_continue(self.current_node, findings, prev_findings)

# ✅ 正确（实际 API：只传 topic，内部查 monitor）
should, reason = controller.should_continue(self.current_node)
# 内部逻辑：
#   returns = monitor.get_marginal_returns(topic)
#   marginal = current_quality - avg(recent_returns)
#   return marginal > MIN_MARGINAL_RETURN
```

**决策3：CuriosityDecomposer.decompose() 是 async**

```python
# ✅ 正确
subtopics = await decomposer.decompose(self.current_node)
# 返回格式：list[dict]，每个 dict 包含 "topic" 字段
```

### 7.4 实现逻辑（spider_engine.py）

```python
import asyncio
import os
import sys
from core.explorer import Explorer
from core.meta_cognitive_controller import MetaCognitiveController
from core.meta_cognitive_monitor import MetaCognitiveMonitor
from core.curiosity_decomposer import CuriosityDecomposer
from core.kg_graph import KGGraph
from core.surprise_detector import SurpriseDetector
from core.r1d3_watcher import R1D3Watcher
from state.checkpoint import Checkpoint

# 复用 v0.2.2 的边际收益阈值常量
MIN_MARGINAL_RETURN = 0.3
MAX_CONSECUTIVE_LOW = 3
LOOP_INTERVAL = 30  # 秒
DEFAULT_DEPTH = 2  # medium
DISCOVERIES_DIR = "shared_knowledge/ca/discoveries"

class SpiderEngine:
    def __init__(self, config: dict = None):
        self.kg = KGGraph()
        self.checkpoint = Checkpoint()

        # 复用 v0.2.2 的元认知组件
        monitor = MetaCognitiveMonitor()
        self.controller = MetaCognitiveController(monitor)

        # 复用 v0.2
        self.explorer = Explorer(exploration_depth="medium")
        # 复用 v0.2.3
        self.decomposer = CuriosityDecomposer()

        # 新增组件
        self.detector = SurpriseDetector()
        self.watcher = R1D3Watcher()

        # 状态
        self.current_node: str | None = None
        self.frontier: list[str] = []
        self.visited: set[str] = set()
        self.consecutive_low_gain: int = 0
        self.step_count: int = 0
        self.previous_findings: dict = {}

        # 从 checkpoint 恢复
        self._restore_from_checkpoint()

    def _restore_from_checkpoint(self):
        saved = self.checkpoint.load()
        if saved:
            self.current_node = saved.get("current_node")
            self.frontier = saved.get("frontier", [])
            self.visited = set(saved.get("visited", []))
            self.consecutive_low_gain = saved.get("consecutive_low_gain", 0)
            self.step_count = saved.get("step_count", 0)
            print(f"[Spider] Restored from checkpoint: node={self.current_node}, step={self.step_count}")

    # ── 主循环 ─────────────────────────────────────────

    def run_loop(self):
        """阻塞主循环"""
        print(f"[Spider] Starting. Loop interval={LOOP_INTERVAL}s")
        while True:
            try:
                self.observe()
                self.run_once()
            except Exception as e:
                print(f"[Spider] Error in loop: {e}")
            import time; time.sleep(LOOP_INTERVAL)

    def run_once(self):
        """执行一轮探索（observe→act→reason→reflect→checkpoint）"""
        # 1. 如果没有 current_node，尝试从 frontier 取
        if not self.current_node:
            self._pick_next_node()
            if not self.current_node:
                return  # 没有可探索的节点

        # 2. act: 探索
        curiosity_item = {
            "topic": self.current_node,
            "score": 0.5,   # 占位，monitor 会重新评估
            "depth": DEFAULT_DEPTH
        }
        findings = self.explorer.explore(curiosity_item)

        # 3. reason: 边际收益判断（复用 v0.2.2）
        should_continue, reason = self.controller.should_continue(self.current_node)

        # 4. 更新 KG + 决定下一步
        if should_continue:
            # 深入：将子节点加入 frontier
            self._expand_frontier(self.current_node, findings)
            self.consecutive_low_gain = 0
        else:
            # 跳转
            self.kg.mark_fully_explored(self.current_node)
            self.consecutive_low_gain += 1

            if self.consecutive_low_gain >= MAX_CONSECUTIVE_LOW:
                # 强制跳转：选 KG 中度最高且未充分探索的节点
                forced = self.kg.get_high_degree_unexplored()
                if forced:
                    print(f"[Spider] Force jump to {forced} (consecutive_low_gain={MAX_CONSECUTIVE_LOW})")
                    self.current_node = forced
                else:
                    self.current_node = None
                self.consecutive_low_gain = 0
            else:
                self._pick_next_node()

        # 5. reflect: 惊异检测 + discoveries 写入
        self._reflect(self.current_node, findings)

        # 6. 记录并 checkpoint
        self.step_count += 1
        self.visited.add(self.current_node)
        self.checkpoint.save({
            "current_node": self.current_node,
            "frontier": self.frontier,
            "visited": list(self.visited),
            "consecutive_low_gain": self.consecutive_low_gain,
            "step_count": self.step_count,
            "kg_path": self.kg.path,
        })

        self.previous_findings = findings

    # ── 子方法 ─────────────────────────────────────────

    def observe(self):
        """感知 R1D3 新命题"""
        propositions = self.watcher.scan_new_propositions()
        for prop in propositions:
            seed_topics = prop.get("seed_topics", [])
            print(f"[Spider] Received proposition: {prop.get('proposition')}, seeds={seed_topics}")
            for topic in seed_topics:
                if self.kg.should_explore(topic, None)[0]:
                    self.frontier.append(topic)
                    self.kg.add_node(topic, None)

    def _pick_next_node(self):
        """从 frontier 取下一个节点"""
        if self.frontier:
            self.current_node = self.frontier.pop(0)
        elif not self.kg.is_empty():
            # frontier 为空，从 KG 选度最高的
            self.current_node = self.kg.get_high_degree_unexplored()

    async def _expand_frontier(self, node: str, findings: dict):
        """从探索结果中提取子节点，加入 frontier"""
        try:
            subtopics = await self.decomposer.decompose(node)
            for st in subtopics[:5]:  # 最多 5 个
                topic_name = st.get("topic", "") or st.get("name", "")
                if not topic_name:
                    continue
                should_exp, reason = self.kg.should_explore(topic_name, node)
                if should_exp:
                    self.kg.add_node(topic_name, node)
                    self.frontier.append(topic_name)
                else:
                    # 已存在节点，只建立关联
                    self.kg.add_relation(node, topic_name)
        except Exception as e:
            print(f"[Spider] Failed to expand frontier: {e}")

    def _reflect(self, node: str, findings: dict):
        """惊异检测 + discoveries 写入"""
        if not node:
            return
        assumptions = self.detector.generate_assumptions(node)
        surprise = self.detector.check_surprise(findings, assumptions)

        monitor = MetaCognitiveMonitor()
        quality = monitor.assess_exploration_quality(node, findings)

        self._write_discoveries(node, findings, surprise, quality)

    def _write_discoveries(self, topic: str, findings: dict, surprise: dict, quality: float):
        """写入 discoveries 文件"""
        summary = findings.get("summary", str(findings)[:500])
        os.makedirs(DISCOVERIES_DIR, exist_ok=True)
        import time
        filename = f"{int(time.time())}_{slugify(topic)}.json"
        filepath = os.path.join(DISCOVERIES_DIR, filename)

        data = {
            "topic": topic,
            "findings_summary": summary,
            "is_surprise": surprise.get("is_surprise", False),
            "surprise_level": surprise.get("surprise_level", 0.0),
            "quality_score": quality,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text[:50]


if __name__ == "__main__":
    # 可选：从命令行接收初始命题
    if len(sys.argv) > 1:
        proposition_text = sys.argv[1]
        # 写入命题文件
        import time, json, os
        prop_dir = "shared_knowledge/r1d3/propositions"
        os.makedirs(prop_dir, exist_ok=True)
        fname = f"{int(time.time())}_cli.json"
        with open(os.path.join(prop_dir, fname), "w") as f:
            json.dump({"proposition": proposition_text, "seed_topics": [proposition_text]}, f)
    engine = SpiderEngine()
    engine.run_loop()
```

### 7.5 复用已有模块

| 模块 | 复用方式 | 注意事项 |
|------|---------|---------|
| `core.explorer.Explorer` | `explorer.explore({"topic":..., "score":..., "depth":...})` | 传 dict 不是 (topic, depth) |
| `core.meta_cognitive_controller.MetaCognitiveController` | `controller.should_continue(topic)` | 只传 topic，内部查 monitor |
| `core.meta_cognitive_monitor.MetaCognitiveMonitor` | `monitor.assess_exploration_quality(topic, findings)` | 用于写 discoveries 时获取质量分 |
| `core.curiosity_decomposer.CuriosityDecomposer` | `await decomposer.decompose(topic)` | async 方法 |

### 7.6 主流程集成点

```
spider_engine.py 是独立进程，不在 curious_agent.py 的 loop 内。
启动方式：
    python3 spider_engine.py --proposition "我对 Agent 架构感兴趣"

或从 curious_agent.py 启动（可选）：
    subprocess.Popen(["python3", "spider_engine.py"])
```

### 7.7 测试方式

```python
import pytest, asyncio, tempfile, os
from spider_engine import SpiderEngine, slugify

@pytest.fixture
def engine(tmp_path):
    # 使用临时路径避免污染
    os.environ["KG_GRAPH_PATH"] = str(tmp_path / "kg.json")
    eng = SpiderEngine()
    eng.kg = KGGraph(str(tmp_path / "kg.json"))
    eng.checkpoint = Checkpoint(str(tmp_path / "ckpt.json"))
    return eng

def test_pick_next_node_from_frontier(engine):
    engine.frontier = ["a", "b", "c"]
    engine.current_node = None
    engine._pick_next_node()
    assert engine.current_node == "a"
    assert engine.frontier == ["b", "c"]

def test_force_jump_triggers_at_max_consecutive_low(engine):
    engine.current_node = "node_a"
    engine.consecutive_low_gain = MAX_CONSECUTIVE_LOW - 1
    engine.frontier = []
    engine.kg.add_node("high_degree_node", None)
    # 让 node_a 成为充分探索
    engine.kg.add_node("node_a", None)
    engine.kg.mark_fully_explored("node_a")

    # 下一次 run_once 会触发强制跳转
    # （实际上 should_continue 返回 False 才会进入跳转逻辑）
    # 这里测试的是状态转换
    engine.consecutive_low_gain = MAX_CONSECUTIVE_LOW
    engine.current_node = None  # 模拟跳转后清空
    engine._pick_next_node()
    assert engine.current_node == "high_degree_node"

def test_slugify():
    assert slugify("Attention Mechanism") == "attention-mechanism"
    assert slugify("Longformer (2020)") == "longformer-2020"
    assert len(slugify("x" * 100)) == 50
```

### 7.8 验收标准

| 编号 | 标准 | 验证方式 |
|------|------|---------|
| V1.1 | `run_loop()` 启动后持续运行，不中断 | 后台启动，观察 10 分钟 |
| V1.2 | `should_continue` 返回 False 时跳转 | mock controller.should_continue，观察日志 |
| V1.3 | 连续 3 次低收益时强制跳转到 `get_high_degree_unexplored()` | mock `should_continue` 持续返回 False |
| V1.4 | frontier 为空时从 KG 选择节点 | 清空 frontier，观察 current_node |
| V1.5 | `explorer.explore()` 传 dict 参数 | 检查源码调用方式 |
| V1.6 | `decomposer.decompose()` 使用 await | 检查源码调用方式 |

---

## 八、F3: 边际收益驱动（P0，集成在 F1 中）

### 8.1 需求描述

基于边际收益决定继续深入还是跳转。

### 8.2 设计目的

实现内在动机驱动，让蜘蛛自主判断探索方向。

### 8.3 实际 API（与文档旧版不同）

**重要纠正**：很多人以为 `should_continue` 需要外部传入 findings 来比较。
实际上 v0.2.2 的实现是**内部计算**：

```python
# MetaCognitiveController.should_continue(topic) 内部：
def should_continue(self, topic: str) -> tuple[bool, str]:
    returns = self.monitor.get_marginal_returns(topic)  # 历史列表
    # ↓ 这里不需要外部传 findings
    if not returns:
        return True, "First exploration, continue"
    last_return = returns[-1]
    if last_return < self.thresholds["min_marginal_return"]:  # 0.3
        return False, f"Marginal return ({last_return:.2f}) below threshold"
    return True, f"Marginal return healthy ({last_return:.2f})"
```

`monitor.get_marginal_returns(topic)` 返回历史 marginal return 列表。
Explorer 探索完成后，monitor 会自动更新这个列表（由 v0.2.2 框架管理）。

### 8.4 复用已有模块

| 模块 | 复用方式 |
|------|---------|
| `MetaCognitiveController.should_continue(topic)` | 直接调用，返回 `(bool, str)` |
| `MetaCognitiveMonitor.get_marginal_returns(topic)` | 用于日志/调试输出 |

### 8.5 主流程集成点

```python
# spider_engine.py run_once() 中：
should_continue, reason = self.controller.should_continue(self.current_node)
print(f"[Spider] should_continue={should_continue}, reason={reason}")
```

### 8.6 测试方式

```python
def test_should_continue_calls_internal_monitor():
    """验证 should_continue 不需要外部传 findings"""
    from core.meta_cognitive_controller import MetaCognitiveController
    from core.meta_cognitive_monitor import MetaCognitiveMonitor

    monitor = MetaCognitiveMonitor()
    controller = MetaCognitiveController(monitor)

    # 第一次调用（无历史）→ True
    ok, reason = controller.should_continue("test_topic")
    assert ok == True

    # 模拟低收益：直接操作 monitor 的边际收益
    # （实际由 explorer.explore() 后自动更新，这里测试接口契约）
    # 只要 marginal_return < 0.3 就返回 False
```

### 8.7 验收标准

| 编号 | 标准 | 验证方式 |
|------|------|---------|
| V3.1 | `should_continue(topic)` 返回 `tuple[bool, str]` | 单元测试 |
| V3.2 | 无历史数据时返回 `(True, ...)` | 单元测试 |
| V3.3 | marginal_return < 0.3 时返回 `(False, ...)` | mock monitor |

### 8.8 已知限制

- 边际收益阈值 0.3 是固定值（来自 DEFAULT_THRESHOLDS），Spider 不修改
- 阈值的动态调整是未来优化方向（v0.2.x 之外的课题）

---

## 九、F5: R1D3 命题感知（P1，并行开发）

### 9.1 需求描述

感知 R1D3 写入的命题文件，初始化蜘蛛 frontier。

### 9.2 设计目的

让 R1D3 能通过文件系统触发蜘蛛探索，实现"R1D3 命题 → CA 执行"的单向驱动。

### 9.3 实现逻辑（core/r1d3_watcher.py）

```python
import json
import os
from typing import Optional

class R1D3Watcher:
    """
    感知 shared_knowledge/r1d3/propositions/ 下的新命题文件。
    命题文件格式：
        shared_knowledge/r1d3/propositions/{timestamp}_{slug}.json
    """

    PROPOSITIONS_DIR = "shared_knowledge/r1d3/propositions"

    def __init__(self, propositions_dir: str = None):
        self.propositions_dir = propositions_dir or self.PROPOSITIONS_DIR
        self._processed: set[str] = set()  # 已处理过的文件名

    def scan_new_propositions(self) -> list[dict]:
        """
        扫描新命题文件。
        返回新增命题列表（每次调用只返回一次）。
        """
        if not os.path.exists(self.propositions_dir):
            return []

        propositions = []
        for filename in sorted(os.listdir(self.propositions_dir)):
            if not filename.endswith(".json"):
                continue
            if filename in self._processed:
                continue

            filepath = os.path.join(self.propositions_dir, filename)
            try:
                with open(filepath, encoding="utf-8") as f:
                    prop = json.load(f)
                    propositions.append(prop)
                    self._processed.add(filename)
            except Exception as e:
                print(f"[R1D3Watcher] Failed to read {filename}: {e}")
        return propositions

    def get_seed_topics(self, proposition: dict) -> list[str]:
        """
        从命题中提取 seed_topics。
        如果没有 seed_topics 字段，
        则用 LLM 从 proposition 文本中提取关键词。
        """
        topics = proposition.get("seed_topics", [])
        if topics:
            return topics

        # TODO: 如果没有 seed_topics，调用 LLM 提取
        # 目前先返回空列表
        return []
```

### 9.4 复用已有模块

无。

### 9.5 主流程集成点

```python
# spider_engine.py 的 observe() 方法：
def observe(self):
    propositions = self.watcher.scan_new_propositions()
    for prop in propositions:
        seed_topics = self.watcher.get_seed_topics(prop)
        for topic in seed_topics:
            self.frontier.append(topic)
```

### 9.6 测试方式

```python
import pytest, tempfile, os, json
from core.r1d3_watcher import R1D3Watcher

@pytest.fixture
def watcher(tmp_path):
    prop_dir = tmp_path / "propositions"
    prop_dir.mkdir()
    return R1D3Watcher(str(prop_dir))

def test_scans_new_proposition(watcher, tmp_path):
    prop_file = tmp_path / "propositions" / "123456_test.json"
    prop_file.write_text(json.dumps({
        "proposition": "我对 Agent 架构感兴趣",
        "seed_topics": ["agent", "autonomous"]
    }))

    props = watcher.scan_new_propositions()
    assert len(props) == 1
    assert props[0]["seed_topics"] == ["agent", "autonomous"]

def test_no_duplicate_scan(watcher, tmp_path):
    prop_file = tmp_path / "propositions" / "test.json"
    prop_file.write_text(json.dumps({"seed_topics": ["x"]}))

    first = watcher.scan_new_propositions()
    second = watcher.scan_new_propositions()
    assert len(first) == 1
    assert len(second) == 0  # 不重复返回

def test_ignores_non_json(watcher, tmp_path):
    txt_file = tmp_path / "propositions" / "readme.txt"
    txt_file.write_text("not json")
    assert watcher.scan_new_propositions() == []
```

### 9.7 验收标准

| 编号 | 标准 | 验证方式 |
|------|------|---------|
| V5.1 | R1D3 写入命题后能被检测到 | 手动写入文件，调用 scan_new_propositions |
| V5.2 | `get_seed_topics` 正确提取 | 单元测试 |
| V5.3 | 同一命题不会重复返回 | 单元测试 `test_no_duplicate_scan` |
| V5.4 | 非 .json 文件被忽略 | 单元测试 `test_ignores_non_json` |

### 9.8 已知限制

- 如果命题文件没有 `seed_topics` 字段，目前返回空列表（未来用 LCM 提取）
- 不处理命题的删除（processed 集合只增不减，重启后清空）

---

## 十、F4: 惊异检测（P1，依赖 F1）

### 10.1 需求描述

探索前生成假设，探索后检测"意外发现"。

### 10.2 设计目的

让蜘蛛能感知"预期之外"（surprise），这是内在动机的增强。

### 10.3 实现逻辑（core/surprise_detector.py）

```python
import json
from core.llm_manager import LLMManager

class SurpriseDetector:
    """
    惊异检测：
    探索前生成假设，探索后与 findings 对比。
    """

    def __init__(self):
        self.llm = LLMManager()

    def generate_assumptions(self, topic: str) -> list[str]:
        """
        探索前：生成 3 条假设。
        返回格式：["我以为：...", "我以为：...", "我以为：..."]
        """
        prompt = f"""关于「{topic}」，请列出 3 条你认为最可能正确的假设。
每行一条，格式必须为：我以为：{具体内容}
不要有其他格式，不要编号。"""
        try:
            response = self.llm.chat(prompt, task_type="insights")
            lines = [l.strip() for l in response.split("\n") if l.strip()]
            # 过滤掉明显不是假设的行
            assumptions = [l for l in lines if "我以为：" in l]
            return assumptions[:3]
        except Exception as e:
            print(f"[SurpriseDetector] Failed to generate assumptions: {e}")
            return []

    def check_surprise(self, findings: dict, assumptions: list[str]) -> dict:
        """
        探索后：对比 findings 和假设，判断是否有惊异。
        返回：{"is_surprise": bool, "surprise_level": float}
        """
        if not assumptions:
            return {"is_surprise": False, "surprise_level": 0.0}

        findings_text = findings.get("summary", str(findings)[:1000])
        assumptions_text = "\n".join(assumptions)

        prompt = f"""给定探索结论：
{findings_text}

检验以下假设是否被推翻或出乎意料：
{assumptions_text}

请仔细判断：
- 如果结论完全符合假设 → is_surprise=false, surprise_level=0.0
- 如果结论部分出乎意料 → is_surprise=true, surprise_level=0.3~0.6
- 如果结论完全出乎意料/颠覆认知 → is_surprise=true, surprise_level=0.7~1.0

输出 JSON（不要有其他内容）：
{{"is_surprise": true/false, "surprise_level": 0.0~1.0}}"""

        try:
            response = self.llm.chat(prompt, task_type="insights")
            # 尝试从响应中提取 JSON
            import re
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as e:
            print(f"[SurpriseDetector] Failed to check surprise: {e}")

        return {"is_surprise": False, "surprise_level": 0.0}
```

### 10.4 复用已有模块

| 模块 | 复用方式 |
|------|---------|
| `core.llm_manager.LLMManager` | `llm.chat(prompt, task_type="insights")` |

### 10.5 主流程集成点

```python
# spider_engine.py 的 _reflect() 方法中：
def _reflect(self, node: str, findings: dict):
    assumptions = self.detector.generate_assumptions(node)
    surprise = self.detector.check_surprise(findings, assumptions)
    self._write_discoveries(node, findings, surprise, quality)
```

### 10.6 测试方式

```python
import pytest
from core.surprise_detector import SurpriseDetector

def test_generate_assumptions_format(monkeypatch):
    detector = SurpriseDetector()

    def mock_chat(prompt, task_type):
        return "我以为：attention 是 O(n²)\n我以为：transformer 很高效\n我以为：需要大量数据"

    monkeypatch.setattr(detector.llm, "chat", mock_chat)
    assumptions = detector.generate_assumptions("attention")
    assert len(assumptions) == 3
    assert all("我以为：" in a for a in assumptions)

def test_check_surprise_returns_json(monkeypatch):
    detector = SurpriseDetector()

    def mock_chat(prompt, task_type):
        return '{"is_surprise": true, "surprise_level": 0.8}'

    monkeypatch.setattr(detector.llm, "chat", mock_chat)
    result = detector.check_surprise({"summary": "xxx"}, ["我以为：x"])
    assert result["is_surprise"] == True
    assert result["surprise_level"] == 0.8
```

### 10.7 验收标准

| 编号 | 标准 | 验证方式 |
|------|------|---------|
| V4.1 | 每个 topic 生成 3 条假设 | mock LLM，检查返回数量 |
| V4.2 | findings 与假设不符时 is_surprise=True | mock LLM 返回 `{"is_surprise": true, ...}` |
| V4.3 | surprise_level 在 0.0~1.0 范围 | 边界测试 |
| V4.4 | LLM 异常时优雅降级返回默认值 | monkeypatch 抛异常，验证返回值 |

### 10.8 已知限制

- 依赖 LLM 生成假设和判断惊异，有 token 消耗
- 假设质量取决于 LLM 对 topic 的预训练知识
- surprise_level 是 LLM 主观判断，不是精确指标

---

## 十一、F7: discoveries 写入（P1，依赖 F1）

### 11.1 需求描述

每次探索完成后写入 discoveries/ 目录，供 R1D3 感知。

### 11.2 设计目的

建立 CA → R1D3 的信息通道（R1D3 心跳时扫描此目录）。

### 11.3 实现逻辑

已集成在 `spider_engine.py` 的 `_write_discoveries()` 方法中（见 F1 章节）。
如需独立测试：

```python
def write_discoveries(topic: str, findings: dict, surprise: dict, quality: float):
    os.makedirs(DISCOVERIES_DIR, exist_ok=True)
    import time, re
    filename = f"{int(time.time())}_{slugify(topic)}.json"
    filepath = os.path.join(DISCOVERIES_DIR, filename)

    data = {
        "topic": topic,
        "findings_summary": findings.get("summary", str(findings)[:500]),
        "is_surprise": surprise.get("is_surprise", False),
        "surprise_level": surprise.get("surprise_level", 0.0),
        "quality_score": quality,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return filepath
```

### 11.4 复用已有模块

无。

### 11.5 主流程集成点

```
SpiderEngine._reflect() 末尾调用 self._write_discoveries(...)
```

### 11.6 测试方式

```python
import pytest, tempfile, os, json
from spider_engine import slugify

def test_write_discovers_creates_file(tmp_path):
    disc_dir = tmp_path / "discoveries"
    disc_dir.mkdir()

    topic = "test_topic"
    findings = {"summary": "测试发现内容"}
    surprise = {"is_surprise": True, "surprise_level": 0.8}
    quality = 7.5

    import time
    filename = f"{int(time.time())}_{slugify(topic)}.json"
    filepath = disc_dir / filename
    with open(filepath, "w") as f:
        json.dump({
            "topic": topic,
            "findings_summary": findings["summary"],
            "is_surprise": surprise["is_surprise"],
            "surprise_level": surprise["surprise_level"],
            "quality_score": quality,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
        }, f)

    files = list(disc_dir.glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["is_surprise"] == True
    assert data["quality_score"] == 7.5
```

### 11.7 验收标准

| 编号 | 标准 | 验证方式 |
|------|------|---------|
| V7.1 | 每次探索完成写入 discoveries/ | 检查文件数量变化 |
| V7.2 | 文件包含 `is_surprise`, `quality_score`, `timestamp` | 检查文件内容 |
| V7.3 | R1D3 心跳能感知新文件（v0.2.5 验证） | 后续集成测试 |

### 11.8 已知限制

- 文件名用时间戳，同一秒内多次探索会覆盖（实际概率极低）
- discoveries 文件只追加不删除，长期运行会积累（未来加清理策略）

---

## 十二、F8: KG 图谱共享（P1，基础设施）

### 12.1 需求描述

KG 图谱作为 R1D3 和 CA 的共享知识源。

### 12.2 设计目的

为 v0.2.5 的 KG Search Skill 奠定基础。

### 12.3 实现逻辑

KG 图谱存储在 `shared_knowledge/ca/kg/kg_graph.json`。
格式见 F2 章节的"节点数据结构"。

### 12.4 主流程集成点

```
SpiderEngine.run_once() 末尾：
    self.kg.save()  # 每次探索后自动保存

R1D3 心跳（v0.2.5 KG Search Skill）：
    KGGraph("shared_knowledge/ca/kg/kg_graph.json").load()
    # 然后做多跳推理查询
```

### 12.5 验收标准

| 编号 | 标准 | 验证方式 |
|------|------|---------|
| V8.1 | kg_graph.json 格式符合 F2 数据结构 | cat 验证 |
| V8.2 | R1D3 进程可读取 kg_graph.json | `open().read()` 不报错 |
| V8.3 | v0.2.5 KG Search Skill 可查询（后续验证） | v0.2.5 里程碑 |

### 12.6 已知限制

- KG 图谱无访问控制，任何能读 shared_knowledge 的进程都可修改
- v0.2.5 需要考虑读写锁或版本管理

---

## 十三、接口协议汇总

### 13.1 R1D3 → CA：命题

**路径**：`shared_knowledge/r1d3/propositions/{timestamp}_{slug}.json`

```json
{
  "proposition": "我对 Agent 架构感兴趣",
  "seed_topics": ["agent", "autonomous agent"],
  "depth_preference": "deep",
  "timestamp": "2026-03-25T18:00:00"
}
```

### 13.2 CA → R1D3：discoveries

**路径**：`shared_knowledge/ca/discoveries/{timestamp}_{topic}.json`

```json
{
  "topic": "attention mechanism",
  "findings_summary": "Longformer 使用滑动窗口...",
  "is_surprise": true,
  "surprise_level": 0.85,
  "quality_score": 8.2,
  "timestamp": "2026-03-25T18:05:00"
}
```

### 13.3 KG 图谱

**路径**：`shared_knowledge/ca/kg/kg_graph.json`

```json
{
  "nodes": {
    "attention mechanism": {
      "parents": ["transformer"],
      "children": ["self-attention"],
      "explored": true,
      "fully_explored": false,
      "explored_at": "2026-03-25T18:00:00",
      "explored_by": ["transformer"],
      "findings_summary": "..."
    }
  },
  "edges": [
    {"from": "transformer", "to": "attention mechanism", "relation": "uses"}
  ]
}
```

### 13.4 checkpoint

**路径**：`state/spider_checkpoint.json`

```json
{
  "last_loop_time": "2026-03-25T18:00:00",
  "current_node": "attention mechanism",
  "frontier": ["self-attention", "multi-head"],
  "visited": ["transformer", "attention mechanism"],
  "consecutive_low_gain": 0,
  "step_count": 42,
  "kg_path": "shared_knowledge/ca/kg/kg_graph.json"
}
```

---

## 十四、运行手册

### 14.1 启动

```bash
# 方式1：从命令行传入初始命题
python3 spider_engine.py --proposition "我对 Agent 架构感兴趣"

# 方式2：后台运行
nohup python3 spider_engine.py > logs/spider.log 2>&1 &

# 方式3：从 curious_agent.py 调用（可选）
subprocess.Popen(["python3", "spider_engine.py"])
```

### 14.2 停止

```bash
kill -TERM $(pgrep -f "spider_engine.py")
```

### 14.3 查看状态

```bash
# KG 图谱
cat shared_knowledge/ca/kg/kg_graph.json | python3 -m json.tool

# checkpoint
cat state/spider_checkpoint.json

# discoveries
ls -lt shared_knowledge/ca/discoveries/ | head -10
```

### 14.4 配置

| 常量 | 默认值 | 说明 |
|------|--------|------|
| `LOOP_INTERVAL` | 30 秒 | 主循环间隔 |
| `MIN_MARGINAL_RETURN` | 0.3 | 边际收益阈值（复用 v0.2.2） |
| `MAX_CONSECUTIVE_LOW` | 3 | 连续低收益次数上限 |
| `DEFAULT_DEPTH` | 2 | 探索深度（medium） |

---

## 十五、验收标准总览

| 验收项 | 对应特性 | 标准 |
|--------|---------|------|
| V2.1~V2.5 | F2 KG 图 | 多父节点、去重、持久化 |
| V6.1~V6.4 | F6 Checkpoint | kill 恢复、格式正确 |
| V1.1~V1.6 | F1 Spider | 持续运行、跳转、force jump |
| V3.1~V3.3 | F3 边际收益 | should_continue 接口契约 |
| V5.1~V5.4 | F5 Watcher | 命题扫描、去重 |
| V4.1~V4.4 | F4 Surprise | 假设生成、惊异判断 |
| V7.1~V7.3 | F7 Discov. | discoveries 文件正确 |
| V8.1~V8.3 | F8 共享 | kg_graph.json 可读 |

---

## 十六、已知限制汇总

| 特性 | 限制 |
|------|------|
| F1 Spider | KG 所有节点已探索且 frontier 为空时等待新命题 |
| F2 KG | 度相同时按字母顺序选择（不保证最优） |
| F3 边际收益 | 阈值 0.3 固定，不动态调整 |
| F4 Surprise | 依赖 LLM，token 消耗 |
| F5 Watcher | 无 seed_topics 时返回空列表 |
| F7 Discov. | 同秒多次探索可能覆盖文件 |
| F8 共享 | 无访问控制，v0.2.5 需加读写锁 |

---

## 十七、下一步

- **v0.2.4 实现**：完成 Spider Engine + KG Graph（本文）
- **v0.2.5**：R1D3 KG Search Skill，支持多跳推理查询 kg_graph.json

---

_文档版本: v0.2.4_
_创建时间: 2026-03-25_
_最后更新: 2026-03-25 19:00_