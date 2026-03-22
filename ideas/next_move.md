# Curious Agent v0.2.3 — 核心改进：好奇心分解与树状生长

> 核心洞察（weNix, 2026-03-22）：好奇心应该是树状生长的，不是平铺随机搜索
> 状态：规划中

---

## 📋 Phase 索引（按开发顺序）

| 开发优先级 | Phase | 主题 | 文件 |
|-----------|-------|------|------|
| 🥇 **1st** | Phase 1 | 好奇心分解引擎（四级级联 + 多 Provider 验证） | `next_move_v0.2.3-phase1_development.md` |
| 🥈 **2nd** | Phase 2 | 质量评估升级（Quality v2 / CompetenceTracker） | `next_move_v0.2.3-phase2_development.md` |
| 🥉 **3rd** | Phase 3 | 行为闭环（Agent-Behavior-Writer） | `next_move_v0.2.3-phase3_development.md` |

---

## 🔀 开发顺序（按依赖关系排列）

| 顺序 | Phase | 主题 | 理由 |
|------|-------|------|------|
| **1st** | Phase 3 | 好奇心分解引擎 | 上游阻塞——不分解，后面全浪费在噪音上 |
| **2nd** | Phase 2 | 质量评估升级 | 独立——只要有 findings 就能评估 |
| **3rd** | Phase 1 | 行为闭环 | 依赖 Phase 2 的 quality 门槛就位后接入 |

Phase 3 最关键，Phase 2 最独立，Phase 1 最晚接。

---

## 问题：当前探索是「平铺式」，不是「树状生长式」

### 当我给你一个词「agent」时，当前系统的行为：

```
输入：agent
↓
搜索：agent（孤零零一个词）
↓
结果：建筑公司 / 词典定义 / 噪音
↓
结论：质量低，存进知识库，结束
```

**问题**：不知道「agent」由什么组成，搜出来的全是噪音。

### 正确的模式：树状分解

```
输入：agent
↓
好奇心分解器识别核心组成部分：
  agent
  ├── 记忆（memory）
  ├── 上下文窗口（context window）
  ├── 规划（planning）
  ├── 工具使用（tool use）
  └── harness ⭐（最近火热）
       ↓
对 harness 继续分解：
  harness
  ├── agent runtime
  ├── MCP（Model Context Protocol）
  └── ACP（Agent Communication Protocol）
       ↓
对每个叶子节点探索，完成后写回父节点
```

---

## 核心概念：好奇心的「有根生长」

### 三种生长模式

| 模式 | 描述 | 示例 |
|------|------|------|
| **向下分解** | 识别 topic 的组成部分，向下钻 | agent → memory + planning + harness |
| **横向扩展** | 同一层级的相邻概念 | memory → episodic + semantic + working |
| **向上抽象** | 从具体例子归纳共性 | smolagents → lightweight agent framework |

### 生长终止条件

```
遇到以下条件时停止生长：
- 叶子节点已是被充分探索的已知概念（quality 足够高）
- 边际收益递减（多次探索后 marginal_return < 0.2）
- 到达预设深度上限（防止组合爆炸）
```

---

## 架构改动：新增 CuriosityDecomposer

### 位置

```
curious_agent/
└── core/
    ├── knowledge_graph.py      # 现有
    ├── curiosity_engine.py    # 现有
    ├── explorer.py            # 现有
    └── curiosity_decomposer.py  # 新增
```

### Decomposer 接口

```python
class CuriosityDecomposer:
    """
    好奇心分解器
    输入：一个 topic
    输出：一组子 topic + 关系描述
    """
    
    def decompose(self, topic: str) -> list[dict]:
        """
        Returns:
            [
                {
                    "sub_topic": "memory",
                    "relation": "component",       # component | sibling | abstract
                    "depth": 1,
                    "reason": "agent 的核心组成部分"
                },
                ...
            ]
        """
```

### 分解策略（四步级联）

**Step 1: LLM 推理生成候选**
- 给定领域，常见分解方式是什么
- 例：「agent」→ ["agent memory", "agent planning", "agent harness", ...]
- 允许有噪音候选（后续 Step 2 过滤）

**Step 2: 搜索验证（多 Provider 并行）**
- LLM 生成的每个候选 sub-topic，向多个搜索 Provider 并行查询
- 统计每个 Provider 返回的结果数量
- 过滤逻辑：
  - 0 个 Provider 有结果 → 丢弃（LLM 幻觉）
  - 1 个 Provider 有结果 → 可疑，降低优先级
  - 2+ 个 Provider 有结果 → 有效，保留
- 信号强度分级：
  - 合计 < 10 结果 → 弱信号，低优先级
  - 合计 10-100 → 中等信号，正常入队
  - 合计 100+ → 强信号，高优先级

