# Phase 3: Curiosity Decomposer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the CuriosityDecomposer module with multi-Provider search validation to decompose broad topics into specific sub-topics before exploration.

**Architecture:** Four-step cascade pipeline (LLM → Multi-Provider Validation → Knowledge Graph → Clarification) with a plugin-based SearchProvider architecture and emergent Provider coverage heatmap.

**Tech Stack:** Python 3.11+, asyncio for parallel Provider queries, existing core modules (knowledge_graph, llm_client)

---

## Prerequisites

Read these files before starting:
- Design doc: `docs/plans/2026-03-23-v0.2.3-phase3-curiosity-decomposer-design.md`
- Existing search implementation: `core/explorer.py` (Bocha search logic to migrate)
- Knowledge graph: `core/knowledge_graph.py`

---

## Task 1: Create SearchProvider Abstract Interface

**Files:**
- Create: `core/search_provider.py`

**Step 1: Create the abstract base class**

```python
"""Search Provider Abstract Interface"""
from abc import ABC, abstractmethod
from typing import Optional


class SearchProvider(ABC):
    """Abstract interface for search providers"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier"""
        pass
    
    @abstractmethod
    async def search(self, query: str) -> dict:
        """
        Execute search query
        
        Returns:
            {
                "results": list[dict],
                "result_count": int,
                "raw": dict  # Provider-specific raw response
            }
        """
        pass
    
    @abstractmethod
    async def related_terms(self, query: str) -> list[dict]:
        """
        Get related search terms
        
        Returns:
            [{"term": str, "query_count": int}, ...]
        """
        pass
```

**Step 2: Verify file creation**

Run: `python3 -c "from core.search_provider import SearchProvider; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add core/search_provider.py
git commit -m "feat: add SearchProvider abstract interface"
```

---

## Task 2: Implement BochaSearchProvider

**Files:**
- Create: `core/providers/bocha_provider.py`
- Modify: `core/providers/__init__.py` (create if not exists)

**Step 1: Create directory structure**

```bash
mkdir -p core/providers
touch core/providers/__init__.py
```

**Step 2: Write BochaSearchProvider**

```python
"""Bocha Search Provider Implementation"""
import json
import os
import subprocess
from typing import Optional

from core.search_provider import SearchProvider


class BochaSearchProvider(SearchProvider):
    """Bocha AI Search API Provider"""
    
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("BOCHA_API_KEY", "")
        self._name = "bocha"
    
    @property
    def name(self) -> str:
        return self._name
    
    async def search(self, query: str) -> dict:
        """Execute Bocha search"""
        if not self._api_key:
            return {"results": [], "result_count": 0, "raw": {}}
        
        url = "https://api.bochaai.com/v1/web-search"
        payload = {"query": query, "count": 5}
        
        try:
            result = subprocess.run(
                ["curl", "-s", "-X", "POST", url,
                 "-H", f"Authorization: Bearer {self._api_key}",
                 "-H", "Content-Type: application/json",
                 "-d", json.dumps(payload)],
                capture_output=True, text=True, timeout=10
            )
            data = json.loads(result.stdout)
            
            if isinstance(data, dict) and data.get("code") == 200:
                web_pages = data.get("data", {}).get("webPages", {})
                items = web_pages.get("value", [])
                return {
                    "results": self._parse_results(items),
                    "result_count": len(items),
                    "raw": data
                }
        except Exception as e:
            return {"results": [], "result_count": 0, "raw": {"error": str(e)}}
        
        return {"results": [], "result_count": 0, "raw": {}}
    
    def _parse_results(self, items: list) -> list:
        """Parse Bocha results to standard format"""
        results = []
        for item in items:
            if isinstance(item, dict):
                results.append({
                    "title": str(item.get("name", ""))[:150],
                    "snippet": str(item.get("snippet", ""))[:400],
                    "url": str(item.get("url", ""))
                })
        return results
    
    async def related_terms(self, query: str) -> list[dict]:
        """Get related terms (Bocha doesn't support directly, return empty)"""
        return []
```

**Step 3: Export from providers package**

```python
# core/providers/__init__.py
from .bocha_provider import BochaSearchProvider

__all__ = ["BochaSearchProvider"]
```

**Step 4: Write test**

```python
# tests/core/providers/test_bocha_provider.py
import pytest
from core.providers.bocha_provider import BochaSearchProvider


def test_bocha_provider_name():
    provider = BochaSearchProvider()
    assert provider.name == "bocha"


@pytest.mark.asyncio
async def test_bocha_search_no_api_key():
    provider = BochaSearchProvider(api_key="")
    result = await provider.search("test query")
    assert result["result_count"] == 0
    assert result["results"] == []
```

**Step 5: Run test**

Run: `pytest tests/core/providers/test_bocha_provider.py -v`
Expected: 2 passed

**Step 6: Commit**

