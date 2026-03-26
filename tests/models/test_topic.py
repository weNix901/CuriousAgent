import pytest
from datetime import datetime


class TestTopicCreation:
    def test_create_topic_with_name(self):
        from core.models.topic import Topic
        
        topic = Topic(name="attention mechanism")
        assert topic.name == "attention mechanism"
        assert topic.known is False
        assert topic.depth == 0.0
    
    def test_topic_default_values(self):
        from core.models.topic import Topic
        
        topic = Topic(name="test")
        assert topic.parents == []
        assert topic.children == []
        assert topic.relations == []
        assert topic.explored_by == []
        assert topic.fully_explored is False
        assert topic.schema_version == "2.0"
    
    def test_topic_to_dict(self):
        from core.models.topic import Topic
        
        topic = Topic(
            name="attention",
            known=True,
            depth=5.0,
            parents=["transformer"],
            children=["self-attention"],
        )
        data = topic.to_dict()
        
        assert data["name"] == "attention"
        assert data["known"] is True
        assert data["depth"] == 5.0
        assert data["parents"] == ["transformer"]
        assert data["children"] == ["self-attention"]
        assert data["schema_version"] == "2.0"
    
    def test_topic_from_dict(self):
        from core.models.topic import Topic
        
        data = {
            "name": "attention",
            "known": True,
            "depth": 5.0,
            "parents": ["transformer"],
            "children": ["self-attention"],
            "relations": [],
            "explored_by": [],
            "fully_explored": False,
            "created_at": datetime.now().isoformat(),
            "schema_version": "2.0",
        }
        topic = Topic.from_dict(data)
        
        assert topic.name == "attention"
        assert topic.known is True
        assert topic.parents == ["transformer"]


class TestTopicGraphOperations:
    def test_add_parent(self):
        from core.models.topic import Topic
        
        topic = Topic(name="child")
        topic.add_parent("parent")
        
        assert "parent" in topic.parents
        assert topic.parents == ["parent"]
    
    def test_add_parent_deduplication(self):
        from core.models.topic import Topic
        
        topic = Topic(name="child")
        topic.add_parent("parent")
        topic.add_parent("parent")
        
        assert topic.parents == ["parent"]
    
    def test_add_child(self):
        from core.models.topic import Topic
        
        topic = Topic(name="parent")
        topic.add_child("child")
        
        assert "child" in topic.children
    
    def test_mark_explored(self):
        from core.models.topic import Topic
        
        topic = Topic(name="test")
        topic.mark_explored(by="parent_topic")
        
        assert topic.known is True
        assert topic.explored is True
        assert "parent_topic" in topic.explored_by
        assert topic.explored_at is not None
    
    def test_mark_fully_explored(self):
        from core.models.topic import Topic
        
        topic = Topic(name="test")
        topic.mark_fully_explored()
        
        assert topic.fully_explored is True
        assert topic.status == "complete"
        assert topic.fully_explored_at is not None
    
    def test_degree_calculation(self):
        from core.models.topic import Topic
        
        topic = Topic(
            name="test",
            parents=["p1", "p2"],
            children=["c1"],
        )
        
        assert topic.degree == 3


class TestRelation:
    def test_create_relation(self):
        from core.models.topic import Relation
        
        relation = Relation(
            from_topic="A",
            to_topic="B",
            relation_type="associated"
        )
        
        assert relation.from_topic == "A"
        assert relation.to_topic == "B"
        assert relation.relation_type == "associated"
