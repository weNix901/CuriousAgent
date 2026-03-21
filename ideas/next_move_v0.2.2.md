# Curious Agent v0.2.2 — Next Move

> 为 OpenCode 提供实现路径参考
> 创建时间：2026-03-21 | 设计者：R1D3-researcher + weNix
> 更新：2026-03-21（补充质量评分算法 + 通知机制 + 配置管理 + 多 LLM 架构）

---

## 一、核心问题（v0.2.1 生产环境证据）

```
最近 10 次探索日志：
  Topic: "Embodied Generative Cognitive"
  触发: 00:00 → 00:30 → 01:00 → ... → 04:00（连续10次）
  notified_user: 全部 false
  exploration_depth / layers_explored: 全部 N/A
  
结论：同一话题被无意义重复探索 10 次，无任何新发现。
```

| 问题 | 表现 | 根因 |
|------|------|------|
| **无限循环** | 同一话题被探索 10+ 次 | 缺乏"已达上限"检查 |
| **价值缺失** | 60 次探索，0 次通知用户 | 缺乏探索质量评估 |

---

## 二、OpenCode 移交状态

| 内容 | 状态 | 位置 |
|------|------|------|
| 设计文档 | ✅ 完整 | `docs/plans/2026-03-21-v0.2.2-metacognitive-monitor-design.md` |
| 核心 .py 模块 | ❌ 未实现 | 需 OpenCode 开发 |
| API 端点 | ❌ 未实现 | 需 OpenCode 开发 |
| Web UI 区域 | ❌ 未实现 | 需 OpenCode 开发 |

---

## 三、推荐实现路径（按依赖排序）

```
Step 0          Step 1           Step 2           Step 3           Step 4           Step 5           Step 6
┌─────────┐   ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ LLM     │   │Knowl-    │     │ Meta-   │     │ Meta-   │     │ 集成    │     │  API    │     │ Web UI  │
│Manager  │ ─▶│edgeGraph │ ──▶ │Cognitive│ ──▶ │Cognitive│ ──▶ │ MGV     │ ──▶ │ 端点    │ ──▶ │ 元认知  │
│多LLM路由│   │扩展      │     │Monitor  │     │Controller│     │ 循环    │     │         │     │ 区域    │
└─────────┘   └─────────┘     └─────────┘     └─────────┘     └─────────┘     └─────────┘     └─────────┘
```

**Step 0 为新增**：先实现多 LLM 路由管理器，解决资源瓶颈

---

## 四、Step 0: LLMManager 多路由架构（先行）

### 4.0 当前 LLM 使用情况

| 模块 | 调用方式 | 用途 | 频率 |
|------|---------|------|------|
| `core/llm_client.py` | 直接调用 volcengine | Layer 3 洞察生成 | 每轮 deep 探索 1 次 |
| `core/intrinsic_scorer.py` | LLMClient | 内在信号评估（pred_error/graph_density/novelty） | 每次评分 1 次 |
| `core/meta_cognitive_monitor.py`（待实现） | LLMClient | 质量评分（关键词提取/用户相关性） | 每次探索 2-3 次 |

**当前瓶颈**：单一模型，所有 LLM 调用串行执行，资源成为瓶颈

### 4.0.1 行业多 LLM 方案对比

| 方案 | 代表 | 优点 | 缺点 |
|------|------|------|------|
| **API 网关聚合** | PortKey, Helicone | 统一入口，负载均衡，监控完善 | 引入外部依赖 |
| **客户端路由** | 自研 | 灵活，成本可控，无外部依赖 | 需要自己实现路由逻辑 |
| **模型池** | 内部模型服务 | 适合大模型部署 | 运维复杂 |

### 4.0.2 推荐：客户端多 Provider 路由

**架构**：

