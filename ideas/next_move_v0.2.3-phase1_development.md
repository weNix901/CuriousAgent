# Curious Agent v0.2.3 — Phase 3：好奇心分解引擎 & 多 Provider 验证

> **Phase 3 目标**：实现树状分解 + 多 Provider 搜索验证 + emergent Provider 热力图
> 前置依赖：无（独立模块，可先行开发）
> 设计者：weNix + R1D3-researcher
> 文档版本：v1.0 | 2026-03-22

---

## 0. 背景：为什么需要 Phase 3

### 当前问题

```
用户输入/队列：agent
↓
探索：搜索 "agent" → 噪音（建筑公司、词典定义）
↓
结论：质量低，放弃
```

**根本原因**：Curious Agent 不知道"agent"由什么组成，直接搜一个泛词。

### 正确模式：先分解，再探索

```
输入：agent
↓
好奇心分解器 → 识别核心组成部分：
  agent
  ├── 记忆（memory）
  ├── 规划（planning）
  ├── 工具使用（tool use）
  ├── 上下文窗口（context window）
  └── harness ⭐（最近火热）
       ↓
对每个子节点探索，结果写回父节点
```

### Phase 3 与 Phase 1/2 的关系

```
CuriosityEngine 选 topic（Phase 2 的 select_next_v2）
    ↓
Phase 3: CuriosityDecomposer（本文）
    - 把泛 topic 分解为具体子 topic
    - 多 Provider 搜索验证，过滤 LLM 幻觉
    ↓
Explorer 探索具体子 topic
    ↓
Phase 1: Agent-Behavior-Writer（结果写入行为文件）
Phase 2: MetaCognitiveMonitor（评估探索质量）
```

**Phase 3 是所有探索的前置条件**。

---

## 1. 四级级联分解引擎

### 1.1 分解流程

```
输入：topic（如 "agent"）
    ↓
【Step 1】LLM 推理 → 生成候选 sub-topics（允许有幻觉）
    ↓
【Step 2】多 Provider 搜索验证 → 过滤不存在的主题
    ↓
【Step 3】知识图谱补充 → 从已有结构推断父子关系
    ↓
【Step 4】澄清机制 → 无法判断时询问用户
    ↓
输出：高质量 sub-topics 列表 → 入队探索
```

### 1.2 Step 1：LLM 推理生成候选

```python
def generate_candidates(topic: str) -> list[str]:
    """
    用 LLM 推理给定 topic 的常见组成部分
    允许有噪音候选（后续 Step 2 过滤）
    """
    prompt = f"""针对 "{topic}" 这个话题，识别它最常见的子领域或组成部分。

要求：
- 列出 3-7 个子话题
- 每个子话题格式：[子话题名称] - [一句话说明]
- 优先列出技术领域相关的子话题

格式示例：
- agent_memory - AI Agent 的记忆系统，包括短期和长期记忆
- agent_planning - AI Agent 的任务规划和重规划能力
..."""
    
    response = llm.chat(prompt)
    # 解析成结构化列表
    candidates = parse_candidates(response)
    return candidates
```

### 1.3 Step 2：多 Provider 搜索验证（核心）

这是防止 LLM 幻觉污染知识图谱的关键层。

```python
async def verify_candidates(
    candidates: list[str],
    providers: list[SearchProvider]
) -> list[dict]:
    """
    并行向多个搜索 Provider 验证候选 sub-topics
    0 Provider 有结果 = 幻觉，丢弃
    2+ Provider 有结果 = 有效，保留
    """
    results = []
    
    for candidate in candidates:
        provider_results = {}
        
        # 并行查询所有 Provider
        tasks = [
            provider.search(candidate)
            for provider in providers
        ]
        responses = await asyncio.gather(*tasks, return_experiments=True)
        
        for provider, response in zip(providers, responses):
            if response and response.get("result_count", 0) > 0:
                provider_results[provider.name] = response["result_count"]
        
        # 统计验证结果
        total_count = sum(provider_results.values())
        provider_count = len(provider_results)
        
        results.append({
            "candidate": candidate,
            "provider_results": provider_results,
            "total_count": total_count,
            "provider_count": provider_count,
            "signal_strength": classify_signal(provider_count, total_count),
            "verified": provider_count >= 2  # 2+ Provider 确认为有效
        })
    
    # 过滤：只保留 verified=True 的
    verified = [r for r in results if r["verified"]]
    return verified
```

### 1.4 信号强度分级

