# Curious Agent v0.2.1 — ICM 融合评分机制设计文档

> 在 v0.2（分层探索）基础上的核心评分算法升级  
> 设计者：omo-broker + AI Assistant | 实现者：待分配  
> 文档版本：v1.0 | 创建日期：2026-03-20

---

## 1. 背景与动机

### 1.1 当前问题

v0.2 的评分算法是**纯人工设计**的：
```
Score = Relevance × 0.35 + Recency × 0.25 + Depth × 0.25 + Surprise × 0.15
```

**核心缺陷**：
- 话题优先级完全依赖人工注入，没有从探索历史中学习的机制
- 无法感知"我们对这个话题了解多少"（知识缺口）
- 探索结果的质量没有反馈到下次探索的优先级

### 1.2 设计目标

引入 **ICM（Intrinsic Curiosity Module）启发式融合评分**，让 Agent 能够：
1. 自主评估话题的探索价值（内在信号）
2. 平衡人类意图和自主探索（可配置权重）
3. 从探索历史中学习和调整（预测误差反馈）

---

## 2. 核心设计

### 2.1 融合架构

**设计原则**：人类意图和 Agent 自主探索**不是替代关系，是互补信号**

- **人工信号**：确保有用、聚焦、符合用户意图
- **内在信号**：确保惊喜、新鲜、有发现感

### 2.2 融合公式

```
FinalScore = HumanScore × α + IntrinsicScore × (1 - α)

其中：
  HumanScore      = 人工设计的评分（Relevance/Recency/Depth/Surprise）
  IntrinsicScore  = ICM 启发的内在评分
  α               = 用户可控权重（默认 0.5，范围 0.0-1.0）
```

### 2.3 内在评分算法

```python
def intrinsic_score(topic, knowledge_graph, exploration_history):
    """
    三个内在信号，每个 0-10 分
    """
    # 1. 预测误差（Prediction Error）
    #    = 之前探索后，对这个话题的理解误差
    #    误差越大 → 我们越不了解 → 越值得探索
    pred_error = predict_error(topic, exploration_history)

    # 2. 关联密度（Graph Density）
    #    = 图谱中该话题的连接节点数
    #    连接越少 → 越孤立 → 知识空白越大 → 越值得探索
    density = graph_density(topic, knowledge_graph)

    # 3. 新颖性（Novelty）
    #    = 与已知知识库的重叠度
    #    重叠越少 → 越新鲜 → 探索价值越高
    novelty = novelty_score(topic, knowledge_graph)

    return (pred_error * 0.4 + density * 0.3 + novelty * 0.3)
```

---

## 3. 架构设计

### 3.1 模块划分

采用**独立模块 + 集成**方案：

```
core/
├── knowledge_graph.py       # 知识图谱（已有）
├── curiosity_engine.py      # 好奇心引擎（修改：集成 IntrinsicScorer）
├── intrinsic_scorer.py      # 新增：内在评分器
├── explorer.py             # 探索器（已有）
└── ...
```

### 3.2 IntrinsicScorer 模块

