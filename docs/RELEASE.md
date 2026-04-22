# Curious Agent Release Notes

---

## v0.3.3 (2026-04-22) — DeepRead + Web Scrape Pipeline

### Theme

**把论文变成知识图谱——100%覆盖、6维结构、多源输入**

### Overview

v0.3.3 引入 **DeepReadAgent**，实现论文全文深度阅读和结构化知识点提取。不再是简单的摘要存储，而是将每个概念拆解为 6-element 结构化信息。同时支持网页抓取管道，可直接处理 arXiv HTML、GitHub README、官方文档。

### Core Features

#### 1. DeepReadAgent — 论文深读引擎

**滑动窗口全覆盖**：
- 窗口大小: 8000 字符
- 步进大小: 5000 字符 (重叠 3000 字符)
- 覆盖率: 157% (无遗漏)

```
论文 ≤30K chars → 1 段
论文 30-80K chars → 9 段
论文 >80K chars → 20 段
```

**LLM 分段识别**：
- 每段独立调用 LLM 提取候选知识点
- 去重合并（按 topic + relevance_score）
- 全文定位相关段落进行 6-element 提取

#### 2. 6-Element 知识点结构

每个知识点包含完整结构化信息：

| Element | Content | Example |
|---------|---------|---------|
| **definition** | 定义 (1-2句) | LTKD is a framework that... |
| **core** | 核心机制 | Decomposes KL into cross-group + within-group |
| **context** | 背景 | Introduced by Seonghak Kim, ADD Korea |
| **examples** | 应用示例 | CIFAR-100-LT, TinyImageNet-LT |
| **formula** | 关键公式 | KL(p_T || p_S) |
| **relationships** | 关联概念 | parent=Knowledge Distillation |

KG Node 新增字段：`definition`, `core`, `context`, `examples`, `formula`, `completeness_score`

#### 3. 网页抓取管道

**信任源支持**：
- arxiv.org (HTML 版本)
- github.com (README)
- openreview.net
- aclanthology.org
- 官方文档 (docs.python.org, pytorch.org, tensorflow.org, huggingface.co)

**API**：
- `POST /api/web-scrape/enqueue` — 单 URL 抓取入队
- `POST /api/web-scrape/batch` — 批量处理 KG 无知识点节点

**流程**：
```
URL → fetch_page() → clean_html() → save TXT → enqueue deep_read
```

#### 4. Settings Web UI

新增可视化配置页面：
- DeepRead 配置（段落重叠、上下文扩展、完整度阈值）
- 温度系统配置（衰减因子、热点/温区阈值）
- 归档策略配置（触发温度、TXT/PDF 处理）

所有配置实时生效，持久化到 `config.json`。

### Architecture Changes

#### New Components

```
core/agents/deep_read_agent.py    # DeepReadAgent 实现
core/tools/web_scrape_tools.py    # 网页抓取工具
core/daemon/deep_read_daemon.py   # DeepReadDaemon (30min poll)
config/trusted_sources.json       # 信任源配置 (18 sources)
```

#### Modified Files

```
core/kg/kg_repository.py          # 6-element 字段支持
core/kg/repository_factory.py     # 查询返回 6-element
core/knowledge_graph_compat.py    # add_knowledge_async metadata 支持
curious_agent.py                  # 注册 paper_tools + web_scrape_tools
curious_api.py                    # web-scrape API endpoints + Flask 命名修复
ui/views/settings-view.html       # Settings HTML (修复嵌套)
ui/js/settings-view.js            # Settings 逻辑
ui/css/base.css                   # .config-card, .config-row 样式
```

### Bug Fixes

- **Flask `get_config` 冲突**：路由函数遮蔽导入，重命名为 `get_ca_config`
- **ExploreDaemon 夺取 deep_read 任务**：添加 `exclude_task_type` 参数
- **KG 6-element 字段未存储**：修复 params 和 SET 语句遗漏
- **Settings CSS 缺失**：添加 `.config-card`, `.config-row` 样式
- **Settings HTML 双重嵌套**：移除 `<section id="settings-view">` 外层

### API Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/web-scrape/enqueue` | POST | 单 URL 抓取入队 |
| `/api/web-scrape/batch` | POST | 批量处理无知识点节点 |
| `/api/config` | GET/POST | 获取/更新配置 |
| `/api/config/reset` | POST | 重置默认配置 |
| `/api/trusted-sources` | GET | 信任源列表 |

### Test Results

**DeepReadAgent 全覆盖测试**：
- 51K 论文 → 9 段 → 9 知识点 ✅
- 每个知识点 completeness_score = 5 ✅
- 所有 6-element 字段正确存储 ✅

**网页抓取测试**：
- arXiv HTML → 51K chars → Queue pending ✅
- GitHub README → 抓取成功 ✅

### Skills/Hooks Summary

| Type | Name | Purpose |
|------|------|---------|
| **Skill** | knowledge-query | Agent 查询 KG 置信度 |
| **Internal Hook** | knowledge-bootstrap | Session 启动注入 |
| **Internal Hook** | knowledge-learn | 低置信度 → 队列注入 |
| **Plugin Hook** | knowledge-gate | 回复前 KG 检查 |
| **Plugin Hook** | knowledge-inject | web_search 后 KG 记录 |

---

## v0.3.2 (2026-04-21) — Bootstrap Hook System Refactor

### Overview

统一注入架构，CA 后端组装完整注入内容（KG nodes + 行为规范），直接返回。

### Changes

- `/api/knowledge/session/startup` endpoint
- 移除 `/api/kg/overview` endpoint
- handler.ts 简化：仅调用 API
- 行为规范统一存储于 config.json

---

## v0.3.1 (2026-04-17) — Observability Layer

### Changes

- Hook 审计中间件
- Trace writers
- 外部 Agent 跟踪
- WebUI 4-tab dashboard
- 30+ API endpoints

---

## v0.3.0 (2026-04-15) — Cognitive Framework

### Changes

- 4-level 置信度评估
- 自动注入未知话题
- `/api/knowledge/*` endpoints
- Legacy Spider code removed

---

## v0.2.9 (2026-04-13) — Agent Refactor

### Changes

- 统一 CAAgent 类
- ReAct loop + 21 tools
- Hermes error handling
- Neo4j storage
- config.json 中央配置