```
0 Provider 有结果  → 丢弃（LLM 幻觉）
1 Provider 有结果  → 可疑，降低优先级
2 Provider 有结果  → 弱信号，低优先级入队
3+ Provider 有结果 → 强信号，正常入队

结果数量分级：
  < 10    → 弱信号（可能是长尾话题）
  10-100  → 中等信号
  100+    → 强信号（热门话题）
```

### 1.5 Step 3：知识图谱补充

```python
def kg_augment(topic: str, verified_subtopics: list[dict]) -> list[dict]:
    """
    从 KG 已有结构补充父子关系
    如果 graph 中已有 topic → subtopic 的边，直接继承
    """
    kg = knowledge_graph.get_state()
    enriched = []
    
    for item in verified_subtopics:
        subtopic = item["candidate"]
        
        # 检查 KG 中是否已有此连接
        existing_children = kg.get("topics", {}).get(topic, {}).get("children", [])
        
        if subtopic in existing_children:
            # KG 已知，直接继承
            item["kg_confirmed"] = True
            item["relation"] = "known"
        else:
            # KG 新增，建立连接
            item["kg_confirmed"] = False
            item["relation"] = "inferred"
        
        enriched.append(item)
    
    return enriched
```

### 1.6 Step 4：澄清机制

```python
class ClarificationNeeded(Exception):
    """当无法确定 topic 领域时抛出"""
    def __init__(self, topic: str, alternatives: list[str]):
        self.topic = topic
        self.alternatives = alternatives
        super().__init__(f"无法确定 '{topic}' 的领域，请选择或输入具体领域")

def decompose_with_clarification(topic: str) -> list[dict]:
    """
    分解主函数，包含澄清机制
    """
    candidates = generate_candidates(topic)
    verified = await verify_candidates(candidates, providers)
    
    if not verified:
        # 三层都无法判断 → 抛出澄清
        raise ClarificationNeeded(
            topic=topic,
            alternatives=["AI/Agent", "软件开发", "通用概念"]
        )
    
    enriched = kg_augment(topic, verified)
    return enriched
```

### 1.7 OpenClaw 澄清路由

```python
# 在 curious_agent.py 或 OpenClaw 的 hook 中
try:
    subtopics = decompose_with_clarification(topic)
except ClarificationNeeded as e:
    # 通知主 Agent（OpenClaw）询问用户
    send_feishu_message(
        f"🤔 无法确定「{e.topic}」的领域，请选择：\n" +
        "\n".join(f"{i+1}. {a}" for i, a in enumerate(e.alternatives))
    )
    # 等待用户回复后继续
    user_answer = wait_for_feishu_reply()
    # 用用户指定的领域重新分解
    subtopics = decompose_with_clarification(f"{e.topic} {user_answer}")
```

---

## 2. 插件化搜索 Provider 架构

### 2.1 抽象接口

```python
from abc import ABC, abstractmethod

class SearchProvider(ABC):
    """搜索 Provider 抽象接口"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称"""
        pass
    
    @abstractmethod
    async def search(self, query: str) -> dict:
        """
        执行搜索
        Returns: {
            "results": [...],
            "result_count": int,
            "raw": {...}
        }
        """
        pass
    
    @abstractmethod
    async def related_terms(self, query: str) -> list[dict]:
        """
        获取相关搜索词
        Returns: [{"term": str, "query_count": int}, ...]
        """
        pass
```

### 2.2 已实现 Provider

```python
class BraveSearchProvider(SearchProvider):
    """Brave Search（当前已接入）"""
    def __init__(self, api_key: str):
        self.name = "brave"
        self.api_key = api_key
    
    async def search(self, query: str) -> dict:
        # 调用 Brave Search API
        ...

class SerperProvider(SearchProvider):
    """Serper Google Search"""
    def __init__(self, api_key: str):
        self.name = "serper"
        self.api_key = api_key

class BochaProvider(SearchProvider):
    """Bocha 中文搜索"""
    def __init__(self, api_key: str):
        self.name = "bocha"
        self.api_key = api_key
```

### 2.3 Provider 配置

```yaml
# curious-agent.yaml
search_providers:
  brave:
    enabled: true
    api_key: "${BRAVE_API_KEY}"
    priority: 1
  
  serper:
    enabled: true
    api_key: "${SERPER_API_KEY}"
    priority: 2
  
  bocha:
    enabled: true
    api_key: "${BOCHA_API_KEY}"
    priority: 3
```

环境变量注入，不在代码里写 key。

### 2.4 Provider 注册中心

