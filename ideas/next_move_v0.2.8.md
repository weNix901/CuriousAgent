# Curious Agent v0.2.8 — 知识断言评估（Solution C）

> **问题根因**：QualityV2 的 `_assess_information_gain` 判断 summary 是否是 topic 名称的改写，但这个判断依赖 LLM 的文本相似度评估，容易误判。而且即使判断正确，0.0 分的 topic 也不会被 decompose，导致队列里堆积大量窄 topic 继续 explore，产生更多 0.0 分。

> **Solution C 核心思路**：不判断"summary 是否是 topic 改写"，而是判断"这次探索是否产生了可验证的新知识"。具体方法：LLM 从 findings 里生成 3 个具体知识断言，去 KG 里查这些断言是否已被知晓，全部已知则 quality=0.0。

> **状态**：规划中

---

## 1. 当前 QualityV2 的失败模式

### 失败模式 1：summary 是 topic 的同义改写

```
Topic: "Mamba"
Summary: "Mamba is a type of state space model designed for sequence modeling"
```

QualityV2 的 prompt 说"总结只是 topic 名称的重复或极度泛泛的描述 → 0.0"。但实际上这个 summary 包含"state space model"这个关键知识，不是 0.0。

### 失败模式 2：summary 信息密度低但有实质内容

```
Topic: "Reinforcement Learning from Human Feedback"
Summary: "RLHF is a method to align language models with human preferences using reinforcement learning."
```

这个 summary 实际上有 3 个知识断言：1) RLHF 用于对齐；2) 使用强化学习；3) 对齐目标是人类偏好。但 QualityV2 看到"只是 topic 名称的重复"，可能给低分。

### 失败模式 3：窄 topic 产生的窄 summary

```
Topic: "Corrosion resistance testing of offshore engineering harnesses"  
Summary: "This paper discusses corrosion resistance testing methods for offshore engineering harnesses."
```

这个 summary 完全是 topic 名称的展开，确实应该 0.0。Solution C 必须能正确识别这种。

---

## 2. 知识断言评估原理

### 2.1 核心假设

**假设**：一次有价值的探索，必须产生至少 1 个"新的具体知识断言"。

具体知识断言的定义：
- 是一个原子知识陈述（如"X 使用 Y 方法实现 Z"）
- 不等于 topic 名称本身
- 可以被验证（去 KG 里查是否已知）

### 2.2 评估流程

```
探索完成 → findings{summary, sources, papers, insights}
    ↓
Step 1: 生成 3 个知识断言（LLM）
    ↓
Step 2: 对每个断言，检查 KG 里是否已知
    ↓
Step 3: Quality = (新断言数 / 3) × 10
```

### 2.3 断言格式示例

对 topic "Mamba"，一个好的断言：

```
断言1: "Mamba uses selective state spaces to achieve O(N) inference instead of O(N²)"
断言2: "Mamba was proposed by Gu and Dao in 2024"
断言3: "Mamba competes with Transformers on long-sequence tasks"
```

对 topic "Corrosion resistance testing of offshore engineering harnesses"：

```
断言1: "Offshore engineering harnesses are tested for corrosion resistance"  ← 已知（topic 本身）
断言2: "Corrosion testing involves wet-dry cycling exposure"                 ← 可能新
断言3: "Harnesses use cathodic protection systems"                         ← 新，但价值有限
```

如果所有断言都已在 KG 里存在 → 0.0 分。

---

## 3. 实现方案

### 3.1 新文件结构

```
core/
  ├── quality_v2.py          # 修改：集成 KnowledgeAssertionEvaluator
  └── knowledge_assertion.py # 新增：断言评估器
  
models/                        # embedding 模型（自动下载）
  └── all-MiniLM-L6-v2/       # sentence-transformer 模型，约 80MB
  
shared_knowledge/
  └── assertion_index/       # 新增：断言索引（SQLite）
      └── assertions.db       # SQLite 数据库
```

### 3.2 KnowledgeAssertionEvaluator 类