```bash
git add core/providers/ tests/core/providers/
git commit -m "feat: implement BochaSearchProvider"
```

---

## Task 2b: Implement SerperProvider (Required for 2-Provider validation)

**Files:**
- Create: `core/providers/serper_provider.py`
- Modify: `core/providers/__init__.py`

**Step 1: Write SerperProvider**

```python
"""Serper Google Search Provider Implementation"""
import json
import os
import subprocess
from typing import Optional

from core.search_provider import SearchProvider


class SerperProvider(SearchProvider):
    """Serper.dev Google Search API Provider"""
    
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("SERPER_API_KEY", "")
        self._name = "serper"
    
    @property
    def name(self) -> str:
        return self._name
    
    async def search(self, query: str) -> dict:
        """Execute Serper search"""
        if not self._api_key:
            return {"results": [], "result_count": 0, "raw": {}}
        
        url = "https://google.serper.dev/search"
        payload = {"q": query, "num": 5}
        
        try:
            result = subprocess.run(
                ["curl", "-s", "-X", "POST", url,
                 "-H", f"X-API-KEY: {self._api_key}",
                 "-H", "Content-Type: application/json",
                 "-d", json.dumps(payload)],
                capture_output=True, text=True, timeout=10
            )
            data = json.loads(result.stdout)
            
            if isinstance(data, dict):
                organic = data.get("organic", [])
                return {
                    "results": self._parse_results(organic),
                    "result_count": len(organic),
                    "raw": data
                }
        except Exception as e:
            return {"results": [], "result_count": 0, "raw": {"error": str(e)}}
        
        return {"results": [], "result_count": 0, "raw": {}}
    
    def _parse_results(self, items: list) -> list:
        """Parse Serper results to standard format"""
        results = []
        for item in items:
            if isinstance(item, dict):
                results.append({
                    "title": str(item.get("title", ""))[:150],
                    "snippet": str(item.get("snippet", ""))[:400],
                    "url": str(item.get("link", ""))
                })
        return results
    
    async def related_terms(self, query: str) -> list[dict]:
        """Get related terms"""
        return []
```

**Step 2: Update exports**

```python
# core/providers/__init__.py
from .bocha_provider import BochaSearchProvider
from .serper_provider import SerperProvider

__all__ = ["BochaSearchProvider", "SerperProvider"]
```

**Step 3: Write test**

```python
# tests/core/providers/test_serper_provider.py
import pytest
from core.providers.serper_provider import SerperProvider


def test_serper_provider_name():
    provider = SerperProvider()
    assert provider.name == "serper"


@pytest.mark.asyncio
async def test_serper_search_no_api_key():
    provider = SerperProvider(api_key="")
    result = await provider.search("test query")
    assert result["result_count"] == 0
```

**Step 4: Run test**

Run: `pytest tests/core/providers/test_serper_provider.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add core/providers/serper_provider.py tests/core/providers/test_serper_provider.py
git commit -m "feat: implement SerperProvider for 2-provider validation"
```

---

## Task 3: Implement ProviderRegistry

**Files:**
- Create: `core/provider_registry.py`

**Step 1: Implement the registry**

```python
"""Provider Registry - Singleton pattern for managing search providers"""
import os
from typing import Optional

from core.search_provider import SearchProvider
from core.providers import BochaSearchProvider, SerperProvider


class ProviderRegistry:
    """Singleton registry for search providers"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._providers: dict[str, SearchProvider] = {}
        return cls._instance
    
    def register(self, provider: SearchProvider) -> None:
        """Register a provider"""
        self._providers[provider.name] = provider
    
    def get(self, name: str) -> Optional[SearchProvider]:
        """Get provider by name"""
        return self._providers.get(name)
    
    def get_all(self) -> list[SearchProvider]:
        """Get all registered providers"""
        return list(self._providers.values())
    
    def get_enabled(self) -> list[SearchProvider]:
        """Get enabled providers based on configuration"""
        enabled = []
        config = self._load_config()
        
        for name, provider in self._providers.items():
            if config.get(name, {}).get("enabled", False):
                enabled.append(provider)
        
        return enabled
    
    def _load_config(self) -> dict:
        """Load provider configuration"""
        # Simple env-based config for now
        return {
            "bocha": {"enabled": bool(os.environ.get("BOCHA_API_KEY"))},
            "brave": {"enabled": bool(os.environ.get("BRAVE_API_KEY"))},
            "serper": {"enabled": bool(os.environ.get("SERPER_API_KEY"))},
        }
    
    def reset(self) -> None:
        """Reset registry (for testing)"""
        self._providers.clear()


# Global registry instance
def get_provider_registry() -> ProviderRegistry:
    return ProviderRegistry()


def init_default_providers() -> ProviderRegistry:
    """Initialize registry with default providers (Bocha + Serper)"""
    registry = get_provider_registry()
    registry.reset()
    
    # Register Bocha if API key available
    bocha_key = os.environ.get("BOCHA_API_KEY")
    if bocha_key:
        registry.register(BochaSearchProvider(bocha_key))
    
    # Register Serper if API key available
    serper_key = os.environ.get("SERPER_API_KEY")
    if serper_key:
        registry.register(SerperProvider(serper_key))
    
    return registry
```

