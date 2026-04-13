"""Simplified ReAct loop engine for Curious Agent."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from .error_classifier import classify_api_error


@dataclass
class AgentRunSpec:
    content: str
    session_key: str = "default"
    model: Optional[str] = None
    max_iterations: int = 20
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentRunResult:
    content: str
    session_key: str
    iterations_used: int
    success: bool
    error: Optional[str] = None


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool
    
    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)
    
    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)
    
    def has(self, name: str) -> bool:
        return name in self._tools
    
    def get_definitions(self) -> list[dict[str, Any]]:
        return [tool.to_schema() for tool in self._tools.values()]
    
    async def execute(self, name: str, params: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found"

        try:
            errors = tool.validate_params(params)
            if errors:
                return f"Error: Invalid parameters for tool '{name}': " + "; ".join(errors)
            return await tool.execute(**params)
        except Exception as e:
            return f"Error executing {name}: {str(e)}"
    
    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())
    
    def __len__(self) -> int:
        return len(self._tools)
    
    def __contains__(self, name: str) -> bool:
        return name in self._tools


class Tool:
    _TYPE_MAP = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    
    @property
    def name(self) -> str:
        raise NotImplementedError
    
    @property
    def description(self) -> str:
        raise NotImplementedError
    
    @property
    def parameters(self) -> dict[str, Any]:
        raise NotImplementedError
    
    async def execute(self, **kwargs: Any) -> str:
        raise NotImplementedError

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        schema = self.parameters or {}
        if schema.get("type", "object") != "object":
            raise ValueError(f"Schema must be object type, got {schema.get('type')!r}")
        return self._validate(params, {**schema, "type": "object"}, "")

    def _validate(self, val: Any, schema: dict[str, Any], path: str) -> list[str]:
        t, label = schema.get("type"), path or "parameter"
        if t in self._TYPE_MAP and not isinstance(val, self._TYPE_MAP[t]):
            return [f"{label} should be {t}"]
        
        errors = []
        if "enum" in schema and val not in schema["enum"]:
            errors.append(f"{label} must be one of {schema['enum']}")
        if t in ("integer", "number"):
            if "minimum" in schema and val < schema["minimum"]:
                errors.append(f"{label} must be >= {schema['minimum']}")
            if "maximum" in schema and val > schema["maximum"]:
                errors.append(f"{label} must be <= {schema['maximum']}")
        if t == "string":
            if "minLength" in schema and len(val) < schema["minLength"]:
                errors.append(f"{label} must be at least {schema['minLength']} chars")
            if "maxLength" in schema and len(val) > schema["maxLength"]:
                errors.append(f"{label} must be at most {schema['maxLength']} chars")
        if t == "object":
            props = schema.get("properties", {})
            for k in schema.get("required", []):
                if k not in val:
                    errors.append(f"missing required {path + '.' + k if path else k}")
            for k, v in val.items():
                if k in props:
                    errors.extend(self._validate(v, props[k], path + '.' + k if path else k))
        if t == "array" and "items" in schema:
            for i, item in enumerate(val):
                errors.extend(self._validate(item, schema["items"], f"{path}[{i}]" if path else f"[{i}]"))
        return errors
    
    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }


class LLMResponse:
    def __init__(
        self,
        content: str,
        tool_calls: list[ToolCall] | None = None,
        reasoning_content: str | None = None,
    ):
        self.content = content
        self.tool_calls = tool_calls or []
        self.reasoning_content = reasoning_content
    
    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class ToolCall:
    def __init__(self, id: str, name: str, arguments: dict[str, Any]):
        self.id = id
        self.name = name
        self.arguments = arguments


class LLMProvider:
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        raise NotImplementedError


class ContextBuilder:
    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.cwd()
    
    def build_messages(
        self,
        history: list[tuple[str, str]] | None = None,
        current_message: str | None = None,
        media: dict[str, Any] | None = None,
        channel: str = "default",
        chat_id: str = "default",
    ) -> list[dict[str, Any]]:
        messages = []
        
        messages.append({
            "role": "system",
            "content": self._build_system_prompt()
        })
        
        if history:
            for role, content in history:
                messages.append({"role": role, "content": content})
        
        if current_message:
            messages.append({"role": "user", "content": current_message})
        
        return messages
    
    def add_assistant_message(
        self,
        messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
        reasoning_content: str | None = None,
    ) -> list[dict[str, Any]]:
        msg: dict[str, Any] = {"role": "assistant"}
        
        if content:
            msg["content"] = content
        if tool_calls:
            msg["tool_calls"] = tool_calls
        if reasoning_content:
            msg["reasoning_content"] = reasoning_content
        
        messages.append(msg)
        return messages
    
    def add_tool_result(
        self,
        messages: list[dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        result: str,
    ) -> list[dict[str, Any]]:
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": result,
        })
        return messages
    
    def _build_system_prompt(self) -> str:
        return """You are Curious Agent, an autonomous knowledge exploration agent.

