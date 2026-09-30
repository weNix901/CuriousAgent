# Proposal: v0.3.4 Deep Read Closure

## Intent
Transform v0.3.3 from a Draft with hollow skeletons into a fully functional Release. The core problem: two critical tools (`ExtractKnowledgePointsTool`, `ExtractFormulasTool`) return `"status": "not_implemented"`, and the field mapping chain between extraction and KG writing is broken.

## Scope

### In Scope
1. **P0**: Implement `ExtractKnowledgePointsTool` — LLM-driven 6-element extraction
2. **P0**: Implement `ExtractFormulasTool` — regex + LLM formula extraction
3. **P1**: Fix `LLMKnowledgeExtractTool` prompt to align with 6-element spec
4. **P1**: Fix `DeepReadAgent._write_knowledge_point()` field mapping (B4 + B9)
5. **P1**: Fix `DeepReadAgent._create_summary_node()` to include source traceability fields
6. **P2**: Fix `DeepReadAgent.run()` tool check order (B5)
7. **P2**: Add WebUI trusted source management tab
8. **P3**: E2E test — run one paper through complete deep_read pipeline

### Out of Scope
- New agent types
- KG backend migration
- Search provider changes
- Temperature system improvements

## Approach
- Use existing `LLMClient` with volcengine→minimax fallback for all LLM calls
- Implement two-phase extraction: overview identify → 6-element extract per KP
- Add regex-based math-dense section detection to skip non-math paragraphs
- Fix field mapping to support both direct 6-element format and nested content format
- Add WebUI tab reusing existing base.js and styles

## Success Criteria
- All 23 tests pass
- One real paper produces ≥3 knowledge points with ≥2 elements each
- DERIVED_FROM relations correctly established
- Every knowledge point traces back to original URL
- WebUI trusted source tab functional
