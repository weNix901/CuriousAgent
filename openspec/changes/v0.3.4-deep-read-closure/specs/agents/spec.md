# Delta for Agents

## MODIFIED Requirements

### Requirement: DeepReadAgent Processing — Tool Check Order
The `DeepReadAgent.run()` method SHALL check tool availability BEFORE claiming a queue item. The correct sequence:
1. Check read_paper_text tool availability
2. If tool missing → return "read_paper_text tool not available"
3. Claim deep_read item from queue
4. If no items → return "No deep_read items in queue"
5. If items exist → process paper

#### Scenario: No items in queue
- GIVEN an empty queue
- WHEN DeepReadAgent runs
- THEN it returns failure with "No deep_read items in queue"

#### Scenario: Tool missing
- GIVEN a queue with deep_read items but no read_paper_text tool
- WHEN DeepReadAgent runs
- THEN it returns failure with "read_paper_text tool not available"

### Requirement: DeepReadAgent Processing — Field Mapping
The `_write_knowledge_point()` method SHALL support both knowledge point formats:
- **Format A** (ExtractKnowledgePointsTool): `{topic, definition, core, context, examples, formula, relationships}`
- **Format B** (LLMKnowledgeExtractTool): `{topic, content: {definition, core, fact, formula, ...}, source: {...}}`

The method SHALL map `core` from `content.get("core")` or fallback to `content.get("fact")` for backward compatibility.

### Requirement: DeepReadAgent Processing — Summary Node Traceability
The `_create_summary_node()` method SHALL include source traceability fields:
- `source_origin`: Object with type, url, domain, is_trusted
- `pdf_path`: Local PDF path
- `txt_path`: Local TXT path
- `node_type`: "summary"
- `child_count`: Number of expected knowledge points
- `deep_read_status`: "pending"
