# CA Architecture Specification

## Purpose
Describes the overall Curious Agent system architecture — the three-agent model, data flow, and core infrastructure.

## Requirements

### Requirement: Three-Agent Architecture
The system SHALL consist of three independent agents with distinct responsibilities:
- **ExploreAgent**: Active exploration — search → download → summarize → write to KG
- **DreamAgent**: Offline insight — dormant/quality/surprise/cross-domain detection, generates new topics
- **DeepReadAgent**: Deep reading — consumes summary queue → reads TXT → extracts knowledge points → writes to KG

#### Scenario: Normal exploration flow
- GIVEN a topic in the queue
- WHEN ExploreAgent claims it
- THEN it searches, downloads paper, parses to TXT, writes summary to KG, and marks done

#### Scenario: Deep read trigger
- GIVEN ExploreAgent completes a summary
- WHEN it enqueues a deep_read task
- THEN DeepReadAgent claims and processes the paper

#### Scenario: Dream insight
- GIVEN DreamAgent heartbeat
- WHEN it analyzes KG state
- THEN it identifies new topics and enqueues them

### Requirement: Agent Independence
Each agent SHALL be independently deployable and configurable with separate model, concurrency, and timeout settings.

#### Scenario: Agent failure isolation
- GIVEN DeepReadAgent crashes
- WHEN ExploreAgent and DreamAgent are running
- THEN they continue operating normally

### Requirement: Event Bus Communication
The system SHALL use a persistent event bus (`event_bus_persistent.py`) for inter-agent communication.

### Requirement: Configuration System
The system SHALL load configuration from `config/config.json` with support for:
- LLM provider settings (volcengine, minimax)
- Deep read settings
- Archive settings
- Temperature system settings
- Trusted sources settings

### Requirement: WebUI
The system SHALL provide a web interface with:
- Knowledge graph visualization (D3.js force-directed layout)
- Knowledge list view
- Settings page
- External view and internal view modes

### Requirement: LLM Provider Fallback
The system SHALL support multiple LLM providers with automatic fallback from volcengine to minimax.

### Requirement: Search Provider Registry
The system SHALL support multiple search providers (Bocha, Serper, Tavily) with a provider registry and heatmap tracking.

### Requirement: Paper Storage
The system SHALL store downloaded papers in the `papers/` directory with stable hash-based filenames for both PDF and TXT.
