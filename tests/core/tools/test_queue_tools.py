"""Tests for queue tools with SQLite storage."""
import asyncio
import os
import sqlite3
import tempfile
import time
import uuid
from pathlib import Path

import pytest

from core.tools.queue_tools import (
    AddToQueueTool,
    ClaimQueueTool,
    GetQueueTool,
    MarkDoneTool,
    MarkFailedTool,
    QueueStorage,
)


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_queue.db")
        yield db_path


@pytest.fixture
def queue_storage(temp_db_path):
    """Create a QueueStorage instance with temporary database."""
    storage = QueueStorage(db_path=temp_db_path)
    storage.initialize()
    yield storage
    storage.close()


@pytest.fixture
def queue_tools(temp_db_path):
    """Create all queue tools with shared storage."""
    storage = QueueStorage(db_path=temp_db_path)
    storage.initialize()
    
    tools = {
        "add": AddToQueueTool(storage),
        "claim": ClaimQueueTool(storage),
        "get": GetQueueTool(storage),
        "done": MarkDoneTool(storage),
        "failed": MarkFailedTool(storage),
    }
    
    yield tools
    
    storage.close()


class TestQueueStorage:
    """Tests for QueueStorage class."""

    def test_initialize_creates_table(self, queue_storage):
        """Test that initialize creates the queue table."""
        conn = queue_storage._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='queue'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_initialize_idempotent(self, queue_storage):
        """Test that initialize can be called multiple times safely."""
        queue_storage.initialize()
        queue_storage.initialize()
        conn = queue_storage._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM queue")
        assert cursor.fetchone()[0] == 0
        conn.close()

    def test_add_item(self, queue_storage):
        """Test adding an item to the queue."""
        item_id = queue_storage.add_item(
            topic="test topic",
            priority=5,
            metadata={"source": "test"},
        )
        assert item_id is not None
        
        conn = queue_storage._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT topic, priority, status FROM queue WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "test topic"
        assert row[1] == 5
        assert row[2] == "pending"
        conn.close()

    def test_get_pending_items(self, queue_storage):
        """Test getting pending items ordered by priority."""
        queue_storage.add_item("low priority", priority=1)
        queue_storage.add_item("high priority", priority=10)
        queue_storage.add_item("medium priority", priority=5)
        
        items = queue_storage.get_pending_items()
        assert len(items) == 3
        assert items[0]["topic"] == "high priority"
        assert items[1]["topic"] == "medium priority"
        assert items[2]["topic"] == "low priority"

    def test_claim_item(self, queue_storage):
        """Test claiming an item atomically."""
        item_id = queue_storage.add_item("test topic", priority=5)
        holder_id = str(uuid.uuid4())
        
        claimed = queue_storage.claim_item(item_id, holder_id)
        assert claimed is True
        
        conn = queue_storage._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT status, holder_id, claimed_at FROM queue WHERE id = ?",
            (item_id,)
        )
        row = cursor.fetchone()
        assert row[0] == "claimed"
        assert row[1] == holder_id
        assert row[2] is not None
        conn.close()

    def test_claim_nonexistent_item(self, queue_storage):
        """Test claiming a non-existent item fails."""
        holder_id = str(uuid.uuid4())
        claimed = queue_storage.claim_item(99999, holder_id)
        assert claimed is False

    def test_mark_done(self, queue_storage):
        """Test marking an item as done."""
        item_id = queue_storage.add_item("test topic", priority=5)
        holder_id = str(uuid.uuid4())
        queue_storage.claim_item(item_id, holder_id)
        
        result = queue_storage.mark_done(item_id, holder_id)
        assert result is True
        
        conn = queue_storage._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM queue WHERE id = ?", (item_id,))
        assert cursor.fetchone()[0] == "done"
        conn.close()

    def test_mark_done_wrong_holder(self, queue_storage):
        """Test marking done with wrong holder_id fails."""
        item_id = queue_storage.add_item("test topic", priority=5)
        holder_id = str(uuid.uuid4())
        queue_storage.claim_item(item_id, holder_id)
        
        result = queue_storage.mark_done(item_id, "wrong_holder")
        assert result is False
        
        conn = queue_storage._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM queue WHERE id = ?", (item_id,))
        assert cursor.fetchone()[0] == "claimed"
        conn.close()

    def test_mark_failed_with_requeue(self, queue_storage):
        """Test marking an item as failed requeues it."""
        item_id = queue_storage.add_item("test topic", priority=5)
        holder_id = str(uuid.uuid4())
        queue_storage.claim_item(item_id, holder_id)
        
        result = queue_storage.mark_failed(item_id, holder_id, requeue=True)
        assert result is True
        
        conn = queue_storage._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT status, holder_id, claim_timeout FROM queue WHERE id = ?",
            (item_id,)
        )
        row = cursor.fetchone()
        assert row[0] == "pending"
        assert row[1] is None
        assert row[2] is None
        conn.close()

    def test_mark_failed_without_requeue(self, queue_storage):
        """Test marking an item as failed without requeue."""
        item_id = queue_storage.add_item("test topic", priority=5)
        holder_id = str(uuid.uuid4())
        queue_storage.claim_item(item_id, holder_id)
        
        result = queue_storage.mark_failed(item_id, holder_id, requeue=False)
        assert result is True
        
        conn = queue_storage._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM queue WHERE id = ?", (item_id,))
        assert cursor.fetchone()[0] == "failed"
        conn.close()

    def test_release_expired_claims(self, queue_storage):
        """Test that expired claims are released."""
        item_id = queue_storage.add_item("test topic", priority=5)
        holder_id = str(uuid.uuid4())
        queue_storage.claim_item(item_id, holder_id, timeout_seconds=1)
        
        time.sleep(1.5)
        
        released_count = queue_storage.release_expired_claims()
        assert released_count >= 1
        
        conn = queue_storage._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status, holder_id FROM queue WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        assert row[0] == "pending"
        assert row[1] is None
        conn.close()

    def test_get_claimed_items(self, queue_storage):
        """Test getting claimed items by holder_id."""
        holder_id = str(uuid.uuid4())
        item_id1 = queue_storage.add_item("topic 1", priority=5)
        item_id2 = queue_storage.add_item("topic 2", priority=3)
        queue_storage.claim_item(item_id1, holder_id)
        queue_storage.claim_item(item_id2, holder_id)
        
        claimed = queue_storage.get_claimed_items(holder_id)
        assert len(claimed) == 2
        topics = {item["topic"] for item in claimed}
        assert "topic 1" in topics
        assert "topic 2" in topics

    def test_close(self, temp_db_path):
        """Test closing the storage."""
        storage = QueueStorage(db_path=temp_db_path)
        storage.initialize()
        storage.close()
        assert storage._connection is None


