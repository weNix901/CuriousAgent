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

### 2.3 内在评分算法（LLM 主导 + 图谱辅助）

```python
def intrinsic_score(topic, knowledge_graph, exploration_history):
    """
    三个内在信号，每个 0-10 分
    
    设计原则：
    - LLM 是主要计算方式（语义理解、推理能力）
    - 图谱统计作为辅助（冷启动、LLM 不可用时降级）
    """
    # 1. 预测误差（Prediction Error）- LLM 评估
    #    = LLM 评估：基于探索历史，我们对这个话题的理解程度
    #    LLM 会综合分析历史探索的 insight 质量、深度、一致性
    pred_error = llm_assess_prediction_error(topic, exploration_history)

    # 2. 关联密度（Graph Density）- LLM 评估 + 图谱辅助
    #    = LLM 评估：该话题在知识网络中的位置重要性
    #    图谱提供连接数、路径长度等统计数据供 LLM 参考
    density = llm_assess_graph_density(topic, knowledge_graph)

    # 3. 新颖性（Novelty）- LLM 评估 + 图谱辅助
    #    = LLM 评估：与已知知识库的语义重叠度
    #    图谱提供相关话题列表，LLM 做语义对比
    novelty = llm_assess_novelty(topic, knowledge_graph)

    return (pred_error * 0.4 + density * 0.3 + novelty * 0.3)
```

**LLM 主导的原因**：
1. **语义理解**：能识别 "transformer attention" 和 "self-attention mechanism" 的相似性
2. **综合推理**：能综合多个信号做出判断，而非简单公式
3. **自适应**：根据话题领域自动调整评估标准
4. **可解释**：LLM 可以给出评分的推理过程

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

### 3.2 IntrinsicScorer 模块（LLM 主导 + 图谱辅助）

