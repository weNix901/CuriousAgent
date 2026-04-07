# tests/core/test_assertion_index.py
import pytest
import tempfile
import os
from core.assertion_index import AssertionIndex

class TestAssertionIndex:
    @pytest.fixture
    def index(self, tmp_path):
        """Create a fresh index for each test"""
        db_path = tmp_path / "test_assertions.db"
        return AssertionIndex(str(db_path))
    
    def test_init_creates_db(self, index):
        """Test that initialization creates the database"""
        assert index.db_path.exists()
        stats = index.get_stats()
        assert stats["total_assertions"] == 0
    
    def test_insert_and_retrieve(self, index):
        """Test inserting an assertion"""
        embedding = [0.1] * 768
        row_id = index.insert("Test assertion", embedding, topic="test", source_topic="source")
        
        assert row_id > 0
        stats = index.get_stats()
        assert stats["total_assertions"] == 1
    
    def test_insert_duplicate(self, index):
        """Test that duplicate assertions are not inserted twice"""
        embedding = [0.1] * 768
        row_id1 = index.insert("Duplicate test", embedding)
        row_id2 = index.insert("Duplicate test", embedding)
        
        assert row_id1 == row_id2  # Should return same ID
        stats = index.get_stats()
        assert stats["total_assertions"] == 1
    
    def test_search_similar(self, index):
        """Test searching for similar assertions"""
        embedding = [0.1] * 768
        index.insert("First assertion", embedding)
        
        results = index.search_similar(embedding, k=1, threshold=0.9)
        
        assert len(results) == 1
        assert results[0][0] == "First assertion"
        assert results[0][1] > 0.99
    
    def test_max_similarity(self, index):
        """Test getting max similarity"""
        embedding = [0.1] * 768
        index.insert("Test assertion", embedding)
        
        sim = index.max_similarity(embedding)
        
        assert sim > 0.99
    
    def test_empty_index(self, index):
        """Test behavior with empty index"""
        embedding = [0.1] * 768
        sim = index.max_similarity(embedding)
        
        assert sim == 0.0
        
        results = index.search_similar(embedding, k=1, threshold=0.0)
        assert len(results) == 0
    
    def test_similarity_threshold_filtering(self, index):
        """Test that threshold filters results"""
        emb1 = [0.1] * 768
        emb2 = [0.1] * 383 + [0.9] + [0.0] * 384
        
        index.insert("Assertion 1", emb1)
        
        results = index.search_similar(emb2, k=1, threshold=0.95)
        
        assert len(results) == 0
    
    def test_multiple_insertions(self, index):
        """Test inserting multiple assertions"""
        for i in range(10):
            embedding = [float(i) / 10.0] * 768
            index.insert(f"Assertion {i}", embedding)
        
        stats = index.get_stats()
        assert stats["total_assertions"] == 10
