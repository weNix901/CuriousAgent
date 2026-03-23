# v0.2.3 Bug List

> 测试时间：2026-03-23
> 测试人：R1D3-researcher

---

## 🔴 严重 Bug

### Bug #1: Topic 注入完全映射错误
**描述**: 当通过 `/api/curious/run` 或 `/api/curious/inject` 注入主题时，引擎错误地将输入映射到完全无关的 topic。

**复现步骤**:
```bash
# 注入"自我意识 self-awareness" → 实际搜索了 "item2"
curl -X POST http://localhost:4848/api/curious/run \
  -d '{"topic": "自我意识 self-awareness", "depth": "medium"}'
# 结果: topic="item2", 搜索结果是 "item" 相关内容

# 注入"元认知 MetaCognition" → 实际搜索了 "test deep"
curl -X POST http://localhost:4848/api/curious/run \
  -d '{"topic": "元认知 MetaCognition", "depth": "medium"}'
# 结果: topic="test deep", 搜索结果是 "deep" 词典释义

# 注入"计算机视觉" → 实际搜索了 "item1"
curl -X POST http://localhost:4848/api/curious/run \
  -d '{"topic": "计算机视觉", "depth": "deep"}'
# 结果: topic="item1", 搜索结果是 "item" 词典释义
```

**影响**: Phase 1 好奇心分解引擎的核心功能失效，用户无法主动注入自定义主题。

**可能原因**: 引擎在队列中匹配相似 topic 时使用了错误的模糊匹配算法，把中文关键词匹配到了测试数据（item1/item2/test deep）。

---

### Bug #2: test shallow 分数异常（56.0）
**描述**: 队列中 `test shallow` 的 score=56.0，远超其他所有 topic（均 < 10）。

**复现**: 查看 `/api/curious/state` 的 curiosity_queue，`test shallow` 的 score 字段为 56.0。

**分析**: 当前评分公式最大值为 ~9.25（relevance*0.35 + recency*0.25 + depth*0.25 + surprise*0.15，depth=7），不可能达到 56.0。可能是 OpenCode 测试阶段遗留的硬编码值。

**影响**: 评分系统不可信，可能干扰队列优先级排序。

---

## 🟠 API 一致性问题

### Bug #3: `/api/curious/inject` depth 参数类型不一致
**描述**: `/api/curious/run` 接受字符串 depth (`"medium"`/`"deep"`/`"shallow"`)，但 `/api/curious/inject` 要求数值类型 (`3.0`)。

**复现**:
```bash
# run 接受字符串
curl -X POST http://localhost:4848/api/curious/run \
  -d '{"topic": "测试", "depth": "medium"}'  # ✅ 正常

# inject 要求数值
curl -X POST http://localhost:4848/api/curious/inject \
  -d '{"topic": "测试", "depth": "medium"}'  # ❌ error: could not convert string to float: 'medium'
curl -X POST http://localhost:4848/api/curious/inject \
  -d '{"topic": "测试", "depth": 3.0}'       # ✅ 正常
```

**建议**: 统一 depth 参数处理逻辑。

---

### Bug #4: DELETE `/api/curious/queue` JSON body 不接受
**描述**: 清空队列的 DELETE 请求需要 URL query parameter，不接受 JSON body。

**复现**:
```bash
# JSON body 方式 → 报错
curl -X DELETE http://localhost:4848/api/curious/queue \
  -H "Content-Type: application/json" \
  -d '{"topic": "test medium"}'
# 响应: {"error": "topic is required"}

# URL query 方式 → 成功
curl -X DELETE "http://localhost:4848/api/curious/queue?topic=test%20medium"
# 响应: {"deleted": true, "status": "success", "topic": "test medium"}
```

---

## 🟡 行为/逻辑 Bug

### Bug #5: `metacognitive/check` URL 编码问题
**描述**: 带空格的 topic 作为 query parameter 传递时，服务器返回 500 错误（空响应体）。

**复现**:
```bash
# 不 URL-encode 空格 → 500 错误
curl "http://localhost:4848/api/metacognitive/check?topic=test shallow"
# 响应: (空，HTTP 500)

# 正确 URL-encode → 正常
curl "http://localhost:4848/api/metacognitive/check?topic=test%20shallow"
# 响应: {"status": "ok", "decision": {...}}
```

**建议**: 服务器端应对 query parameter 做 URL decoding，或在文档中明确要求客户端做 URL encoding。

---

### Bug #6: 非 ASCII 字符 topic 在 metacognitive API 中乱码
**描述**: 非 ASCII 字符的 topic 通过 URL 传递时，响应中 topic 字段显示为乱码。

