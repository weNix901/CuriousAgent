"""Tests for ExplorationHistory - thread-safe recording of exploration events."""
import threading
import time
from datetime import datetime, timezone, timedelta
import pytest
from core.exploration_history import ExplorationHistory


class TestExplorationHistory:
    """Test suite for ExplorationHistory class."""

    def setup_method(self):
        """Clear singleton and history before each test."""
        # Reset singleton instance
        ExplorationHistory._instance = None
        # Clear history in state
        history = ExplorationHistory()
        history._save_history({
            "co_occurrence": {},
            "insight_generation": {},
            "predictions": {}
        })

    def test_singleton_behavior(self):
        """ExplorationHistory should be a singleton."""
        instance1 = ExplorationHistory()
        instance2 = ExplorationHistory()
        
        assert instance1 is instance2

    def test_record_exploration(self):
        """record_exploration should store co-occurrence data."""
        history = ExplorationHistory()
        now = datetime.now(timezone.utc)
        
        history.record_exploration("topic_a", ["topic_b", "topic_c"], now)
        
        # Check co-occurrence was recorded
        data = history._get_history()
        
        # Should have entries for topic_a|topic_b and topic_a|topic_c
        key_ab = "topic_a|topic_b"
        key_ac = "topic_a|topic_c"
        
        assert key_ab in data["co_occurrence"] or f"topic_b|topic_a" in data["co_occurrence"]
        assert key_ac in data["co_occurrence"] or f"topic_c|topic_a" in data["co_occurrence"]

    def test_co_occurred_time_filtering(self):
        """co_occurred should respect time window."""
        history = ExplorationHistory()
        now = datetime.now(timezone.utc)
        
        # Record exploration 2 hours ago
        past_time = now - timedelta(hours=2)
        history.record_exploration("topic_a", ["topic_b"], past_time)
        
        # Check within 3 hours - should be True
        assert history.co_occurred("topic_a", "topic_b", within_hours=3) is True
        
        # Check within 1 hour - should be False
        assert history.co_occurred("topic_a", "topic_b", within_hours=1) is False

    def test_co_occurred_different_topics(self):
        """co_occurred should return False for topics that never co-occurred."""
        history = ExplorationHistory()
        
        # No explorations recorded
        assert history.co_occurred("topic_x", "topic_y", within_hours=24) is False

    def test_record_insight_generation(self):
        """record_insight_generation should store insight data."""
        history = ExplorationHistory()
        now = datetime.now(timezone.utc)
        
        history.record_insight_generation("insight_001", ("topic_a", "topic_b"), now)
        
        data = history._get_history()
        
        assert "insight_001" in data["insight_generation"]
        insight = data["insight_generation"]["insight_001"]
        assert list(insight["source_pair"]) == ["topic_a", "topic_b"]
        assert insight["triggered"] is False

    def test_was_insight_triggered_false_initially(self):
        """was_insight_triggered should return False for new insights."""
        history = ExplorationHistory()
        now = datetime.now(timezone.utc)
        
        history.record_insight_generation("insight_001", ("topic_a", "topic_b"), now)
        
        assert history.was_insight_triggered("insight_001", within_days=7) is False

    def test_record_prediction_and_outcome(self):
        """record_prediction and record_outcome should work together."""
        history = ExplorationHistory()
        
        # Record a prediction
        history.record_prediction("topic_x", predicted_confidence=0.8, is_hypothesis=True)
        
        # Get the prediction
        pred = history.get_prediction("topic_x")
        assert pred is not None
        assert pred["predicted_confidence"] == 0.8
        assert pred["is_hypothesis"] is True
        assert pred["actual_outcome"] is None
        
        # Record the outcome
        history.record_outcome("topic_x", actual_correct=True)
        
        # Check outcome was recorded
        pred = history.get_prediction("topic_x")
        assert pred["actual_outcome"] is True

    def test_get_all_predictions(self):
        """get_all_predictions should return all predictions."""
        history = ExplorationHistory()
        
        history.record_prediction("topic_a", 0.7, False)
        history.record_prediction("topic_b", 0.9, True)
        
        all_preds = history.get_all_predictions()
        
        assert len(all_preds) == 2
        topics = [p["topic"] for p in all_preds]
        assert "topic_a" in topics
        assert "topic_b" in topics

    def test_get_prediction_nonexistent(self):
        """get_prediction should return None for nonexistent topic."""
        history = ExplorationHistory()
        
        pred = history.get_prediction("nonexistent_topic")
        assert pred is None

    def test_thread_safety_concurrent_writes(self):
        """Concurrent writes from multiple threads should not cause data corruption."""
        history = ExplorationHistory()
        errors = []
        results = {"explorations": 0, "predictions": 0, "insights": 0}
        results_lock = threading.Lock()
        
        def write_explorations(thread_id: int, iterations: int):
            try:
                for i in range(iterations):
                    now = datetime.now(timezone.utc)
                    history.record_exploration(
                        f"topic_{thread_id}_{i}",
                        [f"related_{thread_id}_{i}"],
                        now
                    )
                    with results_lock:
                        results["explorations"] += 1
            except Exception as e:
                errors.append(f"exploration_{thread_id}: {e}")
        
        def write_predictions(thread_id: int, iterations: int):
            try:
                for i in range(iterations):
                    history.record_prediction(
                        f"pred_{thread_id}_{i}",
                        predicted_confidence=0.5 + (i * 0.05),
                        is_hypothesis=(i % 2 == 0)
                    )
                    with results_lock:
                        results["predictions"] += 1
            except Exception as e:
                errors.append(f"prediction_{thread_id}: {e}")
        
        def write_insights(thread_id: int, iterations: int):
            try:
                for i in range(iterations):
                    now = datetime.now(timezone.utc)
                    history.record_insight_generation(
                        f"insight_{thread_id}_{i}",
                        (f"source_a_{thread_id}_{i}", f"source_b_{thread_id}_{i}"),
                        now
                    )
                    with results_lock:
                        results["insights"] += 1
            except Exception as e:
                errors.append(f"insight_{thread_id}: {e}")
        
        # Create 5 threads, each doing 10 writes of each type
        threads = []
        for thread_id in range(5):
            threads.append(threading.Thread(target=write_explorations, args=(thread_id, 10)))
            threads.append(threading.Thread(target=write_predictions, args=(thread_id, 10)))
            threads.append(threading.Thread(target=write_insights, args=(thread_id, 10)))
        
        # Start all threads
        for t in threads:
            t.start()
        
        # Wait for all threads with timeout (deadlock detection)
        for t in threads:
            t.join(timeout=10.0)
        
        # Check no threads are still alive (deadlock indicator)
        alive_threads = [t for t in threads if t.is_alive()]
        assert len(alive_threads) == 0, f"Deadlock detected: {len(alive_threads)} threads still alive"
        
        # Check no errors occurred
        assert len(errors) == 0, f"Errors during concurrent writes: {errors}"
        
        # Check all operations completed
        assert results["explorations"] == 50  # 5 threads * 10 iterations
        assert results["predictions"] == 50
        assert results["insights"] == 50

    def test_co_occurred_sorted_key(self):
        """co_occurred should work regardless of topic order."""
        history = ExplorationHistory()
        now = datetime.now(timezone.utc)
        
        history.record_exploration("zebra", ["apple"], now)
        
        # Should work in both orders
        assert history.co_occurred("zebra", "apple", within_hours=1) is True
        assert history.co_occurred("apple", "zebra", within_hours=1) is True
