"""Tests for the poison-loop fix in ExploreDaemon.

Verifies that an item whose exploration repeatedly "succeeds" but writes no
KG content (the bawadou/ai-data-extractor scenario) no longer loops forever:
- It is first requeued to the BACK of the queue (so it stops starving the head).
- After max_requeue_before_purge bounces it is purged (dead-lettered) instead
  of remaining claimed / re-claiming forever.
"""
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.daemon.explore_daemon import ExploreDaemon, ExploreDaemonConfig


def _make_daemon(mock_agent, mock_queue_storage, purge_threshold=3):
    """Build a daemon wired for direct _tick() testing."""
    with patch("core.tools.queue_tools.QueueStorage"):
        daemon = ExploreDaemon(
            explore_agent=mock_agent,
            queue_storage=mock_queue_storage,
            config=ExploreDaemonConfig(
                poll_interval_seconds=0.1,
                max_retries=2,
                max_requeue_before_purge=purge_threshold,
            ),
        )
    # _tick() reads self.queue_storage (normally created inside run() thread),
    # so set it directly for synchronous unit testing.
    daemon.queue_storage = mock_queue_storage
    return daemon


class TestPoisonItemRequeuedToBack:
    """First empty-KG result should requeue to back, not loop at head."""

    @pytest.mark.asyncio
    async def test_empty_kg_requeues_to_back_not_keeps_claimed(self):
        """Empty/brief KG after 'successful' explore → requeue_to_back."""
        mock_agent = MagicMock()
        mock_agent.holder_id = "test_holder"
        mock_agent.run = AsyncMock(return_value=MagicMock(success=True, content="x"))

        mock_queue_storage = MagicMock()
        mock_queue_storage.get_pending_items.return_value = [
            {"id": 2210, "topic": "poison/thing", "priority": 5}
        ]
        mock_queue_storage.claim_item.return_value = True
        mock_queue_storage.delete_item.return_value = True
        mock_queue_storage.get_item.return_value = {
            "id": 2210, "requeue_count": 0,
        }  # persisted count 0 → first bounce
        mock_queue_storage.requeue_to_back.return_value = True

        with patch("core.daemon.explore_daemon.get_kg_factory") as mock_kg_factory:
            mock_kg_instance = MagicMock()
            # KG node missing → empty/brief path
            mock_kg_instance.get_node_sync.return_value = None
            mock_kg_factory.return_value = mock_kg_instance

            daemon = _make_daemon(mock_agent, mock_queue_storage)
            await daemon._tick()

            # Should NOT delete on a first-time empty result...
            mock_queue_storage.delete_item.assert_not_called()
            # ...but SHOULD requeue it to the back so it stops starving the head.
            mock_queue_storage.requeue_to_back.assert_called_once()


class TestPoisonItemPurgedAfterThreshold:
    """After repeated empty-KG bounces the item is purged (dead lettered)."""

    @pytest.mark.asyncio
    async def test_purges_after_repeated_empty_kg_bounces(self):
        """Once requeue_count reaches threshold, delete (purge) the poison item."""
        mock_agent = MagicMock()
        mock_agent.holder_id = "test_holder"
        mock_agent.run = AsyncMock(return_value=MagicMock(success=True, content="x"))

        mock_queue_storage = MagicMock()
        mock_queue_storage.get_pending_items.return_value = [
            {"id": 2210, "topic": "poison/thing", "priority": 5}
        ]
        mock_queue_storage.claim_item.return_value = True
        mock_queue_storage.delete_item.return_value = True
        # Already bounced purge_threshold-1 times in DB → this attempt crosses it.
        mock_queue_storage.get_item.return_value = {
            "id": 2210, "requeue_count": 2,
        }
        mock_queue_storage.requeue_to_back.return_value = True

        with patch("core.daemon.explore_daemon.get_kg_factory") as mock_kg_factory:
            mock_kg_instance = MagicMock()
            mock_kg_instance.get_node_sync.return_value = None
            mock_kg_factory.return_value = mock_kg_instance

            daemon = _make_daemon(mock_agent, mock_queue_storage, purge_threshold=3)
            await daemon._tick()

            # Should purge (delete) instead of requeueing forever
            mock_queue_storage.delete_item.assert_called_once()
            mock_queue_storage.requeue_to_back.assert_not_called()


class TestRequeueToBackBumpsTimestamp:
    """requeue_to_back should move item to back by bumping created_at."""

    def test_requeue_to_back_sql(self):
        from core.tools.queue_tools import QueueStorage

        storage = QueueStorage(db_path=":memory:")
        storage.initialize()
        sid = storage.add_item("first_item", priority=8)
        storage.add_item("second_item", priority=8)

        # Claim the first item
        assert storage.claim_item(sid, "holder-1")
        # Requeue it to the back
        assert storage.requeue_to_back(sid, "holder-1", reason="explore_success_but_kg_empty")

        # It should now be pending again and be last in FIFO order
        pending = storage.get_pending_items()
        topics = [i["topic"] for i in pending]
        assert "first_item" in topics and "second_item" in topics
        assert pending[-1]["topic"] == "first_item", f"Expected first_item last, got {topics}"

        # requeue_count should be bumped
        item = storage.get_item(sid)
        assert item["requeue_count"] == 1
        storage.close()