**Step 3: 知识图谱补充**
- 从 KG 已有结构推断父子关系
- 如果 graph 中已有 agent → memory 的边，直接继承
- 探索结果写回 KG 时，建立 component_of 边

**Step 4: 澄清机制**
- 如果 Step 1-3 都无法判断领域属性
- 抛出 ClarificationNeeded → OpenClaw 通知用户澄清
- 「agent」是什么领域？AI / 软件开发 / 其他？

---

## 集成到探索流程

### 新探索流程

```
用户输入/队列触发：agent
    ↓
CuriosityDecomposer.decompose("agent")
    ↓
生成子 topic 列表：["agent memory", "agent planning", "agent harness", ...]
    ↓
高质量子 topic 入队（不是全部入队，做质量预筛）
    ↓
取 Top 子 topic 开始探索
    ↓
探索结果写回父节点（agent 的知识图谱节点更新）
    ↓
探索完成后 → 再次 decompose（继续生长）
```

### 关键改动点

**curious_agent.py**
- `run_one_cycle()` 探索前调用 `decomposer.decompose()`
- 分解结果写入 knowledge graph（建立父子关系边）

**curiosity_engine.py**
- 新增：`decompose_and_queue()` 函数
- 修改：`select_next()` 优先选有未探索子节点的父节点

**knowledge_graph.py**
- 新增：边类型 `parent_of`, `child_of`, `component_of`
- 新增：`get_children()`, `get_parent()` 查询

---

## 质量门控：入队前预筛

### 当前问题

太泛的词（"Agent"、"Cognitive"）能进队列。

### 解决方案：入队质量门

```python
def should_queue(topic: str) -> tuple[bool, str]:
    """
    判断 topic 是否应该入队
    Returns: (should_queue, reason)
    """
    # 1. 长度太短 → 拒绝
    if len(topic.split()) < 2:
        return False, "too short, needs domain限定"
    
    # 2. 泛词黑名单 → 拒绝或改写
    if topic.lower() in BLACKLIST:
        return False, f"in blacklist: {topic}"
    
    # 3. 已在队列相似项 → 合并
    if is_similar_to_existing(topic):
        return False, "duplicate/similar in queue"
    
    # 4. 通过
    return True, "ok"
```

### 泛词黑名单（初始集）

```python
BLACKLIST = {
    "agent", "agents", "cognit", "cognition",  # 太泛
    "architecture", "architectures",              # 多义词
    "system", "systems",                        # 太泛
    "overview", "introduction", "what is",      # 非实质
}
```

---

## 与知识图谱的深度集成

### 树状结构在 KG 中的表示

```json
{
  "topics": {
    "agent": {
      "status": "partial",
      "components": ["agent_memory", "agent_planning", "agent_harness"],
      "explored_components": ["agent_memory"]
    },
    "agent_harness": {
      "status": "partial", 
      "components": ["harness_mcp", "harness_acp"],
      "explored_components": []
    },
    "agent_memory": {
      "status": "complete",
      "findings": "..."
    }
  }
}
```

### 探索优先级

```
优先选：status=partial 且有未探索组件的节点
其次：全新节点（从未探索过）
最后：已完成节点（检查边际收益）
```

---

## 实施计划

### Phase 1：最小可运行（v0.2.3-alpha）

- [ ] 实现 `curiosity_decomposer.py`（仅 LLM 推理策略）
- [ ] 入队质量门（黑名单 + 长度检查）
- [ ] 修改 `curious_agent.py` 在探索前调用 decompose
- [ ] 修改 `knowledge_graph.py` 支持父子关系

### Phase 2：知识图谱集成（v0.2.3-beta）

- [ ] 分解结果写入 KG（建立 component_of 边）
- [ ] `select_next()` 优先选有未探索子节点的父节点
- [ ] 探索结果写回父节点

### Phase 3：多策略分解（v0.2.3）

- [ ] 添加 KG 推理策略
- [ ] 添加搜索趋势推断策略
- [ ] 实现生长终止条件判断

---

## 验收标准

```
输入：agent
输出：["agent memory", "agent planning", "agent context", "agent tool use", "agent harness"]
      （5个左右具体子 topic，不是50个噪音词）

质量：
- 子 topic 覆盖率 > 80%（主流组件都被识别）
- 噪音率 < 20%（子 topic 不是建筑公司之类）
- 分解速度 < 2秒
```

---

## 副作用：解决「通知淹没」问题

当好奇心是树状生长时：
- 系统知道哪些分支已经探索完、哪些还没
- 通知用户时，只报告「agent 的 harness 分支发现了 X」，不是「agent 这个词发现了噪音」
- 用户看到的是**有结构的知识**，不是随机词列表

---

_文档版本: v0.2.3 规划_
_创建时间: 2026-03-22_