class TestAddToQueueTool:
    """Tests for AddToQueueTool."""

    @pytest.mark.asyncio
    async def test_add_to_queue_basic(self, queue_tools):
        """Test basic add to queue functionality."""
        result = await queue_tools["add"].execute(
            topic="test topic",
            priority=5,
        )
        assert "added" in result.lower()
        assert "test topic" in result

    @pytest.mark.asyncio
    async def test_add_to_queue_with_metadata(self, queue_tools):
        """Test adding to queue with metadata."""
        result = await queue_tools["add"].execute(
            topic="test topic",
            priority=7,
            metadata={"source": "test", "depth": 5},
        )
        assert "added" in result.lower()

    @pytest.mark.asyncio
    async def test_add_to_queue_default_priority(self, queue_tools):
        """Test adding with default priority."""
        result = await queue_tools["add"].execute(topic="test topic")
        assert "added" in result.lower()

    def test_add_to_queue_properties(self, queue_tools):
        """Test tool properties."""
        tool = queue_tools["add"]
        assert tool.name == "add_to_queue"
        assert "queue" in tool.description.lower()
        assert "properties" in tool.parameters


class TestClaimQueueTool:
    """Tests for ClaimQueueTool."""

    @pytest.mark.asyncio
    async def test_claim_queue_basic(self, queue_tools):
        """Test basic claim functionality."""
        item_id = queue_tools["claim"]._storage.add_item("test topic", priority=5)
        holder_id = str(uuid.uuid4())
        
        result = await queue_tools["claim"].execute(
            item_id=item_id,
            holder_id=holder_id,
        )
        assert "claimed" in result.lower()

    @pytest.mark.asyncio
    async def test_claim_queue_with_custom_timeout(self, queue_tools):
        """Test claiming with custom timeout."""
        item_id = queue_tools["claim"]._storage.add_item("test topic", priority=5)
        holder_id = str(uuid.uuid4())
        
        result = await queue_tools["claim"].execute(
            item_id=item_id,
            holder_id=holder_id,
            timeout_seconds=600,
        )
        assert "claimed" in result.lower()

    @pytest.mark.asyncio
    async def test_claim_nonexistent_item(self, queue_tools):
        """Test claiming non-existent item."""
        holder_id = str(uuid.uuid4())
        result = await queue_tools["claim"].execute(
            item_id=99999,
            holder_id=holder_id,
        )
        assert "not found" in result.lower() or "failed" in result.lower()

    def test_claim_queue_properties(self, queue_tools):
        """Test tool properties."""
        tool = queue_tools["claim"]
        assert tool.name == "claim_queue"
        assert "claim" in tool.description.lower()
        assert "holder_id" in str(tool.parameters)