```python
# core/intrinsic_scorer.py

class IntrinsicScorer:
    """
    ICM 启发的内在评分器
    职责：计算话题的内在探索价值，不依赖人工输入
    """
    
    def __init__(self, knowledge_graph, exploration_history, config=None):
        self.kg = knowledge_graph
        self.history = exploration_history
        self.config = config or {}
    
    def score(self, topic: str) -> dict:
        """
        计算话题的内在评分
        
        Returns:
            {
                'total': float,           # 0-10 总分
                'signals': {
                    'pred_error': float,  # 0-10 预测误差
                    'graph_density': float, # 0-10 图谱密度（反向）
                    'novelty': float,     # 0-10 新颖性
                },
                'weights': {              # 各信号权重
                    'pred_error': 0.4,
                    'graph_density': 0.3,
                    'novelty': 0.3,
                }
            }
        """
        pred_error = self._calc_pred_error(topic)
        density = self._calc_graph_density(topic)
        novelty = self._calc_novelty(topic)
        
        total = (pred_error * 0.4 + density * 0.3 + novelty * 0.3)
        
        return {
            'total': round(total, 2),
            'signals': {
                'pred_error': round(pred_error, 2),
                'graph_density': round(density, 2),
                'novelty': round(novelty, 2),
            },
            'weights': {
                'pred_error': 0.4,
                'graph_density': 0.3,
                'novelty': 0.3,
            }
        }
    
    def _calc_pred_error(self, topic: str) -> float:
        """
        预测误差计算
        逻辑：
        - 从未探索过 → 误差高（10分）
        - 探索过但 insight 质量低 → 误差中高（7-9分）
        - 探索过且 insight 质量高 → 误差低（1-3分）
        """
        records = self.history.get_topic_records(topic)
        
        if not records:
            return 10.0  # 完全未知
        
        # 计算平均 insight 质量
        avg_quality = sum(r.get('insight_quality', 5) for r in records) / len(records)
        
        # 探索次数越多，误差衰减
        explore_count = len(records)
        decay = min(explore_count * 1.5, 5)  # 最多衰减 5 分
        
        # 质量越高，误差越低
        error = 10 - avg_quality - decay
        return max(0.0, error)
    
    def _calc_graph_density(self, topic: str) -> float:
        """
        图谱密度计算（反向）
        逻辑：
        - 连接节点越多 → 了解越充分 → 密度分越低
        - 孤立节点 → 知识空白 → 密度分越高
        """
        related_count = self.kg.count_related_topics(topic)
        
        # 映射：0个连接=10分，10+连接=0分
        if related_count == 0:
            return 10.0
        elif related_count >= 10:
            return 0.0
        else:
            return 10 - related_count
    
    def _calc_novelty(self, topic: str) -> float:
        """
        新颖性计算（混合方案）
        
        默认：纯统计方法（零成本）
        可选：LLM 语义增强（高精度）
        """
        use_llm = self.config.get('use_llm_for_novelty', False)
        
        if use_llm:
            return self._novelty_with_llm(topic)
        else:
            return self._novelty_pure_stats(topic)
    
    def _novelty_pure_stats(self, topic: str) -> float:
        """
        纯统计方法
        
        指标：
        1. Jaccard 文本相似度（与已知话题的重叠）
        2. 邻居节点距离（图谱拓扑）
        3. 历史探索频次
        """
        topic_words = set(topic.lower().split())
        known_topics = self.kg.get_all_topics()
        
        # 1. 最大文本重叠度
        max_overlap = 0.0
        for known in known_topics:
            known_words = set(known.lower().split())
            if not known_words:
                continue
            intersection = len(topic_words & known_words)
            union = len(topic_words | known_words)
            similarity = intersection / union if union > 0 else 0
            max_overlap = max(max_overlap, similarity)
        
        # 2. 邻居节点数（越少越新颖）
        related_count = self.kg.count_related_topics(topic)
        neighbor_score = max(0, 10 - related_count) / 10 * 3  # 权重 3
        
        # 3. 历史探索频次（越多越不新颖）
        explore_count = self.history.get_explore_count(topic)
        explore_score = max(0, 10 - explore_count * 2) / 10 * 3  # 权重 3
        
        # 综合：重叠度低 + 邻居少 + 未探索 = 高分
        novelty = (1 - max_overlap) * 4 + neighbor_score + explore_score
        return min(10, novelty)
    
    def _novelty_with_llm(self, topic: str) -> float:
        """
        LLM 语义增强方法
        
        适用场景：需要高精度语义理解时
        成本：每次评分 1 次 LLM 调用
        """
        from core.llm_client import LLMClient
        
        known_summaries = self.kg.get_related_summaries(topic, top_k=3)
        
        prompt = f"""
        评估这个新话题与已有知识库的语义相似度：
        
        新话题：{topic}
        
        知识库中的相关内容：
        {known_summaries}
        
        请从 1-10 评分：
        - 10 = 完全新颖，与已知知识无关联
        - 1 = 已有详细记录，重复探索
        
        只返回数字，不要解释。
        """
        
        llm = LLMClient()
        similarity_score = float(llm.chat(prompt))  # 1-10
        novelty = 11 - similarity_score  # 反转
        
        return max(0, min(10, novelty))
```

### 3.3 CuriosityEngine 集成