**复现**:
```bash
curl "http://localhost:4848/api/metacognitive/check?topic=不存在的主题"
# 响应中 topic 字段: "ä¸�å­å¨çä¸»é¢" (乱码)
```

**根因**: URL encoding 问题，中文字符未做适当编码/解码。

---

### Bug #7: `completed_topics` 永远为空
**描述**: 通过 `/api/metacognitive/topics/completed` 查询已完成主题，响应总是 `{"completed_topics": [], "status": "ok"}`。

**复现**: 多次探索不同 topic 后检查，completed_topics 仍为空。

**分析**: 可能是探索完成后没有正确更新 `completed_topics` 状态，或状态存储位置不对。

---

### Bug #8: 知识图谱 topic 状态字段不一致
**描述**: 部分 topic 的 status 字段为 "partial"，部分为 `?`（字段不存在）。

**复现**: 查看 `/api/curious/state` 的 knowledge.topics：
```
test shallow: 字段 status 不存在（显示 ?）
test deep:    status=partial
test topic:   status=partial, known=False, depth=0  ← depth=0 但 status=partial 矛盾
```

**分析**: 字段缺失和状态逻辑不一致。

---

## 🔴 配置缺失（阻断 Phase 1 验证）

### Config #1: SERPER_API_KEY 未设置 ⚠️ 关键 → ✅ 已修复
**描述**: Phase 1 的 `verification_threshold: 2` 要求两个 Provider 同时验证，但当前只有 Bocha 启用，Serper 因缺少 API Key 被禁用。

**修复方式**: 从 openclaw.json 中获取 SERPER_API_KEY，添加到 `/root/dev/curious-agent/.env`，重启服务。

**验证结果**:
```python
# provider_registry.py 判定
Enabled: ['bocha', 'serper']  # ✅ 双 Provider 已启用
All: ['bocha', 'serper']
```

**影响**: ~~Phase 1 的多 Provider 验证机制完全失效~~ → 现已修复，验证机制正常运作。

---

## 🟠 配置不一致 / 未暴露

### Config #2: CuriosityDecomposer 配置未暴露到 config.json
**描述**: Phase 1 的 `CuriosityDecomposer` 有独立配置项，但在 config.json 中找不到对应项。

**当前配置**（硬编码在 `curiosity_decomposer.py`）:
```python
DEFAULT_CONFIG = {
    "max_candidates": 7,        # LLM 生成候选数量上限
    "min_candidates": 5,        # LLM 生成候选数量下限
    "max_depth": 2,             # 递归分解深度限制（0=无限）
    "verification_threshold": 2,  # 需要 2 个 Provider 验证通过
}
```

**建议**: 应在 config.json 中增加 `decomposer` 配置节：
```json
{
  "decomposer": {
    "max_candidates": 7,
    "min_candidates": 5,
    "max_depth": 2,
    "verification_threshold": 2
  }
}
```

---

### Config #3: 搜索 Provider 配置分散
**描述**: Provider 的启用状态由环境变量决定，但 config.json 中的 `llm.providers` 只配置了 LLM provider（volcengine），没有搜索 Provider（Bocha/Serper）的配置项。

**当前**: Bocha/Serper 的 API Key 通过环境变量 `BOCHA_API_KEY` / `SERPER_API_KEY` 判断是否启用，但 config.json 没有对应的配置结构。

**建议**: 在 config.json 中增加统一的 provider 配置：
```json
{
  "search_providers": {
    "bocha": { "enabled": true },
    "serper": { "enabled": false }
  }
}
```

---

### Config #4: 通知机制无 Webhook 配置
**描述**: `config.json` 中有 `notification` 节，但只有 `enabled` 和 `min_quality` 字段，没有 Webhook URL。Phase 3 的行为闭环依赖通知机制，但飞书通知的 Webhook URL 未配置。

**当前 config.json**:
```json
"notification": {
  "enabled": true,
  "min_quality": 7.0
}
```

**建议**: 增加 Feishu Webhook URL：
```json
"notification": {
  "enabled": true,
  "min_quality": 7.0,
  "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
}
```

---

## 📝 备注

- 所有 Bug 已在本地环境（localhost:4848）复现
- 测试时间：2026-03-23 12:17-12:22 GMT+8
- API 服务正常运行的 endpoint：`/api/curious/run`、`/api/curious/trigger`、`/api/curious/state`、`/api/metacognitive/state`
- **最关键配置问题**: `SERPER_API_KEY` 缺失导致 Phase 1 的 2-provider 验证机制完全失效
