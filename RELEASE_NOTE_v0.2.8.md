# Release Note - v0.2.8

## 🎯 核心主题：Stuck Items 死锁修复 + 稳定性增强

v0.2.8 修复了导致 SpiderAgent 队列死锁 49+ 小时的严重 bug，以及多个影响知识图谱质量的问题。

---

## 🐛 修复的 Bug

### Bug #1: SpiderAgent 队列死锁（Critical）

**症状**：
- 40 个 queue items 永久卡在 `exploring` 状态
- SpiderAgent 进程存活但不消费队列
- 1752 个 pending items 无法被处理
- 持续 49+ 小时无任何新发现产出

**根因分析**：
```
claim_pending_item()     → 设置 status="exploring" ✅
                         → 但没有设置 claimed_at ❌
                         
update_curiosity_status() → 设置 status="exploring/investigating" ✅
                          → 也没有设置 claimed_at ❌

结果：items 永远没有 claimed_at → hotfix 脚本无法判断哪些是 stuck
    → SpiderAgent 跳过所有已标记 exploring 的 items（不管有没有真正被处理）
    → 死锁
```

**修复方案**：
```python
# core/knowledge_graph.py — claim_pending_item()
item["status"] = "exploring"
item["claimed_at"] = datetime.now(timezone.utc).isoformat()  # ← 新增
_save_state(state)
```

```python
# core/knowledge_graph.py — update_curiosity_status()
for item in state["curiosity_queue"]:
    if item["topic"] == topic:
        item["status"] = status
        # v0.2.8: 设置 claimed_at，防止 stuck items
        if "claimed_at" not in item and status in ("exploring", "investigating"):
            item["claimed_at"] = datetime.now(timezone.utc).isoformat()  # ← 新增
```

### Bug #2: 质量分数读取优先级错误

**症状**：
- API 返回的 quality 字段总是 None
- KG topics 有 quality 数据但 API 不读取

**根因**：`curious_api.py` 中 quality_map 覆盖了 KG 中的 quality 字段

**修复**：
```python
# Before（错误）
topic_copy["quality"] = quality_map.get(name, None)

# After（正确）
topic_copy["quality"] = v.get("quality") or quality_map.get(name)
```

### Bug #3: 知识引用未记录

**症状**：
- 添加子 topic 时没有同时记录 citation
- 知识溯源困难

**修复**：
```python
# core/explorer.py — 在添加子节点时同时添加 citation
kg.add_child(topic, name)
kg.add_citation(topic, name)  # ← 新增
```

---

## 🛠️ 新增工具

### fix_stuck_exploring.py

手动恢复 stuck items 的 hotfix 脚本：

```bash
# Dry run（预览）
python3 fix_stuck_exploring.py --dry-run

# 实际执行
python3 fix_stuck_exploring.py --no-dry-run

# 自定义超时时间（默认 30 分钟）
python3 fix_stuck_exploring.py --no-dry-run --max-age-minutes 60
```

### scripts/backfill_quality_v2.py

质量分数回填脚本，用于修复历史数据的 quality 字段。

---

## 📊 修复效果

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| stuck items | 40 个（49h） | 0 个 |
| 队列流转 | 100% 死锁 | 正常消费 |
| claimed_at 覆盖率 | 0% | 100% |
| 新发现产出 | 0（死锁期间） | 持续产出 |

---

## 🔧 技术细节

### claimed_at 字段语义

| 字段 | 说明 |
|------|------|
| `claimed_at` | 首次被 SpiderAgent claim 的 UTC 时间戳 |
| `status=exploring` | 被 claim 但尚未完成 |
| `status=done` | 探索完成 |
| `status=no_content` | 无有效内容，标记为 stub |

### Stuck Item 判断逻辑

```python
def is_stuck(item):
    if item.status not in ("exploring", "investigating"):
        return False
    if "claimed_at" not in item:
        return True  # v0.2.8 之前的 bug
    if datetime.now(timezone.utc) - item.claimed_at > TIMEOUT:
        return True   # 超时（默认 30 分钟）
    return False
```

---

## 📝 变更文件

```
core/knowledge_graph.py    — claimed_at 写入（两处）
core/explorer.py          — add_citation 调用
curious_api.py            — quality 读取优先级
fix_stuck_exploring.py    — 新增：stuck items 恢复工具
scripts/backfill_quality_v2.py — 新增：质量回填工具
```

---

## 🧪 测试建议

```bash
# 1. 确认无 stuck items
python3 fix_stuck_exploring.py --dry-run
# 预期：✅ No stuck items found

# 2. 验证 API quality 字段
curl http://localhost:4848/api/curious/state | python3 -c "
import json, sys
d = json.load(sys.stdin)
topics = d['knowledge']['topics']
with_quality = {k: v for k, v in topics.items() if v.get('quality')}
print(f'Topics with quality: {len(with_quality)}/{len(topics)}')
"

# 3. 验证 claimed_at 覆盖
python3 -c "
import json
with open('knowledge/state.json') as f:
    state = json.load(f)
q = state['curiosity_queue']
non_pending = [x for x in q if x.get('status') != 'pending']
with_ca = [x for x in non_pending if 'claimed_at' in x]
print(f'Non-pending: {len(non_pending)}, with_claimed_at: {len(with_ca)}')
"
```

---

## 🔮 后续计划

- v0.2.9: DreamInbox 满载时的批量 claim 优化
- v0.3.0: SQLite 持久化替换 JSON 文件

---

_发布时间: 2026-04-04_  
_版本: v0.2.8_  
_修复者: R1D3 (OpenClaw Researcher)_
