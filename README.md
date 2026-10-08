# Curious Agent

[![Version](https://img.shields.io/badge/version-v0.3.6-blue)](https://github.com/weNix901/CuriousAgent)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](#)
[![Neo4j](https://img.shields.io/badge/neo4j-5.x-green)](#)
[![License](https://img.shields.io/badge/license-MIT-blue)](#)

> **别人只帮你收藏链接，CA帮你把资料吃透——读完变本事**

别的系统像只存书单（标题+链接），CA帮你把书读完、拆开揉碎、消化吸收——**PDF、网页、GitHub、文档、博客都能读**，全文不放过，知识不白看。

---

## CA 能帮你做什么？

| 别的系统 | Curious Agent |
|---------|---------------|
| ❌ 问啥答啥，不问不动 | ✅ **主动学习**：没事就自己找资料读，越读越懂 |
| ❌ 什么都敢答，答完你也不知道对不对 | ✅ **知道不知道什么**：懂的就说懂，不懂的就承认，还帮你补上 |
| ❌ 知识短板在哪？不知道 | ✅ **发现短板**：自动找到你没读过的领域，主动补课 |
| ❌ 一本书读三个月，读完还是厚 | ✅ **把书读薄**：核心概念自动提取，几百页变几个知识点 |
| ❌ 读完了就存着，下次还得重新找 | ✅ **主动探索**：读完还会联想，发现相关领域继续读 |
| ❌ 知识锁在库里，用不上 | ✅ **随时迁移**：读到的好方法，直接变成你的做事套路 |

---

## 一句话说明

**CA = 主动学习 + 把书读薄 + 知识变本事**

```
PDF / 网页 / GitHub / 文档 / 博客 / 教程
         ↓
    全文深读，不漏任何一页
         ↓
    把书读薄——每个概念拆成：是什么、怎么用、谁提出的、有公式吗
         ↓
    发现短板——这个领域我还没读过？补上
         ↓
    主动联想——这个概念跟Transformer有关系？继续挖
         ↓
    知识变本事——好方法直接变成做事规则
```

---

## v0.3.6 核心能力

### 🏛️ 唯一真源 + 唯一通路（地基修复，本版主线）

v0.3.6 的主线不是加功能，而是**把被破坏的数据地基修回来**。

**发现**：四个 Agent（Explore / Dream / DeepRead / SleepPruner）不是"各用各的源"，
而是**真源已定义，但一半 Agent 还在读一个已被掏空的旧壳子，且不报错**：

- `state.json` 已退场，但 `_load_state()/_save_state()` 仍返回旧骨架
- `state["knowledge"]["topics"]` **恒为空** → SleepPruner 写 dormant 静默失效
  （修复后候选从 **0 → 691 个**）
- DreamAgent 的 quality/surprise/cross_domain 三维输入恒为默认值
- `competence_tracker` / `exploration_history` 的写入被 `_save_state` 白名单**静默丢弃**

**SSOT 批次修复**（读通路唯一）：

| 批次 | 修复 |
|------|------|
| SSOT-0 | 读源护栏（空 topics 时告警，防静默复发） |
| SSOT-1 | SleepPruner dormant → Neo4j |
| SSOT-2 | DreamAgent 输入 → `get_state()`（Neo4j） |
| SSOT-3 | meta_cognitive_monitor + competence_tracker |
| SSOT-4 | exploration_history → `ops.db.runtime_kv` |
| SSOT-5 | curiosity_engine → queue.db |
| SSOT-6 | 语义化改名 + `_save_state` 白名单改"非 knowledge 键一律持久化" |

**验收**：`scripts/verify_ssot.py` **10/10 PASS**（含反向验证：改前失效、改后生效）。

### 🧹 数据源唯一性与通路一致性（新规范，本版立规）

**weNix 指令**：做改动时保持数据源唯一性与消费通路一致性，
**不得新增消费逻辑的同时还留着旧通路**。

- 新增 `docs/plan/数据源唯一性与通路一致性规范.md`
- 真源/通路裁定表：每个概念**一条写通路 + 一条读通路**
- 6 条新增功能准入 checklist
- **C2b 落地**：队列写入 6 处绕过 `add_curiosity()` 的旁路全部收敛
  （`add_item` 调用点 9 → 2：入口自身 + deep_read 登记例外）

### 🎯 C2 缺口生成修复：去噪 + 消费循环

**两处硬伤**（同一个病：噪声数据上建闭环）：

| 硬伤 | 症状 | 修复 |
|------|------|------|
| 相关性信号混噪声 | `seen_count` 把真人查询和测试打点混在一起 | `gaps` 表加 `observed_by`/`real_seen`，相关性只认真实会话触发 |
| 队列一次性死亡 | `consumed` 全=1，候选恒为 0 | `reset_stale_consumed()` 时间衰减 → C2 变循环 |

实测：`UnknownTopic123`（测试词）相关性归零，`FlashAttention`（真缺口）浮现。

### 🔄 C3-D 重定向：反馈回好奇改为"发现→消费"

**病因**：原 C3-D 用"被动查询"驱动"主动探索"，违反 CA2.0 §1.3 公理
——会让系统系统性遗忘自己主动探过的方向。

**重定向**：

| 批次 | 改动 |
|------|------|
| C3D-R1 | 移除提权通路（因果纠正）——缺口优先级只由 C2 三因子决定 |
| C3D-R2 | `related_discoveries()`：发现 → 消费提示（扩大消费面） |
| C3D-R3 | 引用率口径修正（分母从 360 条爬虫噪声 → 806 真实发现） |

**接入 R1D3**（hook + skill）：回答时附"系统探过的同方向内容"。
加 **30s 缓存**解决端点 2.7s 超时（预热 2.80s → 命中 0.048s）。

实测：查 `FlashAttention` → 返回 FlashAttention-2/3 论文（相似度 0.83~0.85）。

### 🧠 显式学习需求（C2-B）：R1D3 主动声明

**决策**：由 **R1D3 写**——用户只与 R1D3 交互，CA 不"从对话推断"需求（读心违反 C1 公理）。

- `shared_knowledge/r1d3/learning_needs/<slug>.md`（YAML front-matter）
- 接入缺口相关性：**相关性 = max(会话触发, 显式需求权重)**（取大不叠加）
- 效果：有显式需求的 topic 即使没人问过，缺口优先级也会被拉高 → 主动探索

### 🔗 冲突检测地基：provider 一致性落库（批1/批8）

**问题**：分解器的多 Provider 验证产出 `{provider: 结果数}`，但**只在内存用一次就丢**——
`/api/providers/record` 端点存在却无调用方，`provider_heatmap.json` 从未生成。
信号5（provider 一致性）是**死数据**。

**修法**：验证结果落库 `ops.db.provider_agreement(topic, provider, result_count, agreed, ts)`。
- 真值源 = SQLite（v0.3.4 数据治理），非文件副本
- **幂等**：同 topic 重复写覆盖，不累积
- 记录"未找到"的 provider（`agreed=0`）→ C1-B 冲突检测需要"谁没找到"
- `get_agreement()` 直接输出 `disagreement` 布尔，供冲突检测消费

```
RAG      → {bocha:0, serper:5}  disagreement=True（分歧：一个找到一个没找到）
Reranker → {bocha:0, serper:5}  disagreement=True
```

### 🚦 Hook 端到端：四态感知回路真正闭合（批0c）

修好了 `knowledge-gate` Hook 的**三层断裂**（Bug A「看着修好了其实没生效」）：

| 层 | 问题 | 修复 |
|----|------|------|
| L1 匹配策略 | 端点用精确匹配，`RAG` 查不到含 RAG 的节点 | `/api/knowledge/check` 内部改调语义 `check_confidence()` |
| L2 字段选错 | 读恒为 0 的 `confidence` 字段 | 值改为有效置信度（经 quality 调制） |
| L3 四态未接 | Hook 只读数值，不消费 `coverage` | Hook 以四态为主轴分派，`unknown`/`void` 不再静默 |

**端到端验收矩阵（8 项全绿）**：

| 查询 | 结果 |
|------|------|
| `RAG` | 🟢 known 0.700 |
| `transformer attention` | 🟢 known 0.640 |
| `agent 上下文管理` | 🟡 partial 0.175 |
| `知识图谱` | 🟠 **unknown**（修复前静默） |
| `不存在xyz` | 🟠 unknown |
| CA 不可达 | ✅ 不 throw，仅日志（护栏不变式） |
| 旧服务端（无 coverage） | ✅ 回落数值三分支，零回归 |

### 🧱 四态输入净化

| 批次 | 修复 |
|------|------|
| 批0 | E1 内容实质门——拒绝"幽灵节点"污染四态输入 |
| 批0b | quality=0 节点不再伪装"有点知识"（θ₁ 修正） |
| 批0d | 恢复 4 条 CA2.0 对位路由（dream_insights/frontier/calibration） |

---

## v0.3.5 核心能力

### 🎯 知道不知道什么——四态覆盖判定

**问题**：CA 怎么知道一个话题"到底懂不懂"？让 LLM 自省不可靠——它可能自信地答错。

**CA 怎么做**：把"懂不懂"变成**对外部信号的测量**，不问被测量的对象。

```
问题 Q
  ├─ KG 有节点 & quality ≥ θ₁ & 来源 ≥ θ₂  → known    → 直接答，标 [已知]
  ├─ KG 有节点 & quality 低 或 来源单薄    → partial  → 答 + 标注不确定性
  ├─ KG 无节点 & 搜索有结果                → unknown  → 答（基于搜索）+ 触发探索
  └─ KG 无节点 & 搜索无果 & 有 failed 记录 → void     → 明确声明"系统层面无依据"
```

**判决器**：`core/api/coverage_resolver.py` —— 纯函数，无 I/O，易测。
- 阈值 θ₁/θ₂ **回测定标**（非预设），集中在模块顶层，改一处全系统重调
- 20 问标注集一致率 **100%**

### 🔧 测量层修复（C0）

修好了两个让四态判定输入失真的地基缺陷：

| 缺陷 | 症状 | 修复 |
|------|------|------|
| **短词检索失效** | `RAG` 存在于 KG 却返回 0.00（缩写向量落在语义中心） | 关键词 + 语义双通道 |
| **置信度公式归零** | `similarity × (quality/10)`：quality=0 把 0.83 打成 0.09 | 软调制 `similarity × f(quality)`，值域 [0.5, 1.0] |

### 🔌 外部置信度注入（C1-C）

四态语义注入 agent 上下文，替代旧的"置信度百分比"：

```
旧："[KG Context — 置信度中 53%]"
新："[KG Context — partial] 缺口：quality=0.0, sources=0"
```

**单一端点** `/api/kg/confidence/<topic>` 同时服务 Hook 与 Skill（向后兼容保留区间字段）。

> **v0.3.5 附带修复**：`knowledge-gate` Hook 长期调用一个**从未注册**的路由
> → 404 → 被 `catch{}` 静默吞掉 → 一直在注入空内容。已修。
> 教训：**静默失败 = 最贵的失败。**

---

## v0.3.4 核心能力

### 📖 全文深读——把书读薄

**问题**：传统方法只读前几页，80% 内容白给。

**CA 怎么做**：滑动窗口从头读到尾，每一页都过一遍。

```
短论文 ≤30K  →  1 段读完
中等论文 30-80K →  9 段，每段都读
长论文 >80K  →  20 段，157% 覆盖（有重叠，确保不漏）
```

### 🔬 把概念拆开——6块清楚明白

读完不是存个摘要就完事，而是把每个概念拆开揉碎：

| 拆解 | 说明 | 举个例子 |
|------|------|---------|
| **是什么** | 一两句定义 | LTKD 是解决长尾数据知识蒸馏的方法 |
| **怎么工作的** | 核心原理 | 把KL散度拆成跨组损失+组内损失 |
| **谁提出的** | 背景来源 | Seonghak Kim，韩国国防研究院 |
| **怎么用** | 实际例子 | CIFAR-100长尾版、ImageNet长尾版 |
| **有公式吗** | 数学表达 | KL(p_T || p_S) |
| **跟谁有关系** | 关联概念 | 父节点=知识蒸馏，兄弟=教师偏差 |

### 🌐 有内容就能读——不只是论文

| 能读什么 | 支持状态 |
|----------|---------|
| **论文PDF** | ✅ 学术论文、技术报告 |
| **arXiv网页** | ✅ 直接抓HTML，不用下载PDF |
| **GitHub README** | ✅ 代码仓库文档 |
| **官方文档** | ✅ Python、PyTorch、TensorFlow、HuggingFace、React... |
| **博客/教程** | ✅ Medium、个人博客、技术教程 |
| **ACL论文库** | ✅ NLP论文一键入队 |
| **任何网页** | ✅ 只要内容有价值，CA就能读 |

```bash
# 随便丢个链接，CA就去读
curl -X POST http://localhost:4848/api/web-scrape/enqueue \
  -d '{"url": "https://docs.python.org/3/library/asyncio.html", "topic": "asyncio"}'
```

### 🧠 知道不知道什么——发现短板

CA 会自己检查：
- 这个领域我读过吗？
- 读过的概念有没有遗漏的子概念？
- 相关领域我了解吗？

**发现短板 → 自动补课**：没读过的领域自动加入探索队列。

### 🔗 主动联想——发现隐藏关系

读完了不会停，CA会想：
- 这个概念跟Transformer有关系？挖一下
- 这个方法的根原理是什么？追溯到注意力机制
- 这个领域跟另一个领域有交集？都读一下

### 🎯 知识变本事——好方法变成你的套路

读到的好方法不会只存着，而是变成你的做事规则：
- "回答复杂问题前先评估置信度"
- "搜索结果要记下来，下次不用再搜"
- "不懂的领域要主动补充"

**一次学会，永久升级**。

#### 行为规则管道（v0.3.4 修复）

「知识变本事」的落地链路是一条完整管道，v0.3.4 修复了它长期断裂的问题：

```
ExploreAgent 探索
      ↓  quality = 5.0 + 来源数
Daemon 接收结果
      ↓  quality ≥ 7.0 才触发
AgentBehaviorWriter
      ↓  按类型分类（推理/元认知/工具发现…）
curious-agent-behaviors.md
      ↓  OpenClaw 索引（extraPaths）
R1D3 的 context —— 下次对话直接引用
```

**为什么之前断了**：探索质量分（quality）在返回路径上被丢弃，且守护进程从未调用写入器。
修复后：质量分正确落库 → 守护进程触发写入 → 规则进入行为库 → 被检索进上下文。

### 🗄️ 唯一真值源——四源架构（v0.3.4 数据治理）

早期运行状态与知识存在多份平行副本（13 个数据源），互不同步、持续腐化。
v0.3.4 收敛为 **4 个真值源**：

| # | 真值源 | 内容 |
|---|--------|------|
| ① | **Neo4j** | 所有知识（节点 / 关系 / 质量 / 来源） |
| ② | **knowledge/queue.db** | 探索队列（唯一） |
| ③ | **knowledge/ops.db** | 运行状态（配额 / 审计 / 断言 / 元认知 / 根技术池） |
| ④ | **文件** | 仅日志与人类可读报告 |

**原则**：知识进 Neo4j，运行状态进 SQLite，每个概念只有一个写入点，
快照/缓存一律只读派生。已废除 `state.json` 平行副本。

### ⚙️ 配置随时改——Web UI 可视化

Settings 页面直接调：
- 读论文时的段落重叠比例
- 知识热度衰减速度
- 低热度知识什么时候归档

改完立即生效，不用重启。

---

## Quick Start

### 安装

```bash
git clone https://github.com/weNix901/CuriousAgent.git
cd curious-agent

pip install -r requirements.txt
cp config.example.json config.json
# 配置 .env 里的 API keys
```

### 启动

```bash
bash start.sh
```

**启动的服务**：

| 服务 | 端口 | 干啥 |
|------|------|------|
| **API + Web UI** | 4848 | 可视化界面、REST API |
| **Agent守护进程** | — | 自动探索、深读、联想 |

**打开界面**：`http://localhost:4848/`

### 怎么用

**让 CA 自己去读**：

```bash
# 丢个链接，CA就去读
curl -X POST http://localhost:4848/api/web-scrape/enqueue \
  -d '{"url": "https://arxiv.org/html/2506.18496", "topic": "LTKD"}'

# 或者手动注入一个想了解的话题
curl -X POST http://localhost:4848/api/curious/inject \
  -d '{"topic": "FlashAttention", "score": 8.5}'
```

**看看 CA 读到了什么**：

```bash
# 查知识点详情
curl "http://localhost:4848/api/kg/nodes/LTKD"

# 追溯这个概念的根源
curl "http://localhost:4848/api/kg/trace/LTKD"
```

**Web UI 图谱可视化**：

打开界面 → Graph Tab → 拖拽节点、点击查看详情

---

## API Reference

### 核心 API

| Endpoint | 说明 |
|----------|------|
| `GET /api/curious/state` | 系统状态（队列、KG、日志） |
| `POST /api/curious/inject` | 注入探索话题 |
| `GET /api/queue` | 队列状态 |
| `GET /api/kg/nodes/{topic}` | 知识点详情（含 6-element） |
| `GET /api/kg/roots` | 根技术池 |
| `GET /api/kg/trace/{topic}` | 根技术追溯 |

### v0.3.5 新增

| Endpoint | 说明 |
|----------|------|
| `GET /api/kg/confidence/<topic>` | 四态覆盖判定（known/partial/unknown/void）+ 来源数 + legacy 区间 |

> v0.3.5 将原 `/api/kg/confidence/<topic>` 与 `/api/knowledge/confidence`
> 两条重复路由合并为**单一路由**（核心逻辑本就相同，仅响应包装不同）。

### v0.3.6 新增

| Endpoint | 说明 |
|----------|------|
| `POST /api/knowledge/check` | 接四态 + Y 扩展契约（旧字段保留 + `coverage`/`matched_topic`/`similarity` 追加） |
| `GET /api/kg/frontier` | 缺口前沿数据源（C2 上游） |
| `GET /api/kg/calibration` | 自省质量（含 `no_data` 态） |
| `GET /api/kg/dream_insights` | C3 回流 + F8-c 治理 |
| `GET /api/kg/related_discoveries/<topic>?k=3` | 同方向已结案发现（C3-D 消费提示） |
| `GET/POST /api/knowledge/learning_needs` | 显式学习需求（C2-B，R1D3 写 / CA 读） |

### v0.3.4 新增

| Endpoint | 说明 |
|----------|------|
| `GET /api/health` | 健康检查 |
| `GET /api/queue/pending` | 待处理队列项 |
| `POST /api/knowledge/explore` | 按知识边界触发探索 |
| `GET /api/knowledge/confidence?topic=` | 话题置信度 + 缺口（Hook 契约，v0.3.4 修正） |

### v0.3.3 新增

| Endpoint | 说明 |
|----------|------|
| `POST /api/web-scrape/enqueue` | 网页抓取入队深读 |
| `POST /api/web-scrape/batch` | 批量处理 KG 无知识点节点 |
| `GET /api/config` | 获取配置 |
| `POST /api/config` | 更新配置 |
| `GET /api/trusted-sources` | 信任源列表 |

---

## Project Structure

```
curious-agent/
├── curious_agent.py           # CLI + Daemon 协调
├── curious_api.py             # Flask API + Web UI
├── config.json                # 中央配置
├── start.sh                   # 一键启动
│
├── core/
│   ├── agents/
│   │   ├── ca_agent.py        # 统一 Agent 类
│   │   ├── explore_agent.py   # ExploreAgent (ReAct)
│   │   ├── deep_read_agent.py # DeepReadAgent (v0.3.3)
│   │   └── dream_agent.py     # DreamAgent (L1→L4)
│   │
│   ├── tools/
│   │   ├── paper_tools.py     # PDF/TXT 处理
│   │   ├── web_scrape_tools.py # 网页抓取 (v0.3.3)
│   │   ├── kg_tools.py        # KG 操作
│   │   ├── queue_tools.py     # 队列操作
│   │   └── llm_tools.py       # LLM 分析
│   │
│   ├── daemon/
│   │   ├── explore_daemon.py  # ExploreAgent 守护
│   │   ├── deep_read_daemon.py # DeepReadDaemon (v0.3.3)
│   │   └── dream_daemon.py    # DreamAgent 守护
│   │
│   ├── agent_behavior_writer.py # 行为规则写入器 (v0.3.4 接入)
│   ├── knowledge_graph_compat.py # KG 兼容层（Neo4j + ops.db）
│   │
│   ├── kg/
│   │   ├── kg_repository.py   # KG Repository
│   │   └── repository_factory.py
│   │
│   └── hooks/
│       └── cognitive_hook.py  # 认知框架 Hook
│
├── config/
│   └── trusted_sources.json   # 信任源配置 (v0.3.3)
│
├── ui/                        # Web UI
│   ├── index.html
│   ├── css/base.css
│   ├── js/*.js
│   └── views/*.html
│
├── papers/                    # 论文 TXT 存储
├── knowledge/                 # 真值源 (v0.3.4)
│   ├── queue.db               # ① 探索队列（唯一）
│   ├── ops.db                 # ② 运行状态（配额/审计/断言/元认知）
│   └── traces.db              # 派生跟踪数据
└── tests/                     # 测试套件
````

---

## Release History

| Version | Theme | Highlights |
|---------|-------|-----------|
| **v0.3.6** | Foundation Repair + C3-D Redirect | SSOT 唯一真源收敛（四 Agent，10/10 验收）、数据源唯一性与通路一致性规范、C2 缺口去噪 + 消费循环、C2b 写入通路收敛、C3-D 重定向（发现→消费 + 接入 R1D3）、C2-B 显式学习需求（R1D3 写）、批8 provider 一致性接入生产 + 批2 冲突检测重接通 |
| v0.3.5 | Coverage Verdict + Measurement Fix | 四态覆盖判定（known/partial/unknown/void）、θ 回测定标（20问100%）、短词检索修复、置信度公式去归零、单一路由合并；附带修复 Hook 静默 404 |
| v0.3.4 | Behavior Pipeline + Data Governance | 行为规则管道修复（质量分落库/类型截断/垃圾过滤）、数据源 13→4 统一、`state.json` 退场 |
| v0.3.3 | DeepRead + Web Scrape | 滑动窗口100%覆盖、6-element结构、网页抓取管道、Settings UI |
| v0.3.2 | Bootstrap Hook | Session startup API、行为规范统一 |
| v0.3.1 | Observability | Hook审计、追踪可视化、外部Agent跟踪 |
| v0.3.0 | Cognitive | 4级置信度、自动注入未知话题 |
| v0.2.9 | Agent Refactor | 统一CAAgent、ReAct循环、21工具 |

---

## Roadmap

| Status | Feature |
|--------|---------|
| ✅ | DeepReadAgent 滑动窗口全覆盖 |
| ✅ | 6-element 知识点结构 |
| ✅ | 网页抓取管道 (arXiv HTML、GitHub、文档) |
| ✅ | Neo4j KG 可视化 |
| ✅ | Settings Web UI |
| ✅ | 三 Agent 协同架构 |
| ✅ | 行为规则管道（知识→行为库→上下文） |
| ✅ | 唯一真值源架构（13→4 数据源统一） |
| ✅ | SSOT 收敛 + 唯一通路规范（四 Agent 同源） |
| ✅ | 四态覆盖判定 + 外部置信度注入 |
| ✅ | C2 缺口自动生成（去噪 + 消费循环） |
| ✅ | C3-D 发现回流（发现→消费，接入 R1D3） |
| ✅ | 显式学习需求（R1D3 主动声明） |
| ⚪ | 自适应调度（基于队列深度） |
| ⚪ | 自进化引擎（Bayesian权重更新） |
| ⚪ | 多语言论文支持 |

---

## Why Curious Agent

| | |
|---|---|
| **全文不放过** | 滑动窗口从头读到尾，每一页都过一遍 |
| **把书读薄** | 几百页内容变成几个清楚的知识点 |
| **知道不知道什么** | 懂的就说懂，不懂就承认，还帮你补上 |
| **主动联想** | 读完了还会想：这个跟谁有关系？继续挖 |
| **有内容就能读** | 论文、网页、GitHub、文档、博客——都能处理 |
| **知识变本事** | 读到的好方法变成你的做事套路 |
| **不用管它** | 自动运行，没事就自己读，越读越懂 |
| **架构干净** | 知识进图库、状态进SQLite，唯一真值源，无平行副本 |

---

## License

MIT © 2026

---

> **设计理念：主动学习、把书读薄、发现短板、知识变本事**