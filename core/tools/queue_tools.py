"""Queue tools for curiosity management with SQLite storage."""
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional, Tuple

from core.tools.base import Tool

logger = logging.getLogger(__name__)


class QueueStorage:
    """SQLite-based storage for the curiosity queue."""

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(Path(__file__).parent.parent.parent / "knowledge" / "queue.db")
        self._db_path = db_path
        self._connection: sqlite3.Connection | None = None
        self._dedup_enabled: bool = True

    def _get_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            self._connection = sqlite3.connect(self._db_path, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
        return self._connection

    def initialize(self) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                priority INTEGER DEFAULT 5,
                metadata TEXT,
                status TEXT DEFAULT 'pending',
                holder_id TEXT,
                claimed_at REAL,
                claim_timeout REAL,
                completed_at REAL,
                failed_reason TEXT,
                created_at REAL DEFAULT (strftime('%s', 'now')),
                requeue_count INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_queue_status ON queue(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_queue_priority ON queue(priority DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_queue_holder ON queue(holder_id)
        """)
        conn.commit()

    def set_dedup_enabled(self, enabled: bool) -> None:
        self._dedup_enabled = enabled

    def check_duplicate_topic(self, topic: str) -> Optional[Tuple[str, float, str]]:
        """Check if topic duplicates existing queue items using concept dedup."""
        if not self._dedup_enabled:
            return None
        
        from core.concept_normalizer import get_default_normalizer
        
        normalizer = get_default_normalizer()
        pending_items = self.get_pending_items()
        done_items = self.get_completed_items(limit=50)
        all_items = pending_items + done_items
        
        best_match = None
        best_similarity = 0.0
        best_type = "different_concept"
        
        for item in all_items:
            existing_topic = item.get("topic", "")
            if not existing_topic:
                continue
            
            similarity, match_type = normalizer.compute_concept_similarity(
                topic, existing_topic
            )
            
            if similarity > best_similarity:
                best_match = existing_topic
                best_similarity = similarity
                best_type = match_type
        
        if best_type in ("naming_variant", "translated_concept"):
            return (best_match, best_similarity, best_type)
        
        return None

    def add_item(self, topic: str, priority: int = 5, metadata: dict | None = None, skip_dedup: bool = False) -> int:
        if not skip_dedup:
            duplicate = self.check_duplicate_topic(topic)
            if duplicate:
                matched_topic, similarity, dup_type = duplicate
                logger.info(f"Skip duplicate queue item: '{topic}' ≈ '{matched_topic}' ({dup_type}, sim={similarity:.2f})")
                return -1
        
        conn = self._get_connection()
        cursor = conn.cursor()
        metadata_json = json.dumps(metadata) if metadata else None
        cursor.execute(
            """
            INSERT INTO queue (topic, priority, metadata, created_at)
            VALUES (?, ?, ?, strftime('%s', 'now'))
            """,
            (topic, priority, metadata_json),
        )
        conn.commit()
        rowid = cursor.lastrowid
        if rowid is None:
            raise RuntimeError("Failed to get lastrowid after insert")
        return rowid

    def get_pending_items(self, limit: int | None = None) -> list[dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        query = """
            SELECT * FROM queue
            WHERE status = 'pending'
            ORDER BY priority DESC, created_at ASC
        """
        if limit:
            query += f" LIMIT {limit}"
        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_completed_items(self, limit: int | None = None) -> list[dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        query = """
            SELECT * FROM queue
            WHERE status = 'done'
            ORDER BY completed_at DESC
        """
        if limit:
            query += f" LIMIT {limit}"
        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def claim_item(
        self, item_id: int, holder_id: str, timeout_seconds: int = 300
    ) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        now = time.time()
        cursor.execute(
            """
            UPDATE queue
            SET status = 'claimed',
                holder_id = ?,
                claimed_at = ?,
                claim_timeout = ?
            WHERE id = ? AND status = 'pending'
            """,
            (holder_id, now, now + timeout_seconds, item_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def mark_done(self, item_id: int, holder_id: str) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        now = time.time()
        cursor.execute(
            """
            UPDATE queue
            SET status = 'done',
                holder_id = NULL,
                claimed_at = NULL,
                claim_timeout = NULL,
                completed_at = ?
            WHERE id = ? AND status = 'claimed' AND holder_id = ?
            """,
            (now, item_id, holder_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def mark_failed(
        self, item_id: int, holder_id: str, requeue: bool = False, reason: str | None = None
    ) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        now = time.time()
        if requeue:
            cursor.execute(
                """
                UPDATE queue
                SET status = 'pending',
                    holder_id = NULL,
                    claimed_at = NULL,
                    claim_timeout = NULL,
                    failed_reason = ?,
                    requeue_count = requeue_count + 1
                WHERE id = ? AND status = 'claimed' AND holder_id = ?
                """,
                (reason, item_id, holder_id),
            )
        else:
            cursor.execute(
                """
                UPDATE queue
                SET status = 'failed',
                    holder_id = NULL,
                    claimed_at = NULL,
                    claim_timeout = NULL,
                    failed_reason = ?,
                    completed_at = ?
                WHERE id = ? AND status = 'claimed' AND holder_id = ?
                """,
                (reason, now, item_id, holder_id),
            )
        conn.commit()
        return cursor.rowcount > 0

    def release_expired_claims(self) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        now = time.time()
        cursor.execute(
            """
            UPDATE queue
            SET status = 'pending',
                holder_id = NULL,
                claimed_at = NULL,
                claim_timeout = NULL
            WHERE status = 'claimed' AND claim_timeout < ?
            """,
            (now,),
        )
        conn.commit()
        return cursor.rowcount

    def get_claimed_items(self, holder_id: str) -> list[dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM queue
            WHERE status = 'claimed' AND holder_id = ?
            ORDER BY claimed_at ASC
            """,
            (holder_id,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def claim_pending(self, holder_id: str, timeout_seconds: int = 300) -> dict | None:
        conn = self._get_connection()
        cursor = conn.cursor()
        now = time.time()
        cursor.execute(
            """
            SELECT * FROM queue
            WHERE status = 'pending'
            ORDER BY priority DESC, created_at ASC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        if not row:
            return None
        item_id = row["id"]
        cursor.execute(
            """
            UPDATE queue
            SET status = 'claimed',
                holder_id = ?,
                claimed_at = ?,
                claim_timeout = ?
            WHERE id = ? AND status = 'pending'
            """,
            (holder_id, now, now + timeout_seconds, item_id),
        )
        conn.commit()
        if cursor.rowcount > 0:
            return dict(row)
        return None

    def get_item(self, item_id: int) -> dict | None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM queue WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_items_by_topic(self, topic: str) -> list[dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM queue WHERE topic = ? ORDER BY created_at DESC",
            (topic,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_failed_items(self, limit: int | None = None) -> list[dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM queue WHERE status = 'failed' ORDER BY completed_at DESC"
        if limit:
            query += f" LIMIT {limit}"
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]

    def get_all_stats(self) -> dict:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT status, COUNT(*) as cnt FROM queue GROUP BY status"
        )
        stats = {"by_status": {}}
        for row in cursor.fetchall():
            stats["by_status"][row["status"]] = row["cnt"]
            stats[row["status"]] = row["cnt"]
        stats["total"] = sum(stats["by_status"].values())
        return stats

    def close(self) -> None:
        if self._connection:
            self._connection.close()
            self._connection = None


class AddToQueueTool(Tool):
    """Add an item to the curiosity queue with priority."""

    def __init__(self, storage: QueueStorage):
        self._storage = storage

    @property
    def name(self) -> str:
        return "add_to_queue"

    @property
    def description(self) -> str:
        return "Add a topic to the curiosity queue with optional priority and metadata"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The topic to add to the queue",
                },
                "priority": {
                    "type": "integer",
                    "description": "Priority level (1-10, higher = more important). Default: 5",
                    "default": 5,
                },
                "metadata": {
                    "type": "object",
                    "description": "Optional metadata about the topic",
                    "additionalProperties": True,
                },
            },
            "required": ["topic"],
        }

    async def execute(self, **kwargs: Any) -> str:
        topic = kwargs.get("topic")
        priority = kwargs.get("priority", 5)
        metadata = kwargs.get("metadata")

        if not topic:
            return "Error: topic is required"

        item_id = self._storage.add_item(topic, priority, metadata)
        return f"Added topic '{topic}' to queue with ID {item_id} and priority {priority}"


class ClaimQueueTool(Tool):
    """Atomically claim a queue item with holder_id and timeout."""

    def __init__(self, storage: QueueStorage):
        self._storage = storage

    @property
    def name(self) -> str:
        return "claim_queue"

    @property
    def description(self) -> str:
        return "Atomically claim a queue item with holder_id and timeout (default 5 minutes)"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "item_id": {
                    "type": "integer",
                    "description": "The ID of the queue item to claim",
                },
                "holder_id": {
                    "type": "string",
                    "description": "Unique identifier for the claim holder (e.g., UUID)",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Claim timeout in seconds. Default: 300 (5 minutes)",
                    "default": 300,
                },
            },
            "required": ["item_id", "holder_id"],
        }

    async def execute(self, **kwargs: Any) -> str:
        item_id = kwargs.get("item_id")
        holder_id = kwargs.get("holder_id")
        timeout_seconds = kwargs.get("timeout_seconds", 300)

        if item_id is None:
            return "Error: item_id is required"
        if not holder_id:
            return "Error: holder_id is required"

        success = self._storage.claim_item(item_id, holder_id, timeout_seconds)
        if success:
            return f"Successfully claimed queue item {item_id} with holder_id {holder_id} (timeout: {timeout_seconds}s)"
        return f"Error: Failed to claim item {item_id}. Item may not exist or is not pending"


class GetQueueTool(Tool):
    """Get pending queue items ordered by priority."""

    def __init__(self, storage: QueueStorage):
        self._storage = storage

    @property
    def name(self) -> str:
        return "get_queue"

    @property
    def description(self) -> str:
        return "Get pending queue items ordered by priority (highest first)"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of items to return. Default: all",
                },
            },
        }

    async def execute(self, **kwargs: Any) -> str:
        limit = kwargs.get("limit")
        items = self._storage.get_pending_items(limit)

        if not items:
            return "Queue is empty (0 pending items)"

        lines = [f"Pending queue items ({len(items)}):"]
        for item in items:
            metadata_str = ""
            if item.get("metadata"):
                try:
                    meta = json.loads(item["metadata"])
                    if meta:
                        metadata_str = f" metadata={meta}"
                except (json.JSONDecodeError, TypeError):
                    pass
            lines.append(
                f"  - ID {item['id']}: {item['topic']} (priority={item['priority']}, requeue_count={item.get('requeue_count', 0)}){metadata_str}"
            )
        return "\n".join(lines)


class MarkDoneTool(Tool):
    """Mark a claimed queue item as complete."""

    def __init__(self, storage: QueueStorage):
        self._storage = storage

    @property
    def name(self) -> str:
        return "mark_done"

    @property
    def description(self) -> str:
        return "Mark a claimed queue item as complete (must be claimed by the same holder_id)"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "item_id": {
                    "type": "integer",
                    "description": "The ID of the queue item to mark as done",
                },
                "holder_id": {
                    "type": "string",
                    "description": "The holder_id that claimed this item",
                },
            },
            "required": ["item_id", "holder_id"],
        }

    async def execute(self, **kwargs: Any) -> str:
        item_id = kwargs.get("item_id")
        holder_id = kwargs.get("holder_id")

        if item_id is None:
            return "Error: item_id is required"
        if not holder_id:
            return "Error: holder_id is required"

        success = self._storage.mark_done(item_id, holder_id)
        if success:
            return f"Successfully marked queue item {item_id} as done"
        return f"Error: Failed to mark item {item_id} as done. Item may not be claimed by this holder_id"


class MarkFailedTool(Tool):
    """Mark a claimed queue item as failed with optional requeue."""

    def __init__(self, storage: QueueStorage):
        self._storage = storage

    @property
    def name(self) -> str:
        return "mark_failed"

    @property
    def description(self) -> str:
        return "Mark a claimed queue item as failed, optionally requeuing it for another attempt"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "item_id": {
                    "type": "integer",
                    "description": "The ID of the queue item to mark as failed",
                },
                "holder_id": {
                    "type": "string",
                    "description": "The holder_id that claimed this item",
                },
                "requeue": {
                    "type": "boolean",
                    "description": "Whether to requeue the item for another attempt. Default: false",
                    "default": False,
                },
                "reason": {
                    "type": "string",
                    "description": "Optional reason for failure",
                },
            },
            "required": ["item_id", "holder_id"],
        }

    async def execute(self, **kwargs: Any) -> str:
        item_id = kwargs.get("item_id")
        holder_id = kwargs.get("holder_id")
        requeue = kwargs.get("requeue", False)
        reason = kwargs.get("reason")

        if item_id is None:
            return "Error: item_id is required"
        if not holder_id:
            return "Error: holder_id is required"

        success = self._storage.mark_failed(item_id, holder_id, requeue, reason)
        if success:
            if requeue:
                return f"Successfully marked queue item {item_id} as failed and requeued for another attempt"
            reason_str = f" (reason: {reason})" if reason else ""
            return f"Successfully marked queue item {item_id} as failed{reason_str}"
        return f"Error: Failed to mark item {item_id} as failed. Item may not be claimed by this holder_id"
