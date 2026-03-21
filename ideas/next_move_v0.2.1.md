# Curious Agent v0.2.1 — ICM 融合评分机制

> 在 v0.2（分层探索）基础上的核心评分算法升级
> 依赖于 v0.2 的分层探索能力
> 设计者：weNix + R1D3-researcher | 实现者：待分配

---

## 核心问题

v0.2 的评分算法是**纯人工设计**的：
```
Score = Relevance × 0.35 + Recency × 0.25 + Depth × 0.25 + Surprise × 0.15
```

问题：
- 话题优先级依赖人工注入
- 没有从探索历史中学习的机制
- 探索结果的好坏没有反馈到下次探索的优先级

---

## ICM 融合架构

### 设计原则

> 人类意图和 Agent 自主探索**不是替代关系，是互补信号**

- 人工信号：确保有用、聚焦、符合用户意图
- 内在信号：确保惊喜、新鲜、有发现感

### 融合公式

```
FinalScore = HumanScore × α + IntrinsicScore × (1 - α)

其中：
  HumanScore      = 人工设计的评分（现状算法）
  IntrinsicScore  = ICM 启发的内在评分
  α               = 用户可控权重（默认 0.5）
```

### 内在评分（ICM-Inspired）

```python
def intrinsic_score(topic, knowledge_graph, exploration_history):
    """
    三个内在信号，每个 0-10 分
    """
    # 1. 预测误差（Prediction Error）
    #    = 之前探索后，对这个话题的理解误差
    #    误差越大 → 我们越不了解 → 越值得探索
    pred_error = predict_error(topic, exploration_history)

    # 2. 关联密度（Graph Density）
    #    = 图谱中该话题的连接节点数
    #    连接越少 → 越孤立 → 知识空白越大 → 越值得探索
    density = graph_density(topic, knowledge_graph)

    # 3. 新颖性（Novelty）
    #    = 与已知知识库的重叠度
    #    重叠越少 → 越新鲜 → 探索价值越高
    novelty = novelty_score(topic, knowledge_graph)

    return (pred_error * 0.4 + density * 0.3 + novelty * 0.3)
```

---

## 用户控制接口

### α 参数（人类意图权重）

```bash
# 默认（各50%）
python3 curious_agent.py --inject "metacognition"

# 偏重人类意图（70%人工，30%自主）
python3 curious_agent.py --inject "metacognition" --motivation human

# 偏重自主探索（30%人工，70%自主）
python3 curious_agent.py --inject "metacognition" --motivation curious

# 纯探索模式（0%人工，100%自主）
python3 curious_agent.py --run --pure-curious
```

### API 接口

```bash
# 触发自主探索（纯内在信号驱动）
curl -X POST http://10.1.0.13:4848/api/curious/explore \
  -H "Content-Type: application/json" \
  -d '{"mode": "intrinsic", "alpha": 0.0}'

# 融合模式
curl -X POST http://10.1.0.13:4848/api/curious/explore \
  -H "Content-Type: application/json" \
  -d '{"topic": "agent memory", "alpha": 0.5}'
```

---

## 数据格式扩展（v0.2 基础上）

### curiosity_queue 新增字段

```json
{
  "topic": "metacognition in LLM",
  "human_score": 7.5,
  "intrinsic_score": 8.2,
  "alpha": 0.5,
  "final_score": 7.85,
  "intrinsic_signals": {
    "pred_error": 8.5,
    "graph_density": 7.0,
    "novelty": 9.0
  },
  "status": "pending"
}
```

### exploration_log 新增字段

```json
{
  "topic": "metacognition in LLM",
  "alpha": 0.5,
  "human_score": 7.5,
  "intrinsic_score": 8.2,
  "final_score": 7.85,
  "pred_error_before": 7.2,
  "pred_error_after": 2.1,
  "pred_error_reduced": 5.1,
  "insight_gained": "LLM的元认知表现为...（探索后的新理解）",
  "findings": {
    "layer1": "...",
    "layer2": "...",
    "layer3": "..."
  }
}
```

---

## 实现目标