```
┌─────────────────────────────────────────────────────────────┐
│                      LLMManager（单例）                      │
├─────────────────────────────────────────────────────────────┤
│  providers: {                                              │
│    "volcengine": LLMProvider(api_key, url, model, weight),│
│    "openai":     LLMProvider(api_key, url, model, weight),│
│    "anthropic":  LLMProvider(api_key, url, model, weight),│
│  }                                                         │
│                                                             │
│  selection_strategy: "weighted_rr" | "capability"          │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Router（路由选择）                         │
│                                                             │
│  weighted_round_robin: 按 weight 权重轮询                    │
│  capability: 根据任务类型选择最合适的模型                    │
└─────────────────────────────────────────────────────────────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
     ┌──────────┐   ┌──────────┐   ┌──────────┐
     │volcengine│   │ OpenAI   │   │Anthropic │
     │ ark-code │   │ gpt-4o   │   │ claude-3  │
     │  (得快)  │   │  (强大)  │   │ (推理强) │
     └──────────┘   └──────────┘   └──────────┘
```

**使用场景分工建议**：

| 场景 | 推荐模型 | 理由 |
|------|---------|------|
| 关键词提取 | volcengine (ark-code) | 简单任务，不需要强推理，weight 高 |
| 论文对比洞察（Layer 3） | anthropic (claude) | 复杂推理任务，需要长上下文 |
| 内在信号评估（ICM） | openai (gpt-4o) | 平衡速度与能力 |
| 质量评分 | volcengine (ark-code) | 任务简单，高并发 |

**实现代码**：

```python
# core/llm_manager.py

import os
import random
from dataclasses import dataclass
from typing import Optional

@dataclass
class LLMProvider:
    name: str
    api_url: str
    model: str
    api_key: str
    timeout: int = 60
    weight: int = 1  # 权重越高，被选中的概率越高
    capabilities: list = None  # 支持的任务类型

    def __post_init__(self):
        self.capabilities = self.capabilities or ["general"]


class LLMManager:
    """
    多 LLM Provider 管理器
    
    支持：
    1. weighted_round_robin — 按权重轮询（默认）
    2. capability — 根据任务类型选模型
    """
    
    _instance: Optional["LLMManager"] = None
    
    def __init__(self, config: dict = None):
        config = config or {}
        self.providers: list[LLMProvider] = []
        self._init_providers(config.get("providers", {}))
        self.strategy = config.get("selection_strategy", "weighted_rr")
    
    @classmethod
    def get_instance(cls, config: dict = None) -> "LLMManager":
        if cls._instance is None:
            cls._instance = cls(config)
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """重置单例（测试用）"""
        cls._instance = None
    
    def _init_providers(self, providers_config: dict):
        """初始化所有 provider"""
        for name, cfg in providers_config.items():
            api_key = os.environ.get(f"{name.upper()}_API_KEY") or cfg.get("api_key")
            if not api_key:
                print(f"[LLMManager] Skipping {name}: no API key")
                continue
            self.providers.append(LLMProvider(
                name=name,
                api_url=cfg.get("api_url", ""),
                model=cfg.get("model", ""),
                api_key=api_key,
                timeout=cfg.get("timeout", 60),
                weight=cfg.get("weight", 1),
                capabilities=cfg.get("capabilities", ["general"]),
            ))
        
        if not self.providers:
            print("[LLMManager] Warning: No LLM providers configured")
    
    def select(self, task_type: str = "general") -> LLMProvider:
        """根据策略选择 provider"""
        if len(self.providers) == 1:
            return self.providers[0]
        
        if self.strategy == "capability":
            return self._capability_based(task_type)
        else:
            return self._weighted_rr()
    
    def _weighted_rr(self) -> LLMProvider:
        """加权轮询"""
        total_weight = sum(p.weight for p in self.providers)
        r = random.randint(1, total_weight)
        cumsum = 0
        for p in self.providers:
            cumsum += p.weight
            if r <= cumsum:
                return p
        return self.providers[-1]
    
    def _capability_based(self, task_type: str) -> LLMProvider:
        """基于能力的模型选择"""
        for p in self.providers:
            if task_type in p.capabilities:
                return p
        return self.providers[0]
    
    def chat(self, prompt: str, task_type: str = "general", **kwargs) -> str:
        """向选中的 provider 发送请求"""
        provider = self.select(task_type)
        
        import requests
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": provider.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2000),
        }
        
        response = requests.post(
            provider.api_url,
            headers=headers,
            json=payload,
            timeout=provider.timeout
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    
    def chat_batch(self, prompts: list, task_type: str = "general", max_workers: int = 3) -> list:
        """并发发送多个 LLM 请求"""
        import concurrent.futures
        results = [None] * len(prompts)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.chat, p, task_type): i for i, p in enumerate(prompts)}
            for future in concurrent.futures.as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    print(f"[LLMManager] Request {idx} failed: {e}")
                    results[idx] = ""
        return results
```

