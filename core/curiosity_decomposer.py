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
                "sub_topic": candidate,
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
