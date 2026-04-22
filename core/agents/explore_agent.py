"""ExploreAgent with ReAct loop for knowledge exploration."""
import json
import logging
import time
import uuid
from typing import Any

from core.agents.ca_agent import CAAgent, CAAgentConfig, AgentResult
from core.tools.registry import ToolRegistry
from core.llm_client import LLMClient

logger = logging.getLogger(__name__)


DEFAULT_SYSTEM_PROMPT = """You are an ExploreAgent that autonomously explores knowledge topics.

Your workflow for each topic:
1. Search the web for the topic using search_web
2. For each promising URL, use fetch_page to get full content
3. Use llm_analyze to judge if content is useful for this topic
4. Collect useful source URLs for attribution
5. At the end, use llm_summarize to generate a knowledge summary
6. The system will automatically write to KG with your collected sources

Available tools:
- search_web(query): Search the web - returns title, snippet, URL
- fetch_page(url): Fetch full content from a URL - track this URL as a source!
- llm_analyze(content, topic): Analyze content quality and relevance
- llm_summarize(content, topic): Summarize collected content into knowledge
- query_kg(topic): Query existing knowledge

CRITICAL: You MUST respond in valid JSON format ONLY. No other format is accepted.

Your response MUST be a valid JSON object with these exact fields:
{
  "thought": "Your reasoning about what to do next",
  "action": "tool_name",
  "action_input": {"param": "value"}
}

Examples:
- To search: {"thought": "I need to find information", "action": "search_web", "action_input": {"query": "Python asyncio"}}
- To fetch: {"thought": "This URL looks relevant", "action": "fetch_page", "action_input": {"url": "https://example.com"}}
- To finish: {"thought": "I have enough information", "action": "done", "action_input": {}}

Important rules:
- ALWAYS fetch_page for URLs that look relevant before judging
- Track URLs from successful fetch_page calls (these become sources)
- Use llm_analyze to judge content usefulness
- If no useful content found, report what you tried with action "done"
- DO NOT hallucinate knowledge without sources

The system will write your summary to KG with collected sources when done.
"""

DEFAULT_TOOLS = [
    "search_web",
    "query_kg",
    "add_to_kg",
    "claim_queue",
    "mark_done",
    "get_queue",
    "llm_analyze",
    "llm_summarize",
    "fetch_page",
    "process_paper",
    "extract_paper_citations",
    "extract_web_citations",
    "update_kg_status",
    "update_kg_metadata",
    "get_node_relations",
    "add_to_queue",
]


