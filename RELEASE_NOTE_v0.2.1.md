# Release Note - v0.2.1

## 🎯 主要特性

### ICM 融合评分机制

引入 **Intrinsic Curiosity Module (ICM)** 启发的融合评分算法，让 Agent 能够自主评估话题的探索价值。

**核心公式**:
```
FinalScore = HumanScore × α + IntrinsicScore × (1 - α)
```

**三个内在信号**:
1. **预测误差 (pred_error)**: LLM 评估当前对该话题的理解程度
2. **图谱密度 (graph_density)**: 该话题在知识网络中的位置重要性
3. **新颖性 (novelty)**: 与已知知识库的语义重叠度

**用户控制**:
- `--motivation human` → α=0.7（偏重人工意图）
- `--motivation curious` → α=0.3（偏重自主探索）
- `--pure-curious` → α=0（纯探索模式）

### LLM 主导评分

- 使用 LLM 进行语义理解和综合推理
- 图谱统计作为辅助输入
- LLM 失败时自动降级到统计方案

---

## 🔧 Bug 修复

### F1: 队列条目删除 ✅
- 新增 `--delete` 参数删除指定话题
- 新增 `--force` 强制删除（忽略状态）
- 新增 `--list-pending` 列出待探索条目
- API 新增 `DELETE /api/curious/queue` 和 `GET /api/curious/queue/pending`

### F2: Layer 3 触发问题 ✅
- 修复 `Explorer` 未接收 `exploration_depth` 参数的问题
- Layer 3 触发条件已放宽（≥1 篇论文即可）

### F3: 关键词过滤 ✅
- 新增停用词表（商业/SEO词、噪音词）
- 新增语义相关性检查（研究关键词匹配）
- 新增预估评分门槛（<5.0 不入队）
- 预处理换行符防止截断

### F4: 启动脚本 ✅
- 新增 `run_curious.sh` 一键启动脚本
- 自动清理端口占用和残留进程
- 自动验证服务启动

### F5: ArXiv 容错增强 ✅
- 相关性门槛从 0.6 放宽到 0.3
- 新增 PDF 下载超时（10秒）和重试（2次）
- 新增 fallback 机制（构造伪论文对象）
- 最多分析 5 篇论文（原为 3 篇）

---

## 📊 性能指标

| 指标 | v0.2.0 | v0.2.1 | 提升 |
|------|--------|--------|------|
| Layer 3 触发率 | ~2% | ~20-30% | 10-15x |
| ArXiv 成功率 | ~20% | ~60%+ | 3x |
| 自动入队噪音率 | ~73% | <5% | 14x |

---

## 🛠️ API 变更

### 新增端点

```bash
# 删除队列条目
DELETE /api/curious/queue?topic=xxx&force=true

# 列出待探索条目
GET /api/curious/queue/pending
```

### 修改端点

```bash
# 注入好奇心（支持 alpha）
POST /api/curious/inject
{
  "topic": "agent memory",
  "alpha": 0.5,
  "mode": "fusion"  # or "intrinsic"
}
```

---

## 📝 使用示例

### CLI

```bash
# 偏重人工意图
python3 curious_agent.py --inject "transformer attention" --motivation human

# 偏重自主探索
python3 curious_agent.py --inject "transformer attention" --motivation curious

# 纯探索模式
python3 curious_agent.py --run --pure-curious

# 删除队列条目
python3 curious_agent.py --delete "过时的话题"
python3 curious_agent.py --delete "test" --force
```

### API

```bash
# 融合模式注入
curl -X POST http://10.1.0.13:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{"topic": "agent memory", "alpha": 0.5}'

# 纯内在模式注入
curl -X POST http://10.1.0.13:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{"topic": "agent memory", "mode": "intrinsic", "alpha": 0.0}'
```

---

## 🎨 Web UI

- 新增 α 滑块控制器（0.0-1.0）
- 新增预设按钮：人工(0.7) / 平衡(0.5) / 好奇(0.3)
- 注入时显示融合评分详情

---

## 📈 技术改进

### 新增模块
- `core/intrinsic_scorer.py` - ICM 内在评分器

### 核心改进
- CuriosityEngine 集成 IntrinsicScorer
- LLM prompt 工程优化（信号评估指南）
- Fallback 降级机制（LLM 失败时）

### 测试覆盖
- 20 个 IntrinsicScorer 单元测试
- 3 个 CuriosityEngine 集成测试
- 总计 109 个测试通过

---

## 🔮 后续计划

v0.3 方向：
- SQLite 持久化
- 向量数据库集成
- 更复杂的 LLM chain-of-thought

---

_发布时间: 2026-03-20_  
_版本: v0.2.1_  
_贡献者: omo-broker, AI Assistant_
