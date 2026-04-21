# Curious Agent Release Notes

---

## v0.3.2 (2026-04-21) — Bootstrap Hook System Refactor

### Overview

Unified injection architecture for knowledge-bootstrap hook. CA backend now assembles complete injection content (KG nodes + behavior guidelines) and returns it directly via API.

### Changes

#### New Features

- **`/api/knowledge/session/startup` endpoint**: Returns complete injection content for bootstrap hook
  - CA backend assembles KG nodes (filtered by `min_quality`, `max_nodes`)
  - Behavior guidelines from `config.json` templates
  - Returns `injection_content` string directly (no file paths)

#### Removed

- **`/api/kg/overview` endpoint**: No longer needed (was only used by bootstrap hook)

#### Refactored

- **`handler.ts` simplified**: Only calls API and injects returned `injection_content`
  - Removed all hardcoded templates
  - Removed KG filtering logic (now in Python backend)

- **Unified behavior guidelines storage**: 
  - Single source: `config.json` → `hooks.bootstrap.injection_sections`
  - Removed `DEFAULT_INJECTION` constant in audit middleware
  - UI edits now truly affect injection content

#### Documentation

- **README.md**: Added explicit Skills/Hooks table (**1 Skill + 4 Hooks**)
- **Removed obsolete `skills/curious-agent/SKILL.md`**: Content covered by `docs/curious-agent-installation-guide.md`

#### Tests

- Added `tests/api/test_session_startup.py` for new endpoint

### Migration Guide

If you have custom bootstrap hook templates in `config.json`, they will now be used by the backend. Previous hardcoded templates in `handler.ts` are removed.

### Skills/Hooks Summary

| Type | Name | Purpose |
|------|------|---------|
| **Skill** | knowledge-query | Agent queries KG confidence (主动调用) |
| **Internal Hook** | knowledge-bootstrap | Session startup injection |
| **Internal Hook** | knowledge-learn | Detect low confidence → inject to queue |
| **Plugin Hook** | knowledge-gate | Before reply KG check |
| **Plugin Hook** | knowledge-inject | After web_search → record to KG |

---

## v0.3.1-patch (2026-04-19) — Bug Fixes + Repo Cleanup

### Changes

- 搜索顺序: Serper (primary) → Bocha (fallback)
- KG 只存 `status=done` 的知识，Queue 存待探索 topics
- `add_child()` / `add_citation()` 不再创建 KG 占位节点
- Repo 清理: 移除 3400+ 运行时/敏感文件
- UI fixes: stat-log typo, 图谱控件事件绑定, 节点斥力范围 -600~+100

---

## v0.3.1 (2026-04-17) — Observability Layer

### Changes

- Hook audit middleware: All OpenClaw hook calls logged to SQLite
- Trace writers: Explorer/Dream Agent execution steps captured
- External Agent tracking: Agent registry, activity timeline, global event stream
- WebUI 4-tab dashboard: List, Graph, Internal, External views
- 30+ new API endpoints: `/api/audit/*`, `/api/explorer/*`, `/api/dream/*`, `/api/timeline`

---

## v0.3.0 (2026-04-15) — Cognitive Framework

### Changes

- 4-level confidence assessment (Expert → Intermediate → Beginner → Novice)
- Auto-inject unknown topics to CA queue for exploration
- `/api/knowledge/*` endpoints for KG confidence check, learning, analytics
- Legacy Spider code removed (spider_engine.py deleted)

---

## v0.2.9 (2026-04-13) — Agent Refactor

### Changes

- Unified CAAgent class for ExploreAgent and DreamAgent
- ReAct loop with 21 tools across 4 categories
- Hermes error handling from NousResearch
- Neo4j storage layer
- All configuration moved to `config.json`