```python
class ProviderRegistry:
    """搜索 Provider 注册中心"""
    
    def __init__(self):
        self._providers: dict[str, SearchProvider] = {}
    
    def register(self, provider: SearchProvider):
        self._providers[provider.name] = provider
    
    def get_all(self) -> list[SearchProvider]:
        return list(self._providers.values())
    
    def get_enabled(self) -> list[SearchProvider]:
        return [p for p in self._providers.values() if p.enabled]

# 全局注册中心
registry = ProviderRegistry()
registry.register(BraveSearchProvider(os.getenv("BRAVE_API_KEY")))
registry.register(SerperProvider(os.getenv("SERPER_API_KEY")))
registry.register(BochaProvider(os.getenv("BOCHA_API_KEY")))
```

---

## 3. Emergent 功能：Provider 覆盖热力图

### 3.1 副产品怎么来的

每次多 Provider 验证运行时，会自然积累以下数据：

```python
# 每次验证后记录
verification_log.append({
    "timestamp": "...",
    "candidate": "...",
    "provider_results": {
        "brave": 150,
        "serper": 300,
        "bocha": 80
    },
    "topic_language": "en",  # 从内容推断
    "topic_domain": "AI/agent"  # 从上下文推断
})
```

### 3.2 覆盖热力图

从积累的数据里，可以 emergent 地生成：

```python
def compute_coverage_heatmap(verification_log: list) -> dict:
    """
    从验证日志中 emergent 地生成 Provider 覆盖热力图
    不需要人工配置，纯粹从数据里推断
    """
    heatmap = {}
    
    for entry in verification_log:
        lang = entry.get("topic_language", "unknown")
        domain = entry.get("topic_domain", "unknown")
        
        for provider, count in entry.get("provider_results", {}).items():
            key = (lang, domain)
            if key not in heatmap:
                heatmap[key] = {}
            heatmap[key][provider] = heatmap[key].get(provider, 0) + count
    
    return heatmap
```

### 3.3 推断 Provider 能力边界

```
热力图示例输出：
{
    ("en", "AI/agent"):   {"serper": 800, "brave": 400, "bocha": 50},
    ("zh", "AI/agent"):   {"bocha": 600, "serper": 200, "brave": 30},
    ("en", "general"):    {"serper": 500, "brave": 500, "bocha": 100},
    ("ru", "any"):        {"serper": 10, "brave": 5, "bocha": 0},  # 小语种覆盖弱
}
```

**emergent 洞察**：
- 英文 AI topics → Serper 强，Brave 中，Bocha 弱
- 中文 AI topics → Bocha 强，Serper 中，Brave 弱
- 小语种 → 所有 Provider 都弱 → Clarification 触发率高（可能是冷门领域）

### 3.4 热力图的应用

**1. 置信度校准**
```python
# 小语种话题自动降低置信度
if heatmap.get((lang, domain), {}).get(provider_count, 0) < 10:
    confidence *= 0.7  # 降低置信度
```

**2. Provider 优先级排序**
```python
# 给定语言+领域，选择最合适的 Provider 顺序
def best_provider_order(lang: str, domain: str) -> list[str]:
    heat = compute_coverage_heatmap(verification_log)
    scores = heat.get((lang, domain), {})
    return sorted(scores.keys(), key=lambda p: scores[p], reverse=True)
```

**3. 新语言扩展信号**
```
某小语种（ru）突然 serper 覆盖率从 10 → 200
→ 说明 Serper 可能加了俄语索引
→ Curious Agent 自动知道俄语话题的置信度提升了
```

---

## 4. 好奇心分解器 API

### 4.1 核心类

文件：`/root/dev/curious-agent/core/curiosity_decomposer.py`

