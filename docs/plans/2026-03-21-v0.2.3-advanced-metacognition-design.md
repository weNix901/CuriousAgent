# Curious Agent v0.2.3 — 高级元认知能力

> 从 v0.2.2 暂缓的功能合集  
> 依赖于 v0.2.2 的 Monitor-Generate-Verify 基础架构  
> **不训练模型，所有学习通过非参数化方式实现**  
> 设计者：R1D3-researcher + weNix | 验收者：weNix  
> 创建时间：2026-03-21

---

## 一、功能清单（从 v0.2.2 暂缓移入）

> ⚠️ P1 功能（API 端点 + Web UI 状态区域）已移入 v0.2.2，本文档仅包含以下高级功能。

### F1: DK-UV 自动缺口检测

**功能描述**：从探索结果中自动发现知识缺口，加入好奇心队列。

**算法思路**：
```python
class DKUVDector:
    """
    DK-UV: Detecting Known and Unknown
    知道自己知道 / 不知道自己不知道
    """
    
    def detect_gaps(self, topic: str, findings: dict, knowledge_graph) -> list:
        """
        从探索发现中检测知识缺口
        
        方法：
        1. 从 findings 中提取子话题（LLM 抽取）
        2. 检查这些子话题是否在知识图谱中
        3. 不存在 → 标记为 DK-UV（Unknown-Visible）
        4. 存在但深度 < 5 → 标记为 PK（Partially-Known）
        """
        pass
```

**待解决问题**：
- LLM 抽取子话题的准确率
- 误报率控制（噪声话题过滤）
- 与人工注入的优先级排序

**验收测试**：
```bash
# 运行一轮探索后检查
python3 curious_agent.py --run
# state.json 中 known_gaps 应有新条目
grep "known_gaps" knowledge/state.json | grep -v "\[\]"
```

---

### F2: 动态 α 参数调节

**功能描述**：根据边际收益趋势自动调整 α 参数（人类意图 vs 自主探索的权重）。

**算法思路**：
```python
def adjust_alpha(marginal_returns: list, current_alpha: float) -> float:
    """
    基于边际收益趋势调整 α
    
    规则：
    - 边际收益持续上升 → α 减小（更多自主探索）
    - 边际收益持续下降 → α 增大（回归人工意图）
    - α 范围：[0.2, 0.8]
    """
    if len(marginal_returns) < 3:
        return current_alpha
    
    recent = marginal_returns[-3:]
    trend = sum(recent) / len(recent)
    
    if trend > 0.5:
        # 收益好 → 减少人工干预
        return max(0.2, current_alpha - 0.1)
    elif trend < 0.2:
        # 收益差 → 增加人工引导
        return min(0.8, current_alpha + 0.1)
    else:
        return current_alpha
```

**待解决问题**：
- 调整节奏（多久调一次）
- 突变的边际收益如何平滑处理
- 与用户手动 α 设置的冲突处理

**验收测试**：
```bash
# 连续执行多轮低质量探索
for i in {1..5}; do python3 curious_agent.py --run --run-depth shallow; done
# 检查 state.json 中 alpha_history 是否有调整记录
```

---

### F3: D3.js 知识关联图可视化

**功能描述**：在 Web UI 上显示知识节点的关系网络。

**实现方式**：
```
Web UI 新增 Tab: "🔗 知识图谱"

┌──────────────────────────────────────────────────────────────┐
│  🔗 知识关联图                                    [刷新]     │
├──────────────────────────────────────────────────────────────┤
│  筛选:  [全部] [UV缺口] [PK缺口] [已掌握]                  │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │                                                      │    │
│  │        ● Agent 自主意识                              │    │
│  │       /  \                                          │    │
│  │      ●    ●                                         │    │
│  │   (PK)  (UV)                                        │    │
│  │                                                      │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  图例: 🔴 UV(未知)  🟡 PK(部分已知)  🟢 已掌握             │
└──────────────────────────────────────────────────────────────┘
```

**技术依赖**：
- D3.js 力导向图库
- 知识图谱的节点关系数据（从 state.json 提取）
- 前端状态管理（刷新、筛选交互）

**待解决问题**：
- 大规模节点（>100）的性能
- 节点布局稳定性
- 与现有 Web UI 的技术栈整合

**验收测试**：
```bash
# 打开 Web UI
# 应能看到"🔗 知识图谱"Tab
# 点击节点应有交互效果
```

---

## 二、额外规划功能

### F4: 飞书通知集成

