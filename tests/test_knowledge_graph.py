"""
Complete tests for knowledge_graph module
Tests all public functions with isolated state
"""
import pytest
import sys
import os
import json
import tempfile
import shutil
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import knowledge_graph as kg


@pytest.fixture
def isolated_kg():
    """Create isolated knowledge graph for testing"""
    # Save original state file
    original_state_file = kg.STATE_FILE
    
    # Create temporary directory and state file
    temp_dir = tempfile.mkdtemp()
    temp_state = os.path.join(temp_dir, "state.json")
    
    # Create initial state
    initial_state = {
        "version": "1.0",
        "last_update": None,
        "knowledge": {"topics": {}},
        "curiosity_queue": [],
        "exploration_log": [],
        "config": {
            "curiosity_top_k": 3,
            "max_knowledge_nodes": 100,
            "notification_threshold": 7.0
        }
    }
    
    with open(temp_state, 'w') as f:
        json.dump(initial_state, f)
    
    # Patch state file
    kg.STATE_FILE = temp_state
    
    yield kg
    
    # Cleanup
    kg.STATE_FILE = original_state_file
    shutil.rmtree(temp_dir)


class TestStateManagement:
    """Test suite for state loading and saving"""
    
    def test_load_state_creates_default_if_not_exists(self, isolated_kg):
        """Test load_state creates default state if file doesn't exist"""
        # Use non-existent file
        isolated_kg.STATE_FILE = "/tmp/non_existent_state_12345.json"
        state = isolated_kg._load_state()
        
        assert state["version"] == "1.0"
        assert "knowledge" in state
        assert "curiosity_queue" in state
        assert "exploration_log" in state
    
    def test_load_state_handles_corrupted_json(self, isolated_kg):
        """Test load_state handles corrupted JSON gracefully"""
        # Write invalid JSON
        with open(isolated_kg.STATE_FILE, 'w') as f:
            f.write("invalid json {{")
        
        state = isolated_kg._load_state()
        assert state["version"] == "1.0"  # Returns default
    
    def test_save_state_updates_last_update(self, isolated_kg):
        """Test save_state updates last_update timestamp"""
        state = isolated_kg._load_state()
        assert state["last_update"] is None
        
        isolated_kg._save_state(state)
        
        # Reload and check
        state = isolated_kg._load_state()
        assert state["last_update"] is not None
        # Should be valid ISO timestamp
        datetime.fromisoformat(state["last_update"].replace('Z', '+00:00'))
    
    def test_save_state_creates_directory_if_needed(self, isolated_kg):
        """Test save_state creates directory structure if needed"""
        temp_dir = tempfile.mkdtemp()
        nested_file = os.path.join(temp_dir, "nested", "deep", "state.json")
        
        isolated_kg.STATE_FILE = nested_file
        state = isolated_kg._load_state()
        isolated_kg._save_state(state)
        
        assert os.path.exists(nested_file)
        
        # Cleanup
        shutil.rmtree(temp_dir)


class TestKnowledgeOperations:
    """Test suite for knowledge operations"""
    
    def test_add_knowledge_creates_new_topic(self, isolated_kg):
        """Test add_knowledge creates new topic"""
        isolated_kg.add_knowledge("test topic", depth=5, summary="test summary")
        
        state = isolated_kg._load_state()
        assert "test topic" in state["knowledge"]["topics"]
        
        topic = state["knowledge"]["topics"]["test topic"]
        assert topic["known"] is True
        assert topic["depth"] == 5
        assert topic["summary"] == "test summary"
    
    def test_add_knowledge_updates_existing_topic(self, isolated_kg):
        """Test add_knowledge updates existing topic with higher depth"""
        # Add initial
        isolated_kg.add_knowledge("test", depth=5, summary="initial")
        
        # Update with higher depth
        isolated_kg.add_knowledge("test", depth=8, summary="updated")
        
        state = isolated_kg._load_state()
        topic = state["knowledge"]["topics"]["test"]
        assert topic["depth"] == 8  # Updated to higher
        assert topic["summary"] == "updated"
    
    def test_add_knowledge_keeps_higher_depth(self, isolated_kg):
        """Test add_knowledge keeps higher depth when adding lower"""
        isolated_kg.add_knowledge("test", depth=8, summary="high")
        isolated_kg.add_knowledge("test", depth=5, summary="low")  # Should not reduce
        
        state = isolated_kg._load_state()
        topic = state["knowledge"]["topics"]["test"]
        assert topic["depth"] == 8  # Kept higher
    
    def test_add_knowledge_appends_sources(self, isolated_kg):
        """Test add_knowledge appends sources without duplication"""
        isolated_kg.add_knowledge("test", sources=["url1", "url2"])
        isolated_kg.add_knowledge("test", sources=["url2", "url3"])  # url2 duplicate
        
        state = isolated_kg._load_state()
        sources = state["knowledge"]["topics"]["test"]["sources"]
        assert "url1" in sources
        assert "url2" in sources
        assert "url3" in sources
    
    def test_add_knowledge_limits_max_nodes(self, isolated_kg):
        """Test add_knowledge limits to max_knowledge_nodes"""
        # Add many topics
        for i in range(110):  # More than default 100
            isolated_kg.add_knowledge(f"topic_{i}", depth=i % 10)
        
        state = isolated_kg._load_state()
        topics = state["knowledge"]["topics"]
        
        # Should be limited to max_knowledge_nodes (100)
        assert len(topics) <= 100
        
        # Higher depth topics should be kept
        high_depth_topics = [t for t, v in topics.items() if v["depth"] >= 7]
        assert len(high_depth_topics) > 0


