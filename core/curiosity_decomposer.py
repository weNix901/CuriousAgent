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
        """Main entry: decompose topic into sub-topics with cascade fallback"""
        candidates = await self._llm_generate_candidates(topic)
        
        if not candidates:
            raise ClarificationNeeded(topic, reason="LLM generated no candidates")
        
        verified = await self._verify_with_providers(candidates)
        
        if not verified:
            verified = await self._cascade_fallback(topic, candidates)
        
        if not verified:
            raise ClarificationNeeded(
                topic=topic,
                reason="no candidates passed provider validation"
            )
        
        enriched = self._kg_augment(topic, verified)
        return enriched
    
    async def _cascade_fallback(self, topic: str, original_candidates: list[str]) -> list[dict]:
        """3-level cascade fallback when all candidates fail validation"""
        broad_candidates = await self._llm_generate_candidates(topic, style="broad")
        if broad_candidates:
            verified = await self._verify_with_providers(broad_candidates)
            if verified:
                return verified
        
        verified = await self._verify_with_providers_relaxed(original_candidates)
        if verified:
            return verified
        
        kg_candidates = self._get_kg_fallback_candidates(topic)
        if kg_candidates:
            return [{"sub_topic": c, "verified": True, "source": "kg_fallback"} for c in kg_candidates]
        
        if original_candidates:
            best = max(original_candidates, key=len)
            return [{
                "sub_topic": best,
                "verified": True,
                "source": "unverified_fallback",
                "signal_strength": "weak"
            }]
        
        return []
    
    def _get_kg_children(self, topic: str) -> list[str]:
        try:
            return self.kg.get("topics", {}).get(topic, {}).get("children", [])
        except (AttributeError, TypeError):
            return []

    def _get_kg_fallback_candidates(self, topic: str) -> list[str]:
        """
        获取 KG 中的备选 candidates。

        策略（按优先级）：
        1. 使用该 topic 的 children（如果存在）
        2. 使用该 topic 的 parents 的其他 children（兄弟姐妹）
        3. 使用与该 topic 有 citation 关系的 topics

        Fix #10: 修复原来的逻辑只使用 children，导致新 topic 无法触发 fallback。
        """
        candidates = []

        # 1. 尝试获取该 topic 的 children
        try:
            children = self.kg.get("topics", {}).get(topic, {}).get("children", [])
            candidates.extend(children)
        except (AttributeError, TypeError):
            pass

        if candidates:
            return candidates

        # 2. 尝试获取 parents 的其他 children（兄弟姐妹）
        try:
            topic_data = self.kg.get("topics", {}).get(topic, {})
            parents = topic_data.get("parents", [])
            for parent in parents:
                parent_data = self.kg.get("topics", {}).get(parent, {})
                siblings = parent_data.get("children", [])
                for sibling in siblings:
                    if sibling != topic and sibling not in candidates:
                        candidates.append(sibling)
        except (AttributeError, TypeError):
            pass

        if candidates:
            return candidates

        # 3. 尝试获取 citation 相关的 topics
        try:
            topic_data = self.kg.get("topics", {}).get(topic, {})
            cites = topic_data.get("cites", [])
            cited_by = topic_data.get("cited_by", [])
            for t in cites + cited_by:
                if t not in candidates:
                    candidates.append(t)
        except (AttributeError, TypeError):
            pass

        return candidates
    
    async def _llm_generate_candidates(self, topic: str, style: str = "default") -> list[str]:
        """Step 1: Use LLM to generate candidate sub-topics"""
        max_c = self.config.get("max_candidates", 7)
        min_c = self.config.get("min_candidates", 5)
        
        if style == "broad":
            prompt = f"""针对 "{topic}" 这个话题，列出更宽泛、更常见的子领域或相关概念。

粒度要求：每个子 topic 应该是该领域的经典分类或主流分支。
- ✅ 好例子："强化学习基础"、"神经网络架构设计"、"Agent 记忆系统"
- ❌ 坏例子："AlphaFold"（太具体，不是一个分类）、"优化算法进展"（太窄偏研究细项）

要求：
- 列出 {min_c}-{max_c} 个常见的、易于搜索的子话题
- 使用通俗易懂的术语，避免过于学术化的表达
- 每个格式：[子话题名称] - [一句话说明]

输出格式（直接输出列表）：
- topic1 - 说明1
- topic2 - 说明2
- topic3 - 说明3"""
        else:
            prompt = f"""针对 "{topic}" 这个话题，识别它最常见的子领域或组成部分。

粒度要求：每个子 topic 应该是可独立探索的窄问题。
- ✅ 好例子："ReAct prompting techniques"、"Experience replay buffer implementation"、"Self-reflection in LLM agents"
- ❌ 坏例子："Machine Learning"（太宽，是领域不是子问题）、"Q-learning vs DQN对比"（这是对比研究不是子 topic）

要求：
- 列出 {min_c}-{max_c} 个子话题
- 每个格式：[子话题名称] - [一句话说明]
- 优先技术领域相关的子话题

输出格式（直接输出列表）：
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
    
    async def _verify_with_providers_relaxed(self, candidates: list[str]) -> list[dict]:
        """Verify with relaxed threshold (1 provider or total >= 5)"""
        if not candidates:
            return []
        
        tasks = [self._verify_single_relaxed(c) for c in candidates]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid = []
        for r in results:
            if isinstance(r, Exception):
                continue
            if r and r.get("verified", False):
                valid.append(r)
        
        return valid
    
    async def _verify_single_relaxed(self, candidate: str) -> Optional[dict]:
        """Verify with relaxed threshold: 1 provider OR total >= 5"""
        enabled = self.providers.get_enabled()
        
        if not enabled:
            return {
                "sub_topic": candidate,
                "candidate": candidate,
                "provider_results": {},
                "total_count": 0,
                "provider_count": 0,
                "signal_strength": "unknown",
                "verified": True
            }
        
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
        
        return {
            "sub_topic": candidate,
            "candidate": candidate,
            "provider_results": provider_results,
            "total_count": total,
            "provider_count": count,
            "signal_strength": self._classify_signal(count, total),
            "verified": verified
        }
    
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

    def decompose_and_write(self, topic: str) -> list[dict]:
        """decompose + write to KG unified entry."""
        import asyncio
        import threading

        try:
            asyncio.get_running_loop()
            result_holder = []

            def _run_in_thread():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result_holder.append(loop.run_until_complete(self.decompose(topic)))
                finally:
                    loop.close()

            t = threading.Thread(target=_run_in_thread)
            t.start()
            t.join()
            subtopics = result_holder[0] if result_holder else []

        except RuntimeError:
            subtopics = asyncio.run(self.decompose(topic))

        if not subtopics:
            return []

        from core import knowledge_graph as kg
        kg.update_curiosity_status(topic, "exploring")

        for sibling in subtopics:
            s_topic = sibling["sub_topic"]
            s_strength = sibling.get("signal_strength", "unknown")
            s_relevance = 7.0 if s_strength == "strong" else (6.0 if s_strength == "medium" else 5.0)
            s_depth = 6.0 if s_strength == "strong" else (5.5 if s_strength == "medium" else 5.0)

            kg.add_child(topic, s_topic)
            kg.add_curiosity(
                topic=s_topic,
                reason=f"Decomposed from: {topic}",
                relevance=float(s_relevance),
                depth=float(s_depth),
                original_topic=topic
            )

        return subtopics