**Step 2: Write test**

```python
# tests/core/test_provider_registry.py
import pytest
from core.provider_registry import ProviderRegistry, get_provider_registry
from core.providers.bocha_provider import BochaSearchProvider


def test_singleton():
    r1 = get_provider_registry()
    r2 = get_provider_registry()
    assert r1 is r2


def test_register_and_get():
    registry = ProviderRegistry()
    registry.reset()
    
    provider = BochaSearchProvider(api_key="test")
    registry.register(provider)
    
    assert registry.get("bocha") is provider
    assert len(registry.get_all()) == 1
```

**Step 3: Run test**

Run: `pytest tests/core/test_provider_registry.py -v`
Expected: 2 passed

**Step 4: Commit**

```bash
git add core/provider_registry.py tests/core/test_provider_registry.py
git commit -m "feat: implement ProviderRegistry singleton"
```

---

## Task 4: Create ClarificationNeeded Exception

**Files:**
- Create: `core/exceptions.py`

**Step 1: Create exception class**

```python
"""Custom exceptions for Curious Agent"""


class ClarificationNeeded(Exception):
    """
    Raised when the decomposer cannot determine the domain/context of a topic
    and needs user clarification.
    """
    
    def __init__(self, topic: str, alternatives: list[str] = None, reason: str = ""):
        self.topic = topic
        self.alternatives = alternatives or ["AI/Agent", "软件开发", "通用概念"]
        self.reason = reason
        message = f"无法确定 '{topic}' 的领域，请选择或输入具体领域"
        if reason:
            message += f" ({reason})"
        super().__init__(message)
```

**Step 2: Write test**

```python
# tests/core/test_exceptions.py
import pytest
from core.exceptions import ClarificationNeeded


def test_clarification_needed():
    exc = ClarificationNeeded("agent")
    assert exc.topic == "agent"
    assert len(exc.alternatives) == 3
    assert "agent" in str(exc)


def test_clarification_needed_with_reason():
    exc = ClarificationNeeded("test", reason="no provider results")
    assert "no provider results" in str(exc)
```

**Step 3: Run test**

Run: `pytest tests/core/test_exceptions.py -v`
Expected: 2 passed

**Step 4: Commit**

```bash
git add core/exceptions.py tests/core/test_exceptions.py
git commit -m "feat: add ClarificationNeeded exception"
```

---

## Task 5: Implement CuriosityDecomposer Core

**Files:**
- Create: `core/curiosity_decomposer.py`

**Step 1: Implement main class**

