# Delta for Tools

## MODIFIED Requirements

### Requirement: Paper Tools — ExtractKnowledgePointsTool
The `ExtractKnowledgePointsTool` class SHALL implement LLM-driven two-phase extraction:
1. LLM overview on full paper text → identify 5-15 candidate knowledge points with topic, source_section, relevance_score
2. For each candidate, locate relevant paragraphs → extract 6-element structure (definition, core, context, examples, formula, relationships)
3. Calculate completeness_score (count of non-empty fields)
4. Return structured JSON with knowledge_points list

**Implementation**: Use `LLMClient` with volcengine→minimax fallback. Parse JSON from LLM response with regex fallback.

#### Scenario: Successful extraction
- GIVEN a paper text with multiple concepts
- WHEN extract_knowledge_points is called
- THEN it returns ≥3 knowledge points, each with ≥2 non-empty 6-element fields

#### Scenario: Empty result
- GIVEN a paper text with no clear concepts
- WHEN extract_knowledge_points is called
- THEN it returns empty list with status "no_candidates_found"

### Requirement: Paper Tools — ExtractFormulasTool
The `ExtractFormulasTool` class SHALL implement formula extraction:
1. Auto-detect math-dense paragraphs using Unicode math symbol density threshold (>1%)
2. For math-dense sections, call LLM to extract LaTeX formulas
3. Return formula list with formula, context, and source location

**Implementation**: Sliding window over paragraphs. Skip non-math sections to avoid unnecessary LLM calls.

#### Scenario: Formula extraction
- GIVEN a TXT file containing mathematical formulas
- WHEN extract_formulas is called
- THEN it returns ≥1 formulas in valid LaTeX format with source context

#### Scenario: No formulas
- GIVEN a TXT file with no mathematical content
- WHEN extract_formulas is called
- THEN it returns empty list

## MODIFIED Requirements

### Requirement: LLM Tools — LLMKnowledgeExtractTool
The `llm_extract_knowledge` prompt SHALL require the 6-element model:
1. **definition**: What is this concept
2. **core**: Core mechanism/algorithm/process (NOT "fact")
3. **context**: Background (who proposed it, when, why)
4. **examples**: Concrete use cases (list)
5. **formula**: Key formula in LaTeX
6. **relationships**: Relations to other concepts (list of {type, topic})

The JSON output format SHALL use flat top-level fields (definition, core, context, etc.) alongside the `source` object for traceability.
