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
                if isinstance(meta, str):
                    meta = json.loads(meta)
                if meta.get("task_type") == "deep_read":
                    claimed = queue.claim_item(
                        item_id=item["id"],
                        holder_id=self.holder_id,
                        timeout_seconds=600
                    )
                    if claimed:
                        logger.info(f"Claimed deep_read item: {item['topic']}")
                        item["metadata"] = meta
                        return item
        except Exception as e:
            logger.warning(f"Failed to claim deep_read item: {e}")
        return None
    
    async def _process_paper(self, item: dict) -> AgentResult:
        """Process a single paper: read TXT → extract KP → write to KG.
        
        Supports both PDF papers and web-scraped content (TXT only).
        """
        meta = item.get("metadata", {})
        if isinstance(meta, str):
            meta = json.loads(meta)
        topic = meta.get("summary_topic", item.get("topic", "unknown"))
        txt_path = meta.get("txt_path")
        pdf_path = meta.get("pdf_path")
        source_url = meta.get("source_url")
        source_type = meta.get("source_type", "pdf")
        
        if txt_path and os.path.exists(txt_path):
            logger.info(f"TXT available for {topic}, skipping PDF check (source_type={source_type}")
        elif pdf_path and os.path.exists(pdf_path):
            txt_path = await self._parse_pdf_to_txt(pdf_path, topic)
            if not txt_path:
                return AgentResult(
                    content=f"Failed to parse PDF to TXT: {topic}",
                    success=False,
                    iterations_used=0,
                )
        elif source_url:
            if await self._recover_missing_pdf(topic, source_url, pdf_path):
                txt_path = await self._parse_pdf_to_txt(pdf_path, topic)
        
        if not txt_path or not os.path.exists(txt_path):
            return AgentResult(
                content=f"No TXT available for {topic} (pdf_path={pdf_path}, source_url={source_url})",
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
    
    def _get_overview_sections(self, full_text: str) -> list:
        """Get full coverage sections using sliding window.
        
        Uses overlapping windows to ensure 100% coverage:
        - Window size: 8000 chars
        - Step size: 5000 chars (overlap: 3000 chars)
        - Covers entire paper without gaps
        """
        length = len(full_text)
        
        if length <= 8000:
            return [full_text]
        
        sections = []
        window_size = 8000
        step_size = 5000
        
        pos = 0
        while pos < length:
            end = min(pos + window_size, length)
            sections.append(full_text[pos:end])
            pos += step_size
            
            if end == length:
                break
        
        return sections
    
    async def _identify_knowledge_points(self, full_text: str, topic: str) -> dict:
        """Use LLM to identify knowledge points in paper.
        
        Two-phase approach:
        1. LLM overview on multiple segments → identify candidate knowledge points
        2. For each candidate, extract 6-element structure from relevant sections
        """
        sections = self._get_overview_sections(full_text)
        
        llm_tool = self.tool_registry.get("llm_call")
        if not llm_tool:
            logger.warning("llm_call tool not available, skipping KP extraction")
            return {"knowledge_points": []}
        
        json_example = '''[
  {"topic": "concept name", "relevance_score": 8, "section_hint": "keywords"}
]'''
        
        all_candidates = []
        for i, section_text in enumerate(sections):
            section_prompt = """You are analyzing an academic paper: """ + topic + """

Paper content (section """ + str(i + 1) + """):
""" + section_text + """

Identify 3-8 independent knowledge points/concepts from this section.
Return JSON array format:
""" + json_example + """

Only return the JSON array."""

            try:
                section_result = await llm_tool.execute(prompt=section_prompt, task_type="analysis")
                candidates = self._parse_json_from_response(section_result)
                if candidates:
                    all_candidates.extend(candidates)
            except Exception as e:
                logger.warning(f"Section {i + 1} extraction failed: {e}")
        
        if not all_candidates:
            logger.warning("No KP candidates identified for " + topic)
            return {"knowledge_points": []}
        
        deduped_candidates = self._deduplicate_candidates(all_candidates)
        
        knowledge_points = []
        for candidate in deduped_candidates[:10]:
            kp_topic = candidate.get("topic", "")
            section_hint = candidate.get("section_hint", "")
            
            relevant_text = self._locate_relevant_section(full_text, kp_topic, section_hint)
            
            kp = await self._extract_knowledge_point_structure(kp_topic, relevant_text, topic)
            
            if kp and kp.get("completeness_score", 0) >= 2:
                knowledge_points.append(kp)
        
        logger.info("Identified " + str(len(knowledge_points)) + " knowledge points for " + topic + " (from " + str(len(sections)) + " sections)")
        return {"knowledge_points": knowledge_points}
    
    def _deduplicate_candidates(self, candidates: list) -> list:
        seen = {}
        result = []
        
        for c in candidates:
            topic = c.get("topic", "").lower().strip()
            if not topic:
                continue
            
            if topic not in seen:
                seen[topic] = c
                result.append(c)
            else:
                existing_score = seen[topic].get("relevance_score", 0)
                new_score = c.get("relevance_score", 0)
                if new_score > existing_score:
                    idx = result.index(seen[topic])
                    result[idx] = c
                    seen[topic] = c
        
        return sorted(result, key=lambda x: x.get("relevance_score", 0), reverse=True)
    
    def _parse_json_from_response(self, response: str) -> list:
        """Parse JSON array from LLM response."""
        import json
        import re
        
        # Try direct parse
        try:
            return json.loads(response)
        except:
            pass
        
        # Try extracting from markdown code block
        json_match = re.search(r'```(?:json)?\s*([\[\{].*?[\]\}])\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except:
                pass
        
        # Try finding array in response
        array_match = re.search(r'\[\s*\{.*?\}\s*\]', response, re.DOTALL)
        if array_match:
            try:
                return json.loads(array_match.group(0))
            except:
                pass
        
        return []
    
    def _locate_relevant_section(self, full_text: str, kp_topic: str, section_hint: str) -> str:
        """Locate relevant paragraphs for a knowledge point."""
        paragraphs = full_text.split("\n\n")
        relevant = []
        
        keywords = [kw.lower() for kw in (kp_topic + " " + section_hint).split() if len(kw) > 3]
        
        for para in paragraphs:
            para_lower = para.lower()
            if any(kw in para_lower for kw in keywords):
                relevant.append(para)
        
        # Return top 5 most relevant paragraphs (max 2000 chars)
        result = "\n\n".join(relevant[:5])
        if len(result) > 2000:
            result = result[:2000]
        
        return result if result else full_text[:2000]
    
    async def _extract_knowledge_point_structure(self, kp_topic: str, relevant_text: str, parent_topic: str) -> dict | None:
        """Extract 6-element structure for a knowledge point."""
        llm_tool = self.tool_registry.get("llm_call")
        if not llm_tool:
            return None
        
        json_template = '''{
  "topic": "''' + kp_topic + '''",
  "definition": "what is this concept (1-2 sentences)",
  "core": "core mechanism/algorithm (key points)",
  "context": "background - who/when/why introduced",
  "examples": "concrete examples or applications",
  "formula": "key formulas in LaTeX if any, or N/A",
  "relationships": ["related concepts"],
  "completeness_score": 3
}'''
        
        extract_prompt = f"""Extract structured knowledge about "{kp_topic}" from this text:

{relevant_text}

Return JSON with this structure:
{json_template}

Only return the JSON object, no markdown code blocks."""

        try:
            result = await llm_tool.execute(prompt=extract_prompt, task_type="extraction")
            kp = self._parse_json_from_response(result)
            
            if isinstance(kp, dict):
                kp["topic"] = kp_topic
                return kp
            elif isinstance(kp, list) and len(kp) > 0:
                kp[0]["topic"] = kp_topic
                return kp[0]
            
        except Exception as e:
            logger.warning(f"Failed to extract KP structure for {kp_topic}: {e}")
        
        return None
    
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
        """Update summary node metadata after deep read."""
        update_tool = self.tool_registry.get("update_kg_metadata")
        if update_tool:
            await update_tool.execute(topic=topic, confidence=min(1.0, child_count / 10))
    
    async def _mark_done(self, item: dict):
        """Mark queue item as done."""
        from core.tools.queue_tools import QueueStorage
        
        try:
            queue = QueueStorage()
            queue.initialize()
            queue.mark_done(item_id=item["id"])
        except Exception as e:
            logger.warning(f"Failed to mark done: {e}")