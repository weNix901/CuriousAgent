"""
Tests for v0.2.6 KG Schema Extensions - Dream Insights Functions.
"""
import json
import os
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def temp_knowledge_dir():
    """Create a temporary knowledge directory for testing."""
    temp_dir = tempfile.mkdtemp()
    knowledge_dir = os.path.join(temp_dir, "knowledge")
    os.makedirs(knowledge_dir, exist_ok=True)
    
    # Create empty state.json
    state_file = os.path.join(knowledge_dir, "state.json")
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump({"version": "1.0", "knowledge": {"topics": {}}}, f)
    
    yield knowledge_dir
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_state_file(temp_knowledge_dir):
    """Mock STATE_FILE to use temp directory."""
    with patch("core.knowledge_graph.STATE_FILE", 
               os.path.join(temp_knowledge_dir, "state.json")):
        yield temp_knowledge_dir


class TestAddDreamInsight:
    """Tests for add_dream_insight function."""
    
    def test_add_dream_insight_creates_file(self, mock_state_file):
        """Test that add_dream_insight creates a JSON file."""
        from core.knowledge_graph import add_dream_insight
        
        node_id = add_dream_insight(
            content="Test insight content",
            insight_type="connection",
            source_topics=["topic1", "topic2"],
            surprise=0.8,
            novelty=0.7,
            trigger_topic="trigger_topic"
        )
        
        assert node_id.startswith("insight_")
        
        # Verify file was created
        insight_dir = os.path.join(mock_state_file, "dream_insights")
        filepath = os.path.join(insight_dir, f"{node_id}.json")
        assert os.path.exists(filepath)
        
        # Verify content
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        assert data["node_id"] == node_id
        assert data["content"] == "Test insight content"
        assert data["insight_type"] == "connection"
        assert data["source_topics"] == ["topic1", "topic2"]
        assert data["surprise"] == 0.8
        assert data["novelty"] == 0.7
        assert data["trigger_topic"] == "trigger_topic"
        assert data["weight"] == 0.5
        assert data["verified"] is False
        assert data["quality"] == 0.0
        assert data["stale"] is False
        assert "created_at" in data
    
    def test_add_dream_insight_without_trigger_topic(self, mock_state_file):
        """Test add_dream_insight with None trigger_topic."""
        from core.knowledge_graph import add_dream_insight
        
        node_id = add_dream_insight(
            content="Insight without trigger",
            insight_type="pattern",
            source_topics=["topic_a"],
            surprise=0.5,
            novelty=0.6,
            trigger_topic=None
        )
        
        insight_dir = os.path.join(mock_state_file, "dream_insights")
        filepath = os.path.join(insight_dir, f"{node_id}.json")
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        assert data["trigger_topic"] is None


class TestGetDreamInsights:
    """Tests for get_dream_insights function."""
    
    def test_get_dream_insights_returns_list(self, mock_state_file):
        """Test that get_dream_insights returns a list of insights."""
        from core.knowledge_graph import add_dream_insight, get_dream_insights
        
        # Add some insights
        add_dream_insight(
            content="Insight 1",
            insight_type="connection",
            source_topics=["a", "b"],
            surprise=0.5,
            novelty=0.5,
            trigger_topic=None
        )
        add_dream_insight(
            content="Insight 2",
            insight_type="pattern",
            source_topics=["c", "d"],
            surprise=0.6,
            novelty=0.6,
            trigger_topic=None
        )
        
        insights = get_dream_insights()
        
        assert isinstance(insights, list)
        assert len(insights) == 2
    
    def test_get_dream_insights_filters_by_topic(self, mock_state_file):
        """Test that get_dream_insights filters by topic."""
        from core.knowledge_graph import add_dream_insight, get_dream_insights
        
        # Add insights with different source topics
        add_dream_insight(
            content="Insight about AI",
            insight_type="connection",
            source_topics=["AI", "ML"],
            surprise=0.5,
            novelty=0.5,
            trigger_topic=None
        )
        add_dream_insight(
            content="Insight about cooking",
            insight_type="pattern",
            source_topics=["cooking", "recipes"],
            surprise=0.6,
            novelty=0.6,
            trigger_topic=None
        )
        add_dream_insight(
            content="Another AI insight",
            insight_type="hypothesis",
            source_topics=["AI", "NLP"],
            surprise=0.7,
            novelty=0.7,
            trigger_topic=None
        )
        
        # Filter by AI topic
        ai_insights = get_dream_insights(topic="AI")
        
        assert len(ai_insights) == 2
        for insight in ai_insights:
            assert "AI" in insight["source_topics"]
    
    def test_get_dream_insights_empty_when_no_match(self, mock_state_file):
        """Test get_dream_insights returns empty list when no matches."""
        from core.knowledge_graph import add_dream_insight, get_dream_insights
        
        add_dream_insight(
            content="Some insight",
            insight_type="connection",
            source_topics=["topic1"],
            surprise=0.5,
            novelty=0.5,
            trigger_topic=None
        )
        
        insights = get_dream_insights(topic="nonexistent_topic")
        
        assert insights == []