| 目标 | 描述 | 验收方式 |
|------|------|---------|
| G3.1 | α 参数正确控制融合权重 | `--motivation human/curious` 产生不同排序 |
| G3.2 | 内在评分三信号可计算 | 每次评分输出 pred_error/density/novelty |
| G3.3 | 探索结果更新预测误差 | 同一话题两次探索，pred_error_after < pred_error_before |
| G3.4 | Web UI 显示评分来源 | 好奇心队列显示人工分/内在分/融合分 |
| G3.5 | `--pure-curious` 模式正常 | 无人工注入时内在信号可独立驱动探索 |

---

## 验收测试

```bash
# G3.1: α 参数验证
python3 curious_agent.py --inject "agent memory" --motivation human
# 检查 state.json: alpha=0.7, human_score权重高

python3 curious_agent.py --inject "agent memory" --motivation curious
# 检查 state.json: alpha=0.3, intrinsic_score权重高

# G3.2: 内在信号输出
python3 -c "
from curious_agent import CuriousAgent
ca = CuriousAgent()
score = ca.score_topic('agent memory')
print('pred_error:', score.get('intrinsic_signals',{}).get('pred_error'))
print('graph_density:', score.get('intrinsic_signals',{}).get('graph_density'))
print('novelty:', score.get('intrinsic_signals',{}).get('novelty'))
print('intrinsic_score:', score.get('intrinsic_score'))
"

# G3.3: 预测误差衰减（同一话题两次探索）
python3 curious_agent.py --inject "self-reflection LLM"
python3 curious_agent.py --run
# 检查 state.json exploration_log
# pred_error_after < pred_error_before

# G3.4: Web UI 显示
# 打开 http://10.1.0.13:4848/
# 好奇心队列应显示 "人工 7.5 | 内在 8.2 | 最终 7.85" 格式

# G3.5: 纯探索模式
python3 curious_agent.py --run --pure-curious
# 检查 state.json curiosity_queue 中是否有非用户注入的话题
```

---

### F1: 好奇心队列条目删除

**问题**：很多历史录入的好奇心条目不完整或已过时，人工无法清除，导致队列臃肿

**解决方案**：支持从 CLI 和 Web 页面删除指定条目

**CLI 接口**：
```bash
# 删除单个（按 topic 精确匹配）
python3 curious_agent.py --delete "过时的话题"

# 强制删除（忽略 status）
python3 curious_agent.py --delete "test deep" --force

# 列出所有待探索条目（删除前确认）
python3 curious_agent.py --list-pending

# 批量删除（删除多条）
python3 curious_agent.py --delete "topic1" "topic2" "topic3"
```

**Web UI**：
- 好奇心队列每行增加「删除」按钮（🗑️ 图标）
- 点击后弹出确认框（"确认删除：{topic}？"）
- 支持批量选择删除（Checkbox + 批量删除按钮）

**API 接口**：
```bash
# DELETE 方法删除单个
curl -X DELETE "http://10.1.0.13:4848/api/curious/queue?topic=test%20deep"

# POST 批量删除
curl -X POST "http://10.1.0.13:4848/api/curious/queue/delete" \
  -H "Content-Type: application/json" \
  -d '{"topics": ["test deep", "test shallow"], "force": true}'
```

**实现要点**：
1. 删除前检查 `status`：`done`/`exploring` 不可删，除非 `--force`
2. 删除后更新 `state.json` 的 `curiosity_queue` 数组
3. Web UI 删除后局部刷新队列列表，不刷新整页
4. 删除操作记入 `logs/` 操作日志

**验收测试**：
```bash
# F1.1: CLI 删除
python3 curious_agent.py --inject "temp test"
python3 curious_agent.py --list-pending  # 找到 temp test
python3 curious_agent.py --delete "temp test"
python3 curious_agent.py --list-pending  # temp test 已消失

# F1.2: Web 删除
# 打开 http://10.1.0.13:4848/
# 找到任意 pending 条目，点击 🗑️
# 确认后条目消失

# F1.3: API 删除
curl -X DELETE "http://10.1.0.13:4848/api/curious/queue?topic=test"
# 验证 state.json 中该 topic 已移除
```

---

### F2: Layer 3 深度洞察几乎不触发

**发现时间**：2026-03-20 定期巡检 | 状态：待修复

#### 问题描述

运行统计（2026-03-20）：
```
Layer 1 (web搜索):  38次 (77%)
Layer 2 (ArXiv分析): 10次 (20%)
Layer 3 (深度洞察):  1次  (2%)  ← 严重不足
```