**config.json 多 Provider 配置示例**：

```json
{
  "llm": {
    "default_provider": "volcengine",
    "selection_strategy": "capability",
    "providers": {
      "volcengine": {
        "api_url": "https://ark.cn-beijing.volces.com/api/coding/v3/chat/completions",
        "model": "ark-code-latest",
        "timeout": 60,
        "weight": 3,
        "capabilities": ["fast", "general", "keywords", "quality"]
      },
      "openai": {
        "api_url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o",
        "timeout": 120,
        "weight": 2,
        "capabilities": ["general", "icm_signals", "creative"]
      },
      "anthropic": {
        "api_url": "https://api.anthropic.com/v1/messages",
        "model": "claude-sonnet-4-20250514",
        "timeout": 120,
        "weight": 1,
        "capabilities": ["reasoning", "insights", "analysis"]
      }
    }
  }
}
```

**改造现有 LLMClient**：

```python
# core/llm_client.py — 改造为委托给 LLMManager

class LLMClient:
    """兼容现有代码的 LLMClient，改为委托给 LLMManager"""
    
    def __init__(self, provider_name: str = None):
        from core.llm_manager import LLMManager
        self.manager = LLMManager.get_instance()
        self.provider_name = provider_name
    
    def chat(self, prompt: str, **kwargs) -> str:
        return self.manager.chat(prompt, task_type="general", **kwargs)
    
    def generate_insights(self, topic: str, papers: list, **kwargs):
        """论文洞察生成（Layer 3 专用）"""
        prompt = self._build_insight_prompt(topic, papers)
        return self.manager.chat(prompt, task_type="insights", **kwargs)
    
    def _build_insight_prompt(self, topic: str, papers: list) -> str:
        """构建洞察 prompt"""
        # 复用原有 prompt 构建逻辑
        parts = [f"研究主题: {topic}\n"]
        for i, paper in enumerate(papers, 1):
            parts.append(f"论文{i}: {paper.get('title', 'N/A')}\n")
            parts.append(f"摘要: {paper.get('abstract', '')[:300]}...\n")
            parts.append(f"关键发现: {', '.join(paper.get('key_findings', [])[:3])}\n\n")
        parts.append("请提供深度洞察报告。")
        return "".join(parts)
```

---

## 五、Step 1-6 详细设计

### Step 1: KnowledgeGraph 扩展（state.json 持久化）

**文件**：`core/knowledge_graph.py`

```python
def _ensure_meta_cognitive(self, state: dict) -> dict:
    """确保 state.json 包含 meta_cognitive 字段"""
    if "meta_cognitive" not in state:
        state["meta_cognitive"] = {
            "explore_counts": {},
            "marginal_returns": {},
            "last_quality": {},
            "exploration_log": []
        }
    return state

def mark_topic_done(self, topic: str, reason: str):
    """标记话题为已完成，阻止后续探索"""

def update_last_exploration_notified(self, topic: str, notified: bool):
    """更新最近一次探索的 notified 标记"""

def get_topic_keywords(self, topic: str) -> list:
    """获取话题已有关键词（用于质量评估）"""

def get_topic_depth(self, topic: str) -> float:
    """获取话题当前深度"""
```

---

### Step 2: MetaCognitiveMonitor（纯监测模块）

**文件**：`core/meta_cognitive_monitor.py`