**功能描述**：高价值发现自动推送飞书消息。

**实现方式**：
```python
def notify_user(topic: str, findings: dict, quality: float):
    if quality < 7.0:
        return  # 质量不够，不通知
    
    message = f"""
🔍 好奇发现：{topic}
评分：{quality}/10
---
{findings['summary'][:200]}...
"""
    send_feishu_message(message)
```

**待解决问题**：
- 飞书 webhook 配置
- 消息格式优化（卡片 vs 文本）
- 通知频率控制（避免轰炸）

---

### F5: SQLite 持久化

**功能描述**：替换 JSON 文件存储，提升查询性能。

**迁移步骤**：
1. 导出 JSON 数据到 SQLite
2. 修改 knowledge_graph.py 的读写逻辑
3. 保留 JSON 作为备份格式
4. 更新 API 响应格式

**验收测试**：
```bash
# 数据迁移后
python3 curious_agent.py --run
# 验证 state.json 和 SQLite 数据一致
```

---

## 三、新增核心功能

### F6: 情境缓冲区（Episodic Buffer）

**理论来源**：
- Baddeley (2000): 工作记忆的情境缓冲区组件
- arXiv:2603.07670v1 (2026-03): Memory for Autonomous LLM Agents — formalizes agent memory as write-manage-read loop
- arXiv:2602.19320v1 (2026-02): Anatomy of Agentic Memory — four memory structures taxonomy

**约束**：不训练模型，不更新权重，所有实现通过非参数化方式。

#### 6.1 核心思想

```
Baddeley (2000) 原始设计：
  情境缓冲区 = 有限容量的临时存储，连接工作记忆各组件和长时记忆
  → 多模态整合 + 时序编码 + 与长时记忆通信

Curious Agent 实现：
  情境缓冲区 = 连接"当前探索状态"和"持久知识"的临时存储
  → 整合：当前话题 + 探索进度 + 队列状态 + 最近发现
  → 连接：Knowledge Graph（长时记忆）
```

**与 F6 Reflexion 的关系**：
- F6（Reflexion）：专注"口头反思"的学习机制
- F6（Episodic Buffer）：专注"当前情境的整合"能力
- 两者互补，Reflexion 的反思存在 Episodic Buffer 中

#### 6.2 为什么可行（可行性评估）

| 评估维度 | 状态 | 说明 |
|---------|------|------|
| **理论基础** | ✅ 成熟 | Baddeley 2000 + 2026 年最新 LLM Agent 记忆综述 |
| **已有参考** | ✅ 充分 | Generative Agents (Park 2023), Reflexion (Shinn 2023) |
| **实现技术** | ✅ 可行 | Embedding 相似度、LLM 摘要、结构化存储 |
| **无需训练** | ✅ 满足 | 纯非参数化，RAG + 提示词工程 |
| **数据来源** | ✅ 有 | CuriosityEngine 已有探索记录 |
| **容量管理** | ⚠️ 需设计 | 缓冲区容量需要主动管理 |
| **检索准确性** | ⚠️ 依赖 Embedding | 语义匹配可能不准确 |

**关键风险**：情境缓冲区容量需要主动管理（遗忘/压缩），否则会随时间无限增长。

#### 6.3 模块设计

```python
class EpisodicBuffer:
    """
    情境缓冲区 — 整合当前探索状态
    
    职责：
    1. 整合多路信息为"当前情境"
    2. 管理缓冲区容量（遗忘/压缩）
    3. 与 Knowledge Graph（长时记忆）通信
    """
    
    def __init__(self, kg: KnowledgeGraph):
        self.kg = kg
        # 缓冲区容量（ episodes 上限）
        self.capacity = 50
    
    def compose_current_situation(self, topic: str, 
                                  queue_snapshot: list,
                                  recent_findings: dict,
                                  exploration_state: dict) -> str:
        """
        整合多路信息，生成当前情境描述
        
        整合内容：
        - 当前探索的话题
        - 好奇心队列状态
        - 最近发现摘要
        - 探索进度（Layer 1/2/3）
        
        Returns:
            当前情境的结构化描述（用于注入 prompt）
        """
        pass
    
    def store_episode(self, topic: str, situation: str, 
                      outcome: dict, reflections: list):
        """
        存储一个情境片段（episode）
        
        episode = {
            "id": uuid,
            "topic": topic,
            "situation": situation,  # 整合后的情境描述
            "outcome": outcome,       # 探索结果
            "reflections": reflections,  # F6 的口头反思
            "timestamp": datetime.now().isoformat(),
            "context_embedding": embedding(situation)
        }
        """
        # 检查容量，超出则遗忘最旧的
        if len(self.episodes) >= self.capacity:
            self._evict_oldest()
        
        self.episodes.append(episode)
        self._persist()
    
    def retrieve_relevant(self, current_topic: str, 
                         current_situation: str,
                         limit: int = 5) -> list:
        """
        检索与当前情境相关的历史 episodes
        
        检索方式：
        1. 话题关键词匹配（快速过滤）
        2. 情境 embedding 相似度（语义匹配）
        
        Returns:
            [{"episode": {...}, "relevance": 0.8}, ...]
        """
        pass
    
    def _evict_oldest(self):
        """
        遗忘最旧的 episode
        
        策略：
        1. 直接遗忘最旧的（FIFO）
        2. 或基于重要性分数遗忘
        3. 或基于时间衰减概率遗忘
        """
        pass
    
    def compress_episodes(self):
        """
        压缩 episodes
        
        策略：
        1. 相邻相似 episodes 合并
        2. 低重要性的 episodes 摘要
        3. 删除已被 Knowledge Graph 吸收的知识
        """
        pass
```

