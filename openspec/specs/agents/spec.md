# Agents Specification

## Purpose
Describes the behavior and capabilities of each agent type in Curious Agent.

## Requirements

### Requirement: ExploreAgent Capabilities
ExploreAgent SHALL implement a ReAct loop with these tools:
- `search_web`, `download_paper`, `parse_pdf`, `save_paper_text`, `process_paper`
- `llm_summarize` / `llm_extract_knowledge`
- `add_to_kg`, `query_kg`
- `claim_queue`, `mark_done`
- `extract_paper_citations`

#### Scenario: Paper exploration
- GIVEN a topic in the queue
- WHEN ExploreAgent processes it
- THEN it downloads PDF, parses to TXT, generates summary, writes summary node to KG, enqueues deep_read task, and marks done

### Requirement: DreamAgent Levels
DreamAgent SHALL operate in four levels:
- **L1**: Find dormant topics, low-quality nodes, high-citation nodes
- **L2**: Surprise detection, cross-domain connections
- **L3**: Quality assessment and improvement
- **L4**: Knowledge gap identification

#### Scenario: Dormant detection
- GIVEN nodes with status=dormant in KG state
- WHEN DreamAgent L1 runs
- THEN dormant nodes are surfaced for re-exploration

### Requirement: DeepReadAgent Processing
DeepReadAgent SHALL consume queue items with `task_type=deep_read` and:
1. Read full paper text
2. Identify 5-15 knowledge points via LLM
3. Extract 6-element structure for each
4. Write knowledge points to KG with DERIVED_FROM relations
5. Update summary node metadata
6. Mark queue item done

#### Scenario: No items available
- GIVEN no deep_read items in queue
- WHEN DeepReadAgent runs
- THEN it returns failure with "No deep_read items" message

#### Scenario: Tool unavailability
- GIVEN read_paper_text tool is not registered
- WHEN DeepReadAgent runs
- THEN it returns failure with "read_paper_text tool not available"

### Requirement: Curiosity Decomposition
The system SHALL support four-level cascading topic decomposition via `curiosity_decomposer.py`:
1. LLM reasoning → candidate sub-topics
2. Search validation → multi-provider existence check
3. KG supplementation → parent-child inference
4. Clarification → user input when needed
