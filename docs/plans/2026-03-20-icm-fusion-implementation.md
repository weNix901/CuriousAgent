# v0.2.1 ICM Fusion Scoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现 ICM 融合评分机制（IntrinsicScorer 模块 + CuriosityEngine 集成）并修复 F1-F5 五个 bug

**Architecture:** 新增独立的 `core/intrinsic_scorer.py` 模块计算内在评分（pred_error/graph_density/novelty），`CuriosityEngine` 通过组合方式调用它实现融合公式 FinalScore = HumanScore × α + IntrinsicScore × (1 - α)

**Tech Stack:** Python 3.11+, Flask, JSON persistence, minimax LLM (optional)

---

## Phase 1: IntrinsicScorer 核心模块

### Task 1: 创建 IntrinsicScorer 模块骨架

**Files:**
- Create: `core/intrinsic_scorer.py`
- Test: `tests/test_intrinsic_scorer.py`

**Step 1: Write the failing test**

```python
# tests/test_intrinsic_scorer.py
import pytest
from core.intrinsic_scorer import IntrinsicScorer

class TestIntrinsicScorer:
    def test_scorer_initialization(self):
        """测试 IntrinsicScorer 可以正确初始化"""
        scorer = IntrinsicScorer(knowledge_graph={}, exploration_history={})
        assert scorer is not None
    
    def test_score_returns_dict(self):
        """测试 score() 返回字典格式"""
        scorer = IntrinsicScorer(knowledge_graph={}, exploration_history={})
        result = scorer.score("test topic")
        assert isinstance(result, dict)
        assert 'total' in result
        assert 'signals' in result
```

**Step 2: Run test to verify it fails**

```bash
cd /root/dev/curious-agent
pytest tests/test_intrinsic_scorer.py -v
```
Expected: FAIL with "ModuleNotFoundError: No module named 'core.intrinsic_scorer'"

**Step 3: Write minimal implementation**

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
        return {
            'total': 5.0,
            'signals': {
                'pred_error': 5.0,
                'graph_density': 5.0,
                'novelty': 5.0,
            },
            'weights': {
                'pred_error': 0.4,
                'graph_density': 0.3,
                'novelty': 0.3,
            }
        }
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_intrinsic_scorer.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_intrinsic_scorer.py core/intrinsic_scorer.py
git commit -m "feat: add IntrinsicScorer module skeleton"
```

---

### Task 2: 实现 _calc_pred_error 方法

**Files:**
- Modify: `core/intrinsic_scorer.py`
- Test: `tests/test_intrinsic_scorer.py`

**Step 1: Write the failing test**

```python
# tests/test_intrinsic_scorer.py - add to TestIntrinsicScorer class

def test_pred_error_for_unknown_topic(self):
    """未探索过的话题应该有最高预测误差"""
    scorer = IntrinsicScorer(knowledge_graph={}, exploration_history={})
    error = scorer._calc_pred_error("unknown topic")
    assert error == 10.0

def test_pred_error_decreases_with_exploration(self):
    """探索次数越多，预测误差应该越低"""
    history = {
        "known topic": [
            {"insight_quality": 8},
            {"insight_quality": 9}
        ]
    }
    scorer = IntrinsicScorer(knowledge_graph={}, exploration_history=history)
    
    error1 = scorer._calc_pred_error("known topic")
    # 探索两次且质量高，误差应该较低
    assert error1 < 5.0
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_intrinsic_scorer.py::TestIntrinsicScorer::test_pred_error_for_unknown_topic -v
```
Expected: FAIL with "AttributeError: 'IntrinsicScorer' object has no attribute '_calc_pred_error'"

**Step 3: Write minimal implementation**

```python
# core/intrinsic_scorer.py - add to IntrinsicScorer class

def _calc_pred_error(self, topic: str) -> float:
    """
    预测误差计算
    逻辑：
    - 从未探索过 -> 误差高（10分）
    - 探索过但 insight 质量低 -> 误差中高（7-9分）
    - 探索过且 insight 质量高 -> 误差低（1-3分）
    """
    records = self.history.get(topic, [])
    
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
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_intrinsic_scorer.py::TestIntrinsicScorer::test_pred_error_for_unknown_topic tests/test_intrinsic_scorer.py::TestIntrinsicScorer::test_pred_error_decreases_with_exploration -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_intrinsic_scorer.py core/intrinsic_scorer.py
git commit -m "feat: implement pred_error calculation in IntrinsicScorer"
```

---

### Task 3: 实现 _calc_graph_density 方法

**Files:**
- Modify: `core/intrinsic_scorer.py`
- Test: `tests/test_intrinsic_scorer.py`

**Step 1: Write the failing test**

```python
# tests/test_intrinsic_scorer.py - add to TestIntrinsicScorer class