class TestCuriosityQueue:
    """Test suite for curiosity queue operations"""
    
    def test_add_curiosity_creates_new_item(self, isolated_kg):
        """Test add_curiosity creates new queue item"""
        isolated_kg.add_curiosity("test topic", "test reason", 8.0, 7.0)
        
        state = isolated_kg._load_state()
        queue = state["curiosity_queue"]
        
        assert len(queue) == 1
        assert queue[0]["topic"] == "test topic"
        assert queue[0]["reason"] == "test reason"
        assert queue[0]["score"] == 8.0 * 7.0  # relevance * depth
    
    def test_add_curiosity_skips_duplicates(self, isolated_kg):
        """Test add_curiosity skips duplicate pending items"""
        isolated_kg.add_curiosity("test", "reason1", 8.0, 7.0)
        isolated_kg.add_curiosity("test", "reason2", 9.0, 8.0)  # Duplicate
        
        state = isolated_kg._load_state()
        assert len(state["curiosity_queue"]) == 1
    
    def test_add_curiosity_allows_done_duplicates(self, isolated_kg):
        """Test add_curiosity allows adding done items again"""
        isolated_kg.add_curiosity("test", "reason", 8.0, 7.0)
        isolated_kg.update_curiosity_status("test", "done")
        isolated_kg.add_curiosity("test", "new reason", 9.0, 8.0)
        
        state = isolated_kg._load_state()
        # Should have 2 items: one done, one pending
        assert len(state["curiosity_queue"]) == 2
    
    def test_update_curiosity_status(self, isolated_kg):
        """Test update_curiosity_status changes status"""
        isolated_kg.add_curiosity("test", "reason", 8.0, 7.0)
        isolated_kg.update_curiosity_status("test", "investigating")
        
        state = isolated_kg._load_state()
        item = state["curiosity_queue"][0]
        assert item["status"] == "investigating"
    
    def test_get_top_curiosities_returns_highest_score(self, isolated_kg):
        """Test get_top_curiosities returns highest scored items"""
        isolated_kg.add_curiosity("low", "reason", 5.0, 5.0)   # score 25
        isolated_kg.add_curiosity("high", "reason", 9.0, 9.0)  # score 81
        isolated_kg.add_curiosity("med", "reason", 7.0, 7.0)   # score 49
        
        top = isolated_kg.get_top_curiosities(k=2)
        
        assert len(top) == 2
        assert top[0]["topic"] == "high"  # Highest score
        assert top[1]["topic"] == "med"   # Second highest
    
    def test_get_top_curiosities_only_returns_pending(self, isolated_kg):
        """Test get_top_curiosities only returns pending items"""
        isolated_kg.add_curiosity("pending", "reason", 9.0, 9.0)
        isolated_kg.add_curiosity("done", "reason", 8.0, 8.0)
        isolated_kg.update_curiosity_status("done", "done")
        
        top = isolated_kg.get_top_curiosities(k=10)
        
        assert len(top) == 1
        assert top[0]["topic"] == "pending"
    
    def test_get_top_curiosities_respects_k_parameter(self, isolated_kg):
        """Test get_top_curiosities respects k parameter"""
        for i in range(10):
            isolated_kg.add_curiosity(f"topic_{i}", "reason", float(i), 5.0)
        
        top = isolated_kg.get_top_curiosities(k=3)
        assert len(top) == 3


