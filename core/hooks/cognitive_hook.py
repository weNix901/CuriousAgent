"""
CognitiveHook — v0.3.0

Intercepts R1D3's answer flow to enforce the cognitive framework:
  KG first → Search second → LLM last → Always learn

This hook provides deterministic, guaranteed behavior — not probabilistic LLM choices.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any
from enum import Enum
import re

from core.frameworks.agent_hook import AgentHook, AgentHookContext


class ConfidenceLevel(Enum):
    """Knowledge confidence levels."""
    NOVICE = "novice"
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"
    
    @classmethod
    def from_confidence(cls, confidence: float) -> "ConfidenceLevel":
        """Classify confidence into a level."""
        if confidence >= 0.85:
            return cls.EXPERT
        elif confidence >= 0.6:
            return cls.INTERMEDIATE
        elif confidence >= 0.3:
            return cls.BEGINNER
        else:
            return cls.NOVICE


class AnswerStrategy(Enum):
    """Answer strategy types."""
    KG_ANSWER = "kg_answer"
    SEARCH_ANSWER = "search_answer"
    LLM_ANSWER = "llm_answer"


@dataclass
class CognitiveGuidance:
    """Guidance for answering a topic."""
    topic: str
    confidence: float
    level: ConfidenceLevel
    gaps: List[str]
    guidance_message: str
    should_search: bool
    should_inject: bool


class CognitiveHook(AgentHook):
    """
    Hook that enforces the cognitive answer loop.
    
    Core philosophy:
    - Know what it knows → answer from KG
    - Know what it doesn't know → search → inject to CA
    - Transform "unknown" into "known" over time
    
    Called by AgentRunner during ReAct loop iterations.
    """
    
    GUIDANCE_TEMPLATES = {
        ConfidenceLevel.EXPERT: (
            "🟢 Answer from KG knowledge. Cite sources. "
            "No need to search or guess."
        ),
        ConfidenceLevel.INTERMEDIATE: (
            "🟡 Partial KG knowledge. Supplement with web search. "
            "Record findings. Inject to CA for deep exploration."
        ),
        ConfidenceLevel.BEGINNER: (
            "🟠 KG has limited knowledge. Search the web first. "
            "If found → record to KG + inject to CA. "
            "If not found → answer from LLM + inject to CA (mark as uncertain)."
        ),
        ConfidenceLevel.NOVICE: (
            "🔴 No KG knowledge. Search the web. "
            "Then answer from LLM if search fails. "
            "ALWAYS inject this topic to CA for exploration. "
            "Next time it will be in KG!"
        ),
    }
    
    def __init__(self, config: dict):
        """
        Initialize CognitiveHook with configuration.
        
        Args:
            config: Configuration dict with keys:
                - confidence_threshold: float (default 0.6)
                - auto_inject_unknowns: bool (default True)
                - search_before_llm: bool (default True)
        """
        self.confidence_threshold = config.get("confidence_threshold", 0.6)
        self.auto_inject = config.get("auto_inject_unknowns", True)
        self.search_before_llm = config.get("search_before_llm", True)
        
        self._stats = {
            "kg_hits": 0,
            "search_hits": 0,
            "llm_fallbacks": 0,
            "topics_injected": 0,
        }
    
    def check_confidence(self, topic: str, kg_confidence: float, gaps: List[str]) -> CognitiveGuidance:
        """
        Build guidance for a topic based on KG confidence.
        
        Args:
            topic: The topic to check
            kg_confidence: Confidence score from KG (0.0 - 1.0)
            gaps: List of knowledge gaps for this topic
            
        Returns:
            CognitiveGuidance with recommended actions
        """
        level = ConfidenceLevel.from_confidence(kg_confidence)
        template = self.GUIDANCE_TEMPLATES[level]
        
        should_search = kg_confidence < self.confidence_threshold and self.search_before_llm
        should_inject = kg_confidence < self.confidence_threshold and self.auto_inject
        
        guidance_message = (
            f"[COGNITIVE FRAMEWORK] Topic: '{topic}' | "
            f"KG confidence: {kg_confidence:.0%} ({level.value}) | "
            f"{template}"
        )
        
        return CognitiveGuidance(
            topic=topic,
            confidence=kg_confidence,
            level=level,
            gaps=gaps,
            guidance_message=guidance_message,
            should_search=should_search,
            should_inject=should_inject,
        )
    
    def build_guidance(self, topic: str, confidence: float, gaps: List[str]) -> CognitiveGuidance:
        """Alias for check_confidence."""
        return self.check_confidence(topic, confidence, gaps)
    
    def detect_strategy(self, answer_text: str) -> AnswerStrategy:
        """
        Detect which strategy was used in an answer.
        
        Args:
            answer_text: The answer text to analyze
            
        Returns:
            AnswerStrategy enum value
        """
        if not answer_text:
            return AnswerStrategy.LLM_ANSWER
        
        text_lower = answer_text.lower()
        
        kg_patterns = [
            r"knowledge graph",
            r"\bkg\b",
            r"my exploration",
            r"cited sources",
            r"based on my stored knowledge",
        ]
        for pattern in kg_patterns:
            if re.search(pattern, text_lower):
                return AnswerStrategy.KG_ANSWER
        
        search_patterns = [
            r"web search",
            r"search results",
            r"according to my search",
            r"found via search",
            r"searched the web",
        ]
        for pattern in search_patterns:
            if re.search(pattern, text_lower):
                return AnswerStrategy.SEARCH_ANSWER
        
        return AnswerStrategy.LLM_ANSWER
    
    def inject_unknown(self, topic: str, context: str, strategy: AnswerStrategy, priority: bool = False) -> dict:
        """
        Inject topic to CA queue for exploration.
        
        Args:
            topic: Topic to inject
            context: Answer context (up to 500 chars)
            strategy: Strategy used when answering
            priority: Whether to prioritize this injection
            
        Returns:
            Injection result dict
        """
        from core.tools.queue_tools import QueueStorage
        
        qs = QueueStorage()
        qs.initialize()
        
        depth_map = {
            AnswerStrategy.LLM_ANSWER: 9.0,
            AnswerStrategy.SEARCH_ANSWER: 6.0,
            AnswerStrategy.KG_ANSWER: 3.0,
        }
        
        queue_id = qs.add_item(
            topic=topic,
            priority=priority,
            metadata={
                "source": "cognitive_hook",
                "strategy": strategy.value,
                "context": context[:500],
                "depth": depth_map[strategy],
                "auto_injected": True,
            }
        )
        
        self._stats["topics_injected"] += 1
        
        return {
            "success": True,
            "queue_id": queue_id,
            "topic": topic,
            "status": "pending",
            "estimated_exploration": "30-60 minutes" if strategy == AnswerStrategy.LLM_ANSWER else "15-30 minutes",
        }
    
    def record_event(self, event_type: str, topic: str, strategy: AnswerStrategy) -> None:
        """
        Record statistics for analytics.
        
        Args:
            event_type: Event type (e.g., "answer", "inject")
            topic: Topic involved
            strategy: Strategy used
        """
        if event_type == "answer":
            if strategy == AnswerStrategy.KG_ANSWER:
                self._stats["kg_hits"] += 1
            elif strategy == AnswerStrategy.SEARCH_ANSWER:
                self._stats["search_hits"] += 1
            else:
                self._stats["llm_fallbacks"] += 1
    
    def get_stats(self) -> dict:
        """Get current statistics."""
        return dict(self._stats)
    
    def before_iteration(self, context: AgentHookContext) -> None:
        """Called before each ReAct iteration."""
        topic = context.metadata.get("topic")
        if topic:
            confidence = context.metadata.get("kg_confidence", 0.0)
            gaps = context.metadata.get("kg_gaps", [])
            
            guidance = self.check_confidence(topic, confidence, gaps)
            context.metadata["cognitive_guidance"] = guidance
    
    def after_iteration(self, context: AgentHookContext) -> None:
        """Called after each ReAct iteration."""
        guidance = context.metadata.get("cognitive_guidance")
        if not guidance:
            return
        
        response = context.metadata.get("response_content")
        if response:
            strategy = self.detect_strategy(response)
            context.metadata["answer_strategy"] = strategy
            self.record_event("answer", guidance.topic, strategy)
            
            if guidance.should_inject and strategy != AnswerStrategy.KG_ANSWER:
                self.inject_unknown(
                    topic=guidance.topic,
                    context=response,
                    strategy=strategy,
                    priority=guidance.level == ConfidenceLevel.NOVICE,
                )
    
    def on_tool_call(self, tool_name: str, params: dict) -> None:
        """Called when a tool is invoked."""
        pass
    
    def on_error(self, error: Exception) -> None:
        """Called when an error occurs."""
        pass
    
    def on_complete(self, result: Any) -> None:
        """Called when agent run completes."""
        pass