class TestGetQueueTool:
    """Tests for GetQueueTool."""

    @pytest.mark.asyncio
    async def test_get_queue_empty(self, queue_tools):
        """Test getting empty queue."""
        result = await queue_tools["get"].execute()
        assert "0" in result or "empty" in result.lower()

    @pytest.mark.asyncio
    async def test_get_queue_with_items(self, queue_tools):
        """Test getting queue with items."""
        queue_tools["claim"]._storage.add_item("topic 1", priority=5)
        queue_tools["claim"]._storage.add_item("topic 2", priority=10)
        queue_tools["claim"]._storage.add_item("topic 3", priority=3)
        
        result = await queue_tools["get"].execute()
        assert "topic 2" in result
        assert "topic 1" in result
        assert "topic 3" in result

    @pytest.mark.asyncio
    async def test_get_queue_with_limit(self, queue_tools):
        """Test getting queue with limit."""
        for i in range(10):
            queue_tools["claim"]._storage.add_item(f"topic {i}", priority=i)
        
        result = await queue_tools["get"].execute(limit=3)
        assert "topic 9" in result
        assert "topic 8" in result
        assert "topic 7" in result

    def test_get_queue_properties(self, queue_tools):
        """Test tool properties."""
        tool = queue_tools["get"]
        assert tool.name == "get_queue"
        assert "queue" in tool.description.lower() or "pending" in tool.description.lower()


class TestMarkDoneTool:
    """Tests for MarkDoneTool."""

    @pytest.mark.asyncio
    async def test_mark_done_basic(self, queue_tools):
        """Test basic mark done functionality."""
        storage = queue_tools["done"]._storage
        item_id = storage.add_item("test topic", priority=5)
        holder_id = str(uuid.uuid4())
        storage.claim_item(item_id, holder_id)
        
        result = await queue_tools["done"].execute(
            item_id=item_id,
            holder_id=holder_id,
        )
        assert "marked" in result.lower() or "complete" in result.lower()

    @pytest.mark.asyncio
    async def test_mark_done_wrong_holder(self, queue_tools):
        """Test marking done with wrong holder."""
        storage = queue_tools["done"]._storage
        item_id = storage.add_item("test topic", priority=5)
        holder_id = str(uuid.uuid4())
        storage.claim_item(item_id, holder_id)
        
        result = await queue_tools["done"].execute(
            item_id=item_id,
            holder_id="wrong_holder",
        )
        assert "failed" in result.lower() or "not claimed" in result.lower()

    @pytest.mark.asyncio
    async def test_mark_done_unclaimed_item(self, queue_tools):
        """Test marking done on unclaimed item."""
        storage = queue_tools["done"]._storage
        item_id = storage.add_item("test topic", priority=5)
        
        result = await queue_tools["done"].execute(
            item_id=item_id,
            holder_id=str(uuid.uuid4()),
        )
        assert "failed" in result.lower() or "not claimed" in result.lower()

    def test_mark_done_properties(self, queue_tools):
        """Test tool properties."""
        tool = queue_tools["done"]
        assert tool.name == "mark_done"
        assert "complete" in tool.description.lower() or "done" in tool.description.lower()