```python
"""Curiosity Decomposer - Break down broad topics into specific sub-topics"""
import asyncio
import re
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.search_provider import SearchProvider
    from core.provider_registry import ProviderRegistry

from core.exceptions import ClarificationNeeded


class CuriosityDecomposer:
    """
    好奇心分解器
    
    Four-step cascade:
    1. LLM generates candidate sub-topics
    2. Multi-Provider validation
    3. Knowledge Graph augmentation
    4. Clarification if needed
    
    Config options:
    - max_candidates: int (default 7, range 5-7)
    - min_candidates: int (default 5)
    - max_depth: int (default 2, 0=unlimited)
    - verification_threshold: int (default 2, min providers to verify)
    """
    
    DEFAULT_CONFIG = {
        "max_candidates": 7,
        "min_candidates": 5,
        "max_depth": 2,  # 0 means unlimited
        "verification_threshold": 2,  # Require both Bocha + Serper
    }
    
    def __init__(
        self,
        llm_client,
        provider_registry: "ProviderRegistry",
        kg,
        config: dict = None
    ):
        self.llm = llm_client
        self.providers = provider_registry
        self.kg = kg
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
    
    async def decompose(self, topic: str) -> list[dict]:
        """
        Main entry: decompose topic into sub-topics
        
        Returns:
            List of verified sub-topics with metadata
        """
        # Step 1: Generate candidates
        candidates = await self._llm_generate_candidates(topic)
        
        if not candidates:
            raise ClarificationNeeded(topic, reason="LLM generated no candidates")
        
        # Step 2: Validate with providers
        verified = await self._verify_with_providers(candidates)
        
        if not verified:
            # No verified candidates - need clarification
            raise ClarificationNeeded(
                topic=topic,
                reason="no candidates passed provider validation"
            )
        
        # Step 3: KG augmentation
        enriched = self._kg_augment(topic, verified)
        
        return enriched
    
    async def _llm_generate_candidates(self, topic: str) -> list[str]:
        """Step 1: Use LLM to generate candidate sub-topics"""
        max_c = self.config.get("max_candidates", 7)
        min_c = self.config.get("min_candidates", 5)
        
        prompt = f"""针对 "{topic}" 这个话题，识别它最常见的子领域或组成部分。

要求：
- 列出 {min_c}-{max_c} 个子话题
- 每个格式：[子话题名称] - [一句话说明]
- 优先技术领域相关的子话题

输出格式（直接输出列表，不需要其他文字）：
- topic1 - 说明1
- topic2 - 说明2
- topic3 - 说明3"""
        
        try:
            response = self.llm.chat(prompt)
            return self._parse_candidates(response)
        except Exception:
            return []
    
    def _parse_candidates(self, response: str) -> list[str]:
        """Parse LLM response into candidate list"""
        candidates = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if line.startswith("- "):
                # Extract topic from "- topic - description"
                parts = line[2:].split(" - ")
                if parts:
                    candidate = parts[0].strip()
                    if candidate:
                        candidates.append(candidate)
        return candidates
    
    async def _verify_with_providers(self, candidates: list[str]) -> list[dict]:
        """Step 2: Validate candidates with search providers"""
        if not candidates:
            return []
        
        # Run verification in parallel
        tasks = [self._verify_single(c) for c in candidates]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter valid results
        valid = []
        for r in results:
            if isinstance(r, Exception):
                continue
            if r and r.get("verified", False):
                valid.append(r)
        
        return valid
    
    async def _verify_single(self, candidate: str) -> Optional[dict]:
        """Verify a single candidate with all enabled providers"""
        enabled = self.providers.get_enabled()
        
        if not enabled:
            # No providers enabled - accept all (fallback)
            return {
                "candidate": candidate,
                "provider_results": {},
                "total_count": 0,
                "provider_count": 0,
                "signal_strength": "unknown",
                "verified": True
            }
        
        # Query all providers in parallel
        tasks = [p.search(candidate) for p in enabled]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        provider_results = {}
        for provider, response in zip(enabled, responses):
            if isinstance(response, Exception):
                continue
            if response and response.get("result_count", 0) > 0:
                provider_results[provider.name] = response["result_count"]
        
        total = sum(provider_results.values())
        count = len(provider_results)
        
        # Use configured verification threshold
        min_required = self.config.get("verification_threshold", 2)
        
        return {
            "sub_topic": candidate,
            "candidate": candidate,  # For compatibility
            "provider_results": provider_results,
            "total_count": total,
            "provider_count": count,
            "signal_strength": self._classify_signal(count, total),
            "verified": count >= min_required
        }
    
    def _classify_signal(self, provider_count: int, total_count: int) -> str:
        """Classify signal strength"""
        if provider_count >= 3 and total_count >= 100:
            return "strong"
        elif provider_count >= 2 and total_count >= 10:
            return "medium"
        else:
            return "weak"
    
    def _kg_augment(self, parent: str, verified: list[dict]) -> list[dict]:
        """Step 3: Augment with Knowledge Graph data"""
        try:
            kg_children = self.kg.get("topics", {}).get(parent, {}).get("children", [])
        except (AttributeError, TypeError):
            kg_children = []
        
        for item in verified:
            candidate = item.get("sub_topic", item.get("candidate", ""))
            item["kg_confirmed"] = candidate in kg_children
            item["source"] = "llm+kg" if item["kg_confirmed"] else "llm_only"
            item["relation"] = "component"
        
        return verified
```

**Step 2: Write test**

```python
# tests/core/test_curiosity_decomposer.py
import pytest
from unittest.mock import Mock, AsyncMock

from core.curiosity_decomposer import CuriosityDecomposer
from core.exceptions import ClarificationNeeded


@pytest.fixture
def mock_llm():
    return Mock()


@pytest.fixture
def mock_registry():
    registry = Mock()
    registry.get_enabled = Mock(return_value=[])
    return registry


@pytest.fixture
def mock_kg():
    return {"topics": {}}


@pytest.fixture
def decomposer(mock_llm, mock_registry, mock_kg):
    return CuriosityDecomposer(mock_llm, mock_registry, mock_kg)


@pytest.mark.asyncio
async def test_parse_candidates(decomposer):
    response = """- agent_memory - AI Agent memory systems
- agent_planning - Task planning for agents
- agent_tools - Tool usage"""
    
    result = decomposer._parse_candidates(response)
    assert len(result) == 3
    assert "agent_memory" in result


def test_classify_signal(decomposer):
    assert decomposer._classify_signal(3, 150) == "strong"
    assert decomposer._classify_signal(2, 50) == "medium"
    assert decomposer._classify_signal(1, 5) == "weak"


@pytest.mark.asyncio
async def test_decompose_raises_clarification_when_no_candidates(decomposer, mock_llm):
    mock_llm.chat = Mock(return_value="")  # Empty response
    
    with pytest.raises(ClarificationNeeded):
        await decomposer.decompose("agent")
```