```python
class KnowledgeAssertionEvaluator:
    """
    基于知识断言的质量评估器。
    
    核心逻辑：
    1. 从 findings 生成 N 个具体知识断言
    2. 检查每个断言是否在 KG 里已知
    3. Quality = (新断言数 / N) × 10
    """
    
    def __init__(self, llm_client, kg):
        self.llm = llm_client
        self.kg = kg
        self.assertion_db = AssertionIndex()  # SQLite 索引
    
    def generate_assertions(self, topic: str, findings: dict) -> list[str]:
        """从 findings 生成 3 个具体知识断言"""
        
        prompt = f"""你是知识工程师。你刚从探索结果中获得了关于"{topic}"的知识。

探索摘要：
{findings.get('summary', '')[:1000]}

来源：
{[s.get('title', '') for s in findings.get('sources', [])[:3]]}

论文：
{[p.get('title', '') for p in findings.get('papers', [])[:3]}

任务：生成 3 个具体、可验证的知识断言。这些断言必须：
1. 不是 topic 名称本身
2. 是从上述探索结果中提炼出来的具体知识
3. 格式："[Subject] [predicate]"（如"Mamba uses selective state spaces"）

格式要求：
- 每行一个断言
- 不要编号
- 不要解释
- 不要"这篇论文讲的是..."
- 直接陈述事实

输出："""

        response = self.llm.chat(prompt)
        # 解析，提取 3 个断言
        lines = [l.strip() for l in response.split('\n') if l.strip()]
        # 过滤掉空行、编号、解释性文字
        assertions = []
        for line in lines:
            if len(line) > 15 and not line[0].isdigit() and not line.startswith('- '):
                assertions.append(line)
        return assertions[:3]  # 最多 3 个
    
    def is_assertion_known(self, assertion: str) -> bool:
        """
        检查断言是否已在 KG 中已知。
        
        方法：embedding 相似度搜索
        1. 嵌入断言
        2. 在所有已有 KG summary 嵌入中搜索
        3. 如果 max_similarity > threshold → 已知
        4. 否则 → 新断言
        """
        assertion_emb = self._embed(assertion)
        max_sim = self.assertion_db.max_similarity(assertion_emb)
        
        KNOWN_SIMILARITY_THRESHOLD = 0.82  # 相似度 > 0.82 认为已知
        
        return max_sim > KNOWN_SIMILARITY_THRESHOLD
    
    def _embed(self, text: str) -> list[float]:
        """嵌入文本，使用可配置的 embedding provider（不硬编码 API key）"""
        if self._embedding_cache is None:
            from core.config import get_config
            cfg = get_config()
            self._embedding_provider = cfg.embedding.get('provider', 'volcengine')
            self._embedding_model = cfg.embedding.get('model', 'text-embedding-async')
            self._embedding_cache = {}  # 简单 LRU cache
        
        if text in self._embedding_cache:
            return self._embedding_cache[text]
        
        # 调用 embedding API（通过 LLM client 的 embedding 接口）
        embedding = self.llm.embed(text, model=self._embedding_model)
        self._embedding_cache[text] = embedding
        return embedding
    
    def assess_quality(self, topic: str, findings: dict) -> float:
        """主评估入口"""
        # 生成断言
        assertions = self.generate_assertions(topic, findings)
        
        if not assertions:
            # 没有生成断言 → 0.0
            return 0.0
        
        # 检查每个断言是否已知
        new_count = 0
        for assertion in assertions:
            if not self.is_assertion_known(assertion):
                new_count += 1
            # 不管是否已知，都把断言存入索引（更新 KG）
            self._index_assertion(assertion)
        
        quality = (new_count / len(assertions)) * 10
        return round(quality, 1)
    
    def _index_assertion(self, assertion: str):
        """把断言存入索引（用于后续去重）"""
        emb = self._embed(assertion)
        self.assertion_db.insert(assertion, emb)
```

### 3.3 AssertionIndex（SQLite 索引）

```python
import sqlite3
import numpy as np
from sentence_transformers import SentenceTransformer

class AssertionIndex:
    """
    断言嵌入索引，用 SQLite 存储。
    表结构：
    CREATE TABLE assertions (
        id INTEGER PRIMARY KEY,
        text TEXT UNIQUE,
        embedding BLOB,  -- numpy array 序列化
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            import os
            from pathlib import Path
            root = Path(__file__).parent.parent.parent
            db_path = root / "shared_knowledge" / "assertion_index" / "assertions.db"
        self.db_path = str(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS assertions (
                id INTEGER PRIMARY KEY,
                text TEXT UNIQUE,
                embedding BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def insert(self, text: str, embedding: list[float]):
        """插入断言和嵌入"""
        import pickle
        conn = sqlite3.connect(self.db_path)
        emb_bytes = pickle.dumps(np.array(embedding))
        conn.execute(
            "INSERT OR IGNORE INTO assertions (text, embedding) VALUES (?, ?)",
            (text, emb_bytes)
        )
        conn.commit()
        conn.close()
    
    def max_similarity(self, query_emb: list[float]) -> float:
        """
        在所有已有断言中找最大余弦相似度。
        优化：对大数据集用 FAISS加速。
        """
        import pickle
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT embedding FROM assertions").fetchall()
        conn.close()
        
        if not rows:
            return 0.0  # 第一个断言，肯定新
        
        query = np.array(query_emb)
        max_sim = 0.0
        
        for (emb_bytes,) in rows:
            stored_emb = pickle.loads(emb_bytes)
            sim = self._cosine(query, stored_emb)
            max_sim = max(max_sim, sim)
        
        return max_sim
    
    def _cosine(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))
```