#### 6.4 与 MetaCognitiveController 的集成

```python
class MetaCognitiveController:
    """
    元认知控制器现在充当"中央执行系统"
    
    情境缓冲区 = 中央执行系统的工作空间
    """
    
    def __init__(self, monitor, buffer: EpisodicBuffer):
        self.monitor = monitor
        self.buffer = buffer
    
    def decide_action(self, topic: str) -> tuple[str, str]:
        # === 1. 组成当前情境 ===
        situation = self.buffer.compose_current_situation(
            topic=topic,
            queue_snapshot=self.kg.get_queue_snapshot(),
            recent_findings=self.kg.get_recent_findings(topic),
            exploration_state=self.monitor.get_state(topic)
        )
        
        # === 2. 检索相关历史 ===
        relevant = self.buffer.retrieve_relevant(topic, situation, limit=3)
        
        # === 3. 中央执行决策 ===
        decision_prompt = f"""
当前情境：
{situation}

相关历史：
{relevant}

决策：
1. 是否继续当前话题探索？
2. 是否切换到其他话题？
3. 是否通知用户？
"""
        # LLM 调用...
        
        return decision, reason
```

#### 6.5 数据格式

```json
{
  "episodic_buffer": {
    "capacity": 50,
    "episodes": [
      {
        "id": "ep-uuid-xxx",
        "topic": "metacognition in LLM",
        "situation": "正在执行 Layer 3 深度探索...已发现 arXiv:2510.16374...",
        "outcome": {
          "quality": 7.5,
          "marginal_return": 0.4,
          "layers_explored": [1, 2, 3],
          "papers_analyzed": 3
        },
        "reflections": [
          "Monitor-Generate-Verify 框架值得深入..."
        ],
        "timestamp": "2026-03-21T12:00:00Z",
        "importance": 8.5
      }
    ]
  }
}
```

#### 6.6 与现有模块的关系

```
Curious Agent 完整架构（v0.2.3）

┌─────────────────────────────────────────────────────────────┐
│  MetaCognitiveController（中央执行系统）                       │
│  - 注意力分配（现在该探索什么）                               │
│  - 任务切换（继续还是停止）                                  │
│  - 决策（通知还是静默）                                      │
└─────────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ 情境缓冲区        │ │ CuriosityEngine  │ │ KnowledgeGraph  │
│ (Episodic       │ │  (语音回路)      │ │  (长时记忆)     │
│  Buffer)        │ │                 │ │                 │
│                 │ │ - 好奇心队列    │ │ - topics        │
│ - 当前情境整合   │ │ - 探索评分      │ │ - 知识图谱      │
│ - 历史 episodes │ │ - 关键词提取    │ │ - 来源记录      │
│ - 容量管理      │ │                 │ │                 │
└─────────────────┘ └─────────────────┘ └─────────────────┘
          │                │                │
          │ 检索相关历史    │ 探索执行       │ 持久化知识
          ▼                ▼                ▼
      返回给 Controller  Explorer 执行     写入 state.json
```

#### 6.7 验收测试