def test_graph_density_for_isolated_topic(self):
    """孤立的话题应该有最高密度分"""
    kg = {
        "topics": {
            "other topic": {"related": ["another topic"]}
        },
        "relations": []
    }
    scorer = IntrinsicScorer(knowledge_graph=kg, exploration_history={})
    density = scorer._calc_graph_density("isolated topic")
    assert density == 10.0

def test_graph_density_for_connected_topic(self):
    """连接多的话题应该有较低密度分"""
    kg = {
        "topics": {
            "connected topic": {},
            "related1": {},
            "related2": {},
            "related3": {}
        },
        "relations": [
            ["connected topic", "related1"],
            ["connected topic", "related2"],
            ["connected topic", "related3"]
        ]
    }
    scorer = IntrinsicScorer(knowledge_graph=kg, exploration_history={})
    density = scorer._calc_graph_density("connected topic")
    assert density < 10.0
    assert density > 0.0
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_intrinsic_scorer.py::TestIntrinsicScorer::test_graph_density_for_isolated_topic -v
```
Expected: FAIL with "AttributeError: 'IntrinsicScorer' object has no attribute '_calc_graph_density'"

**Step 3: Write minimal implementation**

```python
# core/intrinsic_scorer.py - add to IntrinsicScorer class

def _calc_graph_density(self, topic: str) -> float:
    """
    图谱密度计算（反向）
    逻辑：
    - 连接节点越多 -> 了解越充分 -> 密度分越低
    - 孤立节点 -> 知识空白 -> 密度分越高
    """
    related_count = self._count_related_topics(topic)
    
    # 映射：0个连接=10分，10+连接=0分
    if related_count == 0:
        return 10.0
    elif related_count >= 10:
        return 0.0
    else:
        return 10 - related_count

def _count_related_topics(self, topic: str) -> int:
    """统计与话题相关的节点数"""
    relations = self.kg.get('relations', [])
    count = 0
    for rel in relations:
        if topic in rel:
            count += 1
    return count
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_intrinsic_scorer.py -k "graph_density" -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_intrinsic_scorer.py core/intrinsic_scorer.py
git commit -m "feat: implement graph_density calculation in IntrinsicScorer"
```

---

### Task 4: 实现 _calc_novelty 方法（统计版）

**Files:**
- Modify: `core/intrinsic_scorer.py`
- Test: `tests/test_intrinsic_scorer.py`

**Step 1: Write the failing test**

```python
# tests/test_intrinsic_scorer.py - add to TestIntrinsicScorer class

def test_novelty_for_completely_new_topic(self):
    """全新的话题应该有最高新颖性"""
    kg = {"topics": {"known topic": {}}, "relations": []}
    scorer = IntrinsicScorer(knowledge_graph=kg, exploration_history={})
    novelty = scorer._calc_novelty("completely new xyz topic")
    assert novelty > 7.0  # 应该很高

def test_novelty_for_similar_topic(self):
    """相似的话题应该有较低新颖性"""
    kg = {"topics": {"agent memory": {}}, "relations": []}
    scorer = IntrinsicScorer(knowledge_graph=kg, exploration_history={})
    novelty = scorer._calc_novelty("agent memory")  # 完全相同
    assert novelty < 5.0  # 应该较低
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_intrinsic_scorer.py::TestIntrinsicScorer::test_novelty_for_completely_new_topic -v
```
Expected: FAIL with "AttributeError: 'IntrinsicScorer' object has no attribute '_calc_novelty'"

**Step 3: Write minimal implementation**

```python
# core/intrinsic_scorer.py - add to IntrinsicScorer class

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
    known_topics = self.kg.get('topics', {}).keys()
    
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
    related_count = self._count_related_topics(topic)
    neighbor_score = max(0, 10 - related_count) / 10 * 3  # 权重 3
    
    # 3. 历史探索频次（越多越不新颖）
    explore_count = len(self.history.get(topic, []))
    explore_score = max(0, 10 - explore_count * 2) / 10 * 3  # 权重 3
    
    # 综合：重叠度低 + 邻居少 + 未探索 = 高分
    novelty = (1 - max_overlap) * 4 + neighbor_score + explore_score
    return min(10, novelty)