### 3.4 与 QualityV2 的集成

```python
# quality_v2.py 新增断言评估通道

class QualityV2Assessor:
    def __init__(self, llm_client):
        self.llm = llm_client
        self.assertion_evaluator = None  # 延迟初始化
    
    def assess_quality(self, topic: str, findings: dict, knowledge_graph) -> float:
        """
        双重评估：
        1. 知识断言评估（主要）
        2. 信息增益评估（辅助，防止断言评估失败时完全失效）
        """
        # 尝试知识断言评估
        if self.assertion_evaluator is None:
            self.assertion_evaluator = KnowledgeAssertionEvaluator(self.llm, knowledge_graph)
        
        try:
            assertion_quality = self.assertion_evaluator.assess_quality(topic, findings)
        except Exception as e:
            print(f"[QualityV2] 断言评估失败，回退到信息增益评估: {e}")
            assertion_quality = None
        
        # 信息增益评估（原有逻辑，保留作为 fallback）
        information_gain = self._assess_information_gain(topic, findings.get("summary", ""))
        graph_delta = self._get_graph_delta(topic, knowledge_graph)
        legacy_quality = (
            information_gain * 0.40 +
            self._calculate_semantic_novelty(topic, findings, knowledge_graph) * 0.40 +
            graph_delta * 0.20
        ) * 10
        
        # 选择更高的分数（断言评估更准，用它作为主要）
        if assertion_quality is not None:
            # 如果断言评估说 0.0，用 legacy 作为参考，但置信度加权
            if assertion_quality == 0.0:
                # 断言评估给出 0.0 → 极低质量，信任它
                return 0.0
            else:
                # 断言评估 > 0.0 → 使用断言分数
                return assertion_quality
        else:
            return round(legacy_quality, 1)
```

---

## 4. 关键设计决策

### 4.1 为什么用 embedding 相似度而不是 LLM 判断？

**LLM 判断的问题**：
```
LLM: "这个断言和已有知识重复了吗？"
  → LLM 可能被 topic 名称影响（"Mamba uses state spaces" vs "state space models"）
  → 重复判断
```

**Embedding 的优势**：
- 语义相似度不依赖词汇重叠
- "Mamba uses selective state spaces" 和 "SSM for sequence modeling" 会被识别为相似
- 计算速度快（一次 embedding vs 一次 LLM 调用）

### 4.2 为什么存储断言而不是直接存 KG summaries？

KG summaries 的问题：一个 summary 可能包含多个知识断言，混在一起。

断言存储的优势：
- 每个断言独立，可精确去重
- 即使 summary 改写，断言本身不变
- 支持细粒度的新知识追踪

### 4.3 已知相似度阈值 0.82 是怎么来的？

在 `all-MiniLM-L6-v2` 模型上：
- 相同句子：~1.0
- 改写句子（Paraphrase）：~0.85-0.95
- 同领域不同断言：~0.6-0.8
- 不同领域：~0.3-0.5

所以 0.82 是一个平衡点：高于 0.82 认为"实质相同"，低于认为"新知识"。

---

## 5. 依赖

```
# 新增依赖
# 无新增依赖（使用 OpenClaw 已有 embedding 服务）

# 已有依赖
numpy>=1.21
sqlite3  # 标准库
```

### 5.1 Embedding Provider 配置

**原则：不硬编码 API key，通过环境变量或 OpenClaw credentials 读取**

```python
# core/config.py 新增配置
@dataclass
class EmbeddingConfig:
    provider: str = "volcengine"  # 或 "openai", "bailian", "deepseek"
    model: str = "text-embedding-async"
    api_key_env: str = "EMBEDDING_API_KEY"  # 从环境变量读取
```

**使用方式**：
- API key 通过 `os.environ[config.embedding.api_key_env]` 读取
- 或通过 OpenClaw credentials store 读取（更安全）
- embedding 函数通过 LLM client 的 `embed()` 接口调用

---

## 5B. 技术路线决策（2026-04-07 weNix 确认）

**Q：断言已知检查，用 embedding 相似度还是 LLM 判断？**

**A：用 embedding 相似度。**

