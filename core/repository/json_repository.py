import json
import os
from datetime import datetime, timezone
from core.models.topic import Topic
from core.models.migration import migrate_state_v1_to_v2, detect_schema_version
from core.repository.base import KnowledgeRepository


class JSONKnowledgeRepository(KnowledgeRepository):
    def __init__(self, path="knowledge/state.json"):
        self.path = path
        self._cache = {}
        self._load()
    
    def _load(self):
        if not os.path.exists(self.path) or os.path.getsize(self.path) == 0:
            self._state = self._create_default_state()
            return
        
        with open(self.path, "r", encoding="utf-8") as f:
            raw_state = json.load(f)
        
        version = detect_schema_version(raw_state)
        if version == "1.0":
            raw_state = migrate_state_v1_to_v2(raw_state)
        
        self._state = raw_state
        
        self._cache = {}
        for name, data in self._state.get("knowledge", {}).get("topics", {}).items():
            try:
                data["name"] = name
                self._cache[name] = Topic.from_dict(data)
            except (KeyError, ValueError) as e:
                print(f"[Repository] Skipping corrupt topic '{name}': {e}")
                continue
    
    def _save(self):
        for name, topic in self._cache.items():
            self._state["knowledge"]["topics"][name] = topic.to_dict()
        
        self._state["last_update"] = datetime.now(timezone.utc).isoformat()
        
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)
    
    def get_topic(self, name):
        return self._cache.get(name)
    
    def save_topic(self, topic):
        self._cache[topic.name] = topic
        self._save()
    
    def get_all_topics(self):
        return list(self._cache.values())
    
    def add_relation(self, from_topic, to_topic, relation_type="associated"):
        if from_topic not in self._cache:
            self._cache[from_topic] = Topic(name=from_topic)
        if to_topic not in self._cache:
            self._cache[to_topic] = Topic(name=to_topic)
        
        from_t = self._cache[from_topic]
        to_t = self._cache[to_topic]
        
        from_t.add_child(to_topic)
        to_t.add_parent(from_topic)
        
        self._save()
    
    def get_neighbors(self, topic, relation_type=None):
        t = self._cache.get(topic)
        if not t:
            return []
        return t.children + t.parents
    
    def get_high_degree_unexplored(self):
        candidates = [
            (t.degree, name)
            for name, t in self._cache.items()
            if not t.fully_explored
        ]
        
        if not candidates:
            return None
        
        candidates.sort(key=lambda x: (-x[0], x[1]))
        return candidates[0][1]
    
    def get_storage_path(self):
        return self.path
    
    def _create_default_state(self):
        return {
            "version": "1.0",
            "schema_version": "2.0",
            "last_update": None,
            "knowledge": {"topics": {}},
            "curiosity_queue": [],
            "exploration_log": [],
            "config": {
                "curiosity_top_k": 3,
                "max_knowledge_nodes": 100,
                "notification_threshold": 7.0,
            },
        }