Layer 3 本应是 v0.2 的核心价值之一（多论文对比 + LLM 洞察生成），实际几乎从未运行。

#### 根因分析

`Explorer._explore_layers()` 的触发条件：

```python
# explorer.py, _explore_layers()
if self.exploration_depth == "deep" AND        # ← 问题1: 默认是 "medium"
   "layer2" in layer_results AND              # ← 问题2: 需要 layer2 有结果
   len(papers) >= 2:                          # ← 问题3: 需要至少2篇论文
```

**问题1 — exploration_depth 永远是 "medium"**：
```python
# curious_agent.py, run_one_cycle()
explorer = Explorer()  # ← 没有传 exploration_depth 参数！
```

即使用 `curious_agent.py --run --run-depth deep`，`Explorer` 实例仍然是无参数的默认 "medium"，Layer 3 根本进不去。

**问题2 — ArXiv 链接获取不稳定**：
- Bocha 搜索返回的 arXiv 结果不稳定
- 有时搜索结果里没有 arXiv 链接
- 没有 arXiv 链接 → Layer 2 失败 → Layer 3 更无望

**问题3 — Layer 2 papers 格式不完整**：
- ArxivAnalyzer 返回的 papers 列表经常为空或不完整
- 即便有链接，解析失败也会导致 Layer 2 空转

#### 期望效果

| 状态 | 触发条件 | 期望占比 |
|------|---------|---------|
| Layer 1 | 每次运行 | 100% |
| Layer 2 | medium/deep + 有ArXiv链接 | 50-60% |
| Layer 3 | deep + Layer2有≥2篇论文 | 20-30% |

#### 解决思路

**Step 1 — 传递 exploration_depth 参数（高优）**：
```python
# curious_agent.py run_one_cycle()
def run_one_cycle(depth: str = "medium"):
    explorer = Explorer(exploration_depth=depth)  # ← 传递参数
```

**Step 2 — 改善 ArXiv 搜索稳定性**：
- Layer 1 同时用 Bocha + 直接调用 ArXiv API 搜索，互为备份
- 优先使用 ArXiv API 的结构化结果作为 Layer 2 输入

**Step 3 — Layer 2 容错增强**：
- 即便 ArXiv 链接少，也尝试用 Layer 1 的搜索结果构造伪论文对象
- Layer 2 不再要求 "至少2篇"，1篇也可以生成有限洞察

**Step 4 — Layer 3 触发放宽（可选）**：
- 去掉 `len(papers) >= 2` 硬性要求
- 改为 `len(papers) >= 1 AND exploration_depth == "deep"`

#### 验收测试

```bash
# F2.1: 验证 depth 参数传递
python3 curious_agent.py --run --run-depth deep
# 检查 logs/curious.log，应该出现 "Layer 3" 相关日志

# F2.2: 验证 ArXiv 搜索降级
# 用一个没有 ArXiv 结果的话题测试，看是否有 fallback 机制

# F2.3: 统计验证
# 运行10轮 deep 探索，Layer 3 触发率应 >= 20%
```

---

### F3: 关键词过滤失效导致队列污染

**发现时间**：2026-03-20 定期巡检 | 状态：待修复

#### 问题描述

队列中有大量无意义条目（巡检时间：2026-03-20）：

```
"TeST" (单字符截断)
"Agen" (单词截断)
"Chief Technology Officer" (通用商业词汇)
"SegmentFault" → "CentOS", "Segmentation"... (搜索结果噪音)
"AIGC", "AI Strategy", "AI Business Strategy" (SEO/商业词)
"John Carpenter  AI" (完全无关)
"Cognition\nAI", "Devin\nAI" (换行符导致截断)
```

清理前：184条 pending（135条有问题）
清理后：0条 pending（清理掉89条噪音 + 45条劣质）

#### 根因分析

`_extract_keywords()` 的实现逻辑：

```python
# curiosity_engine.py, _extract_keywords()
keywords = re.findall(r'[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2}', text)
# 问题1: 正则只按大写字母提取，没有停用词表
# 问题2: 数字/特殊字符没有清理（"TeST", "SegmentationfaultusingRPMI"）
# 问题3: 换行符没有预处理（导致 "Devin\nAI" → "Devin" 和 "AI" 被分开处理）
# 问题4: 搜索引擎返回的品牌词/公司名全部被纳入（SegmentFault, CentOS...）
```