理由：
1. **成本**：embedding 计算 ~0.001/次，LLM 判断 ~0.01/次，10 倍差距
2. **速度**：embedding 推理 ~10ms，LLM 判断 ~1s，100 倍差距
3. **一致性**：embedding 的相似度是客观数值，LLM 可能因 prompt 不同而波动
4. **准确性**：对"Mamba uses SSM" vs "State Space Models"这种表述差异，embedding 的语义理解比 LLM 更稳定

**Embedding 服务：使用 OpenClaw 的 embedding 服务（不硬编码 API key）**

实现方式：
- embedding 函数通过 `EMBEDDING_PROVIDER` 配置指定使用哪个 provider
- API key 从环境变量 `EMBEDDING_API_KEY` 或 OpenClaw credentials 读取
- 支持多 provider fallback（如果 primary provider 不可用）

```python
# 配置示例（config.json）
{
  "embedding": {
    "provider": "volcengine",   # 或 "openai", "bailian"
    "model": "text-embedding-async"
  }
}

# 环境变量
EMBEDDING_API_KEY=xxx  # 不硬编码，从环境读取
```

备选方案（如果 embedding 服务不可用）：
- LLM 判断：直接问"这个断言是否已包含在已有知识中？"
- 问题：每次断言检查多一次 LLM 调用，成本高，但作为 fallback 可用

---

## 6. 迁移计划

### Phase 1：基础架构（新增文件）

1. 新增 `core/knowledge_assertion.py`
2. 新增 `AssertionIndex` 类（SQLite + embedding）
3. 实现 `generate_assertions()` prompt 模板
4. 实现 `is_assertion_known()` 嵌入搜索
5. 初始化断言索引数据库

### Phase 2：集成 QualityV2

1. 在 `QualityV2Assessor.__init__` 中初始化 `KnowledgeAssertionEvaluator`
2. 修改 `assess_quality()` 主入口，使用断言评估作为主要通道
3. 保留 legacy 信息增益评估作为 fallback
4. 添加 graceful fallback 逻辑

### Phase 3：冷启动

1. 对已有 KG 里所有 topics，生成断言并建立索引
2. 对新探索，直接使用断言评估

---

## 7. 预期效果

### 当前

```
Topic: "Mamba"
Summary: "Mamba is a state space model for sequence modeling"
Quality: 0.0（QualityV2 误判为 topic 改写）
```

### v0.2.8

```
Topic: "Mamba"
Summary: "Mamba is a state space model for sequence modeling"

断言生成:
1. "Mamba is a type of state space model (SSM)"       → KG 里已有 "State Space Models" 相关 → 已知
2. "Mamba achieves O(N) inference vs Transformer's O(N²)" → KG 里没有 → 新知识
3. "Mamba was proposed by Gu and Dao"                  → KG 里没有 → 新知识

新断言数: 2/3
Quality: (2/3) × 10 = 6.7
```

### 彻底失败案例（真正没新知识）

```
Topic: "Corrosion resistance testing of offshore engineering harnesses"
Summary: "This paper discusses corrosion resistance testing methods for offshore engineering harnesses."

断言:
1. "Corrosion resistance testing is used for offshore harnesses"  → 已知（topic 本身）
2. "Offshore harnesses are tested for corrosion"                  → 已知（topic 本身）
3. "Corrosion testing uses standard methods"                     → 已知

新断言数: 0/3
Quality: 0.0 ✓（正确）
```

---

## 8. 验收标准

1. **无假 0.0**：对有实质内容的 summary，不再给 0.0 分
2. **真 0.0 正确**：对纯 topic 改写，正确识别为 0.0
3. **断言可复用**：断言存入索引，后续探索可以查到
4. **向后兼容**：断言评估失败时，回退到 legacy QualityV2
5. **冷启动完成**：已有 KG 的 summaries 都生成断言并存入索引

---

## 9. 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `core/knowledge_assertion.py` | 新增 | 断言评估器 |
| `core/quality_v2.py` | 修改 | 集成断言评估通道 |
| `shared_knowledge/assertion_index/assertions.db` | 新增 | SQLite 断言索引 |

---

## 10. 已知限制

1. **Embedding 模型依赖**：需要下载 `all-MiniLM-L6-v2`（~80MB），离线环境需提前准备
2. **第一个断言必然新**：索引为空时，第一个断言总是新的（冷启动偏差）
3. **断言质量依赖 LLM**：如果 LLM 生成的断言不好（太泛泛），会导致误判
4. **SQLite 性能**：断言超过 10 万条时，线性扫描会慢，需要后期切 FAISS
5. **embedding 阈值敏感性**：0.82 是经验值，可能需要根据实际效果调整
