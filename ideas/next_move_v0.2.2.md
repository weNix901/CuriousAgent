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
┌─────────────────────────────────────────────────────────────────────────┐
│                           LLMManager（单例）                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  providers: {                                                           │
│    "volcengine": [                                                       │
│        ModelEntry(model="ark-code-latest", weight=3,                     │
│                   capabilities=["fast","general","keywords","quality"]),  │
│        ModelEntry(model="deepseek-chat", weight=2,                       │
│                   capabilities=["reasoning","analysis"]),                │
│    ],                                                                    │
│    "openai": [                                                          │
│        ModelEntry(model="gpt-4o", weight=2,                             │
│                   capabilities=["general","creative","icm_signals"]),     │
│        ModelEntry(model="gpt-4o-mini", weight=3,                        │
│                   capabilities=["fast","keywords","quality"]),            │
│    ],                                                                    │
│    "anthropic": [                                                       │
│        ModelEntry(model="claude-sonnet-4", weight=1,                    │
│                   capabilities=["reasoning","insights","analysis"]),      │
│    ],                                                                    │
│  }                                                                       │
│                                                                         │
│  selection_strategy: "weighted_rr" | "capability"                       │
│  routing_keys: {task_type → (provider, model)}                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Router（两层路由选择）                                 │
│                                                                         │
│  第一层：按 task_type 选 provider                                        │
│  第二层：同 provider 内按 task_type 选 model                             │
│                                                                         │
│  task_type:                                                             │
│    "keywords"  → volcengine[ark-code-latest]                            │
│    "quality"   → openai[gpt-4o-mini]                                   │
│    "insights"  → anthropic[claude-sonnet-4]                             │
│    "icm_signals" → openai[gpt-4o]                                      │
│    "general"   → 加权轮询所有 provider                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

**使用场景分工建议**：

| 场景 | 推荐 Provider | 推荐 Model | 理由 |
|------|-------------|-----------|------|
| 关键词提取 | volcengine | ark-code-latest | 简单任务，不需要强推理 |
| 关键词提取（备选） | openai | gpt-4o-mini | 并发高时降级 |
| 论文对比洞察（Layer 3） | anthropic | claude-sonnet-4 | 复杂推理任务，需要长上下文 |
| 内在信号评估（ICM） | openai | gpt-4o | 平衡速度与能力 |
| 质量评分 | openai | gpt-4o-mini | 任务简单，高并发 |
| 通用任务 | 加权轮询 | — | 分摊负载 |

**实现代码**：