`auto_queue_topics()` 没有任何过滤：

```python
# curiosity_engine.py, auto_queue_topics()
# 问题: 所有关键词都会被加入队列，没有质量门槛
# 即便 _extract_keywords 提取正确，Bocha 搜索结果的 snippet 中
# 包含的无关词汇也会被一并提取（如 OS 名、行业词等）
```

#### 期望效果

自动入队的关键词应满足：
1. 与 Agent/AI 研究相关（有语义关联网）
2. 长度 >= 4 字符
3. 不是通用词/停用词
4. 不含换行/特殊字符
5. 预估评分 > 5.0 才入队

**队列自动增长时，噪音率应 < 5%**

#### 解决思路

**Step 1 — 领域停用词表**：
```python
STOPWORDS = {
    # 通用商业/SEO词
    "AI Strategy", "AI Business", "Digital Marketing", "CTO", "COO",
    "Chief Technology Officer", "Customer Loyalty", "Operations",
    # 搜索结果噪音词
    "SegmentFault", "CentOS", "Segmentation fault",
    # 单字母/截断
    "Agen", "TeST",
}

def _extract_keywords(text):
    # ... 现有逻辑 ...
    # 新增: 停用词过滤
    # 新增: 换行符预处理 text.replace('\n', ' ')
    # 新增: 长度过滤 len(kw) >= 4
```

**Step 2 — 语义相关性预检**：
```python
RESEARCH_KEYWORDS = {
    "agent", "llm", "memory", "planning", "reasoning", "reflection",
    "metacognition", "curiosity", "autonomous", "world model", "cognitive",
    "framework", "architecture", "training", "arxiv", "reinforcement",
    "chain-of-thought", "prompt", "embedding", "attention", "transformer",
}

def _is_research_related(keyword):
    kw_lower = keyword.lower()
    return any(rk in kw_lower for rk in RESEARCH_KEYWORDS)
```

**Step 3 — 最小评分门槛**：
```python
def auto_queue_topics(topics):
    # 改为: 计算预估 score，低于 5.0 不入队
    for topic in topics:
        estimated_score = engine.estimate_score(topic)
        if estimated_score >= 5.0:
            kg.add_curiosity(...)
```

**Step 4 — 换行符预处理（源头修复）**：
```python
def _extract_keywords(text):
    text = text.replace('\n', ' ').replace('\r', ' ')  # ← 加在正则之前
    # 然后再提取
```

#### 验收测试

```bash
# F3.1: 换行符处理
python3 -c "
from core.curiosity_engine import CuriosityEngine
ce = CuriosityEngine()
kw = ce._extract_keywords('Devin\nAI and Machine Learning')
print(kw)  # 应输出干净词汇，不含换行符残留
"

# F3.2: 停用词过滤
kw = ce._extract_keywords('AI Strategy and Digital Marketing with CTO')
print(kw)  # 应为空或极少

# F3.3: 运行一轮探索后检查队列
python3 curious_agent.py --run
# 观察 auto-queue 的条目质量
```

---

### F4: 启动脚本 — 存量进程检测与干净重启

**问题描述**

当前部署需要手动两步：
```bash
# 手动杀进程
pkill -f "curious_api.py"

# 手动启动
cd /root/dev/curious-agent && python3 curious_api.py
```

容易出现：
- 残留旧进程占端口（4848/4849）
- 重复启动多个实例
- 端口冲突

#### 期望效果

一行命令完成干净启动：
```bash
bash run_curious.sh
```

自动完成：
1. 检测并 kill 所有 `curious_api.py` / `curious_agent.py` 进程
2. 检测并 kill 占用 4848/4849 端口的进程
3. 启动新的服务
4. 等待启动完成，验证 API 可访问
5. 报告启动结果（成功/失败 + 原因）

#### 解决思路