You have access to tools that help you explore and build knowledge.

When you use tools:
1. Think carefully about what you need to accomplish
2. Choose the right tool for the job
3. Reflect on the results before taking the next action

You work in a ReAct loop: Thought → Action → Observation → Repeat

When you have completed your task, provide a clear summary of what you accomplished."""


class CAAgentRunner:
    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path | None = None,
        model: str | None = None,
        max_iterations: int = 20,
    ):
        self.provider = provider
        self.workspace = workspace or Path.cwd()
        self.model = model
        self.max_iterations = max_iterations
        
        self.context = ContextBuilder(self.workspace)
        self.tools = ToolRegistry()
        
        self._running = False
    
    def _register_default_tools(self) -> None:
        pass
    
    async def run(self, spec: AgentRunSpec) -> AgentRunResult:
        self._running = True
        logger.info(f"Agent run started for session: {spec.session_key}")
        
        iteration = 0
        final_content = None
        error_message = None
        
        try:
            messages = self.context.build_messages(
                current_message=spec.content,
            )
            
            while iteration < spec.max_iterations:
                iteration += 1
                
                try:
                    response = await self.provider.chat(
                        messages=messages,
                        tools=self.tools.get_definitions(),
                        model=spec.model or self.model,
                    )
                except Exception as e:
                    classified = classify_api_error(e)
                    logger.warning(f"LLM error classified as: {classified.reason}")
                    
                    if not classified.retryable:
                        error_message = f"Non-retryable error: {classified.message}"
                        break
                    
                    messages.append({
                        "role": "user",
                        "content": f"Error occurred: {classified.message}. Please try again or explain the issue."
                    })
                    continue
                
                if response.has_tool_calls:
                    tool_call_dicts = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments)
                            }
                        }
                        for tc in response.tool_calls
                    ]
                    messages = self.context.add_assistant_message(
                        messages, response.content, tool_call_dicts,
                        reasoning_content=response.reasoning_content,
                    )
                    
                    for tool_call in response.tool_calls:
                        args_str = json.dumps(tool_call.arguments, ensure_ascii=False)[:200]
                        logger.info(f"Tool call: {tool_call.name}({args_str})")
                        
                        result = await self.tools.execute(
                            tool_call.name,
                            tool_call.arguments
                        )
                        
                        messages = self.context.add_tool_result(
                            messages, tool_call.id, tool_call.name, result
                        )
                    
                    messages.append({
                        "role": "user",
                        "content": "Reflect on the results and decide next steps."
                    })
                else:
                    final_content = response.content
                    break
            
            if final_content is None:
                if error_message:
                    final_content = f"I encountered an error: {error_message}"
                else:
                    final_content = "I've completed processing but have no response to give."
            
            logger.info(f"Agent run completed for session: {spec.session_key}")
            
            return AgentRunResult(
                content=final_content,
                session_key=spec.session_key,
                iterations_used=iteration,
                success=error_message is None,
                error=error_message,
            )
            
        except Exception as e:
            logger.error(f"Agent run failed: {e}")
            return AgentRunResult(
                content=f"Agent run failed: {str(e)}",
                session_key=spec.session_key,
                iterations_used=iteration,
                success=False,
                error=str(e),
            )
        finally:
            self._running = False
    
    def stop(self) -> None:
        self._running = False
        logger.info("Agent loop stopping")
    
    @property
    def is_running(self) -> bool:
        return self._running
