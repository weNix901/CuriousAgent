# Design: v0.3.4 Deep Read Closure

## Technical Approach

### Phase 0: Implement ExtractKnowledgePointsTool

**File**: `core/tools/paper_tools.py` (lines 112-120)

Replace the `execute()` stub with a two-phase LLM extraction:

1. **Overview phase**: Call LLM with full paper text (truncated to 12K chars), ask it to identify 5-15 knowledge points with topic, source_section, relevance_score. Parse JSON from response with regex fallback.

2. **Extraction phase**: For each candidate (max 12), locate relevant paragraphs using keyword matching against topic name and section hint. Call LLM with section text to extract 6-element structure. Calculate completeness_score.

**JSON parsing**: Use `json.loads()` first, then regex fallback `r'\[\s*\{.*?\}\s*\]'` for array and `r'\{\s*".*?\}\s*'` for object. This handles LLM responses with surrounding text.

**Error handling**: Each LLM call wrapped in try/except with provider fallback. Failed candidates are silently skipped.

### Phase 1: Implement ExtractFormulasTool

**File**: `core/tools/paper_tools.py` (lines 140-149)

Replace the `execute()` stub with:

1. **Detection phase**: Slide over paragraphs, detect math-dense sections using Unicode math symbol count / total chars > 0.01 threshold.

2. **Extraction phase**: For each math-dense section, call LLM asking for LaTeX formula extraction. Return list with formula, context, source_location.

**Optimization**: Skip non-math sections entirely — no LLM calls needed for paragraphs without math symbols.

### Phase 2: Fix LLMKnowledgeExtractTool Prompt

**File**: `core/tools/llm_tools.py` `_call_extraction()` method

Replace prompt to require 6-element model with flat top-level fields:
- definition, core, context, examples, formula, relationships (as list)
- source object remains for traceability

### Phase 3: Fix DeepReadAgent Field Mapping

**File**: `core/agents/deep_read_agent.py`

- `_write_knowledge_point()` (lines **412-434**): Support both Format A (direct 6-element) and Format B (nested content). Map `core` from `content.get("core")` or `content.get("fact")` fallback.

- `_create_summary_node()` (lines **436-450**): Add source_origin object, pdf_path, txt_path, node_type, child_count, deep_read_status to metadata. Use `TrustedSourceManager.check_url()` for domain checking.

- `run()` (lines **82-94**): Add tool check BEFORE claim. Current flow claims items first, then discovers tools are unavailable at `_process_paper()` line 159. Fix: check `read_paper_text` tool availability before claiming. After fix, `_process_paper()` line 159 check becomes redundant — remove it.

- **DEFAULT_TOOLS bug** (line **38**): Lists `"add_kg_relation"` but actual tool name is `"update_kg_relation"` (see `core/tools/kg_tools.py:356`). Fix this as part of Phase 3.

### Phase 4: WebUI Trusted Source Tab

**Files**: `ui/views/trusted-sources.html`, `ui/js/trusted-sources.js`

Reuse existing `base.js` pattern. Fetch from `/api/trusted-sources` GET/POST/DELETE endpoints (already implemented).

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| LLM extraction quality varies | volcengine→minimax dual provider fallback |
| Long papers exceed context | Section-based processing with 12K char limit |
| WebUI style conflicts | Reuse existing CSS from settings-view |
| KG schema mismatch | Verify add_to_kg already supports new metadata fields (it does — confirmed at line 231 of kg_tools.py) |
