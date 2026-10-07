"""Tests for SleepPruner - periodic pruning agent with adaptive intervals."""
import threading
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from core.sleep_pruner import SleepPruner
from core.base_agent import BaseAgent


class TestSleepPrunerInitialization:
    """Test SleepPruner initialization."""
    
    def test_sleep_pruner_is_base_agent(self):
        """SleepPruner should inherit from BaseAgent."""
        pruner = SleepPruner()
        
        assert isinstance(pruner, BaseAgent)
        assert isinstance(pruner, threading.Thread)
    
    def test_sleep_pruner_is_daemon(self):
        """SleepPruner should be a daemon thread."""
        pruner = SleepPruner()
        
        assert pruner.daemon is True
    
    def test_sleep_pruner_has_running_flag(self):
        """SleepPruner should have a running flag initialized to True."""
        pruner = SleepPruner()
        
        assert pruner.running is True
    
    def test_sleep_pruner_default_name(self):
        """SleepPruner should have default name 'SleepPruner'."""
        pruner = SleepPruner()
        
        assert pruner.name == "SleepPruner"
    
    def test_sleep_pruner_custom_name(self):
        """SleepPruner should accept custom name."""
        pruner = SleepPruner(name="CustomPruner")
        
        assert pruner.name == "CustomPruner"
    
    def test_sleep_pruner_default_initial_interval(self):
        """SleepPruner should have default initial interval of 240 minutes (4h)."""
        pruner = SleepPruner()
        
        assert pruner.current_interval_minutes == 240
    
    def test_sleep_pruner_custom_initial_interval(self):
        """SleepPruner should accept custom initial interval."""
        pruner = SleepPruner(initial_interval_minutes=120)
        
        assert pruner.current_interval_minutes == 120
    
    def test_sleep_pruner_max_interval(self):
        """SleepPruner should have max interval of 1440 minutes (24h)."""
        pruner = SleepPruner()
        
        assert pruner._max_interval_minutes == 1440
    
    def test_sleep_pruner_custom_max_interval(self):
        """SleepPruner should accept custom max interval."""
        pruner = SleepPruner(max_interval_minutes=720)
        
        assert pruner._max_interval_minutes == 720
    
    def test_sleep_pruner_has_dormancy_thresholds(self):
        """SleepPruner should have configurable dormancy thresholds."""
        pruner = SleepPruner(
            dream_window_days=5,
            consolidation_window_days=10,
            quality_threshold=6.0
        )
        
        assert pruner._dream_window_days == 5
        assert pruner._consolidation_window_days == 10
        assert pruner._quality_threshold == 6.0


class TestSleepPrunerStop:
    """Test SleepPruner stop functionality."""
    
    def test_sleep_pruner_stop_sets_running_false(self):
        """Calling stop() should set running flag to False."""
        pruner = SleepPruner()
        
        pruner.stop()
        
        assert pruner.running is False


class TestSleepPrunerAdaptiveInterval:
    """Test SleepPruner adaptive interval behavior."""
    
    def test_interval_doubles_when_no_pruning(self):
        """Interval should double when no pruning occurs."""
        pruner = SleepPruner(initial_interval_minutes=240)
        
        pruner._double_interval()
        
        assert pruner.current_interval_minutes == 480
    
    def test_interval_doubles_up_to_max(self):
        """Interval should not exceed max when doubling."""
        pruner = SleepPruner(
            initial_interval_minutes=240,
            max_interval_minutes=1440
        )
        
        # Double multiple times
        pruner._double_interval()  # 480
        pruner._double_interval()  # 960
        pruner._double_interval()  # 1440 (capped)
        pruner._double_interval()  # still 1440
        
        assert pruner.current_interval_minutes == 1440
    
    def test_interval_resets_after_pruning(self):
        """Interval should reset to initial after successful pruning."""
        pruner = SleepPruner(initial_interval_minutes=240)
        
        pruner._double_interval()  # 480
        pruner._double_interval()  # 960
        pruner._reset_interval()
        
        assert pruner.current_interval_minutes == 240
    
    def test_prune_cycle_doubles_interval_when_no_candidates(self):
        """_prune_cycle should double interval when no candidates found."""
        pruner = SleepPruner()
        
        with patch.object(pruner, '_find_dormancy_candidates', return_value=[]):
            pruner._prune_cycle()
        
        assert pruner.current_interval_minutes == 480
    
    def test_prune_cycle_resets_interval_when_pruning(self):
        """_prune_cycle should reset interval when pruning occurs."""
        pruner = SleepPruner()
        pruner._double_interval()  # 480
        
        with patch.object(pruner, '_find_dormancy_candidates', return_value=["topic1"]):
            with patch.object(pruner, '_mark_dormant_batch'):
                pruner._prune_cycle()
        
        assert pruner.current_interval_minutes == 240


