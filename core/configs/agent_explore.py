"""ExploreAgent configuration."""
from dataclasses import dataclass, field
from typing import List


EXPLORE_SYSTEM_PROMPT = """You are an exploration agent that discovers and synthesizes knowledge.

Your goal is to explore topics thoroughly using the ReAct (Reason + Act) pattern:
1. THINK: Analyze what you know and what you need to discover
2. ACT: Use available tools to gather information
3. OBSERVE: Process the results and update your understanding

Repeat until you have comprehensive knowledge about the topic.

Quality standards:
- Seek diverse sources (web, papers, knowledge graph)
- Validate findings across multiple sources
- Synthesize insights, not just collect facts
- Track confidence levels for each finding

When complete, write findings to the knowledge graph with appropriate metadata."""


EXPLORE_TOOLS = [
    "query_kg",
    "query_kg_by_status",
    "query_kg_by_heat",
    "get_node_relations",
    "add_to_kg",
    "update_kg_status",
    "update_kg_metadata",
    "update_kg_relation",
    "merge_kg_nodes",
    "add_to_queue",
    "claim_queue",
    "get_queue",
    "mark_done",
    "mark_failed",
    "search_web",
    "fetch_page",
    "download_paper",
    "parse_pdf",
    "process_paper",
    "llm_analyze",
    "llm_summarize",
]


@dataclass
class ExploreAgentConfig:
    """Configuration for ExploreAgent."""
    name: str = "ExploreAgent"
    system_prompt: str = EXPLORE_SYSTEM_PROMPT
    tools: List[str] = field(default_factory=lambda: EXPLORE_TOOLS[:14])
    max_iterations: int = 10
    model: str = "doubao-pro"