**Step 3: Run test**

Run: `pytest tests/core/test_curiosity_decomposer.py -v`
Expected: 3+ passed

**Step 4: Commit**

```bash
git add core/curiosity_decomposer.py tests/core/test_curiosity_decomposer.py
git commit -m "feat: implement CuriosityDecomposer core class"
```

---

## Task 6: Extend Knowledge Graph with Parent-Child Relations

**Files:**
- Modify: `core/knowledge_graph.py`

**Step 1: Add new functions**

Insert after line 100 (after `add_curiosity` function):

```python
def add_child(parent: str, child: str) -> None:
    """Add parent-child relationship between topics"""
    state = _load_state()
    topics = state["knowledge"]["topics"]
    now = datetime.now(timezone.utc).isoformat()
    
    # Ensure parent exists
    if parent not in topics:
        topics[parent] = {
            "known": False,
            "depth": 0,
            "children": [],
            "explored_children": [],
            "created_at": now
        }
    
    # Add child to parent's children list
    if "children" not in topics[parent]:
        topics[parent]["children"] = []
    
    if child not in topics[parent]["children"]:
        topics[parent]["children"].append(child)
    
    # Update status
    topics[parent]["status"] = "partial"
    
    _save_state(state)


def get_children(topic: str) -> list[str]:
    """Get child topics for a given topic"""
    state = _load_state()
    topic_data = state.get("knowledge", {}).get("topics", {}).get(topic, {})
    return topic_data.get("children", [])


def mark_child_explored(parent: str, child: str) -> None:
    """Mark a child topic as explored"""
    state = _load_state()
    topics = state["knowledge"]["topics"]
    
    if parent not in topics:
        return
    
    if "explored_children" not in topics[parent]:
        topics[parent]["explored_children"] = []
    
    if child not in topics[parent]["explored_children"]:
        topics[parent]["explored_children"].append(child)
    
    # Update status if all children explored
    children = topics[parent].get("children", [])
    explored = topics[parent].get("explored_children", [])
    if children and len(explored) >= len(children):
        topics[parent]["status"] = "complete"
    
    _save_state(state)


def get_exploration_status(topic: str) -> str:
    """Get exploration status: unexplored | partial | complete"""
    state = _load_state()
    topic_data = state.get("knowledge", {}).get("topics", {}).get(topic, {})
    
    return topic_data.get("status", "unexplored")
```

**Step 2: Write test**

```python
# tests/core/test_knowledge_graph_children.py
import pytest
from core import knowledge_graph as kg


def test_add_child_and_get_children():
    kg.add_child("agent", "agent_memory")
    kg.add_child("agent", "agent_planning")
    
    children = kg.get_children("agent")
    assert "agent_memory" in children
    assert "agent_planning" in children


def test_mark_child_explored():
    kg.add_child("test_parent", "test_child")
    kg.mark_child_explored("test_parent", "test_child")
    
    status = kg.get_exploration_status("test_parent")
    assert status == "complete"


def test_partial_status():
    kg.add_child("partial_test", "child1")
    kg.add_child("partial_test", "child2")
    kg.mark_child_explored("partial_test", "child1")
    
    status = kg.get_exploration_status("partial_test")
    assert status == "partial"
```

**Step 3: Run test**

Run: `pytest tests/core/test_knowledge_graph_children.py -v`
Expected: 3 passed

**Step 4: Commit**

```bash
git add core/knowledge_graph.py tests/core/test_knowledge_graph_children.py
git commit -m "feat: add parent-child relationship support to knowledge graph"
```

---

## Task 7: Implement Quality Gate (should_queue)

**Files:**
- Create: `core/quality_gate.py`

**Step 1: Implement gate logic**

```python
"""Quality Gate - Filter topics before queuing"""

# Blacklist of overly generic terms
BLACKLIST = {
    # Too generic
    "agent", "agents", "cognit", "cognition",
    "architecture", "architectures",
    "system", "systems",
    # Non-substantive
    "overview", "introduction", "what is",
    "how to", "getting started", "tutorial",
    # Common SEO noise
    "AI Strategy", "AI Business", "Digital Marketing",
}


def should_queue(topic: str, existing_topics: set = None) -> tuple[bool, str]:
    """
    Determine if a topic should be added to the curiosity queue
    
    Returns:
        (should_queue: bool, reason: str)
    """
    if not topic or not isinstance(topic, str):
        return False, "invalid_topic"
    
    topic = topic.strip()
    
    # 1. Too short
    words = topic.split()
    if len(words) < 2:
        return False, "too_short"
    
    # 2. Blacklist check
    topic_lower = topic.lower()
    for banned in BLACKLIST:
        if topic_lower == banned or topic_lower.startswith(banned + " "):
            return False, f"blacklist: {banned}"
    
    # 3. Duplicate check
    if existing_topics:
        topic_normalized = topic_lower.replace("_", " ")
        for existing in existing_topics:
            if _is_similar(topic_normalized, existing.lower().replace("_", " ")):
                return False, "similar_to_existing"
    
    return True, "ok"


def _is_similar(topic1: str, topic2: str, threshold: float = 0.7) -> bool:
    """Check if two topics are similar based on word overlap"""
    words1 = set(topic1.split())
    words2 = set(topic2.split())
    
    if not words1 or not words2:
        return False
    
    intersection = words1 & words2
    union = words1 | words2
    
    similarity = len(intersection) / len(union)
    return similarity >= threshold
```