```python
# core/curiosity_engine.py

from core.intrinsic_scorer import IntrinsicScorer

class CuriosityEngine:
    def __init__(self, knowledge_graph, config=None):
        self.kg = knowledge_graph
        self.config = config or {}
        
        # 新增：初始化内在评分器
        self.intrinsic_scorer = IntrinsicScorer(
            knowledge_graph=knowledge_graph,
            exploration_history=self.kg.get_exploration_history(),
            config=config
        )
    
    def score_topic(self, topic: str, alpha: float = 0.5) -> dict:
        """
        融合评分：人工信号 + 内在信号
        
        Args:
            topic: 话题名称
            alpha: 人工信号权重（0.0-1.0），默认 0.5
        
        Returns:
            {
                'final_score': float,      # 融合后总分
                'human_score': float,      # 人工评分
                'intrinsic_score': float,  # 内在评分
                'alpha': float,            # 使用的权重
                'signals': dict,           # 内在信号详情
            }
        """
        # 人工评分（原有逻辑）
        human_score = self._human_score(topic)
        
        # 内在评分（新增）
        intrinsic_result = self.intrinsic_scorer.score(topic)
        intrinsic_score = intrinsic_result['total']
        
        # 融合
        final_score = human_score * alpha + intrinsic_score * (1 - alpha)
        
        return {
            'final_score': round(final_score, 2),
            'human_score': round(human_score, 2),
            'intrinsic_score': round(intrinsic_score, 2),
            'alpha': alpha,
            'signals': intrinsic_result['signals'],
            'weights': intrinsic_result['weights'],
        }
    
    def _human_score(self, topic: str) -> float:
        """
        原有评分逻辑：Relevance + Recency + Depth + Surprise
        """
        # ... 保留 v0.2 的实现 ...
        pass
```

---

## 4. 用户接口设计

### 4.1 CLI 接口

```bash
# 默认（α=0.5）
python3 curious_agent.py --inject "metacognition"

# 偏重人类意图（70%人工，30%自主）
python3 curious_agent.py --inject "metacognition" --motivation human
# 等价于：python3 curious_agent.py --inject "metacognition" --alpha 0.7

# 偏重自主探索（30%人工，70%自主）
python3 curious_agent.py --inject "metacognition" --motivation curious
# 等价于：python3 curious_agent.py --inject "metacognition" --alpha 0.3

# 纯探索模式（0%人工，100%自主）
python3 curious_agent.py --run --pure-curious
# 等价于：python3 curious_agent.py --run --alpha 0.0

# 自定义 α 值
python3 curious_agent.py --inject "metacognition" --alpha 0.6
```

**参数映射**：
- `--motivation human` → α = 0.7
- `--motivation curious` → α = 0.3
- `--pure-curious` → α = 0.0
- `--alpha <value>` → 直接使用指定值（覆盖 motivation）

### 4.2 API 接口

```bash
# 触发融合模式探索
curl -X POST http://10.1.0.13:4848/api/curious/explore \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "agent memory",
    "alpha": 0.5
  }'

# 纯自主探索（内在信号驱动）
curl -X POST http://10.1.0.13:4848/api/curious/explore \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "intrinsic",
    "alpha": 0.0
  }'

# 响应格式
{
  "status": "accepted",
  "topic": "agent memory",
  "alpha": 0.5,
  "scores": {
    "final": 7.85,
    "human": 7.5,
    "intrinsic": 8.2,
    "signals": {
      "pred_error": 8.5,
      "graph_density": 7.0,
      "novelty": 9.0
    }
  }
}
```

### 4.3 Web UI

**新增组件**：
1. **α 滑块控制器**（好奇心队列页面）
   - 范围：0.0 - 1.0
   - 步长：0.1
   - 实时显示当前值
   - 预设按钮：Human (0.7) / Balanced (0.5) / Curious (0.3)

2. **评分详情展示**
   ```
   话题: agent memory
   ├─ 最终评分: 7.85 ⭐
   ├─ 人工评分: 7.5 (α=0.5)
   ├─ 内在评分: 8.2
   │  ├─ 预测误差: 8.5 (权重 0.4)
   │  ├─ 图谱密度: 7.0 (权重 0.3)
   │  └─ 新颖性: 9.0 (权重 0.3)
   ```