```python
class CuriosityDecomposer:
    """
    好奇心分解器
    
    输入：一个 topic（如 "agent"）
    输出：一组高质量 sub-topics，带验证状态
    
    设计原则：
    - 四级级联：LLM → 搜索验证 → KG → 澄清
    - 多 Provider 并行验证
    - 插件化 Provider 架构
    """
    
    def __init__(
        self,
        llm_client,
        provider_registry: ProviderRegistry,
        kg
    ):
        self.llm = llm_client
        self.providers = provider_registry
        self.kg = kg
    
    async def decompose(self, topic: str) -> list[dict]:
        """
        主入口：分解 topic 为 sub-topics
        
        Returns:
            [
                {
                    "sub_topic": str,
                    "relation": str,          # "component" | "sibling" | "abstract"
                    "signal_strength": str,    # "weak" | "medium" | "strong"
                    "provider_coverage": dict, # {provider_name: count}
                    "verified": bool,
                    "source": str              # "llm" | "kg" | "both"
                },
                ...
            ]
        """
        try:
            # Step 1: LLM 生成候选
            candidates = await self._llm_generate_candidates(topic)
            
            # Step 2: 多 Provider 验证
            verified = await self._verify_with_providers(candidates)
            
            if not verified:
                # Step 4: 澄清机制
                raise ClarificationNeeded(topic=topic)
            
            # Step 3: KG 补充
            enriched = self._kg_augment(topic, verified)
            
            return enriched
            
        except ClarificationNeeded:
            raise  # 向上传递
    
    async def _llm_generate_candidates(self, topic: str) -> list[str]:
        """Step 1: LLM 推理生成候选"""
        prompt = f"""针对 "{topic}" 这个话题，识别它最常见的子领域或组成部分。

要求：
- 列出 3-7 个子话题
- 每个格式：[子话题名称] - [一句话说明]
- 优先技术领域相关的子话题

输出格式（直接输出列表，不需要其他文字）：
- topic1 - 说明1
- topic2 - 说明2
- topic3 - 说明3"""
        
        response = self.llm.chat(prompt)
        return self._parse_candidates(response)
    
    async def _verify_with_providers(self, candidates: list[str]) -> list[dict]:
        """Step 2: 多 Provider 并行验证"""
        if not candidates:
            return []
        
        tasks = [
            self._verify_single(candidate)
            for candidate in candidates
        ]
        results = await asyncio.gather(*tasks, return_experiments=True)
        
        # 只返回 2+ Provider 验证通过的
        return [r for r in results if r and r.get("provider_count", 0) >= 2]
    
    async def _verify_single(self, candidate: str) -> dict:
        """验证单个候选：并行查所有 Provider"""
        tasks = [provider.search(candidate) for provider in self.providers.get_enabled()]
        responses = await asyncio.gather(*tasks, return_experiments=True)
        
        provider_results = {}
        for provider, response in zip(self.providers.get_enabled(), responses):
            if response and response.get("result_count", 0) > 0:
                provider_results[provider.name] = response["result_count"]
        
        total = sum(provider_results.values())
        
        return {
            "candidate": candidate,
            "provider_results": provider_results,
            "total_count": total,
            "provider_count": len(provider_results),
            "signal_strength": self._classify_signal(len(provider_results), total),
            "verified": len(provider_results) >= 2
        }
    
    def _kg_augment(self, parent: str, verified: list[dict]) -> list[dict]:
        """Step 3: KG 补充"""
        kg_children = self.kg.get(parent, {}).get("children", [])
        
        for item in verified:
            item["kg_confirmed"] = item["candidate"] in kg_children
            item["source"] = "llm+kg" if item["kg_confirmed"] else "llm_only"
            item["relation"] = "component"
        
        return verified
    
    def _parse_candidates(self, response: str) -> list[str]:
        """解析 LLM 输出为候选列表"""
        candidates = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if line.startswith("- "):
                candidate = line[2:].split(" - ")[0].strip()
                candidates.append(candidate)
        return candidates
    
    def _classify_signal(self, provider_count: int, total_count: int) -> str:
        """信号强度分级"""
        if provider_count >= 3 and total_count >= 100:
            return "strong"
        elif provider_count >= 2 and total_count >= 10:
            return "medium"
        else:
            return "weak"
```

### 4.2 集成到探索流程

```python
async def run_one_cycle_v3():
    """
    v0.2.3 版探索循环（集成分解器）
    """
    engine = CuriosityEngine()
    decomposer = CuriosityDecomposer(
        llm_client=llm,
        provider_registry=registry,
        kg=knowledge_graph
    )
    
    # 选择 topic
    next_item = engine.select_next_v2()
    if not next_item:
        return {"status": "idle"}
    
    topic = next_item["topic"]
    
    # 分解（新增）
    try:
        subtopics = await decomposer.decompose(topic)
    except ClarificationNeeded:
        # 通知用户澄清
        notify_user_clarification(topic)
        return {"status": "clarification_needed", "topic": topic}
    
    # 取信号最强的 subtopic 探索（而非原始 topic）
    if subtopics:
        best = max(subtopics, key=lambda x: x["total_count"])
        explore_topic = best["sub_topic"]
    else:
        explore_topic = topic
    
    # 探索
    explorer = Explorer(exploration_depth=next_item.get("depth", "medium"))
    result = explorer.explore({"topic": explore_topic, "depth": next_item["depth"]})
    
    # 探索结果写回 KG（建立父子关系）
    kg.add_child(topic, explore_topic)
    
    return result
```