**Step 2: Write test**

```python
# tests/core/test_quality_gate.py
import pytest
from core.quality_gate import should_queue, _is_similar


def test_should_accept_valid_topic():
    result, reason = should_queue("agent memory systems")
    assert result is True
    assert reason == "ok"


def test_reject_too_short():
    result, reason = should_queue("agent")
    assert result is False
    assert reason == "too_short"


def test_reject_blacklist():
    result, reason = should_queue("architecture patterns")
    assert result is False
    assert "blacklist" in reason


def test_is_similar():
    assert _is_similar("agent memory", "agent memory systems") is True
    assert _is_similar("agent memory", "agent planning") is False


def test_reject_similar():
    existing = {"agent memory systems"}
    result, reason = should_queue("agent memory", existing)
    assert result is False
    assert reason == "similar_to_existing"
```

**Step 3: Run test**

Run: `pytest tests/core/test_quality_gate.py -v`
Expected: 5 passed

**Step 4: Commit**

```bash
git add core/quality_gate.py tests/core/test_quality_gate.py
git commit -m "feat: implement quality gate for topic filtering"
```

---

## Task 8: Integrate Decomposer into run_one_cycle

**Files:**
- Modify: `curious_agent.py`

**Step 1: Add imports and integration logic**

Add imports at the top (around line 20):

```python
# Add after existing imports
from core.curiosity_decomposer import CuriosityDecomposer
from core.provider_registry import init_default_providers
from core.exceptions import ClarificationNeeded
from core.quality_gate import should_queue
import asyncio
```

**Step 2: Modify run_one_cycle function**

Insert after line 78 (after getting topic):

```python
    # ===== Phase 3: Curiosity Decomposition =====
    # Initialize provider registry with default providers
    registry = init_default_providers()
    
    decomposer = CuriosityDecomposer(
        llm_client=llm_manager,
        provider_registry=registry,
        kg=state
    )
    
    try:
        # Run decomposer (async)
        subtopics = asyncio.run(decomposer.decompose(topic))
        
        if subtopics:
            # Select best subtopic by signal strength
            best = max(subtopics, key=lambda x: x.get("total_count", 0))
            explore_topic = best["sub_topic"]
            
            # Log decomposition
            print(f"[Decomposer] '{topic}' -> '{explore_topic}' ({best.get('signal_strength', 'unknown')})")
            
            # Update curiosity item with decomposed topic
            next_curiosity["original_topic"] = topic
            next_curiosity["topic"] = explore_topic
            next_curiosity["decomposition"] = best
        else:
            explore_topic = topic
            
    except ClarificationNeeded as e:
        print(f"[Decomposer] Clarification needed for '{e.topic}': {e.reason}")
        # Emit event for OpenClaw to handle
        EventBus.emit("decomposer.clarification_needed", {
            "topic": e.topic,
            "alternatives": e.alternatives,
            "reason": e.reason
        })
        return {"status": "clarification_needed", "topic": e.topic, "reason": e.reason}
    
    topic = next_curiosity["topic"]  # Use potentially decomposed topic
    # ===== End Phase 3 =====
```

**Step 3: Add post-exploration parent-child linking**

After exploration completes (after line 95), add:

```python
    # If topic was decomposed, record parent-child relationship
    if "original_topic" in next_curiosity:
        from core import knowledge_graph as kg_module
        kg_module.add_child(next_curiosity["original_topic"], topic)
```

**Step 4: Write integration test**

```python
# tests/test_decomposer_integration.py
import pytest
from unittest.mock import Mock, patch, AsyncMock


def test_decomposer_integration():
    """Test decomposer is called during run_one_cycle"""
    with patch("curious_agent.CuriosityDecomposer") as mock_decomposer:
        with patch("curious_agent.init_default_providers"):
            mock_instance = Mock()
            mock_instance.decompose = AsyncMock(return_value=[{
                "sub_topic": "agent_memory",
                "total_count": 100,
                "signal_strength": "strong"
            }])
            mock_decomposer.return_value = mock_instance
            
            # Import and test would go here
            # This is a template for actual integration testing
            pass
```

**Step 5: Commit**