```bash
# T1: 情境整合
python3 curious_agent.py --inject "test episodic buffer"
python3 curious_agent.py --run --run-depth medium
# 检查 state.json 中 episodic_buffer 有新 episode
# 检查 situation 字段包含：topic + queue + recent_findings + exploration_state

# T2: 容量管理
# 手动创建 51 个 episodes（超过 capacity=50）
# 检查最旧的 episode 被遗忘

# T3: 情境检索
# 执行多个不同话题的探索
# 检索时，相似话题的 episodes 应该被返回
# 检查 relevance 分数 > 0.5
```

#### 6.8 与 F6 Reflexion 的整合

```
Reflexion 的反思 → 存入 Episodic Buffer

  F6 生成的 verbal reflection
        ↓
  EpisodicBuffer.store_episode(reflections=[...])
        ↓
  下次探索时
        ↓
  EpisodicBuffer.retrieve_relevant()
        ↓
  返回相关反思 + 情境
        ↓
  注入 Explorer prompt
```

---

### F7: Reflexion 风格的口头反思记忆（非参数化学习）

**理论来源**：arXiv:2303.11366 — Reflexion: Language Agents with Verbal Reinforcement Learning

**约束**：不训练模型，不更新权重，所有学习通过非参数化方式实现。

#### 6.1 核心思想

```
传统 RL（需要训练）：Agent 执行 → 计算梯度 → 更新权重 → 下一轮
Reflexion（不训练）：Agent 执行 → 语言反馈 → 口头反思 → 存入记忆 → 下一轮

Curious Agent 实现：
  → 用 LLM 生成"口头反思"（verbal reflection）
  → 存入 Episodic Memory（事件记忆）
  → 下次探索相似话题时，通过 RAG 检索相关反思
  → 将反思注入 Explorer 的 prompt，引导搜索策略
```

#### 6.2 为什么不用训练

| 训练方式 | 问题 | 非参数化替代 |
|---------|------|-------------|
| Fine-tuning | 需要 GPU、数据集、训练流水线 | RAG 检索 |
| RLHF | 需要人工标注 reward | LLM 自我评估 |
| 持续学习 | 灾难性遗忘风险 | 记忆独立存储 |

#### 6.3 模块设计

```python
class EpisodicMemory:
    """
    事件记忆 — 存储口头反思（verbal reflections）
    
    不训练模型，学习通过记忆检索实现
    """
    
    def __init__(self, kg: KnowledgeGraph):
        self.kg = kg
    
    def add_reflection(self, topic: str, feedback: dict, reflection: str):
        """
        将口头反思存入记忆
        
        Args:
            topic: 探索话题
            feedback: 探索反馈（质量分、边际收益、成功/失败）
            reflection: LLM 生成的反思文本
        """
        entry = {
            "topic": topic,
            "feedback": feedback,
            "reflection": reflection,
            "timestamp": datetime.now().isoformat(),
            "similar_topics": self._find_similar_topics(topic)
        }
        self._save_to_memory(entry)
    
    def _generate_reflection(self, topic: str, findings: dict, 
                            quality: float, marginal: float) -> str:
        """
        用 LLM 生成口头反思
        
        提示词模板：
        "你对'{topic}'的探索结束了。
        探索质量: {quality}/10
        边际收益: {marginal}
        发现了: {findings_summary}
        
        用一段话反思：
        1. 这次探索哪里做得好/不好？
        2. 下次遇到类似话题应该注意什么？
        3. 什么搜索策略最有效？"
        """
        pass  # LLM 调用
    
    def retrieve(self, topic: str, limit: int = 3) -> list:
        """
        检索与当前话题相关的反思
        
        方法：
        1. 找到相似话题（embedding 余弦相似度）
        2. 返回最近 N 条相关反思
        
        Returns:
            [{"topic": "...", "reflection": "...", "similarity": 0.8}, ...]
        """
        pass
    
    def _find_similar_topics(self, topic: str) -> list:
        """
        找到与 topic 相似的已有话题
        
        方法：
        1. 用 embedding 模型计算向量相似度
        2. 或用关键词重叠度
        """
        pass
```

#### 6.4 与 Explorer 的集成

```python
class Explorer:
    def explore(self, topic: str, depth: str):
        # === Retrieve relevant reflections (RAG) ===
        reflections = episodic_memory.retrieve(topic, limit=3)
        
        reflection_prompt = ""
        if reflections:
            reflection_prompt = "【相关反思】\n"
            for r in reflections:
                reflection_prompt += f"- 关于 {r['topic']}: {r['reflection']}\n"
            reflection_prompt += "\n"
        
        # === Inject into search prompt ===
        search_prompt = f"""
{reflection_prompt}
请探索话题：{topic}
探索深度：{depth}

基于以上反思，调整你的搜索策略。
"""
        
        # 执行搜索...
```

