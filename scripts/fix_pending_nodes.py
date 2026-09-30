#!/usr/bin/env python3
"""
Batch fix for pending KG nodes - Scheduler Lite migration script.

This script:
1. Finds all pending nodes in KG that are NOT in queue
2. Assesses exploration worthiness
3. Injects worthy nodes to queue
4. Marks stale/empty nodes as "no_content"

Run once after deploying Scheduler Lite enhancement.
"""

import sys
import os
import logging
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def assess_worthiness(node: dict) -> float:
    """Assess if a pending node is worth exploring (0-1 score)."""
    quality = node.get("quality", 0) or 0
    depth = node.get("depth", 5)
    summary = node.get("summary", "") or ""
    topic = node.get("topic", "")
    
    score = 0.0
    
    # Factor 1: Quality
    if quality >= 7:
        score += 0.4
    elif quality >= 5:
        score += 0.3
    elif quality >= 3:
        score += 0.2
    else:
        score += 0.1
    
    # Factor 2: Depth
    score += min(0.2, depth * 0.02)
    
    # Factor 3: Content
    if len(summary) > 50:
        score += 0.2
    elif len(summary) > 0:
        score += 0.1
    
    # Factor 4: Topic length
    if len(topic) > 20:
        score += 0.1
    
    # Factor 5: Penalize test topics
    test_indicators = ["test", "partial", "stub", "example", "demo"]
    if any(ind in topic.lower() for ind in test_indicators):
        score *= 0.5
    
    return min(1.0, score)


def main():
    print("=" * 60)
    print("Scheduler Lite - Batch Fix for Pending Nodes")
    print("=" * 60)
    print()
    
    # Import CA modules
    try:
        from core.kg.repository_factory import get_kg_factory
        from core.tools.queue_tools import QueueStorage
        from core import knowledge_graph_compat as kg
    except ImportError as e:
        print(f"Error importing CA modules: {e}")
        print("Run from /root/dev/curious-agent directory")
        sys.exit(1)
    
    # Initialize
    kg_factory = get_kg_factory()
    queue_storage = QueueStorage()
    queue_storage.initialize()
    
    # Get all nodes
    print("Scanning KG for pending nodes...")
    all_nodes = kg_factory.get_all_nodes_sync(limit=5000)
    
    # Get queue topics
    queue_items = queue_storage.get_pending_items()
    queue_topics = {item.get("topic", "") for item in queue_items}
    
    print(f"Total KG nodes: {len(all_nodes)}")
    print(f"Queue pending items: {len(queue_items)}")
    print()
    
    # Find pending nodes not in queue
    pending_not_in_queue = []
    for node in all_nodes:
        if node.get("status") == "pending":
            topic = node.get("topic", "")
            if topic and topic not in queue_topics:
                pending_not_in_queue.append(node)
    
    print(f"Pending nodes NOT in queue: {len(pending_not_in_queue)}")
    print()
    
    if not pending_not_in_queue:
        print("✅ No pending nodes need fixing!")
        return
    
    # Process each node
    injected = 0
    marked_no_content = 0
    skipped = 0
    
    print("Processing nodes...")
    print("-" * 60)
    
    for node in pending_not_in_queue:
        topic = node.get("topic", "")
        quality = node.get("quality", 0) or 0
        summary = node.get("summary", "") or ""
        
        worthiness = assess_worthiness(node)
        
        print(f"\nTopic: {topic[:60]}")
        print(f"  Quality: {quality}, Worthiness: {worthiness:.2f}")
        
        # Decision logic
        if worthiness >= 0.3:
            # Inject to queue
            priority = min(10, max(3, int(worthiness * 10)))
            try:
                queue_storage.add_item(
                    topic,
                    priority=priority,
                    metadata={
                        "source": "scheduler_batch_fix",
                        "original_status": "pending",
                        "quality": quality,
                        "worthiness": worthiness,
                        "fixed_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                injected += 1
                print(f"  ✅ INJECTED to queue (priority={priority})")
            except Exception as e:
                print(f"  ❌ FAILED to inject: {e}")
        elif len(summary.strip()) < 30:
            # Mark as no_content using knowledge_graph_compat
            try:
                import asyncio
                from core.kg.repository_factory import get_kg_factory
                
                async def _update():
                    factory = get_kg_factory()
                    repo = await factory._ensure_connected()
                    return await repo.update_status(topic, "no_content")
                
                result = asyncio.run(_update())
                if result:
                    marked_no_content += 1
                    print(f"  🗑️  MARKED as no_content (empty)")
                else:
                    print(f"  ⚠️  NOT MARKED (may not exist)")
            except Exception as e:
                print(f"  ❌ FAILED to mark: {e}")
        else:
            skipped += 1
            print(f"  ⏭️  SKIPPED (low worthiness, has some content)")
    
    print()
    print("=" * 60)
    print("Summary:")
    print(f"  Injected to queue: {injected}")
    print(f"  Marked no_content: {marked_no_content}")
    print(f"  Skipped: {skipped}")
    print(f"  Total processed: {len(pending_not_in_queue)}")
    print("=" * 60)
    
    if injected > 0:
        print(f"\n✅ {injected} nodes will be explored by ExploreDaemon")
        print("   (next DreamAgent cycle or manual trigger)")
    
    if marked_no_content > 0:
        print(f"\n🗑️  {marked_no_content} nodes marked for cleanup by SleepPruner")


if __name__ == "__main__":
    main()
