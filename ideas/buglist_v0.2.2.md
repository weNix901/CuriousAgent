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

---

## Bug #3：话题名称中数字被 URL 解析丢失

### 严重程度
🟡 低

### 影响范围
- 话题名称包含数字时（如 "Curious Agent Architecture 2026"）被错误解析
- 解析时 "2026" 被截断为 "26" 或完全丢失
- 导致同一话题被识别为不同话题（如 "Curious Agent Architecture 2026" vs "Curious Agent Architecture 26"）

### 根因
API 端点使用 URL query parameter 传递 topic，`+` 号或数字解析逻辑有问题。
API `/api/metacognitive/check?topic=xxx` 在处理包含数字的话题时，数字被截断或错误解析。

### 复现步骤

```bash
# 注入包含数字的话题
python3 curious_agent.py --inject "Curious Agent Architecture 2026" --score 8.0 --reason "测试"

# 执行探索
python3 curious_agent.py --run --run-depth deep

# 查看 API 返回
curl "http://localhost:4848/api/metacognitive/check?topic=Curious%20Agent%20Architecture%202026"
# 返回的 topic 字段可能显示为 "Curious Agent Architecture 26"（数字被截断）
```

### 修复建议

1. **短期**：在 API 端点对 topic 参数做 URL decode + 规范化
2. **长期**：改用 POST body 传递 topic，避免 URL 编码问题

```python
@app.get("/api/metacognitive/check")
def check_topic(topic: str = None):
    if topic is None:
        return jsonify({"error": "topic is required"}), 400
    
    # URL decode 并规范化
    topic = topic.strip()
    # 处理可能的编码问题
    topic = re.sub(r'\s+', ' ', topic)  # 规范化空白字符
    
    # ... 后续逻辑
```

### 验证方法

```bash
# 注入包含数字的话题
python3 curious_agent.py --inject "AI Trends 2026" --score 7.0 --reason "测试"

# 执行探索后检查
curl "http://localhost:4848/api/metacognitive/check?topic=AI%20Trends%202026"
# 预期：返回的 topic 字段应保持 "AI Trends 2026"
```

---

## Bug #4：关键词提取时数字被过滤

### 严重程度
🟡 低

### 影响范围
- 探索结果中提取关键词时，数字被过滤
- 导致 "2026" 等有意义的数字被丢弃

### 根因
`_extract_keywords` 方法使用正则 `\b[a-z]{4,}\b` 过滤，只保留 4 个字母以上的单词，数字被排除。

### 修复建议

在 `_extract_keywords` 中保留包含数字的术语（如 "LLM"、"AI"、"V2"、"V3"）：

```python
def _extract_keywords(self, text: str) -> list:
    # 保留包含数字的术语
    words_with_numbers = re.findall(r'\b[a-z]*\d+[a-z]*\b', text.lower())
    # 保留纯字母单词
    words_only_letters = re.findall(r'\b[a-z]{4,}\b', text.lower())
    # 合并去重
    keywords = list(set(words_with_numbers + words_only_letters))
    # ... 后续过滤逻辑
```

---

## 问题 #1：循环阻止阈值提前触发

### Q1：循环阻止阈值提前触发
**现象**：由于 Bug #1 的双重记录，`explore_counts` 会是实际值的 2 倍
**预期**：话题探索 3 次后应被阻止，但由于 bug，可能在探索 2 次后就被阻止
**验证方法**：修复 Bug #1 后，执行 3 次探索，确认第 4 次被阻止

## 问题 #2：边际收益默认 1.0 是否合理
**现象**：首次探索的 `marginal_return` 默认返回 1.0（固定高值）
**问题**：首次探索 quality=8.0，第二次 quality=7.0，marginal=-1.0 会触发停止
**分析**：首次探索没有历史，用默认 1.0 是合理的 placeholder
**建议**：观察 3 次探索后的 marginal_return 趋势，调整默认值

---

---

## 📋 Bug 汇总

| Bug # | 名称 | 严重程度 | 状态 |
|-------|------|---------|------|
| #1 | 双重记录 | 🔴 中 | 待修复 |
| #2 | LLMClient 未加载 config | 🔴 高 | ✅ 已修复 |
| #3 | 话题名称数字被解析丢失 | 🟡 低 | 待修复 |
| #4 | 关键词数字被过滤 | 🟡 低 | 待修复 |

| 问题 # | 名称 | 说明 |
|--------|------|------|
| #1 | 循环阻止阈值提前触发 | 因 Bug #1 导致 |
| #2 | 边际收益默认 1.0 | 需观察调整 |

---

_最后更新：2026-03-21_
_发现者：R1D3-researcher_
_状态：待 OpenCode 修复（Bug #1, #3, #4）_