```python
class MetaCognitiveMonitor:
    def __init__(self, kg: KnowledgeGraph, llm_client=None):
        self.kg = kg
        self.llm = llm_client  # 用于 LLM 评估（可选）
    
    # 只读查询
    def get_explore_count(self, topic: str) -> int: ...
    def get_marginal_returns(self, topic: str) -> list[float]: ...
    def get_last_quality(self, topic: str) -> float: ...
    
    # 评估（核心：质量评分算法）
    def assess_exploration_quality(self, topic: str, findings: dict) -> float:
        """
        三维质量评分（0-10）
        - new_discovery_rate × 0.35
        - depth_improvement × 0.35
        - user_relevance × 0.30
        """
    def compute_marginal_return(self, topic: str, current_quality: float) -> float: ...
    
    # 写入
    def record_exploration(self, topic: str, quality: float,
                           marginal_return: float, notified: bool): ...
    
    # 私有辅助方法
    def _extract_keywords(self, text: str) -> list: ...
    def _assess_depth_score(self, findings: dict) -> float: ...
    def _compute_user_relevance(self, topic: str) -> float: ...
    def _fallback_quality(self, topic: str, findings: dict) -> float: ...
```

**assess_exploration_quality 完整算法**：

```python
def assess_exploration_quality(self, topic: str, findings: dict) -> float:
    # Signal 1: 新关键词率 (0-1) × 权重 0.35
    current_keywords = self._extract_keywords(findings.get("summary", ""))
    known_keywords = set(self.kg.get_topic_keywords(topic))
    new_keywords = [k for k in current_keywords if k not in known_keywords]
    new_discovery_rate = len(new_keywords) / max(len(current_keywords), 1)
    
    # Signal 2: 理解深度提升 (0-1) × 权重 0.35
    prev_depth = self.kg.get_topic_depth(topic)
    depth_score = self._assess_depth_score(findings)
    depth_improvement = min(1.0, depth_score / max(prev_depth + 1, 1))
    
    # Signal 3: 用户相关性 (0-1) × 权重 0.30
    user_relevance = self._compute_user_relevance(topic)
    
    quality = (new_discovery_rate * 0.35 + depth_improvement * 0.35 + user_relevance * 0.30) * 10
    return round(quality, 1)


def _extract_keywords(self, text: str) -> list:
    """从文本提取关键词（5-10个），优先 LLM，fail-fast 到规则"""
    if self.llm:
        prompt = f"从以下文本提取5-10个核心概念关键词（用逗号分隔）：\n{text[:500]}\n只返回关键词。"
        try:
            response = self.llm.chat(prompt)
            return [k.strip() for k in response.split(",") if k.strip()]
        except Exception:
            pass
    # 降级：规则提取
    import re
    words = re.findall(r'\b[a-z]{4,}\b', text.lower())
    stopwords = {'that', 'this', 'with', 'from', 'have', 'been', 'will', 'would', 'could', 'their'}
    return [w for w in words if w not in stopwords][:10]


def _assess_depth_score(self, findings: dict) -> float:
    """评估探索深度得分（0-10）"""
    summary_len = len(findings.get("summary", ""))
    source_count = len(findings.get("sources", []))
    paper_count = len(findings.get("papers", []))
    summary_score = min(1.0, summary_len / 1000)
    source_score = min(1.0, source_count / 5)
    paper_score = min(1.0, paper_count / 3)
    return (summary_score * 0.4 + source_score * 0.3 + paper_score * 0.3) * 10


def _compute_user_relevance(self, topic: str) -> float:
    """计算与用户兴趣的相关性（0-1）"""
    from core.config import get_config
    user_interests = get_config().user_interests
    if not user_interests:
        return 0.5
    if self.llm:
        prompt = f"评估话题与用户兴趣的相关性（0.0-1.0）：\n用户兴趣：{', '.join(user_interests)}\n待评估话题：{topic}\n只返回一个数字。"
        try:
            return max(0.0, min(1.0, float(self.llm.chat(prompt).strip())))
        except Exception:
            pass
    # 降级：关键词重叠率
    topic_words = set(topic.lower().split())
    interest_words = set(' '.join(user_interests).lower().split())
    return min(1.0, len(topic_words & interest_words) / max(len(topic_words), 1))
```

