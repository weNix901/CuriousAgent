# Tools Specification

## Purpose
Describes the tool system architecture and individual tool capabilities.

## Requirements

### Requirement: Tool Architecture
The system SHALL use a `Tool` base class with `name`, `description`, `parameters`, and `execute()` method. Tools are registered via `ToolRegistry`.

### Requirement: Paper Tools
The `paper_tools.py` module SHALL provide:
- **`save_paper_text`**: Save parsed paper text to file, return paths
- **`read_paper_text`**: Read full text from TXT file
- **`extract_knowledge_points`**: Extract 6-element structured knowledge points from paper text
- **`extract_formulas`**: Extract mathematical formulas as LaTeX from text sections

#### Scenario: Knowledge point extraction
- GIVEN a paper's full text and topic
- WHEN extract_knowledge_points is called
- THEN it returns a list of knowledge points with 6-element fields and completeness_score ≥ 2

#### Scenario: Formula extraction
- GIVEN a TXT file with mathematical content
- WHEN extract_formulas is called
- THEN it returns formulas in LaTeX format with source context

### Requirement: KG Tools
The `kg_tools.py` module SHALL provide:
- **`add_to_kg`**: Add knowledge node with 6-element fields, calculates completeness_score, creates DERIVED_FROM relation if parent_topic provided
- **`update_kg_status`**: Update node status (pending/done/dormant)
- **`update_kg_metadata`**: Update node metadata fields

### Requirement: LLM Tools
The `llm_tools.py` module SHALL provide:
- **`llm_call`**: General LLM call with volcengine→minimax fallback
- **`llm_extract_knowledge`**: Extract structured knowledge with 6-element model, multi-provider fallback

### Requirement: Search Tools
The `search_tools.py` module SHALL provide:
- **`search_web`**: Multi-provider web search
- **`download_paper`**: Download PDF from URL
- **`parse_pdf`**: Parse PDF to plain text
- **`process_paper`**: Full pipeline: download + parse + save

### Requirement: Queue Tools
The `queue_tools.py` module SHALL provide:
- **`claim_queue`**: Atomically claim queue item
- **`mark_done`**: Mark queue item as completed
- Queue items support `metadata` field with `task_type` for routing

### Requirement: Web Scrape Tools
The `web_scrape_tools.py` module SHALL provide:
- **`scrape_web_for_deepread`**: Scrape web content and enqueue for deep read
- **`batch_web_scrape`**: Batch scrape multiple URLs
- Respects `web_scrape_config` and trusted source allowlist