```python
# core/llm_manager.py

import os
import random
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModelEntry:
    """
    单个模型的配置条目
    
    同一个 Provider 下可以配置多个模型，
    根据 task_type 和 weight 动态选择
    """
    model: str                          # 模型名称
    weight: int = 1                     # 同 provider 内权重
    capabilities: list = field(default_factory=list)  # 支持的能力
    max_tokens: int = 2000              # 最大 token
    temperature: float = 0.7             # 默认温度


@dataclass
class LLMProvider:
    """
    LLM Provider 配置
    
    一个 Provider（如 volcengine）下可配置多个 Model（如 ark-code-latest、deepseek-chat）
    """
    name: str                           # provider 名称
    api_url: str                        # API 端点
    api_key: str                        # API key
    models: list[ModelEntry] = field(default_factory=list)  # 该 provider 下的模型列表
    timeout: int = 60                   # 默认超时
    default_model: str = ""             # 默认模型（第一个）
    enabled: bool = True                # 是否启用

    def get_model(self, task_type: str = "general") -> ModelEntry:
        """根据 task_type 在该 provider 内选择合适的模型"""
        # 1. 精确匹配 capability
        for m in self.models:
            if task_type in m.capabilities:
                return m
        # 2. 返回第一个（默认）
        return self.models[0] if self.models else ModelEntry(model=self.default_model)


class LLMManager:
    """
    多 Provider + 多 Model 的 LLM 管理器
    
    核心能力：
    1. 多 Provider 支持（volcengine / openai / anthropic / ...）
    2. 同 Provider 多 Model 支持（按 task_type 选模型）
    3. 两层路由：Provider 层（capability/加权轮询）+ Model 层（capability）
    4. 并发请求支持
    """
    
    _instance: Optional["LLMManager"] = None
    
    def __init__(self, config: dict = None):
        config = config or {}
        self.providers: list[LLMProvider] = []
        self._init_providers(config.get("providers", {}))
        self.strategy = config.get("selection_strategy", "capability")
    
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
        """初始化所有 provider 及其下的 models"""
        for provider_name, cfg in providers_config.items():
            api_key = os.environ.get(f"{provider_name.upper()}_API_KEY") or cfg.get("api_key")
            if not api_key:
                print(f"[LLMManager] Skipping {provider_name}: no API key")
                continue
            
            # 解析该 provider 下的所有模型
            models = []
            raw_models = cfg.get("models", [])
            
            # 兼容旧格式：直接是 model 字段（单个模型）
            if "model" in cfg and not raw_models:
                raw_models = [{"model": cfg["model"], "weight": cfg.get("weight", 1),
                               "capabilities": cfg.get("capabilities", ["general"])}]
            
            for m_cfg in raw_models:
                models.append(ModelEntry(
                    model=m_cfg.get("model", ""),
                    weight=m_cfg.get("weight", 1),
                    capabilities=m_cfg.get("capabilities", ["general"]),
                    max_tokens=m_cfg.get("max_tokens", 2000),
                    temperature=m_cfg.get("temperature", 0.7),
                ))
            
            provider = LLMProvider(
                name=provider_name,
                api_url=cfg.get("api_url", ""),
                api_key=api_key,
                models=models,
                timeout=cfg.get("timeout", 60),
                default_model=models[0].model if models else "",
                enabled=cfg.get("enabled", True),
            )
            self.providers.append(provider)
        
        if not self.providers:
            print("[LLMManager] Warning: No LLM providers configured")
    
    def select(self, task_type: str = "general") -> tuple[LLMProvider, ModelEntry]:
        """
        根据策略选择 (provider, model)
        
        Returns:
            (LLMProvider, ModelEntry)
        """
        if len(self.providers) == 1 and len(self.providers[0].models) == 1:
            p = self.providers[0]
            return p, p.models[0]
        
        if self.strategy == "capability":
            return self._capability_based(task_type)
        else:
            return self._weighted_rr(task_type)
    
    def _capability_based(self, task_type: str) -> tuple[LLMProvider, ModelEntry]:
        """基于能力选择：遍历所有 provider 的所有 model，找精确匹配"""
        for p in self.providers:
            if not p.enabled:
                continue
            model = p.get_model(task_type)
            if model and task_type in model.capabilities:
                return p, model
        # fallback：加权轮询
        return self._weighted_rr(task_type)
    
    def _weighted_rr(self, task_type: str = "general") -> tuple[LLMProvider, ModelEntry]:
        """加权轮询：先选 provider，再在 provider 内选 model"""
        # 按 weight 计算所有 (provider, model) 的权重
        candidates = []
        for p in self.providers:
            if not p.enabled:
                continue
            for m in p.models:
                # provider weight × model weight
                weight = self._get_provider_weight(p.name) * m.weight
                candidates.append((p, m, weight))
        
        if not candidates:
            raise ValueError("No available LLM providers")
        
        total_weight = sum(c[2] for c in candidates)
        r = random.randint(1, total_weight)
        cumsum = 0
        for p, m, w in candidates:
            cumsum += w
            if r <= cumsum:
                return p, m
        return candidates[-1][:2]
    
    def _get_provider_weight(self, provider_name: str) -> int:
        """获取 provider 的权重（从配置或默认 1）"""
        for p in self.providers:
            if p.name == provider_name:
                # provider 权重 = 所有 model weight 之和
                return sum(m.weight for m in p.models) if p.models else 1
        return 1
    
    def chat(self, prompt: str, task_type: str = "general",
             model_override: str = None, provider_override: str = None,
             **kwargs) -> str:
        """
        向选中的 provider + model 发送请求
        
        Args:
            prompt: 对话 prompt
            task_type: 任务类型，影响路由选择
            model_override: 强制使用指定模型（绕过路由）
            provider_override: 强制使用指定 provider（绕过路由）
            **kwargs: 传递给底层 API 的参数（temperature, max_tokens 等）
        """
        if provider_override:
            provider = next((p for p in self.providers if p.name == provider_override), None)
            if not provider:
                raise ValueError(f"Provider {provider_override} not found")
            if model_override:
                model = next((m for m in provider.models if m.model == model_override), None)
                if not model:
                    raise ValueError(f"Model {model_override} not found in {provider_override}")
            else:
                model = provider.get_model(task_type)
        else:
            provider, model = self.select(task_type)
            if model_override:
                model = next((m for m in provider.models if m.model == model_override), model)
        
        # 合并参数
        temperature = kwargs.pop("temperature", model.temperature)
        max_tokens = kwargs.pop("max_tokens", model.max_tokens)
        
        import requests
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json"
        }
        
        # OpenAI-compatible API
        payload = {
            "model": model.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        response = requests.post(
            provider.api_url,
            headers=headers,
            json=payload,
            timeout=provider.timeout
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    
    def chat_batch(self, prompts: list, task_type: str = "general",
                   max_workers: int = 3, **kwargs) -> list:
        """
        并发发送多个 LLM 请求，自动分摊到不同 provider
        
        会尽可能把请求分散到不同的 provider，
        避免同一个 provider 的 API 限流
        """
        import concurrent.futures
        
        results = [None] * len(prompts)
        
        # 按 provider 分组，优先用权重高的 provider
        assignments = self._assign_to_providers(len(prompts), task_type)
        
        def send_request(idx: int, provider_name: str, model_name: str, prompt: str):
            return idx, self.chat(prompt, provider_override=provider_name,
                                  model_override=model_name, **kwargs)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for idx, (p_name, m_name) in enumerate(assignments):
                futures.append(executor.submit(send_request, idx, p_name, m_name, prompts[idx]))
            
            for future in concurrent.futures.as_completed(futures):
                idx, result = future.result()
                results[idx] = result
        
        return results
    
    def _assign_to_providers(self, count: int, task_type: str) -> list:
        """
        将 N 个请求分配到不同的 (provider, model)
        
        策略：轮询分配，确保负载分散
        """
        assignments = []
        available = []
        
        for p in self.providers:
            if not p.enabled:
                continue
            for m in p.models:
                available.append((p.name, m.model, self._get_provider_weight(p.name) * m.weight))
        
        if not available:
            raise ValueError("No available LLM models")
        
        # 按权重展开，轮询分配
        expanded = []
        for p_name, m_name, w in available:
            expanded.extend([(p_name, m_name)] * w)
        
        random.shuffle(expanded)
        
        for i in range(count):
            assignments.append(expanded[i % len(expanded)])
        
        return assignments
    
    def list_capabilities(self) -> dict:
        """列出所有 provider 和 model 的能力"""
        result = {}
        for p in self.providers:
            result[p.name] = {
                "api_url": p.api_url,
                "models": {}
            }
            for m in p.models:
                result[p.name]["models"][m.model] = {
                    "capabilities": m.capabilities,
                    "weight": m.weight
                }
        return result
```