**边界处理**：
| 场景 | 处理 |
|------|------|
| 话题不存在 | `get_explore_count` → 0 |
| 无历史质量 | `compute_marginal_return` → 1.0 |
| LLM 提取失败 | 降级到规则提取 |
| LLM 评估失败 | 降级到纯统计 |
| `assess_exploration_quality` 完全失败 | 返回 5.0（默认中等） |
| state.json 损坏 | 初始化空 `meta_cognitive` 结构 |

---

### Step 3: MetaCognitiveController（纯决策模块）

**文件**：`core/meta_cognitive_controller.py`

```python
class MetaCognitiveController:
    def __init__(self, monitor: MetaCognitiveMonitor, config: dict = None):
        from core.config import get_config
        cfg = get_config()
        self.thresholds = {
            "max_explore_count": cfg.thresholds.max_explore_count,
            "min_marginal_return": cfg.thresholds.min_marginal_return,
            "high_quality_threshold": cfg.thresholds.high_quality_threshold,
        }
        if config:
            self.thresholds.update(config.get("thresholds", {}))
    
    def should_explore(self, topic: str) -> tuple[bool, str]: ...
    def should_continue(self, topic: str) -> tuple[bool, str]: ...
    def should_notify(self, topic: str) -> tuple[bool, str]: ...
```

**决策真值表**：

| 探索次数 | 边际收益趋势 | 质量分 | should_explore | should_continue | should_notify |
|---------|------------|--------|---------------|----------------|--------------|
| 0 | — | — | ✅ | — | — |
| 1 | 高(0.9) | 8.0 | ✅ | ✅ | ✅ 通知 |
| 2 | 低(0.1) | 6.0 | ✅ | ❌ 停止 | ❌ 不通知 |
| 3 | -0.2 | 4.0 | ❌ 阻止 | ❌ 停止 | ❌ 不通知 |
| 4+ | 任意 | 任意 | ❌ 阻止 | ❌ 停止 | ❌ 不通知 |

---

### Step 4: 集成到 CuriousAgent（Monitor-Generate-Verify 循环）

**文件**：`curious_agent.py`

```python
def run_one_cycle(self, topic: str):
    from core.meta_cognitive_monitor import MetaCognitiveMonitor
    from core.meta_cognitive_controller import MetaCognitiveController
    from core.event_bus import EventBus
    
    monitor = MetaCognitiveMonitor(self.kg, llm_client=self.llm_client)
    controller = MetaCognitiveController(monitor)
    
    # === Monitor: 探索前检查 ===
    allowed, reason = controller.should_explore(topic)
    if not allowed:
        logger.info(f"探索被阻止: {topic} — {reason}")
        self.kg.mark_topic_done(topic, reason)
        EventBus.emit("exploration.blocked", {"topic": topic, "reason": reason})
        return
    
    # === Generate: 执行探索 ===
    explorer = Explorer(exploration_depth=self.depth)
    findings = explorer.explore(topic)
    
    # === Monitor: 评估质量 ===
    quality = monitor.assess_exploration_quality(topic, findings)
    marginal = monitor.compute_marginal_return(topic, quality)
    monitor.record_exploration(topic, quality, marginal, notified=False)
    
    # === Verify: 决策 ===
    should_notify, notify_reason = controller.should_notify(topic)
    if should_notify:
        self.notify_user(topic, findings, quality)
        self.kg.update_last_exploration_notified(topic, True)
    
    continue_allowed, continue_reason = controller.should_continue(topic)
    if continue_allowed:
        self.kg.add_curiosity(topic, score=quality, reason=f"边际收益:{marginal:.2f}")
    else:
        self.kg.mark_topic_done(topic, continue_reason)


def notify_user(self, topic: str, findings: dict, quality: float):
    """触发通知，事件总线模式"""
    from core.event_bus import EventBus
    formatted = self._format_discovery(topic, findings, quality)
    
    EventBus.emit("discovery.high_quality", {
        "topic": topic,
        "quality": quality,
        "formatted": formatted,
        "timestamp": datetime.now().isoformat(),
    })
    EventBus.emit("notification.external", {
        "topic": topic,
        "quality": quality,
        "message": formatted,
    })
```