```bash
#!/bin/bash
# run_curious.sh

PORT=${PORT:-4848}
APP_DIR="/root/dev/curious-agent"
LOG_FILE="$APP_DIR/logs/api.log"

# 1. 检测占用端口的进程
echo "[清理] 检测端口 $PORT ..."
fuser -k ${PORT}/tcp 2>/dev/null

# 2. Kill 残留的 curious 进程
pkill -f "curious_api.py" 2>/dev/null && echo "[清理] 已终止 curious_api.py"
pkill -f "curious_agent.py" 2>/dev/null && echo "[清理] 已终止 curious_agent.py"

# 3. 等待端口释放
sleep 2

# 4. 启动服务
echo "[启动] 启动 Curious Agent ..."
cd "$APP_DIR"
nohup python3 curious_api.py > "$LOG_FILE" 2>&1 &
PID=$!
echo "[启动] PID: $PID"

# 5. 等待启动并验证
for i in {1..10}; do
    sleep 1
    if curl -s "http://localhost:$PORT/api/curious/state" > /dev/null 2>&1; then
        echo "[完成] Curious Agent 已启动: http://10.1.0.13:$PORT/"
        exit 0
    fi
done

echo "[错误] 启动失败，请检查日志: $LOG_FILE"
exit 1
```

#### 验收测试

```bash
# F4.1: 干净启动
bash run_curious.sh
# 预期: 显示清理步骤 + 启动成功

# F4.2: 重复执行（验证幂等）
bash run_curious.sh
# 预期: 第二次仍然干净启动，无端口冲突

# F4.3: 验证残留进程清理
# 手动启动一个 python3 curious_api.py（后台）
# 然后运行 bash run_curious.sh
# 预期: 旧进程被清理，新进程启动
```

---

### F5: ArXiv Analyzer 容错增强

**发现时间**：2026-03-20 巡检 | 状态：待修复

#### 问题描述

Layer 2 的核心输入依赖 `ArxivAnalyzer.analyze_papers()`，但该模块经常返回空或不完整：

```
# 实际运行日志
Layer 2 → ArXiv search for: autonomous agent planning
Layer 2 → Papers analyzed: 0  ← 经常失败
```

导致即使 Layer 1 找到了 ArXiv 链接，Layer 2 也拿不到论文内容，Layer 3 更无望。

#### 根因分析

`core/arxiv_analyzer.py` 可能存在：
1. PDF 下载超时/失败无容错
2. 论文摘要提取正则不够健壮
3. 论文相关性评分逻辑简单，误过滤
4. 无 fallback：PDF 失败时没有用 search snippet 构造伪论文对象

#### 期望效果

- Layer 2 的 papers 分析成功率从当前 ~20% 提升到 60%+
- 即便论文 PDF 下载失败，也能用摘要/snippet 构造可用的 paper 对象
- Layer 3 能稳定触发（不再因为 Layer 2 无输出而跳过）

#### 解决思路

**Step 1 — 健壮性修复**：
```python
# core/arxiv_analyzer.py
def analyze_papers(topic, links):
    results = []
    for link in links[:5]:
        try:
            # 增加超时和重试
            paper = fetch_arxiv_paper(link, timeout=10, retries=2)
            if paper:
                results.append(paper)
        except Exception:
            # Fallback: 用 search result 的 snippet 构造伪对象
            fallback = build_fallback_paper(link, topic)
            if fallback:
                results.append(fallback)
    return results
```

**Step 2 — 相关性评分放宽**：
```python
# 当前: relevance_score < 0.6 的论文被过滤
# 改为: < 0.3 才过滤，保留边缘论文给 Layer 3 处理
```

**Step 3 — Layer 2 输出验证**：
```python
# 即使只有1篇论文，也传给 Layer 3
# Layer 3 可以对单论文做深度摘要，不一定要对比
```

#### 验收测试

```bash
# F5.1: 验证 ArXiv 解析成功率
# 运行10轮带 ArXiv 链接的探索，Layer 2 输出率应 >= 60%

# F5.2: 验证 fallback 机制
# 用一个链接无效的话题测试，确认 fallback paper 被生成

# F5.3: 端到端验证
python3 curious_agent.py --run --run-depth deep
# 观察 Layer 2 是否有输出，Layer 3 是否被触发
```

---
_文档版本: v0.2.1（第四版）_
_创建时间: 2026-03-19_
_最后更新: 2026-03-20 11:30_
_追加内容: F1(队列删除) + F2(Layer3触发) + F3(关键词过滤) + F4(启动脚本) + F5(ArXiv容错)_
_前置依赖: v0.2 (next_move.md)_


