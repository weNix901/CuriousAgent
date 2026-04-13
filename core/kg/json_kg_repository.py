"""JSON-backed KG Repository for knowledge graph operations."""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class JSONKGRepository:
    """JSON file-backed Knowledge Graph Repository."""

    def __init__(self, state_file: str = "knowledge/state.json"):
        self._state_file = Path(state_file)
        self._lock = threading.RLock()
        self._state: Optional[dict] = None

    def _load(self) -> dict:
        """Load state from JSON file."""
        if self._state is None:
            if self._state_file.exists():
                with open(self._state_file, "r", encoding="utf-8") as f:
                    self._state = json.load(f)
            else:
                self._state = {
                    "knowledge": {"topics": {}},
                    "curiosity_queue": [],
                    "exploration_log": [],
                    "last_update": datetime.now(timezone.utc).isoformat()
                }
        return self._state

    def _save(self, state: dict = None) -> None:
        """Save state to JSON file."""
        if state is None:
            state = self._state
        state["last_update"] = datetime.now(timezone.utc).isoformat()
        with open(self._state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    def _ensure_meta(self) -> dict:
        """Ensure meta_cognitive structure exists."""
        state = self._load()
        if "meta_cognitive" not in state:
            state["meta_cognitive"] = {
                "exploration_log": [],
                "topic_quality": {},
                "marginal_returns": {},
                "last_quality": {}
            }
        return state

    # ========== Node Operations ==========

    def get_node(self, topic: str) -> Optional[Dict[str, Any]]:
        """Get a single node by exact topic match."""
        state = self._load()
        topics = state.get("knowledge", {}).get("topics", {})
        node = topics.get(topic)
        if node:
            return {
                "topic": topic,
                "content": node.get("summary", ""),
                "status": node.get("status", "pending"),
                "quality": node.get("quality", 0.0),
                "confidence": node.get("confidence", 0.0),
                "heat": node.get("heat", 0),
                "source_urls": node.get("source_urls", [])
            }
        return None

    def create_knowledge_node(
        self,
        topic: str,
        content: str = "",
        source_urls: List[str] = None,
        relations: List[Dict[str, str]] = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Create or update a knowledge node."""
        source_urls = source_urls or []
        relations = relations or []
        metadata = metadata or {}

        state = self._load()
        if "knowledge" not in state:
            state["knowledge"] = {"topics": {}}
        if "topics" not in state["knowledge"]:
            state["knowledge"]["topics"] = {}

        topic_data = state["knowledge"]["topics"].get(topic, {})
        topic_data.update({
            "summary": content,
            "source_urls": source_urls,
            "heat": metadata.get("heat", topic_data.get("heat", 0)),
            "quality": metadata.get("quality", topic_data.get("quality", 0.0)),
            "confidence": metadata.get("confidence", topic_data.get("confidence", 0.0)),
            "status": metadata.get("status", topic_data.get("status", "pending")),
            "last_updated": datetime.now(timezone.utc).isoformat()
        })
        state["knowledge"]["topics"][topic] = topic_data

        # Handle relations
        for rel in relations:
            parent = rel.get("parent", "")
            rel_type = rel.get("type", "derived_from")
            if parent:
                self.add_relation(parent, topic, rel_type)

        self._save(state)
        return topic

    def query_knowledge(
        self,
        topic: str,
        limit: int = 10,
        include_relations: bool = False
    ) -> List[Dict[str, Any]]:
        """Query knowledge nodes by topic substring match."""
        state = self._load()
        topics = state.get("knowledge", {}).get("topics", {})
        results = []
        topic_lower = topic.lower()

        for name, data in topics.items():
            if topic_lower in name.lower() or name.lower() in topic_lower:
                results.append({
                    "topic": name,
                    "content": data.get("summary", ""),
                    "status": data.get("status", "unknown"),
                    "heat": data.get("heat", 0),
                    "quality": data.get("quality", 0.0),
                    "confidence": data.get("confidence", 0.0)
                })
                if len(results) >= limit:
                    break

        return results

    def update_status(self, topic: str, status: str) -> bool:
        """Update node status."""
        state = self._load()
        topics = state.get("knowledge", {}).get("topics", {})
        if topic in topics:
            topics[topic]["status"] = status
            topics[topic]["last_updated"] = datetime.now(timezone.utc).isoformat()
            self._save(state)
            return True
        return False

    def update_metadata(
        self,
        topic: str,
        heat: Optional[int] = None,
        quality: Optional[float] = None,
        confidence: Optional[float] = None
    ) -> bool:
        """Update node metadata fields."""
        state = self._load()
        topics = state.get("knowledge", {}).get("topics", {})
        if topic not in topics:
            return False

        if heat is not None:
            topics[topic]["heat"] = heat
        if quality is not None:
            topics[topic]["quality"] = quality
        if confidence is not None:
            topics[topic]["confidence"] = confidence

        topics[topic]["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._save(state)
        return True

    def mark_dormant(self, topic: str) -> bool:
        """Mark a node as dormant."""
        return self.update_status(topic, "dormant")

    def reactivate(self, topic: str) -> bool:
        """Reactivate a dormant node."""
        return self.update_status(topic, "pending")

    # ========== Relation Operations ==========

    def add_relation(
        self,
        from_topic: str,
        to_topic: str,
        relation_type: str = "derived_from"
    ) -> bool:
        """Create a relation between two topics."""
        if not from_topic or not to_topic:
            return False

        state = self._load()
        topics = state.get("knowledge", {}).get("topics", {})

        # Ensure relations structure exists
        if "relations" not in state["knowledge"]:
            state["knowledge"]["relations"] = {}

        key = f"{from_topic}|{to_topic}"
        state["knowledge"]["relations"][key] = {
            "from": from_topic,
            "to": to_topic,
            "type": relation_type,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        self._save(state)
        return True

    def get_relations(self, topic: str) -> List[Dict[str, str]]:
        """Get all relations for a topic."""
        state = self._load()
        relations = state.get("knowledge", {}).get("relations", {})
        results = []

        for key, rel in relations.items():
            if rel.get("from") == topic or rel.get("to") == topic:
                results.append({
                    "related_topic": rel.get("to") if rel.get("from") == topic else rel.get("from"),
                    "relation_type": rel.get("type", "unknown"),
                    "direction": "outgoing" if rel.get("from") == topic else "incoming"
                })

        return results

    def get_children(self, topic: str) -> List[str]:
        """Get all child topics."""
        state = self._load()
        relations = state.get("knowledge", {}).get("relations", {})
        children = []

        for rel in relations.values():
            if rel.get("from") == topic and rel.get("type") == "derived_from":
                children.append(rel.get("to"))

        return children

    def get_parents(self, topic: str) -> List[str]:
        """Get all parent topics."""
        state = self._load()
        relations = state.get("knowledge", {}).get("relations", {})
        parents = []

        for rel in relations.values():
            if rel.get("to") == topic and rel.get("type") == "derived_from":
                parents.append(rel.get("from"))

        return parents

    # ========== Query Operations ==========

    def get_pending_topics(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending topics sorted by priority."""
        state = self._load()
        topics = state.get("knowledge", {}).get("topics", {})
        pending = []

        for name, data in topics.items():
            if data.get("status") == "pending":
                pending.append({
                    "topic": name,
                    "heat": data.get("heat", 0),
                    "quality": data.get("quality", 0.0)
                })

        # Sort by heat DESC, quality DESC
        pending.sort(key=lambda x: (-x.get("heat", 0), -x.get("quality", 0)))
        return pending[:limit]

    def get_all_nodes(self, active_only: bool = False) -> List[tuple]:
        """Get all nodes as (topic, data) tuples."""
        state = self._load()
        topics = state.get("knowledge", {}).get("topics", {})

        if active_only:
            return [(n, d) for n, d in topics.items() if d.get("status") == "active"]
        return [(n, d) for n, d in topics.items()]

    def get_topic_count(self) -> int:
        """Get total number of topics."""
        state = self._load()
        return len(state.get("knowledge", {}).get("topics", {}))

    # ========== Meta Cognitive Operations ==========

    def record_exploration(self, topic: str, quality: float, marginal_return: float) -> None:
        """Record exploration result for meta-cognitive tracking."""
        state = self._ensure_meta()
        mc = state["meta_cognitive"]

        if "exploration_log" not in mc:
            mc["exploration_log"] = []
        mc["exploration_log"].append({
            "topic": topic,
            "quality": quality,
            "marginal_return": marginal_return,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        # Keep last 1000 entries
        mc["exploration_log"] = mc["exploration_log"][-1000:]

        mc["topic_quality"] = mc.get("topic_quality", {})
        mc["topic_quality"][topic] = quality

        mc["marginal_returns"] = mc.get("marginal_returns", {})
        if topic not in mc["marginal_returns"]:
            mc["marginal_returns"][topic] = []
        mc["marginal_returns"][topic].append(marginal_return)
        mc["marginal_returns"][topic] = mc["marginal_returns"][topic][-100:]

        self._save(state)

    def get_topic_explore_count(self, topic: str) -> int:
        """Get how many times a topic has been explored."""
        state = self._ensure_meta()
        mc = state["meta_cognitive"]
        exploration_log = mc.get("exploration_log", [])
        return sum(1 for e in exploration_log if e.get("topic") == topic)

    def get_marginal_returns(self, topic: str) -> List[float]:
        """Get marginal returns history for a topic."""
        state = self._ensure_meta()
        mc = state["meta_cognitive"]
        return mc.get("marginal_returns", {}).get(topic, [])