def _novelty_with_llm(self, topic: str) -> float:
    """LLM 语义增强方法（占位）"""
    # 暂不实现，返回统计结果
    return self._novelty_pure_stats(topic)
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_intrinsic_scorer.py -k "novelty" -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_intrinsic_scorer.py core/intrinsic_scorer.py
git commit -m "feat: implement novelty calculation (stats-based) in IntrinsicScorer"
```

---

### Task 5: 更新 score() 方法集成三个信号

**Files:**
- Modify: `core/intrinsic_scorer.py`
- Test: `tests/test_intrinsic_scorer.py`

**Step 1: Write the failing test**

```python
# tests/test_intrinsic_scorer.py - add to TestIntrinsicScorer class

def test_score_calculates_all_signals(self):
    """测试 score() 正确计算所有信号"""
    kg = {"topics": {"known": {}}, "relations": []}
    history = {"known": [{"insight_quality": 8}]}
    scorer = IntrinsicScorer(knowledge_graph=kg, exploration_history=history)
    
    result = scorer.score("new topic")
    
    assert 'total' in result
    assert 'signals' in result
    assert 'weights' in result
    assert 'pred_error' in result['signals']
    assert 'graph_density' in result['signals']
    assert 'novelty' in result['signals']
    assert 0 <= result['total'] <= 10
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_intrinsic_scorer.py::TestIntrinsicScorer::test_score_calculates_all_signals -v
```
Expected: 当前返回固定值 5.0，需要更新实现

**Step 3: 更新 score() 方法**

```python
# core/intrinsic_scorer.py - update score() method

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
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_intrinsic_scorer.py::TestIntrinsicScorer::test_score_calculates_all_signals -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_intrinsic_scorer.py core/intrinsic_scorer.py
git commit -m "feat: integrate all three signals in IntrinsicScorer.score()"
```

---

## Phase 2: CuriosityEngine 集成

### Task 6: CuriosityEngine 集成 IntrinsicScorer

**Files:**
- Modify: `core/curiosity_engine.py`
- Test: `tests/test_curiosity_engine.py` (更新现有测试)

**Step 1: 查看现有 CuriosityEngine 代码**

```bash
head -50 core/curiosity_engine.py
```

**Step 2: 修改 CuriosityEngine 初始化**

```python
# core/curiosity_engine.py - 在文件顶部添加导入

from core.intrinsic_scorer import IntrinsicScorer

# 在 CuriosityEngine.__init__ 中添加

def __init__(self, knowledge_graph, config=None):
    self.kg = knowledge_graph
    self.config = config or {}
    
    # 新增：初始化内在评分器
    self.intrinsic_scorer = IntrinsicScorer(
        knowledge_graph=knowledge_graph,
        exploration_history=self._get_exploration_history(),
        config=config
    )

def _get_exploration_history(self):
    """从知识图谱获取探索历史"""
    # 根据实际数据结构实现
    return getattr(self.kg, 'exploration_history', {})