---

## 5. 数据格式扩展

### 5.1 curiosity_queue 条目

```json
{
  "topic": "metacognition in LLM",
  "human_score": 7.5,
  "intrinsic_score": 8.2,
  "alpha": 0.5,
  "final_score": 7.85,
  "intrinsic_signals": {
    "pred_error": 8.5,
    "graph_density": 7.0,
    "novelty": 9.0
  },
  "status": "pending"
}
```

### 5.2 exploration_log 条目

```json
{
  "topic": "metacognition in LLM",
  "alpha": 0.5,
  "human_score": 7.5,
  "intrinsic_score": 8.2,
  "final_score": 7.85,
  "pred_error_before": 7.2,
  "pred_error_after": 2.1,
  "pred_error_reduced": 5.1,
  "insight_gained": "LLM的元认知表现为...",
  "signals_snapshot": {
    "pred_error": 8.5,
    "graph_density": 7.0,
    "novelty": 9.0
  },
  "findings": {
    "layer1": "...",
    "layer2": "...",
    "layer3": "..."
  }
}
```

---

## 6. Bug 修复（F1-F5）

### F1: 好奇心队列条目删除

**问题**：历史条目无法清除，队列臃肿（清理前 184 条 → 清理后 0 条）

**解决方案**：
- CLI: `python3 curious_agent.py --delete "topic" [--force]`
- API: `DELETE /api/curious/queue?topic=xxx`
- Web UI: 每行增加 🗑️ 删除按钮 + 批量删除

**实现要点**：
1. 删除前检查 `status`：`done`/`exploring` 不可删，除非 `--force`
2. 删除后更新 `state.json`
3. 操作记入 `logs/` 日志

### F2: Layer 3 深度洞察几乎不触发

**问题**：触发率仅 2%，核心功能闲置

**根因**：
1. `Explorer` 实例化时未传递 `exploration_depth` 参数
2. ArXiv 链接获取不稳定
3. Layer 2 论文格式不完整

**解决方案**：
1. 修复 `curious_agent.py` 中 `Explorer(exploration_depth=depth)` 参数传递
2. Layer 1 同时用 Bocha + ArXiv API 搜索，互为备份
3. Layer 2 容错：1 篇论文也能生成有限洞察
4. Layer 3 触发条件放宽：`len(papers) >= 1` 即可

**期望效果**：Layer 3 触发率从 2% 提升到 20-30%

### F3: 关键词过滤失效导致队列污染

**问题**：噪音入队率高达 73%（"Agen", "TeST", "CTO" 等）

**根因**：
1. `_extract_keywords()` 正则只按大写字母提取，无停用词表
2. `auto_queue_topics()` 无任何过滤
3. 换行符未预处理导致截断

**解决方案**：
1. **停用词表**（领域相关）
   ```python
   STOPWORDS = {
       "AI Strategy", "Digital Marketing", "CTO", "COO",
       "Chief Technology Officer", "SegmentFault", "CentOS",
       "Agen", "TeST",
   }
   ```
2. **语义相关性预检**
   ```python
   RESEARCH_KEYWORDS = {
       "agent", "llm", "memory", "planning", "reasoning",
       "metacognition", "curiosity", "autonomous",
   }
   ```
3. **换行符预处理**：`text.replace('\n', ' ')`
4. **最小评分门槛**：预估 score < 5.0 不入队

**期望效果**：队列自动增长时噪音率 < 5%

### F4: 启动脚本 — 存量进程检测与干净重启

**问题**：需手动两步杀进程 + 启动，易出现端口冲突

**解决方案**：创建 `run_curious.sh` 脚本

```bash
#!/bin/bash
# 1. 检测占用端口的进程
fuser -k ${PORT}/tcp 2>/dev/null

# 2. Kill 残留的 curious 进程
pkill -f "curious_api.py" 2>/dev/null
pkill -f "curious_agent.py" 2>/dev/null

# 3. 等待端口释放
sleep 2

# 4. 启动服务
nohup python3 curious_api.py > "$LOG_FILE" 2>&1 &

# 5. 等待启动并验证
for i in {1..10}; do
    if curl -s "http://localhost:$PORT/api/curious/state" > /dev/null 2>&1; then
        echo "[完成] Curious Agent 已启动"
        exit 0
    fi
    sleep 1
done
```