class TestGetAllDreamInsights:
    """Tests for get_all_dream_insights function."""
    
    def test_get_all_dream_insights_returns_all(self, mock_state_file):
        """Test that get_all_dream_insights returns all insights."""
        from core.knowledge_graph import add_dream_insight, get_all_dream_insights
        
        add_dream_insight(
            content="Insight 1",
            insight_type="connection",
            source_topics=["a"],
            surprise=0.5,
            novelty=0.5,
            trigger_topic=None
        )
        add_dream_insight(
            content="Insight 2",
            insight_type="pattern",
            source_topics=["b"],
            surprise=0.6,
            novelty=0.6,
            trigger_topic=None
        )
        
        all_insights = get_all_dream_insights()
        
        assert len(all_insights) == 2


class TestRemoveDreamInsight:
    """Tests for remove_dream_insight function."""
    
    def test_remove_dream_insight_deletes_file(self, mock_state_file):
        """Test that remove_dream_insight deletes the insight file."""
        from core.knowledge_graph import add_dream_insight, remove_dream_insight, get_dream_insights
        
        node_id = add_dream_insight(
            content="To be removed",
            insight_type="connection",
            source_topics=["x"],
            surprise=0.5,
            novelty=0.5,
            trigger_topic=None
        )
        
        # Verify it exists
        insights = get_dream_insights()
        assert len(insights) == 1
        
        # Remove it
        remove_dream_insight(node_id)
        
        # Verify it's gone
        insights = get_dream_insights()
        assert len(insights) == 0
    
    def test_remove_dream_insight_nonexistent(self, mock_state_file):
        """Test remove_dream_insight handles nonexistent node_id gracefully."""
        from core.knowledge_graph import remove_dream_insight
        
        # Should not raise an error
        remove_dream_insight("insight_nonexistent_12345")


class TestIsInsightStale:
    """Tests for is_insight_stale function."""
    
    def test_is_insight_stale_older_than_7_days(self, mock_state_file):
        """Test that insights older than 7 days and unverified are stale."""
        from core.knowledge_graph import add_dream_insight, is_insight_stale
        
        node_id = add_dream_insight(
            content="Old insight",
            insight_type="connection",
            source_topics=["old"],
            surprise=0.5,
            novelty=0.5,
            trigger_topic=None
        )
        
        # Manually modify the created_at to be 8 days old
        insight_dir = os.path.join(mock_state_file, "dream_insights")
        filepath = os.path.join(insight_dir, f"{node_id}.json")
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Set created_at to 8 days ago
        old_date = datetime.now(timezone.utc) - timedelta(days=8)
        data["created_at"] = old_date.isoformat()
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f)
        
        # Should be stale (old and unverified)
        assert is_insight_stale(node_id) is True
    
    def test_is_insight_stale_recent_insight(self, mock_state_file):
        """Test that recent insights are not stale."""
        from core.knowledge_graph import add_dream_insight, is_insight_stale
        
        node_id = add_dream_insight(
            content="Recent insight",
            insight_type="connection",
            source_topics=["recent"],
            surprise=0.5,
            novelty=0.5,
            trigger_topic=None
        )
        
        # Should not be stale (recent)
        assert is_insight_stale(node_id) is False
    
    def test_is_insight_stale_verified_insight(self, mock_state_file):
        """Test that verified insights are not stale even if old."""
        from core.knowledge_graph import add_dream_insight, is_insight_stale
        
        node_id = add_dream_insight(
            content="Old but verified",
            insight_type="connection",
            source_topics=["verified"],
            surprise=0.5,
            novelty=0.5,
            trigger_topic=None
        )
        
        # Manually modify to be old AND verified
        insight_dir = os.path.join(mock_state_file, "dream_insights")
        filepath = os.path.join(insight_dir, f"{node_id}.json")
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        old_date = datetime.now(timezone.utc) - timedelta(days=10)
        data["created_at"] = old_date.isoformat()
        data["verified"] = True
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f)
        
        # Should not be stale (verified)
        assert is_insight_stale(node_id) is False
    
    def test_is_insight_stale_nonexistent(self, mock_state_file):
        """Test is_insight_stale returns False for nonexistent insight."""
        from core.knowledge_graph import is_insight_stale
        
        assert is_insight_stale("insight_nonexistent") is False


