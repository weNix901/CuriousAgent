# Curious Agent

[![Version](https://img.shields.io/badge/version-v0.3.3-blue)](https://github.com/weNix901/CuriousAgent)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](#)
[![Neo4j](https://img.shields.io/badge/neo4j-5.x-green)](#)
[![License](https://img.shields.io/badge/license-MIT-blue)](#)

> **把论文变成知识图谱，把知识变成能力——100%覆盖、6维结构、自主进化**

不是等待提问的搜索引擎，而是**主动阅读论文**、**提取结构化知识点**、**构建可追溯知识图谱**的自主 Agent。

---

## 核心差异化

| 传统知识管理 | Curious Agent |
|-------------|---------------|
| ❌ 只存储摘要，不理解结构 | ✅ **6维知识点提取**：定义、核心、背景、示例、公式、关系 |
| ❌ PDF 必须手动处理 | ✅ **多源管道**：PDF、arXiv HTML、GitHub README、官方文档 |
| ❌ 只读前几页，遗漏核心内容 | ✅ **100%全覆盖**：滑动窗口读取全文，无遗漏 |
| ❌ 知识散落，无法追溯 | ✅ **图谱结构**：每个知识点可追溯到论文原文 |
| ❌ 需要手动触发 | ✅ **7×24 自主运行**：探索、深读、洞察三Agent协同 |

---

## 一句话定位

**Curious Agent = DeepRead (论文深读) + KG (知识图谱) + AutoEvolution (自主进化)**

```
论文 PDF / 网页 / GitHub README
         ↓
    DeepReadAgent (滑动窗口 100% 覆盖)
         ↓
    6-element 知识点提取
         ↓
    Neo4j 知识图谱 (可追溯、可关联)
         ↓
    高质量发现 → 行为规则 → 永久能力升级
```

---

## v0.3.3 核心特性

### 📖 DeepReadAgent — 论文深读引擎

**问题**：传统方法只读前 8000 字符，论文 80% 内容被遗漏。

**解决方案**：滑动窗口全覆盖读取

```
论文长度 ≤30K  →  1 段 (8000 chars)
论文长度 30-80K →  9 段 (重叠 3000 chars)
论文长度 >80K  →  20 段 (157% 覆盖率)
```

**效果**：
- 51K 论文 → 提取 9 个知识点（vs 传统方法 5 个）
- 每个知识点包含完整 6-element 结构

### 🔬 6-Element 知识点结构

每个知识点不再只是摘要，而是完整的结构化信息：

| 元素 | 说明 | 示例 |
|------|------|------|
| **definition** | 定义（1-2句） | Long-Tailed Knowledge Distillation (LTKD) is a framework... |
| **core** | 核心机制 | Decomposes KL into cross-group + within-group loss |
| **context** | 背景 | Introduced by Seonghak Kim, Agency for Defense Development |
| **examples** | 应用示例 | CIFAR-100-LT, TinyImageNet-LT, ImageNet-LT |
| **formula** | 关键公式 | KL(p_T || p_S) |
| **relationships** | 关联概念 | parent=Knowledge Distillation, related=Teacher Bias |

### 🌐 多源输入管道

不只支持 PDF，还能直接抓取网页内容：

| 来源 | 支持状态 | 说明 |
|------|---------|------|
| **arXiv PDF** | ✅ | 自动下载、解析、提取 |
| **arXiv HTML** | ✅ | 网页抓取，无需 PDF |
| **GitHub README** | ✅ | 代码仓库文档直接提取 |
| **官方文档** | ✅ | Python.org, TensorFlow, PyTorch, HuggingFace |
| **ACL Anthology** | ✅ | NLP 论文库 |

**一键抓取入队**：

```bash
curl -X POST http://localhost:4848/api/web-scrape/enqueue \
  -d '{"url": "https://arxiv.org/html/2506.18496v2", "topic": "LTKD"}'
# → Scraped 51K chars, queued for DeepRead
```

### 🕸️ Neo4j 知识图谱

所有知识点存储在 Neo4j，支持：

- **追溯**：每个知识点可追溯到原文位置
- **关联**：自动建立 parent-child、citation 关系
- **可视化**：Web UI 图谱交互（拖拽、缩放、点击查看详情）
- **查询**：置信度查询、根技术追溯、热度分析

### 🤖 三 Agent 协同架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Curious Agent Daemon                          │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ ExploreAgent │  │ DeepReadAgent│  │  DreamAgent  │          │
│  │   (ReAct)    │  │  (滑动窗口)   │  │   (L1→L4)   │          │
│  │              │  │              │  │              │          │
│  │ Web Search   │  │ PDF/网页深读  │  │ KG 洞察生成  │          │
│  │ KG 写入      │  │ 6-element提取 │  │ 队列补充     │          │
│  │ Queue 入队   │  │ KG 结构化写入 │  │ 跨域联想     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│        ↓                  ↓                  ↓                  │
│   5min poll          30min poll          6h heartbeat           │
│                                                                  │
│  ┌──────────────┐                                               │
│  │ SleepPruner │  ← KG 维护：清理低热度节点                      │
│  │  (自适应)   │                                                 │
│  └──────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
```

| Agent | 触发 | 功能 | 工具数 |
|-------|------|------|--------|
| **ExploreAgent** | 5min poll | Web 搜索 → KG 写入 → Queue 入队 | 14 |
| **DeepReadAgent** | 30min poll | 论文深读 → 6-element → KG 结构化 | 8 |
| **DreamAgent** | 6h heartbeat | KG 洞察 → 新探索候选 | 15 |

### ⚙️ Web UI 可视化配置

Settings Tab 支持实时配置：

- **DeepRead 配置**：段落重叠、上下文扩展、完整度阈值
- **温度系统配置**：衰减因子、热点/温区阈值
- **归档策略配置**：触发温度、TXT/PDF 处理

所有配置持久化到 `config.json`，无需重启。

---

## Quick Start

### 安装

```bash
git clone https://github.com/weNix901/CuriousAgent.git
cd curious-agent

pip install -r requirements.txt
cp config.example.json config.json
# 编辑 .env 配置 API keys
```

### 启动

```bash
bash start.sh
```

**服务启动**：

| 服务 | 端口 | 说明 |
|------|------|------|
| **curious_api** | 4848 | REST API + Web UI |
| **curious_agent --daemon** | - | 三 Agent 协同运行 |

**访问**：
- 🌐 Web UI: `http://localhost:4848/`
- 📡 API: `http://localhost:4848/api/curious/state`

### 使用

**1. 注入探索话题**：

```bash
curl -X POST http://localhost:4848/api/curious/inject \
  -d '{"topic": "FlashAttention", "score": 8.5}'
```

**2. 抓取网页入队深读**：

```bash
curl -X POST http://localhost:4848/api/web-scrape/enqueue \
  -d '{"url": "https://arxiv.org/html/2506.18496v2", "topic": "LTKD"}'
```

**3. 查询 KG 知识点**：

```bash
curl "http://localhost:4848/api/kg/nodes/Long-Tailed%20Knowledge%20Distillation"
```

**4. 查看图谱可视化**：

打开 Web UI → Graph Tab → 拖拽节点、点击查看 6-element 详情

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
├── knowledge/                 # KG 状态
└── tests/                     # 测试套件
```

---

## Release History

| Version | Theme | Highlights |
|---------|-------|-----------|
| **v0.3.3** | DeepRead + Web Scrape | 滑动窗口100%覆盖、6-element结构、网页抓取管道、Settings UI |
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
| ⚪ | 自适应调度（基于队列深度） |
| ⚪ | 自进化引擎（Bayesian权重更新） |
| ⚪ | 多语言论文支持 |

---

## Why Curious Agent

| | |
|---|---|
| **100%覆盖** | 滑动窗口确保论文每一页都被阅读，无遗漏 |
| **结构化知识** | 6-element 让知识点可理解、可追溯、可关联 |
| **多源输入** | PDF、网页、GitHub——任何有价值的文本都能处理 |
| **自主运行** | 7×24 不间断探索、深读、洞察 |
| **可视化** | Web UI 图谱交互，配置实时生效 |
| **可追溯** | 每个知识点追溯到原文，不凭空生成 |

---

## License

MIT © 2026

---

> **设计理念：好奇驱动、主动探索、深度理解、自主进化**