```python
# core/intrinsic_scorer.py

class IntrinsicScorer:
    """
    ICM 启发的内在评分器
    职责：计算话题的内在探索价值，不依赖人工输入
    
    设计原则：
    - LLM 是主要计算方式（语义理解、综合推理）
    - 图谱统计作为辅助输入（冷启动、LLM 不可用时降级）
    """
    
    def __init__(self, knowledge_graph, exploration_history, config=None, llm_client=None):
        self.kg = knowledge_graph
        self.history = exploration_history
        self.config = config or {}
        self.llm = llm_client or self._init_llm()
    
    def _init_llm(self):
        """初始化 LLM 客户端"""
        from core.llm_client import LLMClient
        return LLMClient()
    
    def score(self, topic: str) -> dict:
        """
        计算话题的内在评分
        
        流程：
        1. 收集图谱统计数据（作为 LLM 的上下文）
        2. 调用 LLM 评估三个信号
        3. 加权汇总
        
        Returns:
            {
                'total': float,           # 0-10 总分
                'signals': {
                    'pred_error': float,  # 0-10 预测误差（LLM 评估）
                    'graph_density': float, # 0-10 图谱密度（LLM 评估）
                    'novelty': float,     # 0-10 新颖性（LLM 评估）
                },
                'weights': {              # 各信号权重
                    'pred_error': 0.4,
                    'graph_density': 0.3,
                    'novelty': 0.3,
                },
                'reasoning': str          # LLM 的推理过程（可解释性）
            }
        """
        # 收集图谱上下文
        context = self._gather_context(topic)
        
        # LLM 评估三个信号
        llm_result = self._llm_assess_signals(topic, context)
        
        pred_error = llm_result['pred_error']
        density = llm_result['graph_density']
        novelty = llm_result['novelty']
        
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
            },
            'reasoning': llm_result.get('reasoning', ''),
            'context': context  # 用于调试
        }
    
    def _gather_context(self, topic: str) -> dict:
        """
        收集图谱上下文，作为 LLM 评估的辅助信息
        """
        # 1. 探索历史
        records = self.history.get(topic, [])
        history_summary = {
            'explore_count': len(records),
            'avg_insight_quality': sum(r.get('insight_quality', 5) for r in records) / len(records) if records else 0,
            'last_explore': records[-1].get('timestamp') if records else None,
        }
        
        # 2. 图谱连接
        related_topics = self._get_related_topics(topic)
        
        # 3. 相关话题的摘要（供 LLM 对比）
        related_summaries = []
        for related in related_topics[:5]:  # 最多 5 个相关话题
            topic_data = self.kg.get('topics', {}).get(related, {})
            if topic_data:
                related_summaries.append({
                    'topic': related,
                    'summary': topic_data.get('summary', '')[:200]  # 截断
                })
        
        return {
            'topic': topic,
            'history': history_summary,
            'related_count': len(related_topics),
            'related_topics': related_topics,
            'related_summaries': related_summaries,
        }
    
    def _llm_assess_signals(self, topic: str, context: dict) -> dict:
        """
        使用 LLM 评估三个内在信号
        
        LLM 会综合语义理解、历史数据、图谱关系做出判断
        """
        prompt = f"""
你是一个用于评估 AI Agent 好奇心优先级的评分系统。

请评估以下话题的内在探索价值，给出三个信号的评分（1-10分）：

【待评估话题】
{topic}

【探索历史】
- 探索次数: {context['history']['explore_count']}
- 平均洞察质量: {context['history']['avg_insight_quality']:.1f}/10
- 上次探索: {context['history']['last_explore'] or '从未'}

【知识图谱上下文】
- 相关话题数: {context['related_count']}
- 相关话题列表: {', '.join(context['related_topics'][:10])}

【相关话题摘要】
{chr(10).join([f"- {s['topic']}: {s['summary'][:100]}..." for s in context['related_summaries']])}

请评估以下三个信号（1-10分，10=最高）：

1. **预测误差 (pred_error)**: 我们当前对这个话题的理解程度
   - 从未探索过 → 高误差 (8-10)
   - 探索过但 insight 质量低/不一致 → 中高误差 (6-8)
   - 探索过且 insight 质量高 → 低误差 (1-4)
   - 需要探索来消除认知不确定性 → 误差高

2. **图谱密度 (graph_density)**: 该话题在知识网络中的位置重要性
   - 与许多核心话题关联 → 密度低 (1-3)，因为了解充分
   - 孤立节点，连接少 → 密度高 (7-10)，知识空白
   - 处于知识边疆 → 密度高，值得探索

3. **新颖性 (novelty)**: 与已知知识库的语义重叠度
   - 全新概念，从未涉及 → 高新颖 (8-10)
   - 与已知话题高度相似 → 低新颖 (1-3)
   - 需考虑语义相似，非字面匹配

请以 JSON 格式返回（不要其他文字）：
{{
    "pred_error": 评分,
    "graph_density": 评分,
    "novelty": 评分,
    "reasoning": "简要的评分理由"
}}
"""
        
        try:
            response = self.llm.chat(prompt)
            import json
            result = json.loads(response)
            return {
                'pred_error': max(0, min(10, float(result.get('pred_error', 5)))),
                'graph_density': max(0, min(10, float(result.get('graph_density', 5)))),
                'novelty': max(0, min(10, float(result.get('novelty', 5)))),
                'reasoning': result.get('reasoning', '')
            }
        except Exception as e:
            # LLM 失败时，降级到纯统计方法
            print(f"LLM assessment failed: {e}, falling back to stats")
            return self._fallback_stats_assessment(topic, context)
    
    def _fallback_stats_assessment(self, topic: str, context: dict) -> dict:
        """
        纯统计降级方案（LLM 不可用时）
        """
        history = context['history']
        
        # 1. 预测误差（统计版）
        if history['explore_count'] == 0:
            pred_error = 10.0
        else:
            avg_quality = history['avg_insight_quality']
            decay = min(history['explore_count'] * 1.5, 5)
            pred_error = max(0, 10 - avg_quality - decay)
        
        # 2. 图谱密度（统计版）
        related_count = context['related_count']
        if related_count == 0:
            density = 10.0
        elif related_count >= 10:
            density = 0.0
        else:
            density = 10 - related_count
        
        # 3. 新颖性（统计版）
        if history['explore_count'] == 0 and related_count == 0:
            novelty = 10.0
        else:
            novelty = max(0, 10 - history['explore_count'] * 2 - related_count * 0.5)
        
        return {
            'pred_error': pred_error,
            'graph_density': density,
            'novelty': novelty,
            'reasoning': '[Fallback] Stats-based assessment (LLM unavailable)'
        }
    
    def _get_related_topics(self, topic: str) -> list:
        """获取相关话题列表"""
        relations = self.kg.get('relations', [])
        related = set()
        for rel in relations:
            if topic in rel:
                related.update([r for r in rel if r != topic])
        return list(related)
        
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
2. 实现 `_gather_context()` - 收集图谱统计作为 LLM 上下文
3. 实现 `_llm_assess_signals()` - LLM 评估三个信号（主要方式）
4. 实现 `_fallback_stats_assessment()` - 统计降级方案（LLM 失败时使用）
5. 单元测试覆盖（包含 LLM mock 和 fallback 测试）

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
| LLM 评分延迟或失败 | 评分响应慢或降级 | 实现 fallback 统计方案，LLM 失败时自动降级 |
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