---

## 5. 质量门控（入队前过滤）

### 5.1 入队质量门

即使通过分解验证，以下情况不入队：

```python
BLACKLIST = {
    # 太泛
    "agent", "agents", "cognit", "cognition",
    "architecture", "architectures",
    "system", "systems",
    # 非实质
    "overview", "introduction", "what is",
    "how to", "getting started",
}

def should_queue(topic: str) -> tuple[bool, str]:
    """判断 topic 是否应该入队"""
    
    # 1. 太短
    if len(topic.split()) < 2:
        return False, "too_short"
    
    # 2. 泛词黑名单
    topic_lower = topic.lower()
    if topic_lower in BLACKLIST:
        return False, f"blacklist: {topic}"
    
    # 3. 已在队列相似项（去重）
    if is_similar_to_queued(topic):
        return False, "duplicate_in_queue"
    
    return True, "ok"
```

### 5.2 相似度去重

```python
def is_similar_to_queued(topic: str) -> bool:
    """检查是否与队列中已有 topic 过于相似"""
    queue = kg.get_pending_topics()
    
    for existing in queue:
        # 简单词重叠检查
        shared = set(topic.split()) & set(existing.split())
        overlap_ratio = len(shared) / max(len(set(topic.split())), 1)
        
        if overlap_ratio > 0.7:
            return True  # 太相似，不入队
    
    return False
```

---

## 6. 实施检查清单

### 核心模块
- [ ] 创建 `core/curiosity_decomposer.py`
- [ ] 实现 `SearchProvider` 抽象接口
- [ ] 实现 `BraveSearchProvider`
- [ ] 实现 `SerperProvider`
- [ ] 实现 `BochaProvider`
- [ ] 实现 `ProviderRegistry`
- [ ] 实现 `verify_candidates()` 多 Provider 并行验证
- [ ] 实现 `kg_augment()` KG 补充
- [ ] 实现 `ClarificationNeeded` 抛出 + OpenClaw 路由

### 集成
- [ ] 修改 `curious_agent.py` 的 `run_one_cycle()` 调用分解器
- [ ] 修改 `curiosity_engine.py` 的入队逻辑，加质量门
- [ ] 实现 Provider 热力图计算（`compute_coverage_heatmap`）

### 验证
- [ ] 输入"agent" → 输出 ["agent memory", "agent planning", ...]（非噪音）
- [ ] LLM 幻觉词（如"agent esoteric"）被过滤
- [ ] 多 Provider 并行验证，响应时间 < 5秒
- [ ] Provider 热力图正确生成

---

## 7. 技术指标

| 指标 | 目标 |
|------|------|
| 分解延迟（不含网络） | < 500ms |
| 分解延迟（含 3 Provider 并行） | < 5s |
| 幻觉过滤准确率 | > 90%（多 Provider 一致性判断） |
| Provider 热力图更新 | 每次验证后增量更新 |
| 泛词入队率 | < 5% |

---

## 8. 关键设计决策

| 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|
| Provider 验证门槛 | 1/2/3 个 Provider | **2+** | 1个不够（可能是该 Provider 的噪音覆盖），3个太严格 |
| 候选生成策略 | 仅 LLM / 仅 KG / 混合 | **LLM 为主，KG 补充** | LLM 泛化能力强，KG 保证一致性 |
| 澄清粒度 | 问具体 topic / 问领域 | **问领域** | 太具体的问题用户也难答 |
| 热力图更新频率 | 实时 / 每日汇总 | **每日汇总** | 实时更新成本高，daily batch 足够 |

---

## 9. 与 Phase 1/2 的接口

```
Phase 3 输出：
  subtopics[] → 入队 → Explorer 探索
                           ↓
                Phase 2: MetaCognitiveMonitor.assess()
                           ↓
                Phase 1: Agent-Behavior-Writer.process()
```

Phase 3 不依赖 Phase 1/2，但 Phase 1/2 的效果直接取决于 Phase 3 的分解质量。

---

## 10. 参考资料

- `next_move.md` — v0.2.3 总体设计
- `next_move_v0.2.3-phase1.md` — Phase 1：行为闭环
- `next_move_v0.2.3-phase2.md` — Phase 2：质量评估升级

---

_文档版本: v1.0_
_创建时间: 2026-03-22_