### F5: ArXiv Analyzer 容错增强

**问题**：Layer 2 成功率仅 20%，经常返回空

**解决方案**：
1. **超时和重试**：`fetch_arxiv_paper(link, timeout=10, retries=2)`
2. **Fallback 机制**：PDF 下载失败时用 search snippet 构造伪论文对象
3. **相关性评分放宽**：`< 0.3` 才过滤（原 `< 0.6`）
4. **Layer 2 输出验证**：1 篇论文也传给 Layer 3

**期望效果**：Layer 2 成功率从 20% 提升到 60%+

---

## 7. 验收标准

### G3.1: α 参数正确控制融合权重
- `--motivation human` → `state.json` 中 `alpha=0.7`，人工分权重高
- `--motivation curious` → `state.json` 中 `alpha=0.3`，内在分权重高

### G3.2: 内在评分三信号可计算
```python
score = ca.score_topic('agent memory')
assert 'pred_error' in score['signals']
assert 'graph_density' in score['signals']
assert 'novelty' in score['signals']
```

### G3.3: 探索结果更新预测误差
- 同一话题两次探索，`pred_error_after < pred_error_before`
- 误差衰减值记录到 `exploration_log`

### G3.4: Web UI 显示评分来源
- 好奇心队列显示格式：`人工 7.5 | 内在 8.2 | 最终 7.85`
- α 滑块实时调整并生效

### G3.5: `--pure-curious` 模式正常
- 无人工注入时，内在信号可独立驱动探索
- `state.json curiosity_queue` 中有非用户注入的话题

### F1-F5: 各修复项验收
见上文各节"验收测试"部分。

---

## 8. 实现计划

### Phase 1: 核心模块（Week 1）
1. 创建 `core/intrinsic_scorer.py` 模块
2. 实现 `_calc_pred_error()`
3. 实现 `_calc_graph_density()`
4. 实现 `_calc_novelty()`（默认统计版）
5. 单元测试覆盖

### Phase 2: 集成与接口（Week 1-2）
1. 修改 `CuriosityEngine` 集成 `IntrinsicScorer`
2. 实现 CLI `--alpha` / `--motivation` / `--pure-curious`
3. 实现 API `alpha` 参数支持
4. 实现 Web UI α 滑块

### Phase 3: Bug 修复（Week 2）
按顺序：F2 → F3 → F1 → F5 → F4

### Phase 4: 验收与文档（Week 3）
1. 运行所有验收测试
2. 更新 README 和 RELEASE NOTE
3. 编写使用示例

---

## 9. 风险与应对

| 风险 | 影响 | 应对策略 |
|------|------|---------|
| IntrinsicScorer 信号计算不准确 | 探索质量下降 | 先上线统计版，观察后再考虑 LLM 增强 |
| α 参数调优困难 | 用户体验差 | 提供预设值（human/curious/balanced），降低决策成本 |
| F2-F5 修复引入回归 | 现有功能损坏 | 每个修复配单元测试，E2E 验证 |
| 性能下降（评分计算耗时） | 响应变慢 | 评分结果缓存，图谱索引优化 |

---

## 10. 附录

### 10.1 配置项

```python
# config.json
{
  "icm": {
    "default_alpha": 0.5,
    "signal_weights": {
      "pred_error": 0.4,
      "graph_density": 0.3,
      "novelty": 0.3
    },
    "use_llm_for_novelty": false,
    "min_score_to_queue": 5.0
  }
}
```

### 10.2 参考文献

- v0.2 设计文档: `docs/plans/2026-03-18-v0.2-design.md`
- v0.2 发布说明: `RELEASE_NOTE_v0.2.0.md`
- ICM 论文: Pathak et al. "Curiosity-driven Exploration by Self-supervised Prediction"

---

_文档版本: v1.0_  
_创建时间: 2026-03-20_  
_最后更新: 2026-03-20_  
_前置依赖: v0.2.0 已完成_