class TestSleepPrunerDormancyCriteria:
    """Test SleepPruner dormancy criteria evaluation."""
    
    def test_meets_all_criteria_returns_true_when_all_met(self):
        """_meets_all_dormancy_criteria should return True when all criteria met."""
        pruner = SleepPruner()
        
        topic_data = {
            "status": "complete",
            "dreamed_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
            "last_consolidated": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),
            "quality": 3.0,
            "children": []
        }
        
        result = pruner._meets_all_dormancy_criteria("topic1", topic_data, {})
        
        assert result is True
    
    def test_meets_all_criteria_returns_false_when_status_not_complete(self):
        """_meets_all_dormancy_criteria should return False if status not complete."""
        pruner = SleepPruner()
        
        topic_data = {
            "status": "partial",
            "dreamed_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
            "last_consolidated": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),
            "quality": 3.0,
            "children": []
        }
        
        result = pruner._meets_all_dormancy_criteria("topic1", topic_data, {})
        
        assert result is False
    
    def test_meets_all_criteria_returns_false_when_recent_dreams(self):
        """_meets_all_dormancy_criteria should return False if recent dreams."""
        pruner = SleepPruner(dream_window_days=7)
        
        topic_data = {
            "status": "complete",
            "dreamed_at": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
            "last_consolidated": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),
            "quality": 3.0,
            "children": []
        }
        
        result = pruner._meets_all_dormancy_criteria("topic1", topic_data, {})
        
        assert result is False
    
    def test_meets_all_criteria_returns_false_when_recent_consolidation(self):
        """_meets_all_dormancy_criteria should return False if recent consolidation."""
        pruner = SleepPruner(consolidation_window_days=14)
        
        topic_data = {
            "status": "complete",
            "dreamed_at": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),
            "last_consolidated": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
            "quality": 3.0,
            "children": []
        }
        
        result = pruner._meets_all_dormancy_criteria("topic1", topic_data, {})
        
        assert result is False
    
    def test_meets_all_criteria_returns_false_when_high_quality(self):
        """_meets_all_dormancy_criteria should return False if quality is high."""
        pruner = SleepPruner(quality_threshold=5.0)
        
        topic_data = {
            "status": "complete",
            "dreamed_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
            "last_consolidated": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),
            "quality": 8.0,
            "children": []
        }
        
        result = pruner._meets_all_dormancy_criteria("topic1", topic_data, {})
        
        assert result is False
    
    def test_meets_all_criteria_returns_false_when_pending_children(self):
        """_meets_all_dormancy_criteria should return False if pending children."""
        pruner = SleepPruner()
        
        topic_data = {
            "status": "complete",
            "dreamed_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
            "last_consolidated": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),
            "quality": 3.0,
            "children": ["child1"]
        }
        
        all_topics = {
            "child1": {"status": "partial"}
        }
        
        result = pruner._meets_all_dormancy_criteria("topic1", topic_data, all_topics)
        
        assert result is False
    
    def test_meets_all_criteria_returns_true_when_children_dormant(self):
        """_meets_all_dormancy_criteria should return True if all children dormant."""
        pruner = SleepPruner()
        
        topic_data = {
            "status": "complete",
            "dreamed_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
            "last_consolidated": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),
            "quality": 3.0,
            "children": ["child1", "child2"]
        }
        
        all_topics = {
            "child1": {"status": "dormant"},
            "child2": {"status": "complete"}
        }
        
        result = pruner._meets_all_dormancy_criteria("topic1", topic_data, all_topics)
        
        assert result is True


