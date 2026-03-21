# Curious Agent v0.2.2 — Bug List

> 记录 v0.2.2 版本发现的 bug 及分析
> 创建时间：2026-03-21 | 发现者：R1D3-researcher
> 状态：待 OpenCode 修复

---

## Bug #1：双重记录（Double Recording）

### 严重程度
🔴 中

### 影响范围
- `meta_cognitive.explore_counts` 膨胀（显示值 = 实际探索次数 × 2）
- `meta_cognitive.exploration_log` 重复条目
- 循环阻止阈值（3次）会提前触发

### 根因
`curious_agent.py` 中 `run_one_cycle()` 函数对每个话题调用了 **两次** `record_exploration()`：

```python
# curious_agent.py — run_one_cycle()

# 第1次调用（第89行）
monitor.record_exploration(topic, quality, marginal, notified=False)

should_notify, notify_reason = controller.should_notify(topic)
notified = False

if should_notify:
    # ... emit events ...
    
    # 第2次调用（第103行）
    monitor.record_exploration(topic, quality, marginal, notified=True)
    notified = True
```

### 修复建议

移除第 1 次 `record_exploration` 调用，只在函数末尾记录一次：

```python
# curious_agent.py — run_one_cycle()

quality = monitor.assess_exploration_quality(topic, findings)
marginal = monitor.compute_marginal_return(topic, quality)

should_notify, notify_reason = controller.should_notify(topic)
notified = False

if should_notify:
    formatted = explorer.format_for_user(result)
    
    EventBus.emit("discovery.high_quality", {
        "topic": topic,
        "quality": quality,
        "formatted": formatted,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    EventBus.emit("notification.external", {
        "topic": topic,
        "quality": quality,
        "message": formatted
    })
    
    kg.update_last_exploration_notified(topic, True)
    notified = True

# 只在这里记录一次
monitor.record_exploration(topic, quality, marginal, notified=notified)
```

### 验证方法

```bash
# 1. 注入一个全新话题
python3 curious_agent.py --inject "test double record bug" --score 7.0 --reason "bug验证"

# 2. 执行探索
python3 curious_agent.py --run --run-depth shallow

# 3. 检查 state.json
# 预期：explore_counts["test double record bug"] = 1（不是2）
# 预期：exploration_log 中该话题条目数 = 1（不是2）
```

---

## Bug #2：LLMClient 未加载 config（已修复）

### 严重程度
🔴 高（已修复）

### 影响范围
- LLMManager 无法从 config.json 加载 provider 配置
- 所有 LLM 调用降级到 fallback（纯统计），无 LLM 能力

### 根因
`LLMClient.__init__()` 直接调用 `LLMManager.get_instance()` 但未传入 config，
导致 LLMManager 使用空配置初始化。

### 修复方式（已应用）
在 `LLMClient.__init__()` 中添加 config 加载逻辑：

```python
# core/llm_client.py

def __init__(self, api_key: Optional[str] = None, ...):
    from core.llm_manager import LLMManager
    from core.config import get_config  # 新增
    
    # 新增：从 config 加载 provider 配置
    config = get_config()
    llm_config = {
        "providers": {},
        "selection_strategy": "capability"
    }
    for p in config.llm_providers:
        llm_config["providers"][p.name] = {
            "api_url": p.api_url,
            "timeout": p.timeout,
            "enabled": p.enabled,
            "models": [
                {"model": m.model, "weight": m.weight, 
                 "capabilities": m.capabilities, "max_tokens": m.max_tokens}
                for m in p.models
            ]
        }
    
    self.manager = LLMManager.get_instance(llm_config)  # 传入配置
```

### 验证方法

```bash
# 1. 确保 config.json 存在且有 volcengine 配置
# 2. 运行探索，观察日志

python3 curious_agent.py --run --run-depth deep

# 预期：无 "[LLMManager] Warning: No LLM providers configured"
# 预期：日志显示 Layer 3 insights 正常生成
```

---

## 待确认问题

### Q1：循环阻止阈值提前触发
**现象**：由于 Bug #1 的双重记录，`explore_counts` 会是实际值的 2 倍
**预期**：话题探索 3 次后应被阻止，但由于 bug，可能在探索 2 次后就被阻止
**验证方法**：修复 Bug #1 后，执行 3 次探索，确认第 4 次被阻止

### Q2：边际收益默认 1.0 是否合理
**现象**：首次探索的 `marginal_return` 默认返回 1.0（固定高值）
**问题**：首次探索 quality=8.0，第二次 quality=7.0，marginal=-1.0 会触发停止
**分析**：首次探索没有历史，用默认 1.0 是合理的 placeholder
**建议**：观察 3 次探索后的 marginal_return 趋势，调整默认值

---

_最后更新：2026-03-21_
_发现者：R1D3-researcher_
_状态：待 OpenCode 修复_