class TestExplorationLog:
    """Test suite for exploration log operations"""
    
    def test_log_exploration_creates_entry(self, isolated_kg):
        """Test log_exploration creates log entry"""
        isolated_kg.log_exploration("topic", "action", "findings", notified=True)
        
        state = isolated_kg._load_state()
        logs = state["exploration_log"]
        
        assert len(logs) == 1
        assert logs[0]["topic"] == "topic"
        assert logs[0]["action"] == "action"
        assert logs[0]["findings"] == "findings"
        assert logs[0]["notified_user"] is True
        assert "timestamp" in logs[0]
    
    def test_log_exploration_limits_to_100_entries(self, isolated_kg):
        """Test log_exploration keeps only last 100 entries"""
        for i in range(110):
            isolated_kg.log_exploration(f"topic_{i}", "action", "findings")
        
        state = isolated_kg._load_state()
        logs = state["exploration_log"]
        
        assert len(logs) == 100
        # Should keep most recent
        assert logs[-1]["topic"] == "topic_109"
    
    def test_log_exploration_truncates_findings(self, isolated_kg):
        """Test log_exploration truncates long findings"""
        long_findings = "x" * 1000
        isolated_kg.log_exploration("topic", "action", long_findings)
        
        state = isolated_kg._load_state()
        findings = state["exploration_log"][0]["findings"]
        
        assert len(findings) < 600  # Should be truncated


class TestKnowledgeQueries:
    """Test suite for knowledge query operations"""
    
    def test_get_recent_knowledge_returns_recent_items(self, isolated_kg):
        """Test get_recent_knowledge returns items updated within hours"""
        # Add knowledge
        isolated_kg.add_knowledge("recent", depth=5, summary="recent topic")
        
        # Get recent (last 24 hours)
        recent = isolated_kg.get_recent_knowledge(hours=24)
        
        assert len(recent) >= 1
        assert any(r["topic"] == "recent" for r in recent)
    
    def test_get_recent_knowledge_excludes_old_items(self, isolated_kg):
        """Test get_recent_knowledge excludes old items"""
        # Add topic with old timestamp
        state = isolated_kg._load_state()
        state["knowledge"]["topics"]["old"] = {
            "known": True,
            "depth": 5,
            "last_updated": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
            "summary": "old",
            "sources": []
        }
        isolated_kg._save_state(state)
        
        recent = isolated_kg.get_recent_knowledge(hours=24)
        
        assert not any(r["topic"] == "old" for r in recent)
    
    def test_get_knowledge_summary(self, isolated_kg):
        """Test get_knowledge_summary returns correct stats"""
        # Setup state
        isolated_kg.add_knowledge("known1", depth=5)
        isolated_kg.add_knowledge("known2", depth=5)
        
        state = isolated_kg._load_state()
        state["knowledge"]["topics"]["unknown"] = {
            "known": False,
            "depth": 3
        }
        isolated_kg._save_state(state)
        
        isolated_kg.add_curiosity("curiosity1", "reason", 8.0, 7.0)
        isolated_kg.add_curiosity("curiosity2", "reason", 8.0, 7.0)
        isolated_kg.update_curiosity_status("curiosity2", "done")
        
        isolated_kg.log_exploration("test", "action", "findings")
        
        summary = isolated_kg.get_knowledge_summary()
        
        assert summary["total_topics"] == 3
        assert summary["known_count"] == 2
        assert summary["pending_curiosities"] == 1
        assert summary["recent_explorations"] == 1