---

### Step 5: API 端点 + Web UI 区域

**文件**：`curious_api.py`、`ui/index.html`

```python
# API 端点
@app.get("/api/metacognitive/check")
def check_topic(topic: str): ...

@app.get("/api/metacognitive/state")
def get_meta_state(): ...

@app.get("/api/metacognitive/history/<topic>")
def get_topic_history(topic: str): ...
```

---

## 六、通知机制：事件总线 + 发现库双轨

```python
# core/event_bus.py

class EventBus:
    _subscribers: dict = {}
    
    @classmethod
    def subscribe(cls, event_type: str, handler: callable):
        cls._subscribers.setdefault(event_type, []).append(handler)
    
    @classmethod
    def emit(cls, event_type: str, payload: dict):
        for handler in cls._subscribers.get(event_type, []):
            try:
                handler(payload)
            except Exception as e:
                print(f"[EventBus] Handler error: {e}")
    
    @classmethod
    def unsubscribe(cls, event_type: str, handler: callable):
        cls._subscribers.get(event_type, []).remove(handler)
```

**事件类型**：

| 事件类型 | 触发时机 | 消费者 |
|---------|---------|--------|
| `discovery.high_quality` | 质量 >= 7.0 | `on_discovery_record`（写发现库） |
| `notification.external` | 质量 >= 7.0 | 飞书/Discord/钉钉 |
| `exploration.blocked` | 探索被阻止 | 记录日志 |
| `curiosity.injected` | 新增好奇心 | 记录日志 |

---

## 七、配置管理：config.json + dataclass 分层

**文件结构**：

```
curious-agent/
├── config.json              # 业务阈值（非敏感）
└── .env                     # API keys（不提交 git）
```

**config.json 结构**：

```json
{
  "meta_cognitive": {
    "max_explore_count": 3,
    "min_marginal_return": 0.3,
    "high_quality_threshold": 7.0
  },
  "user_interests": [
    "agent framework",
    "self-reflection",
    "metacognition"
  ],
  "notification": {
    "enabled": true,
    "min_quality": 7.0
  },
  "llm": {
    "default_provider": "volcengine",
    "selection_strategy": "capability",
    "providers": {
      "volcengine": {
        "api_url": "https://ark.cn-beijing.volces.com/api/coding/v3/chat/completions",
        "model": "ark-code-latest",
        "timeout": 60,
        "weight": 3,
        "capabilities": ["fast", "general", "keywords", "quality"]
      },
      "openai": {
        "api_url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o",
        "timeout": 120,
        "weight": 2,
        "capabilities": ["general", "icm_signals"]
      },
      "anthropic": {
        "api_url": "https://api.anthropic.com/v1/messages",
        "model": "claude-sonnet-4-20250514",
        "timeout": 120,
        "weight": 1,
        "capabilities": ["reasoning", "insights"]
      }
    }
  }
}
```

**配置加载实现**：

