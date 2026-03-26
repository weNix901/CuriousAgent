import pytest
import tempfile
import os
from core.repository.json_repository import JSONKnowledgeRepository
from core.models.topic import Topic


class TestJSONRepository:
    @pytest.fixture
    def repo(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            path = f.name
        
        repo = JSONKnowledgeRepository(path)
        yield repo
        
        if os.path.exists(path):
            os.remove(path)
    
    def test_get_topic_nonexistent(self, repo):
        result = repo.get_topic("nonexistent")
        assert result is None
    
    def test_save_and_get_topic(self, repo):
        topic = Topic(name="attention", known=True, depth=5.0)
        
        repo.save_topic(topic)
        result = repo.get_topic("attention")
        
        assert result is not None
        assert result.name == "attention"
        assert result.known is True
        assert result.depth == 5.0
    
    def test_add_relation_creates_topics(self, repo):
        repo.add_relation("parent", "child", "parent_child")
        
        parent = repo.get_topic("parent")
        child = repo.get_topic("child")
        
        assert parent is not None
        assert child is not None
        assert "child" in parent.children
        assert "parent" in child.parents
    
    def test_get_high_degree_unexplored(self, repo):
        repo.add_relation("A", "B")
        repo.add_relation("A", "C")
        
        result = repo.get_high_degree_unexplored()
        
        assert result == "A"
    
    def test_get_high_degree_skips_fully_explored(self, repo):
        repo.add_relation("A", "B")
        repo.add_relation("C", "D")
        repo.add_relation("C", "E")
        
        topic_a = repo.get_topic("A")
        topic_a.mark_fully_explored()
        repo.save_topic(topic_a)
        
        result = repo.get_high_degree_unexplored()
        
        assert result == "C"