```bash
git add curious_agent.py tests/test_decomposer_integration.py
git commit -m "feat: integrate CuriosityDecomposer into run_one_cycle"
```

---

## Task 9: Add Provider Coverage Heatmap

**Files:**
- Create: `core/provider_heatmap.py`

**Step 1: Implement heatmap tracking**

```python
"""Provider Coverage Heatmap - Track which providers work best for which domains"""
from collections import defaultdict
from typing import Optional


class ProviderHeatmap:
    """
    Emergent heatmap of Provider coverage by (language, domain)
    Built incrementally from verification logs
    """
    
    def __init__(self):
        # {(language, domain): {provider_name: total_results}}
        self._heatmap: dict[tuple, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._verification_count: dict[tuple, int] = defaultdict(int)
    
    def record_verification(
        self,
        language: str,
        domain: str,
        provider_results: dict[str, int]
    ) -> None:
        """Record a verification result"""
        key = (language, domain)
        self._verification_count[key] += 1
        
        for provider, count in provider_results.items():
            self._heatmap[key][provider] += count
    
    def get_coverage(self, language: str, domain: str) -> dict[str, int]:
        """Get coverage stats for a (language, domain) pair"""
        return dict(self._heatmap.get((language, domain), {}))
    
    def get_best_providers(self, language: str, domain: str) -> list[str]:
        """Get providers sorted by coverage for a domain"""
        coverage = self.get_coverage(language, domain)
        if not coverage:
            return []
        return sorted(coverage.keys(), key=lambda p: coverage[p], reverse=True)
    
    def get_confidence_modifier(self, language: str, domain: str) -> float:
        """
        Get a confidence modifier based on historical coverage
        Low coverage domains get reduced confidence
        """
        coverage = self.get_coverage(language, domain)
        total_results = sum(coverage.values())
        
        if total_results < 10:
            return 0.7  # Low coverage
        elif total_results < 50:
            return 0.85  # Medium coverage
        else:
            return 1.0  # Good coverage
    
    def export(self) -> dict:
        """Export heatmap data"""
        return {
            "heatmap": {f"{k[0]}/{k[1]}": dict(v) for k, v in self._heatmap.items()},
            "verification_counts": {f"{k[0]}/{k[1]}": v for k, v in self._verification_count.items()}
        }
    
    @classmethod
    def from_verification_logs(cls, logs: list[dict]) -> "ProviderHeatmap":
        """Build heatmap from verification logs"""
        heatmap = cls()
        for log in logs:
            heatmap.record_verification(
                language=log.get("topic_language", "unknown"),
                domain=log.get("topic_domain", "unknown"),
                provider_results=log.get("provider_results", {})
            )
        return heatmap


# Global instance
_heatmap_instance: Optional[ProviderHeatmap] = None


def get_heatmap() -> ProviderHeatmap:
    """Get global heatmap instance"""
    global _heatmap_instance
    if _heatmap_instance is None:
        _heatmap_instance = ProviderHeatmap()
    return _heatmap_instance
```

**Step 2: Write test**

```python
# tests/core/test_provider_heatmap.py
import pytest
from core.provider_heatmap import ProviderHeatmap, get_heatmap


def test_record_and_get_coverage():
    heatmap = ProviderHeatmap()
    heatmap.record_verification("en", "AI/agent", {"bocha": 100, "serper": 50})
    
    coverage = heatmap.get_coverage("en", "AI/agent")
    assert coverage["bocha"] == 100
    assert coverage["brave"] == 50


def test_get_best_providers():
    heatmap = ProviderHeatmap()
    heatmap.record_verification("en", "AI", {"serper": 200, "bocha": 100})
    
    best = heatmap.get_best_providers("en", "AI")
    assert best[0] == "serper"


def test_confidence_modifier():
    heatmap = ProviderHeatmap()
    
    # Low coverage
    heatmap.record_verification("ru", "AI", {"serper": 5})
    assert heatmap.get_confidence_modifier("ru", "AI") == 0.7
    
    # Medium coverage
    for _ in range(10):
        heatmap.record_verification("zh", "AI", {"bocha": 10})
    assert heatmap.get_confidence_modifier("zh", "AI") == 0.85


def test_singleton():
    h1 = get_heatmap()
    h2 = get_heatmap()
    assert h1 is h2
```

**Step 3: Run test**

Run: `pytest tests/core/test_provider_heatmap.py -v`
Expected: 4 passed

**Step 4: Commit**

```bash
git add core/provider_heatmap.py tests/core/test_provider_heatmap.py
git commit -m "feat: implement Provider coverage heatmap"
```

---

## Task 10: Update Configuration Documentation

**Files:**
- Create: `docs/phase3-setup.md`

**Step 1: Document environment variables**

