"""DreamAgent - Creative dreaming agent with high/low priority queue handling.

Implements F7 (High-priority queue with 5s timeout) and F8 (Three-layer randomization)
from v0.2.6 optimizations.
"""
import queue
import random
import threading
import time
from typing import Optional

from core.base_agent import BaseAgent
from core import knowledge_graph as kg
from core.node_lock_registry import NodeLockRegistry


class DreamAgent(BaseAgent):
    """
    Creative dreaming agent that generates insights from distant topic pairs.
    
    Features:
    - High-priority queue from SpiderAgent (5s timeout with batching)
    - Low-priority round-robin polling with pointer
    - Three-layer randomization for distant pair selection
    - Creative insight generation via LLM
    - SharedInbox integration for SpiderAgent notification
    - Insight verification and quality decay tracking
    
    Three-Layer Randomization (F8):
    - 70% distance-based: Select pairs with maximum graph distance
    - 20% cross-domain: Select pairs from different parent branches
    - 10% neural noise: Pure random selection for serendipity
    
    Thread Safety:
    - All KG reads use NodeLockRegistry for node-level locking
    - Uses queue.Queue for thread-safe SpiderAgent notification
    """
    
    HIGH_PRIORITY_TIMEOUT_SECONDS = 5  # F7: 5s timeout (not 60s)
    HIGH_PRIORITY_BATCH_SIZE = 5       # F7: Batch up to 5 items
    DISTANCE_WEIGHT = 0.70             # F8: Three-layer randomization weights
    CROSS_DOMAIN_WEIGHT = 0.20
    NEURAL_NOISE_WEIGHT = 0.10
    QUALITY_THRESHOLD = 0.5
    QUALITY_DECAY_RATE = 0.1
    STALE_THRESHOLD_DAYS = 7
    
    def __init__(
        self,
        name: str = "DreamAgent",
        high_priority_queue: Optional[queue.Queue] = None,
        poll_interval: float = 1.0,
        llm_client=None
    ):
        """
        Initialize DreamAgent.
        
        Args:
            name: Thread name for debugging
            high_priority_queue: Queue for high-priority items from SpiderAgent
            poll_interval: Seconds to wait between low-priority polls
            llm_client: LLM client for insight generation
        """
        super().__init__(name=name)
        
        self.high_priority_queue = high_priority_queue
        self.poll_interval = poll_interval
        
        if llm_client is None:
            from core.llm_client import LLMClient
            self.llm = LLMClient()
        else:
            self.llm = llm_client
        
        self._low_priority_pointer = 0
        self._low_priority_pointer_lock = threading.Lock()
        
        self._recently_processed: list[str] = []
        self._recently_processed_lock = threading.Lock()
        
        self._insights_generated = 0
        self._insights_verified = 0
        self._high_priority_processed = 0
        self._low_priority_processed = 0
    
    def run(self):
        """
        Main loop: process high-priority queue, then low-priority round-robin.
        
        Loop continues until running flag is set to False via stop().
        """
        while self.running:
            try:
                processed_high = self._process_high_priority_batch()
                if not processed_high:
                    self._process_low_priority_cycle()
            except Exception as e:
                print(f"[DreamAgent] Error in dream cycle: {e}")
            
            self.yield_to_other()
            time.sleep(self.poll_interval)
    
    def _process_high_priority_batch(self) -> bool:
        """
        Process high-priority queue with 5s timeout and batching (F7).
        
        Collects up to HIGH_PRIORITY_BATCH_SIZE items within timeout,
        then processes them together for efficiency.
        
        Returns:
            True if any items were processed, False otherwise
        """
        if self.high_priority_queue is None:
            return False
        
        batch = []
        deadline = time.time() + self.HIGH_PRIORITY_TIMEOUT_SECONDS
        
        while len(batch) < self.HIGH_PRIORITY_BATCH_SIZE and self.running:
            remaining_time = deadline - time.time()
            if remaining_time <= 0:
                break

            try:
                item = self.high_priority_queue.get(timeout=min(remaining_time, 0.1))
                batch.append(item)
            except queue.Empty:
                break
        
        if not batch:
            return False
        
        for item in batch:
            self._process_high_priority_item(item)
            self._high_priority_processed += 1
        
        return True
    
    def _process_high_priority_item(self, item: dict):
        """
        Process a single high-priority item from SpiderAgent.
        
        Args:
            item: Dict with 'type', 'topic', 'findings', etc.
        """
        item_type = item.get("type", "unknown")
        topic = item.get("topic", "")
        
        if item_type == "exploration_complete":
            kg.mark_dreamed(topic)
            self._generate_insight_with_distant_pair(topic, item.get("findings", ""))
    
    def _process_low_priority_cycle(self):
        """
        Process low-priority items using round-robin polling.
        
        Uses a pointer to cycle through available topics fairly.
        """
        all_nodes = kg.get_all_nodes(active_only=True)
        
        if not all_nodes:
            return
        
        recently_dreamed = kg.get_recently_dreamed(within_days=3)
        candidates = [
            (name, data) for name, data in all_nodes
            if name not in recently_dreamed
            and data.get("status") != "dormant"
        ]
        
        if not candidates:
            return
        
        with self._low_priority_pointer_lock:
            if self._low_priority_pointer >= len(candidates):
                self._low_priority_pointer = 0
            
            selected_index = self._low_priority_pointer
            self._low_priority_pointer += 1
        
        topic, topic_data = candidates[selected_index]
        
        with self._recently_processed_lock:
            if topic in self._recently_processed:
                return
            self._recently_processed.append(topic)
            if len(self._recently_processed) > 100:
                self._recently_processed = self._recently_processed[-100:]
        
        self._generate_insight_with_distant_pair(topic, topic_data.get("summary", ""))
        self._low_priority_processed += 1
    
    def _generate_insight_with_distant_pair(self, topic: str, findings: str):
        """
        Generate insight by combining topic with a distant pair.
        
        Uses three-layer randomization (F8) to select the distant pair.
        
        Args:
            topic: Primary topic
            findings: Findings from the topic
        """
        distant_topic = self._select_distant_pair(topic)
        
        if distant_topic is None:
            return
        
        distant_data = self._get_topic_data(distant_topic)
        insight = self._generate_creative_insight(topic, findings, distant_topic, distant_data)
        
        if insight is None:
            return
        
        if insight.get("quality", 0) >= self.QUALITY_THRESHOLD:
            node_id = kg.add_dream_insight(
                content=insight.get("content", ""),
                insight_type=insight.get("type", "creative"),
                source_topics=[topic, distant_topic],
                surprise=insight.get("surprise", 0.5),
                novelty=insight.get("novelty", 0.5),
                trigger_topic=topic
            )
            
            self._notify_spider_agent(topic, distant_topic, insight)
            
            self._insights_generated += 1
    
    def _select_distant_pair(self, topic: str) -> Optional[str]:
        """
        Select a distant topic pair using three-layer randomization (F8).
        
        Three layers:
        - 70% distance-based: Maximum graph distance
        - 20% cross-domain: Different parent branches
        - 10% neural noise: Pure random
        
        Args:
            topic: Primary topic to find distant pair for
            
        Returns:
            Name of distant topic, or None if no candidates
        """
        all_nodes = kg.get_all_nodes(active_only=True)
        candidates = [name for name, _ in all_nodes if name != topic]
        
        if not candidates:
            return None
        
        roll = random.random()
        
        if roll < self.DISTANCE_WEIGHT:
            return self._select_by_distance(topic, candidates)
        elif roll < self.DISTANCE_WEIGHT + self.CROSS_DOMAIN_WEIGHT:
            return self._select_cross_domain(topic, candidates)
        else:
            return random.choice(candidates)
    
    def _select_by_distance(self, topic: str, candidates: list[str]) -> str:
        """
        Select topic with maximum graph distance from primary topic.
        
        Args:
            topic: Primary topic
            candidates: List of candidate topics
            
        Returns:
            Topic with maximum distance
        """
        max_distance = -1
        best_candidate = candidates[0] if candidates else None
        
        for candidate in candidates:
            distance = kg.get_shortest_path_length(topic, candidate)
            if distance > max_distance:
                max_distance = distance
                best_candidate = candidate
        
        return best_candidate
    
    def _select_cross_domain(self, topic: str, candidates: list[str]) -> str:
        """
        Select topic from a different parent branch (cross-domain).
        
        Args:
            topic: Primary topic
            candidates: List of candidate topics
            
        Returns:
            Topic from different domain
        """
        topic_parents = self._get_topic_parents(topic)
        
        cross_domain_candidates = []
        for candidate in candidates:
            candidate_parents = self._get_topic_parents(candidate)
            if not topic_parents.intersection(candidate_parents):
                cross_domain_candidates.append(candidate)
        
        if cross_domain_candidates:
            return random.choice(cross_domain_candidates)
        
        return random.choice(candidates)
    
    def _get_topic_parents(self, topic: str) -> set[str]:
        """
        Get parent topics for a given topic.
        
        Args:
            topic: Topic to get parents for
            
        Returns:
            Set of parent topic names
        """
        with NodeLockRegistry.global_write_lock():
            state = kg._load_state()
            topics = state.get("knowledge", {}).get("topics", {})
            if topic in topics:
                return set(topics[topic].get("parents", []))
            return set()
    
    def _get_topic_data(self, topic: str) -> dict:
        """
        Get data for a topic.
        
        Args:
            topic: Topic to get data for
            
        Returns:
            Topic data dictionary
        """
        with NodeLockRegistry.global_write_lock():
            state = kg._load_state()
            topics = state.get("knowledge", {}).get("topics", {})
            return topics.get(topic, {})
    
    def _generate_creative_insight(
        self,
        topic_a: str,
        findings_a: str,
        topic_b: str,
        data_b: dict
    ) -> Optional[dict]:
        """
        Generate creative insight by combining two distant topics via LLM.
        
        Args:
            topic_a: First topic
            findings_a: Findings from first topic
            topic_b: Second topic
            data_b: Data from second topic
            
        Returns:
            Insight dictionary with content, quality, surprise, novelty
        """
        prompt = f"""You are a creative AI research synthesizer. Generate a novel insight by combining two seemingly unrelated topics.

Topic A: {topic_a}
Findings A: {findings_a[:500] if findings_a else 'No specific findings'}

Topic B: {topic_b}
Findings B: {data_b.get('summary', 'No specific findings')[:500]}

Task: Find a creative connection or insight that bridges these two topics. Think outside the box - look for:
1. Unexpected analogies or metaphors
2. Shared underlying principles
3. Potential cross-pollination of ideas
4. Novel hypotheses that combine both domains

Output JSON format:
{{
  "content": "The creative insight content (2-3 sentences)",
  "type": "analogy|principle|hypothesis|connection",
  "reasoning": "Why this connection makes sense",
  "surprise": <0.0-1.0 score of how unexpected this insight is>,
  "novelty": <0.0-1.0 score of how novel this insight is>,
  "quality": <0.0-1.0 score of overall insight quality>
}}

Quality criteria:
- Insights should be non-obvious (not just "both are related to AI")
- Should provide actionable or thought-provoking value
- Should have clear reasoning connecting the topics
"""
        
        try:
            response = self.llm.chat(prompt)
            return self._parse_insight_response(response)
        except Exception as e:
            print(f"[DreamAgent] Insight generation failed: {e}")
            return None
    
    def _parse_insight_response(self, response: str) -> Optional[dict]:
        """
        Parse LLM response into insight dictionary.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Parsed insight dictionary or None
        """
        import json
        import re
        
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                
                if "content" not in data:
                    return None
                
                data.setdefault("type", "creative")
                data.setdefault("reasoning", "")
                data.setdefault("surprise", 0.5)
                data.setdefault("novelty", 0.5)
                data.setdefault("quality", 0.5)
                
                return data
        except (json.JSONDecodeError, AttributeError) as e:
            print(f"[DreamAgent] Failed to parse insight: {e}")
        
        return None
    
    def _notify_spider_agent(self, topic_a: str, topic_b: str, insight: dict):
        """
        Notify SpiderAgent of new insight via SharedInbox.
        
        Args:
            topic_a: First topic
            topic_b: Second topic
            insight: Generated insight
        """
        insight_summary = insight.get("content", "")[:200]
        
        kg.add_to_dream_inbox(topic_a, f"Dream insight: {insight_summary}")
        kg.add_to_dream_inbox(topic_b, f"Dream insight: {insight_summary}")
    
    def verify_insight(self, node_id: str) -> bool:
        """
        Verify an insight by checking if it led to valuable exploration.
        
        Args:
            node_id: Insight node ID to verify
            
        Returns:
            True if insight was verified as valuable
        """
        insights = kg.get_dream_insights()
        insight = next((i for i in insights if i.get("node_id") == node_id), None)
        
        if insight is None:
            return False
        
        source_topics = insight.get("source_topics", [])
        for topic in source_topics:
            if kg.has_recent_dreams(topic, within_days=3):
                kg.update_insight_weight(node_id, delta=0.1)
                kg.update_insight_quality(node_id, delta=0.1)
                self._insights_verified += 1
                return True
        
        return False
    
    def apply_quality_decay(self):
        """
        Apply quality decay to unverified insights.
        
        Insights that haven't been verified lose quality over time.
        """
        insights = kg.get_dream_insights()
        
        for insight in insights:
            node_id = insight.get("node_id")
            
            if insight.get("verified", False):
                continue
            
            if kg.is_insight_stale(node_id):
                kg.update_insight_quality(node_id, delta=-self.QUALITY_DECAY_RATE)
    
    def get_status(self) -> dict:
        """
        Get current status of the DreamAgent.
        
        Returns:
            Dictionary with current state information
        """
        return {
            "running": self.running,
            "high_priority_timeout_seconds": self.HIGH_PRIORITY_TIMEOUT_SECONDS,
            "high_priority_batch_size": self.HIGH_PRIORITY_BATCH_SIZE,
            "poll_interval": self.poll_interval,
            "low_priority_pointer": self._low_priority_pointer,
            "insights_generated": self._insights_generated,
            "insights_verified": self._insights_verified,
            "high_priority_processed": self._high_priority_processed,
            "low_priority_processed": self._low_priority_processed,
            "quality_threshold": self.QUALITY_THRESHOLD,
            "randomization_weights": {
                "distance": self.DISTANCE_WEIGHT,
                "cross_domain": self.CROSS_DOMAIN_WEIGHT,
                "neural_noise": self.NEURAL_NOISE_WEIGHT
            }
        }
