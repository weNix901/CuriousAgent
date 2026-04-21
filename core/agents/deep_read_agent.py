"""DeepReadAgent for deep paper reading and knowledge point decomposition."""
import json
import logging
import os
from typing import Any

from core.agents.ca_agent import CAAgent, CAAgentConfig, AgentResult
from core.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = """You are a DeepReadAgent that reads full paper text and extracts structured knowledge points.

Your workflow:
1. Read the full paper text using read_paper_text
2. Identify 5-15 independent knowledge points
3. For each knowledge point, extract 6 elements:
   - definition: what is this concept
   - core: core mechanism/algorithm
   - context: background (who/when/why)
   - examples: concrete examples
   - formula: key formulas (LaTeX)
   - relationships: relations to other concepts
4. Write each knowledge point to KG using add_to_kg
5. Establish DERIVED_FROM relations to parent summary
6. Mark task as done

CRITICAL: Respond in valid JSON format ONLY.
"""

DEFAULT_TOOLS = [
    "read_paper_text",
    "extract_formulas",
    "extract_knowledge_points",
    "download_paper",  # For PDF recovery
    "add_to_kg",
    "add_kg_relation",
    "query_kg",
    "query_kg_children",
    "claim_queue",
    "mark_done",
    "llm_call",
]


class DeepReadAgentConfig(CAAgentConfig):
    """Configuration for DeepReadAgent."""
    
    def __init__(
        self,
        name: str = "deep_read_agent",
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        tools: list[str] | None = None,
        max_iterations: int = 20,
        model: str = "volcengine",
    ):
        if tools is None:
            tools = DEFAULT_TOOLS
        super().__init__(
            name=name,
            system_prompt=system_prompt,
            tools=tools,
            max_iterations=max_iterations,
            model=model,
        )