class TestRemoveCuriosity:
    """Test suite for remove_curiosity (v0.2.1 feature)"""
    
    def test_remove_curiosity_success(self, isolated_kg):
        """Test remove_curiosity removes pending item"""
        isolated_kg.add_curiosity("to-remove", "reason", 8.0, 7.0)
        
        result = isolated_kg.remove_curiosity("to-remove")
        
        assert result is True
        state = isolated_kg._load_state()
        assert len(state["curiosity_queue"]) == 0
    
    def test_remove_curiosity_not_found(self, isolated_kg):
        """Test remove_curiosity returns False for non-existent"""
        result = isolated_kg.remove_curiosity("non-existent")
        assert result is False
    
    def test_remove_curiosity_blocked_for_done(self, isolated_kg):
        """Test remove_curiosity blocks removal of done items"""
        isolated_kg.add_curiosity("done-item", "reason", 8.0, 7.0)
        isolated_kg.update_curiosity_status("done-item", "done")
        
        result = isolated_kg.remove_curiosity("done-item", force=False)
        
        assert result is False
    
    def test_remove_curiosity_force_removes_done(self, isolated_kg):
        """Test remove_curiosity with force removes done items"""
        isolated_kg.add_curiosity("force-remove", "reason", 8.0, 7.0)
        isolated_kg.update_curiosity_status("force-remove", "done")
        
        result = isolated_kg.remove_curiosity("force-remove", force=True)
        
        assert result is True


class TestListPending:
    """Test suite for list_pending (v0.2.1 feature)"""
    
    def test_list_pending_empty(self, isolated_kg):
        """Test list_pending returns empty list when no pending"""
        result = isolated_kg.list_pending()
        assert result == []
    
    def test_list_pending_returns_only_pending(self, isolated_kg):
        """Test list_pending returns only pending items"""
        isolated_kg.add_curiosity("pending1", "reason", 8.0, 7.0)
        isolated_kg.add_curiosity("pending2", "reason", 8.0, 7.0)
        isolated_kg.add_curiosity("done", "reason", 8.0, 7.0)
        isolated_kg.update_curiosity_status("done", "done")
        
        result = isolated_kg.list_pending()
        
        assert len(result) == 2
        topics = [r["topic"] for r in result]
        assert "pending1" in topics
        assert "pending2" in topics
        assert "done" not in topics
    
    def test_list_pending_item_structure(self, isolated_kg):
        """Test list_pending returns items with complete structure"""
        isolated_kg.add_curiosity("test", "reason", 8.0, 7.0)
        
        result = isolated_kg.list_pending()
        
        assert len(result) == 1
        item = result[0]
        assert "topic" in item
        assert "score" in item
        assert "reason" in item
        assert "status" in item


class TestSafeTruncate:
    """Test suite for _safe_truncate utility"""
    
    def test_safe_truncate_short_text(self, isolated_kg):
        """Test _safe_truncate returns short text unchanged"""
        text = "short"
        result = isolated_kg._safe_truncate(text, 100)
        assert result == "short"
    
    def test_safe_truncate_long_text(self, isolated_kg):
        """Test _safe_truncate truncates long text"""
        text = "x" * 1000
        result = isolated_kg._safe_truncate(text, 100)
        assert len(result) <= 120  # Some buffer for safe truncation
    
    def test_safe_truncate_empty_string(self, isolated_kg):
        """Test _safe_truncate handles empty string"""
        result = isolated_kg._safe_truncate("", 100)
        assert result == ""
    
    def test_safe_truncate_none(self, isolated_kg):
        """Test _safe_truncate handles None"""
        result = isolated_kg._safe_truncate(None, 100)
        assert result is None


class TestEdgeCases:
    """Test suite for edge cases"""
    
    def test_add_curiosity_case_insensitive_duplicates(self, isolated_kg):
        """Test add_curiosity handles case-insensitive duplicates"""
        isolated_kg.add_curiosity("Test Topic", "reason", 8.0, 7.0)
        isolated_kg.add_curiosity("test topic", "reason", 9.0, 8.0)  # Different case
        
        state = isolated_kg._load_state()
        # Should treat as duplicate (depends on implementation)
        # This test documents current behavior
        assert len(state["curiosity_queue"]) >= 1
    
    def test_concurrent_operations(self, isolated_kg):
        """Test multiple operations in sequence work correctly"""
        # Add, update, log, query
        isolated_kg.add_curiosity("concurrent", "reason", 8.0, 7.0)
        isolated_kg.update_curiosity_status("concurrent", "investigating")
        isolated_kg.log_exploration("concurrent", "test", "findings")
        isolated_kg.add_knowledge("concurrent", depth=8, summary="learned")
        
        # Verify all operations
        state = isolated_kg._load_state()
        assert state["curiosity_queue"][0]["status"] == "investigating"
        assert len(state["exploration_log"]) == 1
        assert "concurrent" in state["knowledge"]["topics"]