**config.json 多 Provider + 多 Model 配置示例**：

```json
{
  "llm": {
    "default_provider": "volcengine",
    "selection_strategy": "capability",
    "providers": {
      "volcengine": {
        "api_url": "https://ark.cn-beijing.volces.com/api/coding/v3/chat/completions",
        "timeout": 60,
        "enabled": true,
        "models": [
          {
            "model": "ark-code-latest",
            "weight": 3,
            "capabilities": ["fast", "general", "keywords", "quality"],
            "max_tokens": 2000
          },
          {
            "model": "deepseek-chat",
            "weight": 2,
            "capabilities": ["reasoning", "analysis", "icm_signals"],
            "max_tokens": 4000
          }
        ]
      },
      "openai": {
        "api_url": "https://api.openai.com/v1/chat/completions",
        "timeout": 120,
        "enabled": true,
        "models": [
          {
            "model": "gpt-4o",
            "weight": 2,
            "capabilities": ["general", "creative", "insights", "icm_signals"],
            "max_tokens": 4000
          },
          {
            "model": "gpt-4o-mini",
            "weight": 3,
            "capabilities": ["fast", "keywords", "quality"],
            "max_tokens": 2000
          }
        ]
      },
      "anthropic": {
        "api_url": "https://api.anthropic.com/v1/messages",
        "timeout": 120,
        "enabled": true,
        "models": [
          {
            "model": "claude-sonnet-4-20250514",
            "weight": 1,
            "capabilities": ["reasoning", "insights", "analysis"],
            "max_tokens": 4000
          },
          {
            "model": "claude-3-5-haiku-20241022",
            "weight": 2,
            "capabilities": ["fast", "keywords", "quality"],
            "max_tokens": 2000
          }
        ]
      }
    }
  }
}
```

**关键设计决策**：

1. **两层路由**：先按 `task_type` 选 `provider`，再在 provider 内按 `task_type` 选 `model`
2. **provider 间加权轮询**：`provider.weight = Σ(model.weight)`，跨 provider 负载均衡
3. **model_override / provider_override**：支持强制指定，跳过路由
4. **`chat_batch` 智能分散**：自动将并发请求分配到不同 provider，避免单点限流
5. **向后兼容**：支持旧的单 `model` 字段格式（自动转成 `models` 数组）

**与旧版 LLMClient 的兼容性**：

