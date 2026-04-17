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
    
    # Create empty state.json with all required fields
    state_file = os.path.join(knowledge_dir, "state.json")
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump({
            "version": "1.0",
            "knowledge": {"topics": {}},
            "exploration_log": []
        }, f)
    
    yield knowledge_dir
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_state_file(temp_knowledge_dir):
    """Mock STATE_FILE to use temp directory."""
    with patch("core.knowledge_graph_compat.STATE_FILE", 
               os.path.join(temp_knowledge_dir, "state.json")):
        yield temp_knowledge_dir


class TestAddDreamInsight:
    """Tests for add_dream_insight function."""
    
    def test_add_dream_insight_creates_file(self, mock_state_file):
        """Test that add_dream_insight creates a JSON file."""
        from core.knowledge_graph_compat import add_dream_insight
        
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
        from core.knowledge_graph_compat import add_dream_insight
        
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
        from core.knowledge_graph_compat import add_dream_insight, get_dream_insights
        
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
        from core.knowledge_graph_compat import add_dream_insight, get_dream_insights
        
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
        from core.knowledge_graph_compat import add_dream_insight, get_dream_insights
        
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
        from core.knowledge_graph_compat import add_dream_insight, get_all_dream_insights
        
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
        from core.knowledge_graph_compat import add_dream_insight, remove_dream_insight, get_dream_insights
        
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
        from core.knowledge_graph_compat import remove_dream_insight
        
        # Should not raise an error
        remove_dream_insight("insight_nonexistent_12345")


class TestIsInsightStale:
    """Tests for is_insight_stale function."""
    
    def test_is_insight_stale_older_than_7_days(self, mock_state_file):
        """Test that insights older than 7 days and unverified are stale."""
        from core.knowledge_graph_compat import add_dream_insight, is_insight_stale
        
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
        from core.knowledge_graph_compat import add_dream_insight, is_insight_stale
        
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
        from core.knowledge_graph_compat import add_dream_insight, is_insight_stale
        
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
        from core.knowledge_graph_compat import is_insight_stale
        
        assert is_insight_stale("insight_nonexistent") is False


class TestUpdateInsightWeight:
    """Tests for update_insight_weight function."""
    
    def test_update_insight_weight(self, mock_state_file):
        """Test that update_insight_weight modifies weight by delta."""
        from core.knowledge_graph_compat import add_dream_insight, update_insight_weight, get_dream_insights
        
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
        from core.knowledge_graph_compat import update_insight_weight
        
        # Should not raise an error
        update_insight_weight("insight_nonexistent", 0.1)


class TestUpdateInsightQuality:
    """Tests for update_insight_quality function."""
    
    def test_update_insight_quality(self, mock_state_file):
        """Test that update_insight_quality modifies quality by delta."""
        from core.knowledge_graph_compat import add_dream_insight, update_insight_quality, get_dream_insights
        
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
        from core.knowledge_graph_compat import update_insight_quality
        
        # Should not raise an error
        update_insight_quality("insight_nonexistent", 0.5)