```

**Step 3: 添加融合评分方法**

```python
# core/curiosity_engine.py - 添加到 CuriosityEngine 类

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
    复用现有的 _score_curiosity 逻辑
    """
    # 如果已有 _score_curiosity 方法，直接调用
    if hasattr(self, '_score_curiosity'):
        return self._score_curiosity(topic)
    # 否则返回默认值
    return 5.0
```

**Step 4: 编写集成测试**

```python
# tests/test_curiosity_engine.py - 添加测试

def test_score_topic_returns_fusion_result():
    """测试融合评分返回正确格式"""
    from core.curiosity_engine import CuriosityEngine
    from core.knowledge_graph import KnowledgeGraph
    
    kg = KnowledgeGraph()
    engine = CuriosityEngine(kg)
    
    result = engine.score_topic("test topic", alpha=0.5)
    
    assert 'final_score' in result
    assert 'human_score' in result
    assert 'intrinsic_score' in result
    assert 'alpha' in result
    assert result['alpha'] == 0.5
```

**Step 5: 运行测试**

```bash
pytest tests/test_curiosity_engine.py -k "score_topic" -v
```
Expected: PASS

**Step 6: Commit**

```bash
git add core/curiosity_engine.py tests/test_curiosity_engine.py
git commit -m "feat: integrate IntrinsicScorer into CuriosityEngine with fusion scoring"
```

---

## Phase 3: CLI 接口

### Task 7: CLI 添加 --alpha 和 --motivation 参数

**Files:**
- Modify: `curious_agent.py`
- Test: `tests/test_cli.py`

**Step 1: 查看现有 CLI 参数处理**

```bash
grep -n "argparse\|add_argument" curious_agent.py | head -20
```

**Step 2: 添加新参数**

```python
# curious_agent.py - 在参数解析部分添加

parser.add_argument(
    '--alpha',
    type=float,
    default=0.5,
    help='Human signal weight (0.0-1.0), default 0.5'
)

parser.add_argument(
    '--motivation',
    choices=['human', 'curious'],
    help='Preset alpha: human=0.7, curious=0.3'
)

parser.add_argument(
    '--pure-curious',
    action='store_true',
    help='Pure exploration mode (alpha=0.0)'
)
```

**Step 3: 实现参数解析逻辑**

```python
# curious_agent.py - 在主函数中添加

def resolve_alpha(args):
    """解析 alpha 值，优先级：--pure-curious > --alpha > --motivation > default"""
    if args.pure_curious:
        return 0.0
    if args.alpha != 0.5:  # 用户明确指定了 --alpha
        return args.alpha
    if args.motivation == 'human':
        return 0.7
    if args.motivation == 'curious':
        return 0.3
    return 0.5

# 在使用时
alpha = resolve_alpha(args)
```

**Step 4: 更新 --inject 命令使用融合评分**

```python
# curious_agent.py - 在 --inject 处理逻辑中

if args.inject:
    alpha = resolve_alpha(args)
    result = engine.score_topic(args.inject, alpha=alpha)
    
    print(f"Topic: {args.inject}")
    print(f"Final Score: {result['final_score']}")
    print(f"  - Human: {result['human_score']} (α={result['alpha']})")
    print(f"  - Intrinsic: {result['intrinsic_score']}")
    print(f"  - Signals: {result['signals']}")
```

**Step 5: 编写 CLI 测试**

```python
# tests/test_cli.py - 添加测试

def test_cli_alpha_parameter():
    """测试 --alpha 参数正确传递"""
    import subprocess
    result = subprocess.run(
        ['python3', 'curious_agent.py', '--inject', 'test', '--alpha', '0.3'],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    # 检查输出中包含 alpha=0.3

def test_cli_motivation_human():
    """测试 --motivation human 使用 alpha=0.7"""
    import subprocess
    result = subprocess.run(
        ['python3', 'curious_agent.py', '--inject', 'test', '--motivation', 'human'],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
```

**Step 6: Commit**

```bash
git add curious_agent.py tests/test_cli.py
git commit -m "feat: add --alpha, --motivation, --pure-curious CLI parameters"
```

---

## Phase 4: Bug 修复

### Task 8: F2 - 修复 Layer 3 触发问题

**Files:**
- Modify: `curious_agent.py`
- Modify: `core/explorer.py`

**Step 1: 诊断问题**

```bash
grep -n "Explorer()" curious_agent.py
```
确认是否传递了 exploration_depth 参数。

**Step 2: 修复参数传递**

```python
# curious_agent.py - 在 run_one_cycle 或类似函数中

# 修改前：
# explorer = Explorer()

# 修改后：
explorer = Explorer(exploration_depth=args.run_depth if hasattr(args, 'run_depth') else 'medium')
```

**Step 3: 放宽 Layer 3 触发条件**

```python
# core/explorer.py - 在 _explore_layers 方法中

# 修改前：
# if self.exploration_depth == "deep" and "layer2" in layer_results and len(papers) >= 2:

# 修改后：
if self.exploration_depth == "deep" and "layer2" in layer_results and len(papers) >= 1:
```

**Step 4: 测试修复**

```bash
python3 curious_agent.py --run --run-depth deep
# 检查 logs/curious.log 中是否出现 "Layer 3" 日志
grep -i "layer 3" logs/curious.log
```

**Step 5: Commit**

```bash
git add curious_agent.py core/explorer.py
git commit -m "fix(F2): pass exploration_depth to Explorer and relax Layer 3 trigger to >=1 papers"
```

---

### Task 9: F3 - 修复关键词过滤

**Files:**
- Modify: `core/curiosity_engine.py`

**Step 1: 添加停用词表**

```python
# core/curiosity_engine.py - 在模块级别添加

STOPWORDS = {
    # 通用商业/SEO词
    "AI Strategy", "AI Business", "Digital Marketing", 
    "CTO", "COO", "Chief Technology Officer",
    "Customer Loyalty", "Operations",
    # 搜索结果噪音词
    "SegmentFault", "CentOS", "Segmentation fault",
    # 单字母/截断
    "Agen", "TeST", "LL", "AI",
}

RESEARCH_KEYWORDS = {
    "agent", "llm", "memory", "planning", "reasoning", 
    "reflection", "metacognition", "curiosity", "autonomous", 
    "world model", "cognitive", "framework", "architecture", 
    "training", "arxiv", "reinforcement", "chain-of-thought", 
    "prompt", "embedding", "attention", "transformer",
}
```

**Step 2: 改进 _extract_keywords 方法**

```python
# core/curiosity_engine.py - 修改 _extract_keywords

def _extract_keywords(self, text: str) -> list:
    """
    提取关键词，带过滤和清理
    """
    import re
    
    # 1. 预处理：清理换行符
    text = text.replace('\n', ' ').replace('\r', ' ')
    
    # 2. 提取候选词（大写字母开头的短语）
    keywords = re.findall(r'[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2}', text)
    
    # 3. 过滤
    filtered = []
    for kw in keywords:
        # 长度过滤
        if len(kw) < 4:
            continue
        # 停用词过滤
        if kw in STOPWORDS:
            continue
        # 语义相关性过滤
        if not self._is_research_related(kw):
            continue
        filtered.append(kw)
    
    return filtered

def _is_research_related(self, keyword: str) -> bool:
    """检查关键词是否与 AI/Agent 研究相关"""
    kw_lower = keyword.lower()
    return any(rk in kw_lower for rk in RESEARCH_KEYWORDS)
```

**Step 3: 添加最小评分门槛到 auto_queue_topics**

```python
# core/curiosity_engine.py - 修改 auto_queue_topics

def auto_queue_topics(self, topics):
    """
    自动入队，带质量门槛
    """
    queued = []
    for topic in topics:
        # 计算预估分数
        score_result = self.score_topic(topic, alpha=0.5)
        if score_result['final_score'] >= 5.0:
            self.kg.add_curiosity(topic, score=score_result['final_score'])
            queued.append(topic)
    return queued
```

**Step 4: Commit**

```bash
git add core/curiosity_engine.py
git commit -m "fix(F3): add stopwords filter and research keyword validation for auto-queue"
```

---

### Task 10: F1 - 添加队列删除功能

**Files:**
- Modify: `curious_agent.py`
- Modify: `core/knowledge_graph.py`
- Modify: `curious_api.py`

**Step 1: 添加 KnowledgeGraph 删除方法**

```python
# core/knowledge_graph.py - 添加

def remove_curiosity(self, topic: str, force: bool = False) -> bool:
    """
    删除好奇心队列条目
    
    Args:
        topic: 话题名称
        force: 是否强制删除（忽略状态）
    
    Returns:
        bool: 是否成功删除
    """
    queue = self.state.get('curiosity_queue', [])
    
    for i, item in enumerate(queue):
        if item.get('topic') == topic:
            # 检查状态
            if not force and item.get('status') in ['exploring', 'done']:
                return False
            
            # 删除
            queue.pop(i)
            self.state['curiosity_queue'] = queue
            self._persist()
            return True
    
    return False

def list_pending(self) -> list:
    """列出所有待探索条目"""
    queue = self.state.get('curiosity_queue', [])
    return [item for item in queue if item.get('status') == 'pending']
```

**Step 2: 添加 CLI 命令**

```python
# curious_agent.py - 添加参数

parser.add_argument('--delete', nargs='+', help='删除队列条目（支持多个）')
parser.add_argument('--force', action='store_true', help='强制删除（忽略状态）')
parser.add_argument('--list-pending', action='store_true', help='列出待探索条目')

# 处理逻辑
if args.list_pending:
    pending = kg.list_pending()
    for item in pending:
        print(f"- {item['topic']} (score: {item.get('score', 'N/A')})")

if args.delete:
    for topic in args.delete:
        success = kg.remove_curiosity(topic, force=args.force)
        if success:
            print(f"Deleted: {topic}")
        else:
            print(f"Failed to delete: {topic} (use --force to force)")
```

**Step 3: 添加 API 接口**

```python
# curious_api.py - 添加路由

@app.route('/api/curious/queue', methods=['DELETE'])
def delete_queue_item():
    topic = request.args.get('topic')
    force = request.args.get('force', 'false').lower() == 'true'
    
    kg = KnowledgeGraph()
    success = kg.remove_curiosity(topic, force=force)
    
    if success:
        return jsonify({"status": "success", "topic": topic})
    else:
        return jsonify({"status": "error", "message": "Topic not found or cannot be deleted"}), 400

@app.route('/api/curious/queue/delete', methods=['POST'])
def batch_delete_queue():
    data = request.json
    topics = data.get('topics', [])
    force = data.get('force', False)
    
    kg = KnowledgeGraph()
    results = []
    for topic in topics:
        success = kg.remove_curiosity(topic, force=force)
        results.append({"topic": topic, "deleted": success})
    
    return jsonify({"status": "success", "results": results})
```

**Step 4: Commit**

```bash
git add core/knowledge_graph.py curious_agent.py curious_api.py
git commit -m "feat(F1): add queue item deletion (CLI, API, force option)"
```

---

### Task 11: F4 - 创建启动脚本

**Files:**
- Create: `run_curious.sh`

**Step 1: 编写启动脚本**

```bash
#!/bin/bash
# run_curious.sh - 干净启动脚本

PORT=${PORT:-4848}
APP_DIR="/root/dev/curious-agent"
LOG_FILE="$APP_DIR/logs/api.log"

# 1. 检测占用端口的进程
echo "[清理] 检测端口 $PORT ..."
fuser -k ${PORT}/tcp 2>/dev/null || true

# 2. Kill 残留的 curious 进程
echo "[清理] 终止残留进程 ..."
pkill -f "curious_api.py" 2>/dev/null && echo "  - 已终止 curious_api.py"
pkill -f "curious_agent.py" 2>/dev/null && echo "  - 已终止 curious_agent.py"

# 3. 等待端口释放
sleep 2

# 4. 启动服务
echo "[启动] 启动 Curious Agent ..."
cd "$APP_DIR"
nohup python3 curious_api.py > "$LOG_FILE" 2>&1 &
PID=$!
echo "[启动] PID: $PID"

# 5. 等待启动并验证
echo "[验证] 等待服务启动 ..."
for i in {1..10}; do
    sleep 1
    if curl -s "http://localhost:$PORT/api/curious/state" > /dev/null 2>&1; then
        echo "[完成] Curious Agent 已启动: http://10.1.0.13:$PORT/"
        exit 0
    fi
    echo "  - 尝试 $i/10 ..."
done

echo "[错误] 启动失败，请检查日志: $LOG_FILE"
exit 1
```

**Step 2: 设置执行权限**

```bash
chmod +x run_curious.sh
```

**Step 3: 测试脚本**

```bash
bash run_curious.sh
```
Expected: 显示清理步骤 + 启动成功

**Step 4: Commit**

```bash
git add run_curious.sh
git commit -m "feat(F4): add run_curious.sh startup script with cleanup and verification"
```

---

### Task 12: F5 - ArXiv Analyzer 容错增强

**Files:**
- Modify: `core/arxiv_analyzer.py`

**Step 1: 添加超时和重试**

```python
# core/arxiv_analyzer.py - 修改 fetch 逻辑

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def fetch_arxiv_paper(self, link: str, timeout: int = 10, retries: int = 2):
    """
    获取 arXiv 论文，带超时和重试
    """
    session = requests.Session()
    retry = Retry(total=retries, backoff_factor=1)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    try:
        response = session.get(link, timeout=timeout)
        response.raise_for_status()
        return self._parse_paper(response.text)
    except Exception as e:
        print(f"Failed to fetch {link}: {e}")
        return None
```

**Step 2: 添加 fallback 机制**

```python
# core/arxiv_analyzer.py - 添加

def build_fallback_paper(self, link: str, topic: str) -> dict:
    """
    用链接信息构造伪论文对象
    """
    import re
    
    # 从链接提取 arXiv ID
    match = re.search(r'arXiv:(\d+\.\d+)', link)
    arxiv_id = match.group(1) if match else "unknown"
    
    return {
        "id": arxiv_id,
        "title": f"Paper about {topic}",
        "summary": f"ArXiv paper on {topic} (fallback)",
        "link": link,
        "is_fallback": True
    }
```

**Step 3: 修改 analyze_papers 使用容错逻辑**

```python
# core/arxiv_analyzer.py - 修改 analyze_papers

def analyze_papers(self, topic, links):
    """
    分析论文，带容错和 fallback
    """
    results = []
    for link in links[:5]:  # 最多分析 5 篇
        try:
            paper = self.fetch_arxiv_paper(link, timeout=10, retries=2)
            if paper:
                results.append(paper)
            else:
                # Fallback
                fallback = self.build_fallback_paper(link, topic)
                results.append(fallback)
        except Exception as e:
            print(f"Error analyzing {link}: {e}")
            # 仍然添加 fallback
            fallback = self.build_fallback_paper(link, topic)
            results.append(fallback)
    
    return results
```

**Step 4: 放宽相关性评分**

```python
# core/arxiv_analyzer.py - 修改相关性过滤

# 修改前：
# if relevance_score < 0.6:
#     continue

# 修改后：
if relevance_score < 0.3:  # 更宽松
    continue
```

**Step 5: Commit**

```bash
git add core/arxiv_analyzer.py
git commit -m "fix(F5): add timeout/retry, fallback papers, and relaxed relevance filter to ArXiv analyzer"
```

---

## Phase 5: API 和 Web UI

### Task 13: API 支持 alpha 参数

**Files:**
- Modify: `curious_api.py`

**Step 1: 更新 /api/curious/explore 接口**

```python
# curious_api.py - 修改 explore 路由

@app.route('/api/curious/explore', methods=['POST'])
def explore():
    data = request.json or {}
    topic = data.get('topic')
    alpha = data.get('alpha', 0.5)
    mode = data.get('mode', 'fusion')  # 'fusion' or 'intrinsic'
    
    kg = KnowledgeGraph()
    engine = CuriosityEngine(kg)
    
    if mode == 'intrinsic':
        # 纯内在模式
        result = engine.intrinsic_scorer.score(topic)
        return jsonify({
            "status": "success",
            "mode": "intrinsic",
            "topic": topic,
            "intrinsic_score": result['total'],
            "signals": result['signals']
        })
    else:
        # 融合模式
        result = engine.score_topic(topic, alpha=alpha)
        return jsonify({
            "status": "success",
            "mode": "fusion",
            "topic": topic,
            "alpha": alpha,
            "scores": {
                "final": result['final_score'],
                "human": result['human_score'],
                "intrinsic": result['intrinsic_score'],
                "signals": result['signals']
            }
        })
```

**Step 2: Commit**

```bash
git add curious_api.py
git commit -m "feat(api): add alpha parameter and intrinsic mode to explore endpoint"
```

---

### Task 14: Web UI 显示评分详情

**Files:**
- Modify: `ui/index.html`

**Step 1: 添加 α 滑块控制器**

```html
<!-- ui/index.html - 在好奇心队列区域添加 -->

<div class="alpha-control">
    <label>探索倾向:</label>
    <input type="range" id="alphaSlider" min="0" max="1" step="0.1" value="0.5">
    <span id="alphaValue">0.5</span>
    <div class="alpha-presets">
        <button onclick="setAlpha(0.7)">Human (0.7)</button>
        <button onclick="setAlpha(0.5)">Balanced (0.5)</button>
        <button onclick="setAlpha(0.3)">Curious (0.3)</button>
    </div>
</div>
```

**Step 2: 更新队列显示格式**

```javascript
// ui/index.html - 在渲染队列时

function renderQueueItem(item) {
    return `
        <div class="queue-item">
            <div class="topic-name">${item.topic}</div>
            <div class="scores">
                <span class="final-score">最终: ${item.final_score || 'N/A'}</span>
                <span class="human-score">人工: ${item.human_score || 'N/A'}</span>
                <span class="intrinsic-score">内在: ${item.intrinsic_score || 'N/A'}</span>
                <span class="alpha">α=${item.alpha || 0.5}</span>
            </div>
            <div class="signals">
                预测误差: ${item.intrinsic_signals?.pred_error || 'N/A'} |
                图谱密度: ${item.intrinsic_signals?.graph_density || 'N/A'} |
                新颖性: ${item.intrinsic_signals?.novelty || 'N/A'}
            </div>
            <button onclick="deleteTopic('${item.topic}')">🗑️</button>
        </div>
    `;
}
```

**Step 3: 添加删除功能**

```javascript
// ui/index.html - 添加删除函数

async function deleteTopic(topic) {
    if (!confirm(`确认删除: ${topic}?`)) return;
    
    const response = await fetch(`/api/curious/queue?topic=${encodeURIComponent(topic)}`, {
        method: 'DELETE'
    });
    
    if (response.ok) {
        // 局部刷新队列
        loadQueue();
    } else {
        alert('删除失败');
    }
}
```

**Step 4: Commit**

```bash
git add ui/index.html
git commit -m "feat(ui): add alpha slider, score breakdown display, and delete buttons"
```

---

## Phase 6: 验收测试

### Task 15: 运行验收测试

**Files:**
- Test: All test files

**Step 1: 运行所有测试**

```bash
cd /root/dev/curious-agent
pytest tests/ -v --tb=short
```
Expected: All tests PASS

**Step 2: 验收 G3.1: α 参数验证**

```bash
python3 curious_agent.py --inject "agent memory" --motivation human
# 检查 state.json: alpha=0.7

grep -A5 '"agent memory"' knowledge/state.json | grep alpha
```

**Step 3: 验收 G3.2: 内在信号输出**

```bash
python3 -c "
from curious_agent import CuriousAgent
ca = CuriousAgent()
score = ca.score_topic('agent memory')
print('pred_error:', score.get('signals',{}).get('pred_error'))
print('graph_density:', score.get('signals',{}).get('graph_density'))
print('novelty:', score.get('signals',{}).get('novelty'))
print('intrinsic_score:', score.get('intrinsic_score'))
"
```

**Step 4: 验收 G3.3: 预测误差衰减**

```bash
# 探索同一话题两次
python3 curious_agent.py --inject "self-reflection LLM"
python3 curious_agent.py --run
# 检查 exploration_log 中的 pred_error_before/after
```

**Step 5: 验收 G3.4: Web UI 显示**

```bash
bash run_curious.sh
# 打开浏览器访问 http://10.1.0.13:4848/
# 验证队列显示格式: "人工 X | 内在 Y | 最终 Z"
```

**Step 6: 验收 G3.5: 纯探索模式**

```bash
python3 curious_agent.py --run --pure-curious
# 检查 state.json curiosity_queue 中有非用户注入的话题
```

**Step 7: Commit 验收结果**

```bash
git add -A
git commit -m "test: complete acceptance tests for v0.2.1 ICM fusion scoring"
```

---

## Phase 7: 文档更新

### Task 16: 更新 README 和 RELEASE NOTE

**Files:**
- Modify: `README.md`
- Create: `RELEASE_NOTE_v0.2.1.md`

**Step 1: 更新 README 新增功能部分**

```markdown
## v0.2.1 新特性

### ICM 融合评分机制
- 人工评分 + 内在评分融合
- 可配置权重 α（CLI/API/Web UI）
- 三个内在信号：预测误差、图谱密度、新颖性

### 使用方式
```bash
# 偏重人类意图
python3 curious_agent.py --inject "topic" --motivation human

# 偏重自主探索
python3 curious_agent.py --inject "topic" --motivation curious

# 纯探索模式
python3 curious_agent.py --run --pure-curious
```

### Bug 修复
- F1: 支持删除队列条目
- F2: Layer 3 触发率提升
- F3: 关键词过滤增强
- F4: 一键启动脚本
- F5: ArXiv 容错增强
```

**Step 2: 创建 RELEASE_NOTE_v0.2.1.md**

```markdown
# Release Note - v0.2.1

## 主要特性
- ICM 融合评分机制
- IntrinsicScorer 模块
- α 参数全接口支持

## Bug 修复
- F1: 队列删除功能
- F2: Layer 3 触发问题
- F3: 关键词过滤
- F4: 启动脚本
- F5: ArXiv 容错

## 技术改进
- 新增 core/intrinsic_scorer.py 模块
- CuriosityEngine 集成融合评分
- Web UI 评分详情展示
```

**Step 3: Commit**

```bash
git add README.md RELEASE_NOTE_v0.2.1.md
git commit -m "docs: update README and add v0.2.1 release note"
```

---

## 总结

**总计任务数**: 16 个

**预估时间**:
- Phase 1 (Tasks 1-5): 2-3 小时
- Phase 2 (Task 6): 1 小时
- Phase 3 (Task 7): 1 小时
- Phase 4 (Tasks 8-12): 3-4 小时
- Phase 5 (Tasks 13-14): 1-2 小时
- Phase 6 (Task 15): 1 小时
- Phase 7 (Task 16): 1 小时

**总计**: 10-14 小时

**关键依赖**:
- Task 5 完成后才能开始 Task 6
- Task 6 完成后才能开始 Task 7
- Task 6 完成后才能开始 Tasks 8-12
- Task 12 完成后才能开始 Tasks 13-14

**可并行**:
- Tasks 8-12 (Bug 修复) 可以顺序或部分并行
- Task 13-14 (API/Web) 可以部分并行

---

*Plan created: 2026-03-20*  
*Based on design: docs/plans/2026-03-20-icm-fusion-design.md*
