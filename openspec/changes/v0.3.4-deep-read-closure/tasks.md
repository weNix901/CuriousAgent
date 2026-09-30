# Tasks

## Phase 0: Implement ExtractKnowledgePointsTool
- [ ] 0.1 Replace `ExtractKnowledgePointsTool.execute()` in `core/tools/paper_tools.py:112-120`
  - [ ] 0.1.1 LLM overview prompt (full text → candidate KPs)
  - [ ] 0.1.2 LLM 6-element extraction prompt (per KP)
  - [ ] 0.1.3 JSON parsing with regex fallback
  - [ ] 0.1.4 Section localization via keyword matching
  - [ ] 0.1.5 Completeness score calculation
- [ ] 0.2 Test: run against a real paper TXT, verify ≥3 KPs returned

## Phase 1: Implement ExtractFormulasTool
- [ ] 1.1 Replace `ExtractFormulasTool.execute()` in `core/tools/paper_tools.py:140-149`
  - [ ] 1.1.1 Math-dense section detection (Unicode symbol density)
  - [ ] 1.1.2 LLM formula extraction prompt
  - [ ] 1.1.3 Section-based extraction with context
- [ ] 1.2 Test: run against a formula-containing paper TXT, verify ≥1 formula returned

## Phase 2: Fix LLMKnowledgeExtractTool Prompt
- [ ] 2.1 Update `_call_extraction()` prompt in `core/tools/llm_tools.py`
  - [ ] 2.1.1 Change from Content/Source/Relations to flat 6-element model
  - [ ] 2.1.2 Replace `fact` with `core`
  - [ ] 2.1.3 Add `context` field requirement
  - [ ] 2.1.4 Add `relationships` as list of {type, topic}
- [ ] 2.2 Test: verify JSON output matches 6-element format

## Phase 3: Fix DeepReadAgent Field Mapping
- [ ] 3.1 Fix `_write_knowledge_point()` in `deep_read_agent.py:412-434`
  - [ ] 3.1.1 Support Format A (direct 6-element) and Format B (nested)
  - [ ] 3.1.2 Map `core` from `content.get("core")` or `content.get("fact")` fallback
  - [ ] 3.1.3 Add DERIVED_FROM relation via `update_kg_relation` tool
- [ ] 3.2 Fix `_create_summary_node()` in `deep_read_agent.py:436-450`
  - [ ] 3.2.1 Add source_origin object (type, url, domain, is_trusted)
  - [ ] 3.2.2 Add pdf_path, txt_path
  - [ ] 3.2.3 Add node_type, child_count, deep_read_status
  - [ ] 3.2.4 Use `TrustedSourceManager.check_url()` for domain checking
- [ ] 3.3 Fix `run()` tool check order in `deep_read_agent.py:82-94`
  - [ ] 3.3.1 Add tool check BEFORE claim in `run()`
  - [ ] 3.3.2 Remove `_process_paper()` line 159 check (redundant after fix)
- [ ] 3.4 Fix test `test_deep_read_agent_run_returns_no_items`
- [ ] 3.5 Fix DEFAULT_TOOLS bug in `deep_read_agent.py:38` — change `"add_kg_relation"` to `"update_kg_relation"`

## Phase 4: WebUI Trusted Source Tab
- [ ] 4.1 Create `ui/views/trusted-sources.html`
- [ ] 4.2 Create `ui/js/trusted-sources.js`
- [ ] 4.3 Add tab navigation entry in `ui/index.html`
- [ ] 4.4 Test: add, delete, toggle, import/export

## Phase 5: E2E Validation
- [ ] 5.1 Create `tests/e2e/test_deep_read_e2e.py`
- [ ] 5.2 Run full pipeline: topic → explore → deep_read → verify KPs
- [ ] 5.3 Verify all 23 tests pass
- [ ] 5.4 Verify DERIVED_FROM relations in KG
- [ ] 5.5 Verify source traceability for all nodes
