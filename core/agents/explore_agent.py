"""ExploreAgent with ReAct loop for knowledge exploration."""
import json
import uuid
from typing import Any

from core.agents.ca_agent import CAAgent, CAAgentConfig, AgentResult
from core.tools.registry import ToolRegistry
from core.llm_client import LLMClient


DEFAULT_SYSTEM_PROMPT = """You are an ExploreAgent that autonomously explores knowledge topics.

Your workflow for each topic:
1. Search the web for the topic
2. For each promising URL, fetch_page to get full content
3. Use llm_analyze to judge if the fetched content is useful for this topic
4. If content is useful, synthesize findings into knowledge
5. Write to KG and mark the topic as done

Use ReAct loop: Thought -> Action -> Observation (max 10 iterations)

Available tools:
- search_web: Search the web (returns title, snippet, URL)
- fetch_page: Fetch full content from a URL
- query_kg: Query existing knowledge in the KG
- add_to_kg: Add new knowledge nodes
- claim_queue: Claim a topic from the queue
- mark_done: Mark a topic as complete
- get_queue: View pending topics
- llm_analyze: Analyze content with LLM (use this to judge if content is relevant!)
- llm_summarize: Summarize content

Content quality judgment rules:
- A URL's full content is useful if it provides substantive information about the topic
- Use llm_analyze to judge: "Does this content help explain or explore [topic]?"
- Even short content can be useful if it's substantive (not just navigation/ads)
- Snippets alone are NOT enough - always try to fetch_page for full content

When search APIs are exhausted (no results or all fail):
- Mark the topic with "no_content" status
- Do NOT generate fake/hallucinated knowledge
- Report what you tried and why it failed

Always think before acting. After each action, observe the result and decide next steps.
When you have enough verified information, write to KG and mark the topic done.
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

    async def run(self, input_data: str) -> AgentResult:
        """Run the ExploreAgent workflow: claim -> explore -> mark done."""
        topic = input_data.strip()

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
            action_input = parsed.get("action_input", {})

            if thought:
                content_parts.append(f"Thought: {thought}")

            if not action or action.lower() == "done":
                if not content_parts:
                    content_parts.append(f"Exploration of '{topic}' complete")
                return {
                    "success": True,
                    "content": "\n".join(content_parts),
                    "iterations": iterations,
                }

            observation = await self._execute_action(action, action_input)
            observations.append(f"Iteration {iterations}: {action}({action_input}) -> {observation[:200]}")
            content_parts.append(f"Action: {action}({action_input})\nObservation: {observation[:200]}")

            messages.append(
                {
                    "role": "assistant",
                    "content": f"Thought: {thought}\nAction: {action}\nAction Input: {action_input}",
                }
            )
            messages.append({"role": "user", "content": f"Observation: {observation}"})

        return {
            "success": False,
            "content": "\n".join(content_parts) + f"\n\nReached max iterations ({self.config.max_iterations})",
            "iterations": iterations,
        }

    def _parse_react_response(self, response: str) -> dict[str, Any]:
        """Parse ReAct response from non-JSON format."""
        result = {"thought": "", "action": "", "action_input": {}}

        lines = response.split("\n")
        for line in lines:
            line = line.strip()
            if line.lower().startswith("thought:"):
                result["thought"] = line.split(":", 1)[1].strip()
            elif line.lower().startswith("action:"):
                result["action"] = line.split(":", 1)[1].strip()
            elif line.lower().startswith("action input:"):
                try:
                    result["action_input"] = json.loads(line.split(":", 1)[1].strip())
                except json.JSONDecodeError:
                    result["action_input"] = {}

        return result

    async def _execute_action(self, action: str, action_input: dict[str, Any]) -> str:
        """Execute a tool action and return observation."""
        tool = self.tool_registry.get(action)
        if not tool:
            return f"Tool '{action}' not found"

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
        except Exception:
            return False
