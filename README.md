# Curious Agent

[![Version](https://img.shields.io/badge/version-v0.3.3-blue)](https://github.com/weNix901/CuriousAgent)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](#)
[![Neo4j](https://img.shields.io/badge/neo4j-5.x-green)](#)
[![License](https://img.shields.io/badge/license-MIT-blue)](#)

> **别人只帮你收集论文，CA帮你消化论文——读完变本事**

别的系统像只存外卖菜单（标题+摘要），CA帮你把菜做出来吃下去——**全文读完、拆开揉碎、变成营养**。PDF、网页、GitHub都能消化。

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
PDF / 网页 / GitHub / 官方文档
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

## v0.3.3 核心能力

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

### 🌐 多源都能读——不只PDF

| 能读什么 | 支持状态 |
|----------|---------|
| **论文PDF** | ✅ 上传就读 |
| **arXiv网页** | ✅ 直接抓HTML |
| **GitHub README** | ✅ 代码文档也能提取 |
| **Python/PyTorch官方文档** | ✅ 教程、API文档都行 |
| **ACL论文库** | ✅ NLP论文一键入队 |

```bash
# 随便丢个链接，CA就去读
curl -X POST http://localhost:4848/api/web-scrape/enqueue \
  -d '{"url": "https://arxiv.org/html/2506.18496", "topic": "LTKD"}'
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
| **全文不放过** | 滑动窗口从头读到尾，每一页都过一遍 |
| **把书读薄** | 几百页论文变成几个清楚的知识点 |
| **知道不知道什么** | 懂的就说懂，不懂就承认，还帮你补上 |
| **主动联想** | 读完了还会想：这个跟谁有关系？继续挖 |
| **多源都能读** | PDF、网页、GitHub、文档——有内容就能读 |
| **知识变本事** | 读到的好方法变成你的做事套路 |
| **不用管它** | 自动运行，没事就自己读，越读越懂 |

---

## License

MIT © 2026

---

> **设计理念：主动学习、把书读薄、发现短板、知识变本事**