```python
# core/config.py

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

@dataclass
class MetaCognitiveThresholds:
    max_explore_count: int = 3
    min_marginal_return: float = 0.3
    high_quality_threshold: float = 7.0

@dataclass
class LLMProvider:
    api_url: str
    model: str
    api_key: Optional[str] = None
    timeout: int = 60
    weight: int = 1

@dataclass
class Config:
    thresholds: MetaCognitiveThresholds
    user_interests: list = field(default_factory=list)
    notification: dict = field(default_factory=dict)
    llm_providers: dict = field(default_factory=dict)
    default_llm_provider: str = "volcengine"

def load_config() -> Config:
    config_path = Path(__file__).parent.parent / "config.json"
    raw = {}
    if config_path.exists():
        with open(config_path) as f:
            raw = json.load(f)
    
    _load_env_file()
    
    mc = raw.get("meta_cognitive", {})
    thresholds = MetaCognitiveThresholds(
        max_explore_count=mc.get("max_explore_count", 3),
        min_marginal_return=mc.get("min_marginal_return", 0.3),
        high_quality_threshold=mc.get("high_quality_threshold", 7.0),
    )
    
    llm_providers = {}
    for name, cfg in raw.get("llm", {}).get("providers", {}).items():
        api_key = os.environ.get(f"{name.upper()}_API_KEY") or cfg.get("api_key")
        llm_providers[name] = LLMProvider(
            api_url=cfg.get("api_url", ""),
            model=cfg.get("model", ""),
            api_key=api_key,
            timeout=cfg.get("timeout", 60),
            weight=cfg.get("weight", 1),
        )
    
    return Config(
        thresholds=thresholds,
        user_interests=raw.get("user_interests", []),
        notification=raw.get("notification", {}),
        llm_providers=llm_providers,
        default_llm_provider=raw.get("llm", {}).get("default_provider", "volcengine"),
    )

def _load_env_file():
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

_config: Optional[Config] = None

def get_config() -> Config:
    global _config
    if _config is None:
        _config = load_config()
    return _config
```

---

## 八、验收测试清单

| Step | 测试命令 | 预期结果 |
|------|---------|---------|
| 0 | `python3 -c "from core.llm_manager import LLMManager; print(LLMManager.get_instance())"` | 单例正常初始化 |
| 0 | `python3 -c "from core.llm_manager import LLMManager; m = LLMManager.get_instance(); print(m.chat('1+1='))"` | 返回计算结果 |
| 1 | 启动服务，查看 `state.json` 有 `meta_cognitive` 字段 | 字段存在且为空结构 |
| 2 | `python3 -c "from core.meta_cognitive_monitor import MetaCognitiveMonitor; print(MetaCognitiveMonitor)"` | 类可导入 |
| 3 | `python3 -c "from core.meta_cognitive_controller import MetaCognitiveController; print(MetaCognitiveController)"` | 类可导入 |
| 4 | 注入话题 → 执行 4 次探索 | 第 4 次被阻止 |
| 5 | `curl "http://localhost:4848/api/metacognitive/state"` | 返回完整 meta_cognitive 状态 |
| 6 | 打开 Web UI | 看到元认知状态区域 |

---

## 九、版本依赖总结

```
v0.2.2
  ├── Step 0: core/llm_manager.py（多LLM路由）⭐ 新增
  ├── Step 1: core/knowledge_graph.py 扩展
  ├── Step 2: core/meta_cognitive_monitor.py（纯监测）
  ├── Step 3: core/meta_cognitive_controller.py（纯决策）
  ├── Step 4: curious_agent.py（MGV 循环集成）
  ├── Step 5: curious_api.py（API 端点）
  ├── Step 5: ui/index.html（Web UI 元认知区域）
  └── Step 5: core/event_bus.py（事件总线）⭐ 新增
      └── core/config.py（配置管理）⭐ 新增

前置条件：v0.2.1 ICM 融合评分 + Layer 3 深度探索（已就绪）
```

---

## 十、暂存 v0.2.3 的功能（P2）

| 功能 | 原因 | 文档位置 |
|------|------|---------|
| DK-UV 自动缺口检测 | 算法待验证 | `docs/plans/2026-03-21-v0.2.3-advanced-metacognition-design.md` |
| 动态 α 参数调节 | 依赖长期数据积累 | 同上 |
| D3.js 知识关联图 | 工作量过大 | 同上 |
| 飞书通知集成 | 暂缓 | 同上 |
| SQLite 持久化 | 暂缓 | 同上 |
| 情境缓冲区（Episodic Buffer） | 暂缓 | 同上 |
| Reflexion 口头反思记忆 | 暂缓 | 同上 |

---

_创建时间：2026-03-21_
_更新：2026-03-21（补充质量评分 + 通知机制 + 配置管理 + 多LLM架构）_
_为 OpenCode 提供实现路径参考_