#### 6.5 数据格式

```json
{
  "episodic_memory": [
    {
      "id": "uuid-xxx",
      "topic": "metacognition in LLM",
      "feedback": {
        "quality": 7.5,
        "marginal_return": 0.4,
        "success": true
      },
      "reflection": "这次探索发现 arXiv:2510.16374 的 Monitor-Generate-Verify 框架很有价值。搜索时优先找 ArXiv 论文效果更好。下次遇到类似框架类话题，应该先用 ArXiv 搜索。"
      ,
      "similar_topics": ["llm reasoning", "self-reflection mechanisms"],
      "timestamp": "2026-03-21T12:00:00Z"
    }
  ]
}
```

#### 6.6 验收测试

```bash
# T1: 反思生成
python3 curious_agent.py --inject "test reflection"
python3 curious_agent.py --run --run-depth medium
# 检查 state.json 中 episodic_memory 是否有新条目
# 检查 reflection 字段是否有内容

# T2: 相似话题检索
# 注入两个相似话题
python3 curious_agent.py --inject "llm metacognition"
python3 curious_agent.py --inject "metacognitive monitoring"
# 执行探索后检索
# 预期：episodic_memory 中 similar_topics 包含相关话题

# T3: 反思影响搜索行为
# 注入一个话题，执行探索（生成反思）
# 再次注入相似话题，执行探索
# 检查第二次探索的搜索词/策略是否与反思一致
```

#### 6.7 实现约束

```
✅ 可以做的：
  - LLM 生成反思文本（提示词工程）
  - Embedding 相似度计算（sentence-transformers）
  - 记忆向量存储（FAISS / ChromaDB）
  - 将反思注入 prompt（RAG）

❌ 不可以做的：
  - Fine-tuning / LoRA
  - RLHF / 奖励模型训练
  - 任何形式的梯度更新
  - 改变模型权重
```

---

## 四、v0.2.3 里程碑

```
v0.2.3 目标：构建在 v0.2.2 监控数据上的高级功能

阶段1: F1 DK-UV 检测
阶段2: F2 动态 α 调节
阶段3: F3 知识关联图
阶段4: F4 飞书通知
阶段5: F5 SQLite 迁移
阶段6: F6 情境缓冲区（Episodic Buffer）
阶段7: F7 Reflexion 口头反思记忆（非参数化学习）
```

---

## 五、与 v0.2.2 的依赖关系

```
v0.2.2（元认知监控基础）
  ├── MetaCognitiveMonitor（监测数据来源）
  ├── MetaCognitiveController（决策框架）
  ├── state.json 扩展（数据格式）
  └── assess_exploration_quality() → 产生反馈数据
         │
         ▼
v0.2.3（高级元认知）
  ├── F1 DK-UV → 依赖 MetaCognitiveMonitor.detect_gaps()
  ├── F2 动态α → 依赖 marginal_returns 历史数据
  ├── F3 知识图谱 → 依赖 state.json 的 knowledge 图谱数据
  ├── F4 飞书通知 → 依赖 should_notify() 决策
  ├── F5 SQLite → 依赖 state.json 结构稳定
  ├── F6 情境缓冲区 → 依赖 CuriosityEngine 队列状态
  │                     依赖 MetaCognitiveController 决策
  │                     依赖 Knowledge Graph 长时记忆
  └── F7 Reflexion → 依赖 F6 情境缓冲区（反思存储）
                      依赖 assess_exploration_quality() 的反馈
                      依赖 Explorer 的 prompt 注入能力
```

---

## 六、与 Reflexion 的对比

| 维度 | Reflexion 原版 | Curious Agent F6 |
|------|---------------|------------------|
| **反馈来源** | 外部环境（游戏、编译器）| LLM 自我评估 |
| **记忆类型** | Episodic Memory Buffer | state.json episodic_memory |
| **检索方式** | 语义相似度 | Embedding 余弦相似度 |
| **行动影响** | 改变 LLM 生成行为 | 注入 prompt 引导搜索策略 |
| **训练** | 不训练（verbal） | 不训练（非参数化） |

**核心差异**：Reflexion 的 Actor 读取记忆后改变"说什么"，Curious Agent 的 Explorer 读取记忆后改变"搜什么"。

---

_最后更新：2026-03-21_
_设计者：R1D3-researcher + weNix_
_验收者：weNix_