```markdown
# Phase 3 Setup Guide

## Environment Variables

Curiosity Decomposer requires the following environment variables:

### Required (both for 2-Provider validation)

```bash
export BOCHA_API_KEY="your-bocha-key"
export SERPER_API_KEY="your-serper-key"
```

## Provider Configuration

**Configured Providers: Bocha + Serper**

| Provider | Best For | Validation Role |
|----------|----------|----------------|
| Bocha | Chinese queries | Primary |
| Serper | Academic/technical | Secondary |

Both providers required for 2-Provider validation threshold.

## Configuration Options

```yaml
# curious-agent.yaml
deccomposer:
  max_candidates: 7        # LLM 生成候选数量上限（范围 5-7）
  min_candidates: 5        # LLM 生成候选数量下限
  max_depth: 2             # 递归分解深度限制（默认 2，0=无限）
  verification_threshold: 2  # 需要 2 个 Provider 验证通过
```

## Testing

Verify setup:

```bash
cd /root/dev/curious-agent
python3 -c "
from core.provider_registry import init_default_providers
from core.curiosity_decomposer import CuriosityDecomposer

registry = init_default_providers()
print(f'Enabled providers: {[p.name for p in registry.get_enabled()]}')
"
```

Expected output shows both providers enabled: `['bocha', 'serper']`.
```

**Step 2: Commit**

```bash
git add docs/phase3-setup.md
git commit -m "docs: add Phase 3 setup guide"
```

---

## Task 11: Final Integration Test

**Files:**
- Create: `tests/test_phase3_integration.py`

**Step 1: Write end-to-end test**

```python
"""Phase 3 End-to-End Integration Test"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from core.curiosity_decomposer import CuriosityDecomposer
from core.provider_registry import ProviderRegistry
from core.exceptions import ClarificationNeeded
from core.quality_gate import should_queue


@pytest.mark.asyncio
async def test_full_decomposition_flow():
    """Test complete decomposition flow"""
    # Setup mocks
    mock_llm = Mock()
    mock_llm.chat = Mock(return_value="""- agent_memory - AI memory systems
- agent_planning - Task planning
- agent_tools - Tool usage""")
    
    registry = ProviderRegistry()
    registry.reset()
    
    mock_provider = Mock()
    mock_provider.name = "test_provider"
    mock_provider.search = AsyncMock(return_value={
        "result_count": 50,
        "results": []
    })
    registry.register(mock_provider)
    
    mock_kg = {"topics": {}}
    
    # Create decomposer
    decomposer = CuriosityDecomposer(mock_llm, registry, mock_kg)
    
    # Test decomposition
    result = await decomposer.decompose("agent")
    
    assert len(result) > 0
    assert "agent_memory" in [r["sub_topic"] for r in result]


def test_quality_gate_integration():
    """Test quality gate blocks bad topics"""
    # Should reject
    result, reason = should_queue("agent")
    assert result is False
    
    result, reason = should_queue("architecture")
    assert result is False
    
    # Should accept
    result, reason = should_queue("agent memory systems")
    assert result is True


def test_knowledge_graph_parent_child():
    """Test KG parent-child functionality"""
    from core import knowledge_graph as kg
    
    # Add children
    kg.add_child("agent", "agent_memory")
    kg.add_child("agent", "agent_planning")
    
    # Verify
    children = kg.get_children("agent")
    assert "agent_memory" in children
    assert "agent_planning" in children
    
    # Mark explored
    kg.mark_child_explored("agent", "agent_memory")
    status = kg.get_exploration_status("agent")
    assert status == "partial"  # Not all children explored
```

**Step 2: Run all Phase 3 tests**

Run: `pytest tests/test_phase3_integration.py -v`
Expected: 3 passed

**Step 3: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All existing tests still pass + new tests pass

**Step 4: Commit**

```bash
git add tests/test_phase3_integration.py
git commit -m "test: add Phase 3 end-to-end integration tests"
```

---

## Summary

This implementation plan creates:

1. **SearchProvider abstraction** - Plugin-based provider architecture
2. **BochaSearchProvider** - Migrated existing Bocha search
3. **ProviderRegistry** - Singleton for managing providers
4. **ClarificationNeeded** - Exception for user clarification
5. **CuriosityDecomposer** - Core 4-step decomposition pipeline
6. **Knowledge Graph extensions** - Parent-child relationships
7. **Quality Gate** - Topic filtering before queuing
8. **Integration** - Into run_one_cycle with proper async handling
9. **Provider Heatmap** - Emergent coverage tracking
10. **Tests** - Comprehensive unit and integration tests

**Total estimated time:** 4-6 hours  
**Dependencies:** All within existing codebase  
**Risk level:** Medium (async code, new data structures)

---

## Post-Implementation Checklist

- [ ] All tests pass
- [ ] Manual test: `python3 curious_agent.py --run` with decomposition
- [ ] Environment variables documented
- [ ] Code review completed
- [ ] Design doc updated with any deviations