class DeepReadAgent(CAAgent):
    """DeepReadAgent for deep paper reading.
    
    Responsibilities: Consume summary queue → Read TXT → Extract KP → Write to KG
    Trigger: Queue consumption (after ExploreAgent writes summary)
    """
    
    def __init__(self, config: DeepReadAgentConfig, tool_registry: ToolRegistry):
        super().__init__(config=config, tool_registry=tool_registry)
        self.name = config.name
        self.holder_id = json.dumps({})  # placeholder
    
    async def run(self) -> AgentResult:
        """Main loop: claim → process → mark_done."""
        item = await self._claim_deep_read_item()
        if not item:
            return AgentResult(
                content="No deep_read items in queue",
                success=False,
                iterations_used=0,
            )
        
        result = await self._process_paper(item)
        await self._mark_done(item)
        return result
    
    async def _claim_deep_read_item(self) -> dict | None:
        """Claim deep_read item from queue."""
        from core.tools.queue_tools import QueueStorage
        
        try:
            queue = QueueStorage()
            queue.initialize()
            
            items = queue.get_pending_items(limit=50)
            for item in items:
                meta = item.get("metadata", {})
                if meta.get("task_type") == "deep_read":
                    claimed = queue.claim_item(
                        item_id=item["id"],
                        holder_id=self.holder_id,
                        timeout_seconds=600
                    )
                    if claimed:
                        logger.info(f"Claimed deep_read item: {item['topic']}")
                        return item
        except Exception as e:
            logger.warning(f"Failed to claim deep_read item: {e}")
        return None
    
    async def _process_paper(self, item: dict) -> AgentResult:
        """Process a single paper: read TXT → extract KP → write to KG."""
        meta = item.get("metadata", {})
        topic = meta.get("summary_topic", item.get("topic", "unknown"))
        txt_path = meta.get("txt_path")
        pdf_path = meta.get("pdf_path")
        source_url = meta.get("source_url")
        
        # 0. PDF recovery check
        if not pdf_path or not os.path.exists(pdf_path):
            if not await self._recover_missing_pdf(topic, source_url, pdf_path):
                return AgentResult(
                    content=f"PDF missing and cannot recover: {topic}",
                    success=False,
                    iterations_used=0,
                )
        
        if not txt_path or not os.path.exists(txt_path):
            txt_path = await self._parse_pdf_to_txt(pdf_path, topic)
            if not txt_path:
                return AgentResult(
                    content=f"Failed to parse PDF to TXT: {topic}",
                    success=False,
                    iterations_used=0,
                )
        
        # 1. Read full text
        read_tool = self.tool_registry.get("read_paper_text")
        if not read_tool:
            return AgentResult(content="read_paper_text tool not available", success=False, iterations_used=0)
        
        full_text = await read_tool.execute(txt_path=txt_path)
        if full_text.startswith("Error"):
            return AgentResult(content=f"Failed to read paper: {full_text}", success=False, iterations_used=0)
        
        # 2. LLM overview → identify knowledge points
        kp_list = await self._identify_knowledge_points(full_text, topic)
        
        # 3. Write each knowledge point
        written = 0
        for kp in kp_list.get("knowledge_points", []):
            if kp.get("completeness_score", 0) < 2:
                continue  # Skip low-quality KPs
            
            await self._write_knowledge_point(kp, topic)
            written += 1
        
        # 4. Update summary node
        await self._update_summary_metadata(topic, child_count=written)
        
        logger.info(f"Deep read complete: {topic} → {written} knowledge points")
        return AgentResult(
            content=f"Extracted {written} knowledge points from {topic}",
            success=written > 0,
            iterations_used=1,
        )
    
    async def _recover_missing_pdf(self, topic: str, source_url: str | None, pdf_path: str | None) -> bool:
        """Recover missing PDF from source URL."""
        if not source_url:
            return False
        
        try:
            download_tool = self.tool_registry.get("download_paper")
            if not download_tool:
                return False
            
            from core.tools.paper_tools import paper_storage_paths, PAPERS_DIR
            os.makedirs(PAPERS_DIR, exist_ok=True)
            pdf_path_actual, _ = paper_storage_paths(topic)
            
            result = await download_tool.execute(url=source_url, output_path=pdf_path_actual)
            return "Error" not in result
        except Exception as e:
            logger.error(f"PDF recovery failed for {topic}: {e}")
            return False
    
    async def _parse_pdf_to_txt(self, pdf_path: str, topic: str) -> str | None:
        """Parse PDF to TXT."""
        parse_tool = self.tool_registry.get("parse_pdf")
        if parse_tool:
            result = await parse_tool.execute(pdf_path=pdf_path)
            if not result.startswith("Error"):
                from core.tools.paper_tools import paper_storage_paths
                _, txt_path = paper_storage_paths(topic)
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(result)
                return txt_path
        return None
    
    async def _identify_knowledge_points(self, full_text: str, topic: str) -> dict:
        """Use LLM to identify knowledge points in paper."""
        # Placeholder: returns empty list until extract_knowledge_points tool is implemented
        return {"knowledge_points": []}
    
    async def _write_knowledge_point(self, kp: dict, parent_topic: str):
        """Write a single knowledge point to KG."""
        add_tool = self.tool_registry.get("add_to_kg")
        if add_tool:
            await add_tool.execute(
                topic=kp.get("topic", "unknown"),
                definition=kp.get("definition"),
                core=kp.get("core"),
                context=kp.get("context"),
                examples=kp.get("examples"),
                formula=kp.get("formula"),
                parent_topic=parent_topic,
            )
    
    async def _update_summary_metadata(self, topic: str, child_count: int):
        """Update summary node with child count."""
        update_tool = self.tool_registry.get("update_kg_metadata")
        if update_tool:
            await update_tool.execute(topic=topic, depth=child_count)
    
    async def _mark_done(self, item: dict):
        """Mark queue item as done."""
        from core.tools.queue_tools import QueueStorage
        
        try:
            queue = QueueStorage()
            queue.initialize()
            queue.mark_done(item_id=item["id"])
        except Exception as e:
            logger.warning(f"Failed to mark done: {e}")