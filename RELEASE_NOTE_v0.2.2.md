# Release Note - v0.2.2

## 🎯 核心主题：元认知与智能控制

v0.2.2 解决了 v0.2.1 生产环境中的两个关键问题：

1. **无限循环问题**: 同一话题被无意义重复探索 10+ 次
2. **价值缺失问题**: 60 次探索，0 次通知用户

**解决方案：元认知监控器 (Metacognitive Monitor) + MGV 循环架构**

---

## 🧠 主要特性

### 1. 元认知监控器 (MetaCognitiveMonitor)

**三维质量评分算法**:
```
Quality = new_discovery_rate × 0.35
        + depth_improvement × 0.35
        + user_relevance × 0.30
```

| 维度 | 权重 | 说明 |
|------|------|------|
| **新发现率** | 35% | 新关键词 / 总关键词 |
| **深度提升** | 35% | 内容长度、来源数、论文数 |
| **用户相关性** | 30% | 与用户兴趣的重叠度 |

**质量范围**: 0-10 分，默认阈值 7.0 触发通知

### 2. 元认知控制器 (MetaCognitiveController)

**三大决策函数**:

```python
should_explore(topic)     # 检查探索次数上限 (默认 max 3)
should_continue(topic)    # 检查边际收益 (默认 min 0.3)
should_notify(topic)      # 检查质量阈值 (默认 ≥7.0)
```

**智能停止机制**:
- 达到最大探索次数 → 阻止继续
- 边际收益连续 2 次低于阈值 → 停止探索
- 质量低于通知阈值 → 静默记录

### 3. MGV 循环架构

```
┌─────────────────────────────────────────────────────────┐
│  Monitor（监控层）                                       │
│  • 探索前检查 should_explore()                          │
│  • 质量评估 assess_quality()                            │
│  • 边际收益计算 compute_marginal()                      │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Generate（生成层）                                      │
│  • 执行分层探索 (shallow/medium/deep)                    │
│  • 关键词提取、论文分析、LLM洞察                         │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Verify（验证层）                                        │
│  • 通知决策 should_notify()                             │
│  • 继续决策 should_continue()                           │
│  • 事件触发 EventBus.emit()                             │
└─────────────────────────────────────────────────────────┘
```

### 4. 事件总线 (EventBus)

**解耦的事件驱动架构**:

```python
EventBus.subscribe("discovery.high_quality", handler)
EventBus.emit("discovery.high_quality", {
    "topic": topic,
    "quality": quality,
    "formatted": formatted
})
```

**事件类型**:
- `discovery.high_quality` → 写入发现库
- `notification.external` → 飞书/Discord/钉钉
- `exploration.blocked` → 记录日志
- `exploration.completed` → 标记完成

### 5. 多 LLM 路由 (LLMManager)

**两层路由架构**:

```
┌──────────────────────────────────────┐
│           LLMManager                  │
├──────────────────────────────────────┤
│  Provider 1 (volcengine)              │
│    ├── Model A: ark-code-latest       │
│    └── Model B: deepseek-chat         │
│  Provider 2 (openai)                  │
│    ├── Model C: gpt-4o                │
│    └── Model D: gpt-4o-mini           │
└──────────────────────────────────────┘
```

**路由策略**:
- `capability`: 按 task_type 匹配能力
- `weighted_rr`: 加权轮询负载均衡

**使用示例**:
```python
llm.chat(prompt, task_type="insights")  # 自动路由到最适合的模型
```

### 6. 配置管理 (Config)

**config.json 结构**:
```json
{
  "meta_cognitive": {
    "max_explore_count": 3,
    "min_marginal_return": 0.3,
    "high_quality_threshold": 7.0
  },
  "user_interests": ["agent framework", "self-reflection"],
  "llm": {
    "providers": {
      "volcengine": { ... },
      "openai": { ... }
    }
  }
}
```

---

## 🔧 API 新增

### 元认知 API 端点

```bash
# 获取完整元认知状态
GET /api/metacognitive/state

# 检查特定话题决策
GET /api/metacognitive/check?topic=xxx

# 获取话题探索历史
GET /api/metacognitive/history/xxx

# 获取已完成话题列表
GET /api/metacognitive/topics/completed
```

**响应示例**:
```json
{
  "status": "ok",
  "summary": {
    "completed_topics": 5,
    "total_explorations": 23,
    "topics_with_history": 12
  }
}
```

---

## 🎨 Web UI 增强

### 元认知状态面板

新增「🧠 元认知状态」面板，实时显示：

- **已完成话题数**: 被阻止/完成的话题统计
- **总探索次数**: 系统累计探索计数
- **有历史话题数**: 有探索记录的话题数
- **已完成话题列表**: 话题名 + 完成原因

---

## 📊 解决的问题

| 问题 | v0.2.1 | v0.2.2 | 改善 |
|------|--------|--------|------|
| 无限循环 | 同一话题探索 10+ 次 | 最多 3 次 | 阻止无意义重复 |
| 价值缺失 | 60 次探索 0 通知 | 仅高质量通知 | 提升信噪比 |
| 资源浪费 | 低价值探索持续 | 边际收益检测 | 自动停止低价值 |
| 通知噪音 | 所有探索都通知 | 仅 ≥7.0 通知 | 减少打扰 |

---

## 🛠️ 新增模块

```
core/
├── llm_manager.py              # 多 LLM 路由
├── meta_cognitive_monitor.py   # 元认知监控器
├── meta_cognitive_controller.py # 元认知控制器
├── event_bus.py                # 事件总线
└── config.py                   # 配置管理

tests/
├── test_llm_manager.py         # 6 个测试
├── test_meta_cognitive_monitor.py  # 22 个测试
├── test_meta_cognitive_controller.py # 14 个测试
└── test_event_bus.py           # 6 个测试
```

---

## ✅ 测试覆盖

**新功能测试**: 48 个测试，100% 通过

| 模块 | 测试数 | 覆盖率 |
|------|--------|--------|
| LLMManager | 6 | 100% |
| MetaCognitiveMonitor | 22 | 100% |
| MetaCognitiveController | 14 | 100% |
| EventBus | 6 | 100% |

---

## 📝 使用示例

### 元认知决策检查

```python
from core.meta_cognitive_monitor import MetaCognitiveMonitor
from core.meta_cognitive_controller import MetaCognitiveController

monitor = MetaCognitiveMonitor()
controller = MetaCognitiveController(monitor)

# 检查是否应该探索
allowed, reason = controller.should_explore("transformer")
print(f"Should explore: {allowed}, Reason: {reason}")

# 获取完整决策摘要
summary = controller.get_decision_summary("transformer")
print(summary)
```

### 事件订阅

```python
from core.event_bus import EventBus

def on_high_quality_discovery(payload):
    print(f"High quality: {payload['topic']} (score: {payload['quality']})")

EventBus.subscribe("discovery.high_quality", on_high_quality_discovery)
```

---

## 🔄 迁移指南

### 从 v0.2.1 迁移

1. **复制配置模板**:
   ```bash
   cp config.json.example config.json
   # 编辑 config.json 添加你的 API keys
   ```

2. **无需修改现有代码**: 所有变更向后兼容

3. **可选**: 调整阈值参数以适应你的场景

---

## 🔮 后续计划

v0.3 方向：
- SQLite 持久化
- 向量数据库集成
- D3.js 知识图谱可视化
- 飞书/Discord 通知集成

---

_发布时间: 2026-03-21_  
_版本: v0.2.2_  
_贡献者: OpenCode Agent_