class TestMarkFailedTool:
    """Tests for MarkFailedTool."""

    @pytest.mark.asyncio
    async def test_mark_failed_with_requeue(self, queue_tools):
        """Test marking failed with requeue."""
        storage = queue_tools["failed"]._storage
        item_id = storage.add_item("test topic", priority=5)
        holder_id = str(uuid.uuid4())
        storage.claim_item(item_id, holder_id)
        
        result = await queue_tools["failed"].execute(
            item_id=item_id,
            holder_id=holder_id,
            requeue=True,
        )
        assert "marked" in result.lower() or "requeue" in result.lower()

    @pytest.mark.asyncio
    async def test_mark_failed_without_requeue(self, queue_tools):
        """Test marking failed without requeue."""
        storage = queue_tools["failed"]._storage
        item_id = storage.add_item("test topic", priority=5)
        holder_id = str(uuid.uuid4())
        storage.claim_item(item_id, holder_id)
        
        result = await queue_tools["failed"].execute(
            item_id=item_id,
            holder_id=holder_id,
            requeue=False,
        )
        assert "marked" in result.lower() or "failed" in result.lower()

    @pytest.mark.asyncio
    async def test_mark_failed_with_reason(self, queue_tools):
        """Test marking failed with reason."""
        storage = queue_tools["failed"]._storage
        item_id = storage.add_item("test topic", priority=5)
        holder_id = str(uuid.uuid4())
        storage.claim_item(item_id, holder_id)
        
        result = await queue_tools["failed"].execute(
            item_id=item_id,
            holder_id=holder_id,
            requeue=False,
            reason="test failure reason",
        )
        assert "marked" in result.lower()

    def test_mark_failed_properties(self, queue_tools):
        """Test tool properties."""
        tool = queue_tools["failed"]
        assert tool.name == "mark_failed"
        assert "failed" in tool.description.lower()


class TestQueueToolsIntegration:
    """Integration tests for complete queue workflow."""

    @pytest.mark.asyncio
    async def test_full_queue_workflow(self, queue_tools):
        """Test complete workflow: add -> claim -> mark_done."""
        storage = queue_tools["add"]._storage
        
        result = await queue_tools["add"].execute(
            topic="integration test topic",
            priority=8,
        )
        assert "added" in result.lower()
        
        items = storage.get_pending_items()
        assert len(items) == 1
        item_id = items[0]["id"]
        
        holder_id = str(uuid.uuid4())
        result = await queue_tools["claim"].execute(
            item_id=item_id,
            holder_id=holder_id,
        )
        assert "claimed" in result.lower()
        
        result = await queue_tools["done"].execute(
            item_id=item_id,
            holder_id=holder_id,
        )
        assert "marked" in result.lower() or "complete" in result.lower()
        
        items = storage.get_pending_items()
        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_claim_timeout_release(self, queue_tools):
        """Test that claimed items are released after timeout."""
        storage = queue_tools["claim"]._storage
        
        item_id = storage.add_item("timeout test", priority=5)
        holder_id = str(uuid.uuid4())
        
        await queue_tools["claim"].execute(
            item_id=item_id,
            holder_id=holder_id,
            timeout_seconds=1,
        )
        
        claimed = storage.get_claimed_items(holder_id)
        assert len(claimed) == 1
        
        time.sleep(1.5)
        
        storage.release_expired_claims()
        
        claimed = storage.get_claimed_items(holder_id)
        assert len(claimed) == 0

    @pytest.mark.asyncio
    async def test_failed_requeue_workflow(self, queue_tools):
        """Test workflow: add -> claim -> mark_failed(requeue) -> claim again."""
        storage = queue_tools["add"]._storage
        
        item_id = storage.add_item("requeue test", priority=5)
        holder_id1 = str(uuid.uuid4())
        
        result = await queue_tools["claim"].execute(
            item_id=item_id,
            holder_id=holder_id1,
        )
        assert "claimed" in result.lower()
        
        result = await queue_tools["failed"].execute(
            item_id=item_id,
            holder_id=holder_id1,
            requeue=True,
        )
        assert "requeue" in result.lower() or "marked" in result.lower()
        
        holder_id2 = str(uuid.uuid4())
        result = await queue_tools["claim"].execute(
            item_id=item_id,
            holder_id=holder_id2,
        )
        assert "claimed" in result.lower()
