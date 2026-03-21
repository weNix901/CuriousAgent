# Curious Agent v0.2 实现方案

> 本文档定义 v0.2 的两个核心改进：主动触发 + 分层探索。
> 实现者：weNix（基于 OpenCode） | 验收者：weNix

---

## 改进一：时间感知 + 事件驱动触发

### 问题现状
- 纯 cron 驱动（每 30 分钟一次）
- 没有"今天想了解 X"的时间感
- 探索队列依赖初始化注入，不够自主

### 解决思路

#### 触发信号体系

```
触发信号
  ├── ⏰ 定时节律（被动基准）
  │     ├── 早安探索（每天 09:00）：浅层快扫
  │     └── 晚安探索（每天 21:00）：深度总结
  │
  ├── 🔗 知识缺口触发（主动核心）
  │     ├── 探索结果发现新关键词 → 自动入队
  │     └── 图谱中某话题无关联节点 → 主动填补
  │
  └── 💬 对话触发（用户交互）
        └── 用户说"让我好奇一下 X" → 立即执行
```

#### 实现目标

| 目标 | 描述 | 验收方式 |
|------|------|---------|
| G1.1 | 每天固定时间自动执行浅层/深层探索 | cron 配置存在且生效 |
| G1.2 | 探索结果中的新关键词自动入队 | 观察 state.json 中 curiosity_queue 自动增长 |
| G1.3 | 用户输入"让我好奇一下 X"可立即触发 | API 或 CLI 接收并执行 |
| G1.4 | 探索深度可配置（浅/中/深） | `--depth shallow\|medium\|deep` 参数生效 |

#### 验收测试

```bash
# G1.1: 定时触发
# 在 cron 中配置两个时间点，观察 state.json 的 timestamp 变化
crontab -e
# 0 9 * * * cd /root/dev/curious-agent && python3 curious_agent.py --run --depth shallow
# 0 21 * * * cd /root/dev/curious-agent && python3 curious_agent.py --run --depth deep

# G1.2: 新关键词自动入队
# 运行一轮探索后，检查 curiosity_queue 是否自动增加了探索中发现的新话题
python3 curious_agent.py --run --depth medium
# 然后检查: grep -c "auto:" knowledge/state.json 中的 auto-queued 条目

# G1.3: 对话触发
curl -X POST http://10.1.0.13:4849/api/curious/trigger \
  -H "Content-Type: application/json" \
  -d '{"topic":"your curiosity here","depth":"shallow"}'
# 预期: 立即开始探索，不等待 cron

# G1.4: 深度参数
python3 curious_agent.py --run --depth deep
# 预期: 探索时间明显变长（>2分钟），输出包含"deep exploration"
```

---

## 改进二：分层探索机制

### 问题现状
- 一次探索 = 一次 web search
- 只拿表层摘要，无法深入论文/PDF
- 知识深度上限低，无法形成洞察

### 解决思路

```
探索深度分级

Layer 1 — 快（30秒）
  └── Web Search（现状）
       → 快速获取概览 + 发现值得深入的论文

Layer 2 — 中（5分钟）
  ├── Layer 1 结果
  └── 如果发现 arXiv 链接 → 下载 PDF 摘要（只读前2页）
       → 提取：方法论、核心贡献、局限性

Layer 3 — 深（15分钟）
  ├── Layer 1+2 结果
  └── 多篇相关论文对比阅读（最多3篇）
       → 生成对比分析表
       → 提炼跨论文洞察
       → 判断是否值得通知用户
```

#### 实现目标

| 目标 | 描述 | 验收方式 |
|------|------|---------|
| G2.1 | `--depth shallow` = 现状（web search） | 耗时 < 30 秒 |
| G2.2 | `--depth medium` = web search + PDF 摘要提取 | 耗时 1-3 分钟 |
| G2.3 | `--depth deep` = 多论文对比 + 洞察生成 | 耗时 5-15 分钟 |
| G2.4 | 探索结果包含"洞察层"（不是简单摘要） | findings 字段包含推理过程 |

#### 验收测试

```bash
# G2.1: 浅层（基准）
time python3 curious_agent.py --run --depth shallow
# 预期: <30s 完成，state.json 的 findings 为搜索摘要

# G2.2: 中层（PDF）
time python3 curious_agent.py --run --depth medium
# 预期: 1-3分钟，检查 findings 是否包含 "【论文分析】" 段落

# G2.3: 深层（多论文对比）
time python3 curious_agent.py --run --depth deep
# 预期: 5-15分钟，检查 findings 是否包含对比分析表

# G2.4: 洞察格式验证
python3 -c "
import json
with open('/root/dev/curious-agent/knowledge/state.json') as f:
    d = json.load(f)
last = d['exploration_log'][-1]
print('depth:', last.get('exploration_depth'))
print('has_insight:', '洞察' in last.get('findings','') or 'insight' in last.get('findings','').lower())
print('findings[:500]:', last.get('findings','')[:500])
"
```

---

## 核心改动文件

```
curious_agent.py
  ├── 新增: --depth {shallow,medium,deep} 参数
  ├── 新增: trigger_from_user(topic) 函数
  ├── 新增: auto_queue_from_findings() 函数
  └── 修改: run_exploration(depth) 函数分派不同策略

core/explorer.py
  ├── Layer 1: search_web() — 保持现状
  ├── Layer 2: extract_pdf_summary(url) — 新增
  └── Layer 3: compare_papers(urls[]) — 新增

core/curiosity_engine.py
  ├── 新增: add_auto_queued(topic, reason="auto:found in ...") — 新增
  └── 修改: score_topic() 考虑 auto-queue 的话题
```

---

## 数据格式扩展

### curiosity_queue 新增字段

```json
{
  "topic": "metacognition in LLM",
  "score": 8.0,
  "depth": "medium",
  "source": "auto:found in swe-agent exploration",  // 新增
  "status": "pending"
}
```

### exploration_log 新增字段

```json
{
  "topic": "metacognition in LLM",
  "exploration_depth": "deep",        // 新增
  "layers_explored": [1, 2, 3],     // 新增
  "papers_analyzed": ["url1", "url2"], // 新增（Layer 2/3）
  "findings": {
    "layer1": "...",  // 搜索摘要
    "layer2": "...",  // 论文分析
    "layer3": "..."   // 深度洞察
  },
  "notified_user": true,
  "timestamp": "..."
}
```

---

## 验收检查清单

实现完成后，运行以下检查：

- [ ] `curious_agent.py --run --depth shallow` 正常完成 < 30s
- [ ] `curious_agent.py --run --depth medium` 正常完成 1-3 分钟
- [ ] `curious_agent.py --run --depth deep` 正常完成 5-15 分钟
- [ ] 深层探索 findings 包含多论文对比内容
- [ ] 探索结果中的新关键词出现在下一轮 curiosity_queue
- [ ] API `/api/curious/trigger` 可立即触发探索
- [ ] `state.json` 中新增字段（exploration_depth, source）正确写入
- [ ] Web UI 刷新后显示正确的探索深度标签

---

_文档版本: v0.2 设计方案_
_创建时间: 2026-03-19_