class ExploreAgentConfig(CAAgentConfig):
    """Configuration for ExploreAgent."""

    def __init__(
        self,
        name: str = "explore_agent",
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        tools: list[str] | None = None,
        max_iterations: int = 10,
        model: str = "doubao-pro",
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


class ExploreAgent(CAAgent):
    """ExploreAgent with ReAct loop for autonomous knowledge exploration."""

    def __init__(self, config: ExploreAgentConfig, tool_registry: ToolRegistry):
        super().__init__(config=config, tool_registry=tool_registry)
        self.name = config.name
        self.holder_id = str(uuid.uuid4())

    async def run(self, input_data: str, pre_claimed_item_id: int = None) -> AgentResult:
        """Run the ExploreAgent workflow: claim -> explore -> mark done.
        
        Args:
            input_data: topic string to explore
            pre_claimed_item_id: if provided, skip internal claim (daemon already claimed it)
        """
        topic = input_data.strip()

        if pre_claimed_item_id is not None:
            # Daemon already claimed - skip internal claim
            item_id = pre_claimed_item_id
            explored_topic = topic
        else:
            # Standalone mode - claim ourselves
            claim_result = await self._claim_topic(topic)
            if not claim_result.get("success"):
                return AgentResult(
                    content=f"Failed to claim topic: {claim_result.get('error', 'Unknown error')}",
                    success=False,
                    iterations_used=0,
                )
            item_id = claim_result["item_id"]
            explored_topic = claim_result["topic"]

        react_result = await self._react_loop(explored_topic)

        # Only mark_done if we claimed ourselves; daemon handles it for pre_claimed items
        if pre_claimed_item_id is None:
            marked_done = await self._mark_done(item_id)
            if not marked_done:
                return AgentResult(
                    content=f"Exploration complete but failed to mark done: {explored_topic}",
                    success=False,
                    iterations_used=react_result.get("iterations", 0),
                )

        return AgentResult(
            content=react_result.get("content", f"Explored topic: {explored_topic}"),
            success=react_result.get("success", True),
            iterations_used=react_result.get("iterations", 0),
        )

    async def _claim_topic(self, topic: str) -> dict[str, Any]:
        """Claim a topic from the curiosity queue."""
        try:
            queue_tool = self.tool_registry.get("get_queue")
            if not queue_tool:
                return {"success": False, "error": "Queue tool not available"}

            queue_result = await queue_tool.execute()

            item_id = None
            for line in queue_result.split("\n"):
                if topic.lower() in line.lower() and "ID" in line:
                    parts = line.split("ID")
                    if len(parts) > 1:
                        id_part = parts[1].strip().split(":")[0].split()[0]
                        try:
                            item_id = int(id_part)
                            break
                        except ValueError:
                            continue

            if item_id is None:
                add_tool = self.tool_registry.get("add_to_queue")
                if add_tool:
                    add_result = await add_tool.execute(topic=topic, priority=5)
                    for line in add_result.split("\n"):
                        if "ID" in line:
                            try:
                                item_id = int(line.split("ID")[1].strip().split()[0])
                                break
                            except (ValueError, IndexError):
                                continue

            if item_id is None:
                return {"success": False, "error": "Could not get item_id"}

            claim_tool = self.tool_registry.get("claim_queue")
            if not claim_tool:
                return {"success": False, "error": "Claim tool not available"}

            claim_result = await claim_tool.execute(
                item_id=item_id, holder_id=self.holder_id, timeout_seconds=300
            )

            if "Successfully claimed" in claim_result:
                return {"success": True, "item_id": item_id, "topic": topic}
            else:
                return {"success": False, "error": claim_result}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _react_loop(self, topic: str) -> dict[str, Any]:
        """Execute ReAct loop: Thought -> Action -> Observation."""
        from core.trace.explorer_trace import TraceWriter
        
        trace_writer = TraceWriter()
        trace_id = trace_writer.start_trace(topic)
        loop_start = time.time()
        tools_used_set = set()
        
        # Track collected sources and useful content for proper KG write
        collected_sources: list[str] = []
        useful_content_parts: list[str] = []
        
        client = LLMClient(provider_name=self.config.model)
        system_prompt = self._build_system_prompt()

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Explore this topic: {topic}\n\nStart by thinking about what you need to do.",
            },
        ]

        iterations = 0
        observations = []
        content_parts = []

        while iterations < self.config.max_iterations:
            iterations += 1

            prompt = "\n".join(
                [f"{m['role']}: {m['content']}" for m in messages]
                + [f"\nObservations so far:\n{chr(10).join(observations)}" if observations else ""]
            )

            response = client.chat(prompt)

            try:
                start = response.find("{")
                end = response.rfind("}")
                if start >= 0 and end > start:
                    parsed = json.loads(response[start : end + 1])
                else:
                    parsed = self._parse_react_response(response)
            except json.JSONDecodeError:
                parsed = self._parse_react_response(response)

            thought = parsed.get("thought", "")
            action = parsed.get("action", "")
            action_input = parsed.get("action_input", {}) or {}
            
            if isinstance(action_input, str):
                param_mapping = {
                    "search_web": "query",
                    "fetch_page": "url",
                    "llm_analyze": "content",
                    "llm_summarize": "content",
                    "query_kg": "topic",
                    "add_to_kg": "topic",
                    "mark_done": "topic",
                    "claim_queue": "topic",
                }
                tool_name = action.split("(")[0] if "(" in action else action
                param_name = param_mapping.get(tool_name, "query")
                action_input = {param_name: action_input}
            
            if action and "(" in action and isinstance(action_input, dict) and not action_input:
                inline_args = self._extract_inline_args(action)
                if inline_args:
                    action_input = inline_args

            if thought:
                content_parts.append(f"Thought: {thought}")

            if not action or action.lower() == "done":
                total_duration = int((time.time() - loop_start) * 1000)
                trace_writer.finish_trace(
                    trace_id=trace_id,
                    status="done",
                    total_steps=iterations,
                    tools_used=list(tools_used_set),
                    duration_ms=total_duration,
                )
                
                final_summary = ""
                if useful_content_parts:
                    summarize_tool = self.tool_registry.get("llm_summarize")
                    if summarize_tool:
                        content_to_summarize = "\n".join(useful_content_parts[-5:])
                        summary_result = await summarize_tool.execute(
                            content=content_to_summarize,
                            topic=topic
                        )
                        final_summary = summary_result if isinstance(summary_result, str) else str(summary_result)
                    else:
                        final_summary = f"Explored {topic} with {len(collected_sources)} sources"
                elif content_parts:
                    final_summary = "\n".join(content_parts[-3:])
                else:
                    final_summary = f"Exploration of '{topic}' complete with {len(collected_sources)} sources"
                
                add_tool = self.tool_registry.get("add_to_kg")
                process_tool = self.tool_registry.get("process_paper")
                if add_tool and final_summary:
                    pdf_path = None
                    txt_path = None
                    source_url = collected_sources[0] if collected_sources else None
                    
                    await add_tool.execute(
                        topic=topic,
                        content=final_summary[:2000],
                        source_urls=collected_sources,
                        metadata={"depth": iterations, "quality": 5.0 + len(collected_sources)}
                    )
                    
                    await self._enqueue_deep_read(
                        topic=topic,
                        pdf_path=pdf_path,
                        txt_path=txt_path,
                        source_url=source_url
                    )
                
                quality = 5.0 + len(collected_sources)
                self._push_webhook(topic, quality=quality, source_type="explore")
                
                return {
                    "success": True,
                    "content": final_summary,
                    "iterations": iterations,
                    "trace_id": trace_id,
                }

            step_start = time.time()
            step_id = trace_writer.record_step(
                trace_id=trace_id,
                step_num=iterations,
                action=action,
                action_input=json.dumps(action_input, ensure_ascii=False)[:500] if action_input else "",
                llm_call=(action in ["llm_analyze", "llm_summarize"]),
            )

            observation = await self._execute_action(action, action_input)
            tools_used_set.add(action)
            
            if action == "fetch_page" and isinstance(action_input, dict):
                url = action_input.get("url")
                if url and "ERROR" not in observation and "failed" not in observation.lower() and "Warning" not in observation:
                    collected_sources.append(url)
                    if len(observation) > 100:
                        useful_content_parts.append(observation[:500])
            
            if action == "llm_analyze" and observation:
                if "useful" in observation.lower() or "relevant" in observation.lower() or "yes" in observation.lower():
                    useful_content_parts.append(observation)
            
            step_duration = int((time.time() - step_start) * 1000)
            trace_writer.update_step(
                step_id=step_id,
                output_summary=observation[:300],
                output_size=len(observation),
                duration_ms=step_duration,
            )

            observations.append(f"Iteration {iterations}: {action}({action_input}) -> {observation[:200]}")
            content_parts.append(f"Action: {action}({action_input})\nObservation: {observation[:200]}")

            messages.append(
                {
                    "role": "assistant",
                    "content": f"Thought: {thought}\nAction: {action}\nAction Input: {action_input}",
                }
            )
            messages.append({"role": "user", "content": f"Observation: {observation}"})

        total_duration = int((time.time() - loop_start) * 1000)
        trace_writer.finish_trace(
            trace_id=trace_id,
            status="done",
            total_steps=iterations,
            tools_used=list(tools_used_set),
            duration_ms=total_duration,
        )

        final_summary = ""
        if useful_content_parts:
            summarize_tool = self.tool_registry.get("llm_summarize")
            if summarize_tool:
                content_to_summarize = "\n".join(useful_content_parts[-5:])
                summary_result = await summarize_tool.execute(
                    content=content_to_summarize,
                    topic=topic
                )
                final_summary = summary_result if isinstance(summary_result, str) else str(summary_result)
            else:
                final_summary = f"Explored {topic} with {len(collected_sources)} sources"
        elif content_parts:
            final_summary = "\n".join(content_parts[-3:])
        else:
            final_summary = f"Exploration of '{topic}' reached max iterations with {len(collected_sources)} sources"
        
        add_tool = self.tool_registry.get("add_to_kg")
        process_tool = self.tool_registry.get("process_paper")
        if add_tool and final_summary:
            pdf_path = None
            txt_path = None
            source_url = collected_sources[0] if collected_sources else None
            
            await add_tool.execute(
                topic=topic,
                content=final_summary[:2000],
                source_urls=collected_sources,
                metadata={"depth": iterations, "quality": 5.0 + len(collected_sources)}
            )
            
            await self._enqueue_deep_read(
                topic=topic,
                pdf_path=pdf_path,
                txt_path=txt_path,
                source_url=source_url
            )
        
        quality = 5.0 + len(collected_sources)
        self._push_webhook(topic, quality=quality, source_type="explore")
        
        return {
            "success": True,
            "content": final_summary + f"\n\nReached max iterations ({self.config.max_iterations})",
            "iterations": iterations,
            "trace_id": trace_id,
        }

    def _parse_react_response(self, response: str) -> dict[str, Any]:
        """Parse ReAct response from non-JSON format."""
        import re
        result = {"thought": "", "action": "", "action_input": {}}

        # First check for special function call format: <|FunctionCallBegin|>[{...}]<|FunctionCallEnd|>
        func_match = re.search(r'<\|FunctionCallBegin\|>\s*\[(.*?)\]\s*<\|FunctionCallEnd\|>', response, re.DOTALL)
        if func_match:
            try:
                func_json = json.loads(func_match.group(1))
                if isinstance(func_json, list) and len(func_json) > 0:
                    func_json = func_json[0]
                result["action"] = func_json.get("name", "")
                result["action_input"] = func_json.get("parameters", {})
                return result
            except json.JSONDecodeError:
                pass

        # Check for XML-style tags: <tool_name param="value">
        xml_match = re.search(r'<(\w+)\s+([^>]+)>', response)
        if xml_match:
            tool_name = xml_match.group(1)
            args_str = xml_match.group(2)
            result["action"] = tool_name
            kv_pairs = re.findall(r'(\w+)="([^"]*)"|(\w+)=([\w\-./:]+)', args_str)
            parsed = {}
            for match in kv_pairs:
                if match[0]:  # key="value" format
                    parsed[match[0]] = match[1]
                elif match[2]:  # key=value format
                    parsed[match[2]] = match[3]
            result["action_input"] = parsed
            return result

        lines = response.split("\n")
        for line in lines:
            line = line.strip()
            if line.lower().startswith("thought:"):
                result["thought"] = line.split(":", 1)[1].strip()
            elif line.lower().startswith("action:"):
                action_str = line.split(":", 1)[1].strip()
                result["action"] = action_str
                # Extract args from inline format like "search_web(query=\"...\")"
                if not result["action_input"]:
                    args_match = re.search(r'\(.*\)$', action_str)
                    if args_match:
                        args_str = args_match.group(0)[1:-1]  # remove parentheses
                        # Try to parse as key=value pairs
                        kv_pairs = re.findall(r'(\w+)=(\"[^\"]*\"|[\w\-./:]+)', args_str)
                        if kv_pairs:
                            parsed = {}
                            for k, v in kv_pairs:
                                if v.startswith('"') and v.endswith('"'):
                                    v = v[1:-1]
                                parsed[k] = v
                            result["action_input"] = parsed
            elif line.lower().startswith("action input:"):
                try:
                    result["action_input"] = json.loads(line.split(":", 1)[1].strip())
                except json.JSONDecodeError:
                    result["action_input"] = {}

        return result

    def _extract_inline_args(self, action_str: str) -> dict[str, Any]:
        """Extract inline arguments from action string like 'fetch_page(url="...")'."""
        import re
        args_match = re.search(r'\(.*\)$', action_str.strip())
        if not args_match:
            return {}
        
        args_str = args_match.group(0)[1:-1]
        kv_pairs = re.findall(r'(\w+)=(\"[^\"]*\"|\x27[^\x27]*\x27|[\w\-./:]+)', args_str)
        if not kv_pairs:
            return {}
        
        parsed = {}
        for k, v in kv_pairs:
            if v.startswith('"') and v.endswith('"'):
                v = v[1:-1]
            elif v.startswith("'") and v.endswith("'"):
                v = v[1:-1]
            parsed[k] = v
        return parsed

    async def _execute_action(self, action: str, action_input: dict[str, Any]) -> str:
        """Execute a tool action and return observation."""
        # Extract just the tool name from action strings like "search_web(query=\"...\")"
        import re
        match = re.match(r'^(\w+)', action.strip())
        tool_name = match.group(1) if match else action.strip()
        tool = self.tool_registry.get(tool_name)
        if not tool:
            return f"Tool '{tool_name}' not found"

        try:
            result = await tool.execute(**action_input)
            return result
        except Exception as e:
            return f"Error executing {action}: {str(e)}"

    async def _mark_done(self, item_id: int) -> bool:
        """Mark the claimed topic as done."""
        try:
            mark_tool = self.tool_registry.get("mark_done")
            if not mark_tool:
                return False

            result = await mark_tool.execute(item_id=item_id, holder_id=self.holder_id)
            return "Successfully marked" in result
        except Exception as e:
            logger.warning(f"Failed to mark item {item_id} as done: {e}", exc_info=True)
            return False

    async def _enqueue_deep_read(self, topic: str, pdf_path: str | None, txt_path: str | None, source_url: str | None):
        """Enqueue a deep_read task after summary is written to KG."""
        from core.tools.queue_tools import QueueStorage
        
        try:
            queue = QueueStorage()
            queue.initialize()
            
            queue.add_item(
                topic=topic,
                priority=8,  # Higher priority than normal exploration
                metadata={
                    "task_type": "deep_read",
                    "summary_topic": topic,
                    "pdf_path": pdf_path,
                    "txt_path": txt_path,
                    "source_url": source_url
                }
            )
            
            logger.info(f"Enqueued deep_read task for: {topic}")
        except Exception as e:
            logger.warning(f"Failed to enqueue deep_read for {topic}: {e}")

    def _push_webhook(self, topic: str, quality: float = 0.0, completeness_score: int = 0, source_type: str = "explore"):
        """Push discovery webhook to R1D3 (non-blocking)."""
        try:
            from core.tools.webhook_tools import push_discovery_webhook
            push_discovery_webhook(topic, quality=quality, completeness_score=completeness_score, source_type=source_type)
        except Exception as e:
            logger.warning(f"Webhook push failed for {topic}: {e}")