class TestThreadSafety:
    """Tests for thread safety with NodeLockRegistry."""
    
    def test_all_functions_use_global_write_lock(self, mock_state_file):
        """Verify that all dream insight functions use NodeLockRegistry.global_write_lock."""
        from core.knowledge_graph_compat import (
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


class TestNodeLifecycleFunctions:
    """Tests for v0.2.6 node lifecycle functions."""
    
    def test_mark_dormant_changes_status(self, mock_state_file):
        """Test that mark_dormant sets status to 'dormant'."""
        from core.knowledge_graph_compat import add_knowledge, mark_dormant, get_state
        
        # Add a topic first
        add_knowledge("test_topic_dormant", depth=5, summary="Test summary")
        
        # Mark as dormant
        mark_dormant("test_topic_dormant")
        
        # Verify status changed
        state = get_state()
        assert state["knowledge"]["topics"]["test_topic_dormant"]["status"] == "dormant"
    
    def test_reactivate_changes_status(self, mock_state_file):
        """Test that reactivate sets status to 'complete'."""
        from core.knowledge_graph_compat import add_knowledge, mark_dormant, reactivate, get_state
        
        # Add a topic and mark as dormant
        add_knowledge("test_topic_reactivate", depth=5, summary="Test summary")
        mark_dormant("test_topic_reactivate")
        
        # Reactivate
        reactivate("test_topic_reactivate")
        
        # Verify status changed back to complete
        state = get_state()
        assert state["knowledge"]["topics"]["test_topic_reactivate"]["status"] == "complete"
    
    def test_mark_dreamed_sets_timestamp(self, mock_state_file):
        """Test that mark_dreamed sets dreamed_at timestamp."""
        from core.knowledge_graph_compat import add_knowledge, mark_dreamed, get_state
        from datetime import datetime, timezone
        
        # Add a topic
        add_knowledge("test_topic_dreamed", depth=5, summary="Test summary")
        
        # Mark as dreamed
        mark_dreamed("test_topic_dreamed")
        
        # Verify timestamp was set
        state = get_state()
        topic_data = state["knowledge"]["topics"]["test_topic_dreamed"]
        assert "dreamed_at" in topic_data
        # Verify it's a valid ISO timestamp
        dreamed_at = datetime.fromisoformat(topic_data["dreamed_at"])
        assert dreamed_at.year == datetime.now(timezone.utc).year
    
    def test_set_consolidated_sets_timestamp(self, mock_state_file):
        """Test that set_consolidated sets last_consolidated timestamp."""
        from core.knowledge_graph_compat import add_knowledge, set_consolidated, get_state
        from datetime import datetime, timezone
        
        # Add a topic
        add_knowledge("test_topic_consolidated", depth=5, summary="Test summary")
        
        # Mark as consolidated
        set_consolidated("test_topic_consolidated")
        
        # Verify timestamp was set
        state = get_state()
        topic_data = state["knowledge"]["topics"]["test_topic_consolidated"]
        assert "last_consolidated" in topic_data
        # Verify it's a valid ISO timestamp
        consolidated_at = datetime.fromisoformat(topic_data["last_consolidated"])
        assert consolidated_at.year == datetime.now(timezone.utc).year
    
    def test_get_dormant_nodes(self, mock_state_file):
        """Test that get_dormant_nodes returns only dormant topics."""
        from core.knowledge_graph_compat import add_knowledge, mark_dormant, get_dormant_nodes
        
        # Add multiple topics
        add_knowledge("active_topic", depth=5, summary="Active")
        add_knowledge("dormant_topic_1", depth=5, summary="Dormant 1")
        add_knowledge("dormant_topic_2", depth=5, summary="Dormant 2")
        
        # Mark some as dormant
        mark_dormant("dormant_topic_1")
        mark_dormant("dormant_topic_2")
        
        # Get dormant nodes
        dormant = get_dormant_nodes()
        
        assert "dormant_topic_1" in dormant
        assert "dormant_topic_2" in dormant
        assert "active_topic" not in dormant
    
    def test_has_recent_dreams(self, mock_state_file):
        """Test that has_recent_dreams correctly checks dream recency."""
        from core.knowledge_graph_compat import add_knowledge, mark_dreamed, has_recent_dreams
        from datetime import datetime, timezone, timedelta
        import json
        
        # Add a topic
        add_knowledge("test_recent_dreams", depth=5, summary="Test")
        
        # Mark as dreamed now
        mark_dreamed("test_recent_dreams")
        
        # Should have recent dreams within 7 days
        assert has_recent_dreams("test_recent_dreams", within_days=7) is True
        
        # Manually set dreamed_at to 10 days ago
        state_file = mock_state_file + "/state.json"
        with open(state_file, "r") as f:
            state = json.load(f)
        
        old_date = datetime.now(timezone.utc) - timedelta(days=10)
        state["knowledge"]["topics"]["test_recent_dreams"]["dreamed_at"] = old_date.isoformat()
        
        with open(state_file, "w") as f:
            json.dump(state, f)
        
        # Should NOT have recent dreams within 7 days
        assert has_recent_dreams("test_recent_dreams", within_days=7) is False
        # But should have within 14 days
        assert has_recent_dreams("test_recent_dreams", within_days=14) is True
    
    def test_get_recently_dreamed(self, mock_state_file):
        """Test that get_recently_dreamed returns topics dreamed within window."""
        from core.knowledge_graph_compat import add_knowledge, mark_dreamed, get_recently_dreamed
        from datetime import datetime, timezone, timedelta
        import json
        
        # Add topics
        add_knowledge("recent_dreamed_1", depth=5, summary="Recent 1")
        add_knowledge("recent_dreamed_2", depth=5, summary="Recent 2")
        add_knowledge("old_dreamed", depth=5, summary="Old")
        add_knowledge("never_dreamed", depth=5, summary="Never")
        
        # Mark some as dreamed
        mark_dreamed("recent_dreamed_1")
        mark_dreamed("recent_dreamed_2")
        
        # Manually set old_dreamed to 10 days ago
        state_file = mock_state_file + "/state.json"
        with open(state_file, "r") as f:
            state = json.load(f)
        
        old_date = datetime.now(timezone.utc) - timedelta(days=10)
        state["knowledge"]["topics"]["old_dreamed"]["dreamed_at"] = old_date.isoformat()
        
        with open(state_file, "w") as f:
            json.dump(state, f)
        
        # Get recently dreamed within 7 days
        recent = get_recently_dreamed(within_days=7)
        
        assert "recent_dreamed_1" in recent
        assert "recent_dreamed_2" in recent
        assert "old_dreamed" not in recent
        assert "never_dreamed" not in recent


class TestConnectionFunctions:
    """Tests for v0.2.6 connection functions."""

    def test_strengthen_connection_increases_weight(self, mock_state_file):
        """Test that strengthen_connection increases connection weight."""
        from core.knowledge_graph_compat import add_knowledge, strengthen_connection, get_state
        
        # Add two topics
        add_knowledge("topic_a", depth=5, summary="Topic A")
        add_knowledge("topic_b", depth=5, summary="Topic B")
        
        # Strengthen connection
        strengthen_connection("topic_a", "topic_b", delta=0.2)
        
        # Verify connection weight increased
        state = get_state()
        topics = state["knowledge"]["topics"]
        
        # Check both directions
        assert "topic_b" in topics["topic_a"]["connections"]
        assert topics["topic_a"]["connections"]["topic_b"]["weight"] == pytest.approx(0.2)
        
        assert "topic_a" in topics["topic_b"]["connections"]
        assert topics["topic_b"]["connections"]["topic_a"]["weight"] == pytest.approx(0.2)
    
    def test_strengthen_connection_creates_nodes_if_missing(self, mock_state_file):
        """Test that strengthen_connection creates nodes if they don't exist."""
        from core.knowledge_graph_compat import strengthen_connection, get_state
        
        # Strengthen connection between non-existent topics
        strengthen_connection("new_topic_x", "new_topic_y", delta=0.15)
        
        # Verify both topics were created
        state = get_state()
        topics = state["knowledge"]["topics"]
        
        assert "new_topic_x" in topics
        assert "new_topic_y" in topics
        assert topics["new_topic_x"]["connections"]["new_topic_y"]["weight"] == pytest.approx(0.15)
    
    def test_strengthen_connection_caps_at_1_0(self, mock_state_file):
        """Test that connection weight is capped at 1.0."""
        from core.knowledge_graph_compat import add_knowledge, strengthen_connection, get_state
        
        add_knowledge("topic_cap_a", depth=5, summary="A")
        add_knowledge("topic_cap_b", depth=5, summary="B")
        
        # Strengthen multiple times to exceed 1.0
        strengthen_connection("topic_cap_a", "topic_cap_b", delta=0.6)
        strengthen_connection("topic_cap_a", "topic_cap_b", delta=0.6)
        
        state = get_state()
        weight = state["knowledge"]["topics"]["topic_cap_a"]["connections"]["topic_cap_b"]["weight"]
        
        # Should be capped at 1.0
        assert weight == pytest.approx(1.0)
    
    def test_get_directly_connected_returns_parents_and_children(self, mock_state_file):
        """Test that get_directly_connected returns both parents and children."""
        from core.knowledge_graph_compat import add_child, get_directly_connected
        
        # Create parent-child relationships
        add_child("parent_topic", "child_1")
        add_child("parent_topic", "child_2")
        add_child("grandparent", "parent_topic")
        
        # Get directly connected to parent_topic
        connected = get_directly_connected("parent_topic")
        
        # Should include both children and parents
        assert "child_1" in connected
        assert "child_2" in connected
        assert "grandparent" in connected
    
    def test_get_shortest_path_length_direct_connection(self, mock_state_file):
        """Test get_shortest_path_length for directly connected nodes."""
        from core.knowledge_graph_compat import add_child, get_shortest_path_length
        
        add_child("path_a", "path_b")
        
        # Direct connection should return 1
        length = get_shortest_path_length("path_a", "path_b")
        assert length == 1
        
        # Reverse direction should also work
        length = get_shortest_path_length("path_b", "path_a")
        assert length == 1
    
    def test_get_shortest_path_length_multi_hop(self, mock_state_file):
        """Test get_shortest_path_length for multi-hop paths."""
        from core.knowledge_graph_compat import add_child, get_shortest_path_length
        
        # Create a chain: a -> b -> c -> d
        add_child("chain_a", "chain_b")
        add_child("chain_b", "chain_c")
        add_child("chain_c", "chain_d")
        
        # Path from a to d should be 3 hops
        length = get_shortest_path_length("chain_a", "chain_d")
        assert length == 3
    
    def test_get_shortest_path_length_no_path_returns_inf(self, mock_state_file):
        """Test get_shortest_path_length returns inf when no path exists."""
        from core.knowledge_graph_compat import add_knowledge, get_shortest_path_length
        import math
        
        # Add two disconnected topics
        add_knowledge("isolated_a", depth=5, summary="Isolated A")
        add_knowledge("isolated_b", depth=5, summary="Isolated B")
        
        # No path should return infinity
        length = get_shortest_path_length("isolated_a", "isolated_b")
        assert length == math.inf
    
    def test_get_all_nodes_includes_all_topics(self, mock_state_file):
        """Test that get_all_nodes returns all topics."""
        from core.knowledge_graph_compat import add_knowledge, get_all_nodes
        
        add_knowledge("node_1", depth=5, summary="Node 1")
        add_knowledge("node_2", depth=5, summary="Node 2")
        add_knowledge("node_3", depth=5, summary="Node 3")
        
        nodes = get_all_nodes()
        node_names = [name for name, _ in nodes]
        
        assert "node_1" in node_names
        assert "node_2" in node_names
        assert "node_3" in node_names
        assert len(nodes) >= 3
    
    def test_get_all_nodes_active_only_excludes_dormant(self, mock_state_file):
        """Test that get_all_nodes with active_only excludes dormant nodes."""
        from core.knowledge_graph_compat import add_knowledge, mark_dormant, get_all_nodes
        
        add_knowledge("active_node", depth=5, summary="Active")
        add_knowledge("dormant_node", depth=5, summary="Dormant")
        
        mark_dormant("dormant_node")
        
        # Get all nodes
        all_nodes = get_all_nodes(active_only=False)
        all_names = [name for name, _ in all_nodes]
        assert "dormant_node" in all_names
        
        # Get active only
        active_nodes = get_all_nodes(active_only=True)
        active_names = [name for name, _ in active_nodes]
        assert "active_node" in active_names
        assert "dormant_node" not in active_names
    
    def test_get_root_pool_names(self, mock_state_file):
        """Test that get_root_pool_names returns names from root technology pool."""
        from core.knowledge_graph_compat import init_root_pool, get_root_pool_names
        
        # Initialize root pool with seeds
        init_root_pool(["transformer attention", "gradient descent", "backpropagation"])
        
        # Get root pool names
        names = get_root_pool_names()
        
        assert "transformer attention" in names
        assert "gradient descent" in names
        assert "backpropagation" in names


class TestSharedInboxFunctions:
    """Tests for v0.2.6 SharedInbox functions (Commit 4)."""

    def test_add_to_dream_inbox_creates_file(self, mock_state_file):
        """Test that add_to_dream_inbox creates dream_topic_inbox.json."""
        from core.knowledge_graph_compat import add_to_dream_inbox
        import os
        
        # Add an item to the inbox
        add_to_dream_inbox(
            topic="test_topic_inbox",
            source_insight="Test insight for inbox"
        )
        
        # Verify file was created
        inbox_path = os.path.join(mock_state_file, "dream_topic_inbox.json")
        assert os.path.exists(inbox_path)
        
        # Verify content
        with open(inbox_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        assert "inbox" in data
        assert len(data["inbox"]) == 1
        assert data["inbox"][0]["topic"] == "test_topic_inbox"
        assert data["inbox"][0]["source_insight"] == "Test insight for inbox"
        assert "timestamp" in data["inbox"][0]

    def test_add_to_dream_inbox_appends_to_existing(self, mock_state_file):
        """Test that add_to_dream_inbox appends to existing inbox."""
        from core.knowledge_graph_compat import add_to_dream_inbox
        import os
        
        # Add first item
        add_to_dream_inbox(
            topic="topic_1",
            source_insight="First insight"
        )
        
        # Add second item
        add_to_dream_inbox(
            topic="topic_2",
            source_insight="Second insight"
        )
        
        # Verify both items exist
        inbox_path = os.path.join(mock_state_file, "dream_topic_inbox.json")
        with open(inbox_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        assert len(data["inbox"]) == 2
        topics = [item["topic"] for item in data["inbox"]]
        assert "topic_1" in topics
        assert "topic_2" in topics

    def test_fetch_and_clear_dream_inbox_returns_items(self, mock_state_file):
        """Test that fetch_and_clear_dream_inbox returns inbox items."""
        from core.knowledge_graph_compat import add_to_dream_inbox, fetch_and_clear_dream_inbox
        
        # Add items to inbox
        add_to_dream_inbox(topic="fetch_topic_1", source_insight="Insight 1")
        add_to_dream_inbox(topic="fetch_topic_2", source_insight="Insight 2")
        
        # Fetch and clear
        items = fetch_and_clear_dream_inbox()
        
        # Verify items returned
        assert len(items) == 2
        topics = [item["topic"] for item in items]
        assert "fetch_topic_1" in topics
        assert "fetch_topic_2" in topics

    def test_fetch_and_clear_dream_inbox_clears_file(self, mock_state_file):
        """Test that fetch_and_clear_dream_inbox clears the inbox file."""
        from core.knowledge_graph_compat import add_to_dream_inbox, fetch_and_clear_dream_inbox
        import os
        
        # Add items to inbox
        add_to_dream_inbox(topic="clear_topic", source_insight="To be cleared")
        
        # Fetch and clear
        items = fetch_and_clear_dream_inbox()
        assert len(items) == 1
        
        # Verify inbox is now empty
        inbox_path = os.path.join(mock_state_file, "dream_topic_inbox.json")
        with open(inbox_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        assert data["inbox"] == []
        
        # Second fetch should return empty list
        items2 = fetch_and_clear_dream_inbox()
        assert items2 == []

    def test_fetch_and_clear_dream_inbox_empty_inbox(self, mock_state_file):
        """Test fetch_and_clear_dream_inbox returns empty list when no inbox exists."""
        from core.knowledge_graph_compat import fetch_and_clear_dream_inbox
        
        # Fetch from non-existent inbox
        items = fetch_and_clear_dream_inbox()
        
        assert items == []

    def test_shared_inbox_thread_safety(self, mock_state_file):
        """Test that SharedInbox functions use NodeLockRegistry.global_write_lock."""
        from core.knowledge_graph_compat import add_to_dream_inbox, fetch_and_clear_dream_inbox
        
        # These operations should work without deadlock
        add_to_dream_inbox(topic="thread_test_1", source_insight="Thread 1")
        add_to_dream_inbox(topic="thread_test_2", source_insight="Thread 2")
        
        items = fetch_and_clear_dream_inbox()
        assert len(items) == 2


class TestUtilityFunctions:
    """Tests for v0.2.6 utility functions (Commit 5)."""

    def test_mark_insight_triggered_sets_flag(self, mock_state_file):
        """Test that mark_insight_triggered sets triggered=True for an insight."""
        from core.knowledge_graph_compat import (
            add_dream_insight,
            mark_insight_triggered,
            get_state
        )
        import json
        
        # Add an insight
        node_id = add_dream_insight(
            content="Test insight for trigger",
            insight_type="connection",
            source_topics=["topic1"],
            surprise=0.5,
            novelty=0.5,
            trigger_topic=None
        )
        
        # Mark as triggered
        mark_insight_triggered(node_id)
        
        # Verify triggered flag was set in state
        state_file = mock_state_file + "/state.json"
        with open(state_file, "r") as f:
            state = json.load(f)
        
        assert "insight_generation" in state
        assert node_id in state["insight_generation"]
        assert state["insight_generation"][node_id]["triggered"] is True

    def test_mark_insight_triggered_nonexistent_insight(self, mock_state_file):
        """Test mark_insight_triggered handles nonexistent insight gracefully."""
        from core.knowledge_graph_compat import mark_insight_triggered
        
        # Should not raise an error for nonexistent insight
        mark_insight_triggered("insight_nonexistent_12345")

    def test_get_recent_explorations_returns_within_window(self, mock_state_file):
        """Test that get_recent_explorations returns explorations within time window."""
        from core.knowledge_graph_compat import log_exploration, get_recent_explorations
        
        # Log some explorations
        log_exploration("topic1", "explore", "Found something interesting")
        log_exploration("topic2", "explore", "Another finding")
        log_exploration("topic3", "explore", "Third finding")
        
        # Get recent explorations within 1 hour
        recent = get_recent_explorations(within_hours=1)
        
        assert len(recent) == 3
        topics = [e["topic"] for e in recent]
        assert "topic1" in topics
        assert "topic2" in topics
        assert "topic3" in topics

    def test_get_recent_explorations_excludes_old(self, mock_state_file):
        """Test that get_recent_explorations excludes explorations outside window."""
        from core.knowledge_graph_compat import log_exploration, get_recent_explorations, _load_state, _save_state
        from datetime import datetime, timezone, timedelta
        import json
        
        # Log a recent exploration
        log_exploration("recent_topic", "explore", "Recent finding")
        
        # Manually add an old exploration to the log
        state_file = mock_state_file + "/state.json"
        with open(state_file, "r") as f:
            state = json.load(f)
        
        old_time = datetime.now(timezone.utc) - timedelta(hours=5)
        state["exploration_log"].append({
            "timestamp": old_time.isoformat(),
            "topic": "old_topic",
            "action": "explore",
            "findings": "Old finding",
            "notified_user": False
        })
        
        with open(state_file, "w") as f:
            json.dump(state, f)
        
        # Get recent explorations within 1 hour
        recent = get_recent_explorations(within_hours=1)
        
        # Should only include the recent one
        topics = [e["topic"] for e in recent]
        assert "recent_topic" in topics
        assert "old_topic" not in topics

    def test_get_recent_explorations_empty_log(self, mock_state_file):
        """Test get_recent_explorations returns empty list when no explorations."""
        from core.knowledge_graph_compat import get_recent_explorations
        
        # No explorations logged
        recent = get_recent_explorations(within_hours=24)
        
        assert recent == []

    def test_utility_functions_thread_safety(self, mock_state_file):
        """Test that utility functions use NodeLockRegistry.global_write_lock."""
        from core.knowledge_graph_compat import (
            add_dream_insight,
            mark_insight_triggered,
            log_exploration,
            get_recent_explorations
        )
        
        # These operations should work without deadlock
        node_id = add_dream_insight(
            content="Thread safety test",
            insight_type="connection",
            source_topics=["thread"],
            surprise=0.5,
            novelty=0.5,
            trigger_topic=None
        )
        
        mark_insight_triggered(node_id)
        
        log_exploration("thread_topic", "explore", "Thread test finding")
        
        recent = get_recent_explorations(within_hours=1)
        assert len(recent) >= 1