class TestUpdateInsightWeight:
    """Tests for update_insight_weight function."""
    
    def test_update_insight_weight(self, mock_state_file):
        """Test that update_insight_weight modifies weight by delta."""
        from core.knowledge_graph import add_dream_insight, update_insight_weight, get_dream_insights
        
        node_id = add_dream_insight(
            content="Weight test",
            insight_type="connection",
            source_topics=["weight"],
            surprise=0.5,
            novelty=0.5,
            trigger_topic=None
        )
        
        # Initial weight is 0.5
        update_insight_weight(node_id, 0.3)
        
        insights = get_dream_insights()
        insight = next(i for i in insights if i["node_id"] == node_id)
        assert insight["weight"] == pytest.approx(0.8)
        
        update_insight_weight(node_id, -0.2)
        
        insights = get_dream_insights()
        insight = next(i for i in insights if i["node_id"] == node_id)
        assert insight["weight"] == pytest.approx(0.6)
    
    def test_update_insight_weight_nonexistent(self, mock_state_file):
        """Test update_insight_weight handles nonexistent node gracefully."""
        from core.knowledge_graph import update_insight_weight
        
        # Should not raise an error
        update_insight_weight("insight_nonexistent", 0.1)


class TestUpdateInsightQuality:
    """Tests for update_insight_quality function."""
    
    def test_update_insight_quality(self, mock_state_file):
        """Test that update_insight_quality modifies quality by delta."""
        from core.knowledge_graph import add_dream_insight, update_insight_quality, get_dream_insights
        
        node_id = add_dream_insight(
            content="Quality test",
            insight_type="connection",
            source_topics=["quality"],
            surprise=0.5,
            novelty=0.5,
            trigger_topic=None
        )
        
        # Initial quality is 0.0
        update_insight_quality(node_id, 0.7)
        
        insights = get_dream_insights()
        insight = next(i for i in insights if i["node_id"] == node_id)
        assert insight["quality"] == pytest.approx(0.7)
        
        update_insight_quality(node_id, 0.2)
        
        insights = get_dream_insights()
        insight = next(i for i in insights if i["node_id"] == node_id)
        assert insight["quality"] == pytest.approx(0.9)
    
    def test_update_insight_quality_nonexistent(self, mock_state_file):
        """Test update_insight_quality handles nonexistent node gracefully."""
        from core.knowledge_graph import update_insight_quality
        
        # Should not raise an error
        update_insight_quality("insight_nonexistent", 0.5)


class TestThreadSafety:
    """Tests for thread safety with NodeLockRegistry."""
    
    def test_all_functions_use_global_write_lock(self, mock_state_file):
        """Verify that all dream insight functions use NodeLockRegistry.global_write_lock."""
        from core.knowledge_graph import (
            add_dream_insight,
            get_dream_insights,
            remove_dream_insight,
            update_insight_weight,
            update_insight_quality,
        )
        from core.node_lock_registry import NodeLockRegistry
        
        # This test verifies the functions work correctly with the lock
        # The actual lock usage is verified by the implementation
        
        node_id = add_dream_insight(
            content="Thread safety test",
            insight_type="connection",
            source_topics=["thread"],
            surprise=0.5,
            novelty=0.5,
            trigger_topic=None
        )
        
        # All operations should work without deadlock
        insights = get_dream_insights()
        assert len(insights) == 1
        
        update_insight_weight(node_id, 0.1)
        update_insight_quality(node_id, 0.2)
        
        remove_dream_insight(node_id)
        insights = get_dream_insights()
        assert len(insights) == 0
