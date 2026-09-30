# Knowledge Graph Specification

## Purpose
Describes the knowledge graph schema, storage, and operations — the central data layer of Curious Agent.

## Requirements

### Requirement: Dual Backend Storage
The system SHALL use Neo4j as the primary graph store and SQLite (`knowledge_graph_compat.py` shim) as a local fallback.

### Requirement: Knowledge Node Types
The system SHALL support these node types:
- **summary**: Paper-level summary node
- **knowledge_point**: Structured sub-knowledge point extracted from a summary

#### Scenario: Summary node creation
- GIVEN ExploreAgent completes paper analysis
- WHEN it writes to KG
- THEN a summary node is created with topic, content, source_urls, pdf_path, txt_path

#### Scenario: Knowledge point node creation
- GIVEN DeepReadAgent extracts a knowledge point
- WHEN it writes to KG
- THEN a knowledge_point node is created with 6-element fields

### Requirement: 6-Element Knowledge Point Structure
Each knowledge_point node SHALL support these structured fields:
- **definition**: What is this concept
- **core**: Core mechanism/algorithm
- **context**: Background (who/when/why)
- **examples**: Concrete use cases
- **formula**: Key formula in LaTeX
- **relationships**: Relations to other concepts

### Requirement: Completeness Scoring
Each knowledge_point node SHALL have a `completeness_score` (0-5) calculated as the count of non-empty 6-element fields.

#### Scenario: Scoring
- GIVEN a knowledge point with definition, core, and examples filled
- WHEN completeness is calculated
- THEN score = 3

### Requirement: Relationship Types
The system SHALL support these relation types:
- **DERIVED_FROM**: Child knowledge point → parent summary
- **DEPENDS_ON**: Concept dependency
- **RELATED_TO**: Concept association
- **CITES**: Paper citation

### Requirement: Source Traceability
Every knowledge node SHALL store source traceability fields:
- `source_origin`: Root source (URL or derived)
- `source_is_trusted`: Whether source is from trusted domain
- `pdf_path`: Local PDF copy path
- `txt_path`: Parsed text path

#### Scenario: Traceability query
- GIVEN a knowledge point node
- WHEN queried for source origin
- THEN the original URL can be traced back

### Requirement: Knowledge Quality Assessment
The system SHALL compute quality scores via `quality_v2.py` for each node.

### Requirement: Knowledge Temperature System
The system SHALL track knowledge "heat" using `temperature_system.py` with exponential decay (0.95 per cycle) and retrieval hit bonuses (+20).

#### Scenario: Heat decay
- GIVEN a knowledge node with heat=100
- WHEN no retrieval for 24 cycles
- THEN heat approaches 30 (cold threshold)

### Requirement: Archive Strategy
The system SHALL archive cold knowledge (heat < 30) by removing TXT files and compressing PDFs, while preserving source origin fields permanently.