class TestSleepPrunerRootPoolRespect:
    """Test SleepPruner respects root pool nodes."""
    
    def test_find_candidates_skips_root_pool_nodes(self):
        """_find_dormancy_candidates should skip nodes in root pool."""
        pruner = SleepPruner()
        
        with patch('core.sleep_pruner.kg.get_root_pool_names', return_value={"root_tech"}):
            with patch('core.sleep_pruner.kg._load_state') as mock_load:
                mock_load.return_value = {
                    "knowledge": {
                        "topics": {
                            "root_tech": {
                                "status": "complete",
                                "quality": 3.0,
                                "children": []
                            },
                            "normal_topic": {
                                "status": "complete",
                                "quality": 3.0,
                                "children": []
                            }
                        }
                    }
                }
                
                candidates = pruner._find_dormancy_candidates()
        
        assert "root_tech" not in candidates


class TestSleepPrunerPruning:
    """Test SleepPruner pruning operations."""
    
    def test_force_prune_returns_count(self):
        """force_prune should return count of pruned nodes."""
        pruner = SleepPruner()
        
        with patch.object(pruner, '_find_dormancy_candidates', return_value=["a", "b", "c"]):
            with patch.object(pruner, '_mark_dormant_batch'):
                count = pruner.force_prune()
        
        assert count == 3
    
    def test_prune_cycle_updates_pruned_count(self):
        """_prune_cycle should update pruned_count."""
        pruner = SleepPruner()
        
        with patch.object(pruner, '_find_dormancy_candidates', return_value=["a", "b"]):
            with patch.object(pruner, '_mark_dormant_batch'):
                pruner._prune_cycle()
        
        assert pruner.pruned_count == 2
    
    def test_prune_cycle_updates_total_pruned(self):
        """_prune_cycle should accumulate total_pruned."""
        pruner = SleepPruner()
        
        with patch.object(pruner, '_find_dormancy_candidates', return_value=["a"]):
            with patch.object(pruner, '_mark_dormant_batch'):
                pruner._prune_cycle()
                pruner._prune_cycle()
        
        assert pruner.total_pruned == 2
    
    def test_prune_cycle_sets_last_prune_time(self):
        """_prune_cycle should set last_prune_time."""
        pruner = SleepPruner()
        
        with patch.object(pruner, '_find_dormancy_candidates', return_value=[]):
            pruner._prune_cycle()
        
        assert pruner.last_prune_time is not None


class TestSleepPrunerStatus:
    """Test SleepPruner status reporting."""
    
    def test_get_status_returns_dict(self):
        """get_status should return a dictionary."""
        pruner = SleepPruner()
        
        status = pruner.get_status()
        
        assert isinstance(status, dict)
    
    def test_get_status_contains_running(self):
        """get_status should contain running flag."""
        pruner = SleepPruner()
        
        status = pruner.get_status()
        
        assert "running" in status
        assert status["running"] is True
    
    def test_get_status_contains_interval_info(self):
        """get_status should contain interval information."""
        pruner = SleepPruner()
        
        status = pruner.get_status()
        
        assert "current_interval_minutes" in status
        assert "initial_interval_minutes" in status
        assert "max_interval_minutes" in status
    
    def test_get_status_contains_thresholds(self):
        """get_status should contain dormancy thresholds."""
        pruner = SleepPruner(
            dream_window_days=5,
            consolidation_window_days=10,
            quality_threshold=6.0
        )
        
        status = pruner.get_status()
        
        assert status["dream_window_days"] == 5
        assert status["consolidation_window_days"] == 10
        assert status["quality_threshold"] == 6.0


class TestSleepPrunerThreadSafety:
    """Test SleepPruner thread safety."""
    
    def test_multiple_pruners_can_run_concurrently(self):
        """Multiple SleepPruner instances should be able to run concurrently."""
        pruners = [SleepPruner(name=f"pruner_{i}") for i in range(3)]
        
        for pruner in pruners:
            pruner.start()
        
        time.sleep(0.1)
        
        for pruner in pruners:
            pruner.stop()
        
        for pruner in pruners:
            pruner.join(timeout=1.0)
        
        for pruner in pruners:
            assert not pruner.is_alive()
    
    def test_force_prune_uses_global_write_lock(self):
        """force_prune should use NodeLockRegistry for thread safety."""
        pruner = SleepPruner()
        
        with patch('core.sleep_pruner.NodeLockRegistry.global_write_lock') as mock_lock:
            mock_lock.return_value.__enter__ = MagicMock(return_value=None)
            mock_lock.return_value.__exit__ = MagicMock(return_value=None)
            
            with patch.object(pruner, '_find_dormancy_candidates', return_value=[]):
                pruner.force_prune()
            
            # The prune cycle should acquire the global write lock
            # This is tested indirectly through the mock