```python
# core/llm_client.py — 改造为委托给 LLMManager

class LLMClient:
    """兼容现有代码的 LLMClient，改为委托给 LLMManager"""
    
    def __init__(self, provider_name: str = None, model_name: str = None):
        from core.llm_manager import LLMManager
        self.manager = LLMManager.get_instance()
        self.provider_override = provider_name
        self.model_override = model_name
    
    def chat(self, prompt: str, **kwargs) -> str:
        return self.manager.chat(
            prompt,
            provider_override=self.provider_override,
            model_override=self.model_override,
            **kwargs
        )
    
    def generate_insights(self, topic: str, papers: list, **kwargs):
        """论文洞察生成（Layer 3 专用）"""
        prompt = self._build_insight_prompt(topic, papers)
        return self.manager.chat(
            prompt,
            task_type="insights",
            provider_override=self.provider_override,
            model_override=self.model_override,
            **kwargs
        )
    
    def _build_insight_prompt(self, topic: str, papers: list) -> str:
        parts = [f"研究主题: {topic}\n"]
        for i, paper in enumerate(papers, 1):
            parts.append(f"论文{i}: {paper.get('title', 'N/A')}\n")
            parts.append(f"摘要: {paper.get('abstract', '')[:300]}...\n")
            parts.append(f"关键发现: {', '.join(paper.get('key_findings', [])[:3])}\n\n")
        parts.append("请提供深度洞察报告。")
        return "".join(parts)
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
        "timeout": 60,
        "enabled": true,
        "models": [
          {
            "model": "ark-code-latest",
            "weight": 3,
            "capabilities": ["fast", "general", "keywords", "quality"],
            "max_tokens": 2000
          },
          {
            "model": "deepseek-chat",
            "weight": 2,
            "capabilities": ["reasoning", "analysis", "icm_signals"],
            "max_tokens": 4000
          }
        ]
      },
      "openai": {
        "api_url": "https://api.openai.com/v1/chat/completions",
        "timeout": 120,
        "enabled": true,
        "models": [
          {
            "model": "gpt-4o",
            "weight": 2,
            "capabilities": ["general", "creative", "insights", "icm_signals"],
            "max_tokens": 4000
          },
          {
            "model": "gpt-4o-mini",
            "weight": 3,
            "capabilities": ["fast", "keywords", "quality"],
            "max_tokens": 2000
          }
        ]
      },
      "anthropic": {
        "api_url": "https://api.anthropic.com/v1/messages",
        "timeout": 120,
        "enabled": true,
        "models": [
          {
            "model": "claude-sonnet-4-20250514",
            "weight": 1,
            "capabilities": ["reasoning", "insights", "analysis"],
            "max_tokens": 4000
          }
        ]
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
class ModelEntry:
    model: str
    weight: int = 1
    capabilities: list = field(default_factory=list)
    max_tokens: int = 2000
    temperature: float = 0.7

@dataclass
class LLMProvider:
    name: str
    api_url: str
    models: list = field(default_factory=list)
    api_key: Optional[str] = None
    timeout: int = 60
    enabled: bool = True

    def get_model(self, task_type: str = "general") -> ModelEntry:
        for m in self.models:
            if task_type in m.capabilities:
                return m
        return self.models[0] if self.models else ModelEntry(model="")

@dataclass
class Config:
    thresholds: MetaCognitiveThresholds
    user_interests: list = field(default_factory=list)
    notification: dict = field(default_factory=dict)
    llm_providers: list = field(default_factory=list)  # list[LLMProvider]
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
    
    llm_providers = []
    for name, cfg in raw.get("llm", {}).get("providers", {}).items():
        api_key = os.environ.get(f"{name.upper()}_API_KEY") or cfg.get("api_key")
        
        # 解析 models 列表
        models = []
        for m_cfg in cfg.get("models", []):
            models.append(ModelEntry(
                model=m_cfg.get("model", ""),
                weight=m_cfg.get("weight", 1),
                capabilities=m_cfg.get("capabilities", ["general"]),
                max_tokens=m_cfg.get("max_tokens", 2000),
                temperature=m_cfg.get("temperature", 0.7),
            ))
        
        # 兼容旧格式
        if "model" in cfg and not models:
            models.append(ModelEntry(
                model=cfg["model"],
                weight=cfg.get("weight", 1),
                capabilities=cfg.get("capabilities", ["general"]),
            ))
        
        llm_providers.append(LLMProvider(
            name=name,
            api_url=cfg.get("api_url", ""),
            models=models,
            api_key=api_key,
            timeout=cfg.get("timeout", 60),
            enabled=cfg.get("enabled", True),
        ))
    
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
