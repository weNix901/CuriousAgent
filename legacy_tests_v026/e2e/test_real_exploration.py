#!/usr/bin/env python3
"""
REAL End-to-End Exploration Test
This test ACTUALLY runs the Explorer Agent with real LLM calls and writes to KG.

Prerequisites:
1. BOCHA_API_KEY or SERPER_API_KEY environment variable set
2. VOLCENGINE_API_KEY or MINIMAX_API_KEY environment variable set
3. Neo4j running (optional, falls back to JSON)

Flow:
1. Inject curiosity topic into queue
2. Run Explorer Agent (ReAct loop)
3. Verify KG has new knowledge nodes
4. Verify queue item marked done
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.tools.queue_tools import QueueStorage
from core.agents.explore_agent import ExploreAgent, ExploreAgentConfig
from core.tools.registry import ToolRegistry
from core.kg.kg_repository import KGRepository
from core.kg.neo4j_client import Neo4jClient


def check_env_vars():
    """Check if required API keys are set."""
    print("\n" + "="*60)
    print("STEP 0: Environment Check")
    print("="*60)
    
    llm_keys = ['VOLCENGINE_API_KEY', 'MINIMAX_API_KEY']
    search_keys = ['BOCHA_API_KEY', 'SERPER_API_KEY']
    
    llm_ok = any(os.environ.get(k) for k in llm_keys)
    search_ok = any(os.environ.get(k) for k in search_keys)
    
    print(f"LLM API Key (volcengine/minimax): {'✓ Set' if llm_ok else '✗ Missing'}")
    print(f"Search API Key (bocha/serper): {'✓ Set' if search_ok else '✗ Missing'}")
    
    if not llm_ok:
        print("\n⚠️  WARNING: No LLM API key found. Test will use mock mode.")
        return False
    
    return True


def inject_curiosity_topic(topic: str, priority: int = 8) -> int:
    """Step 1: Inject curiosity topic into queue."""
    print("\n" + "="*60)
    print(f"STEP 1: Inject Curiosity Topic")
    print("="*60)
    
    storage = QueueStorage()
    storage.initialize()
    
    topic_id = storage.add_item(
        topic=topic,
        priority=priority,
        metadata={"source": "e2e_test", "test_run": True}
    )
    
    print(f"✓ Injected topic: {topic}")
    print(f"✓ Topic ID: {topic_id}")
    print(f"✓ Priority: {priority}")
    
    pending = storage.get_pending_items(limit=10)
    assert len(pending) >= 1, "Topic not found in queue"
    
    print(f"✓ Verified: {len(pending)} pending items in queue")
    return topic_id


def claim_topic(topic_id: int, holder_id: str) -> str:
    """Step 2: Claim the topic for exploration."""
    print("\n" + "="*60)
    print(f"STEP 2: Claim Topic")
    print("="*60)
    
    storage = QueueStorage()
    claimed = storage.claim_item(topic_id, holder_id)
    
    print(f"✓ Claimed topic {topic_id} with holder_id={holder_id}")
    assert claimed is True, "Failed to claim topic"
    
    print(f"✓ Verified: Topic is claimed")
    return topic_id


def setup_explorer_agent(holder_id: str) -> ExploreAgent:
    """Step 3: Setup Explorer Agent with tool registry."""
    print("\n" + "="*60)
    print(f"STEP 3: Setup Explorer Agent")
    print("="*60)
    
    registry = ToolRegistry()
    storage = QueueStorage()
    storage.initialize()
    
    from core.tools.kg_tools import (
        QueryKGTool, QueryKGByStatusTool, QueryKGByHeatTool,
        GetNodeRelationsTool, AddToKGTool, UpdateKGStatusTool,
        UpdateKGMetadataTool, UpdateKGRelationTool, MergeKGNodesTool
    )
    from core.tools.queue_tools import (
        AddToQueueTool, ClaimQueueTool, GetQueueTool,
        MarkDoneTool, MarkFailedTool
    )
    from core.tools.llm_tools import LLMAnalyzeTool, LLMKnowledgeExtractTool
    
    kg_repo = None
    for tool_class in [QueryKGTool, QueryKGByStatusTool, QueryKGByHeatTool,
                       GetNodeRelationsTool, AddToKGTool, UpdateKGStatusTool,
                       UpdateKGMetadataTool, UpdateKGRelationTool, MergeKGNodesTool]:
        try:
            registry.register(tool_class(kg_repo))
        except TypeError:
            registry.register(tool_class())
    
    for tool_class in [AddToQueueTool, ClaimQueueTool, GetQueueTool,
                       MarkDoneTool, MarkFailedTool]:
        registry.register(tool_class(storage))
    
    for tool_class in [LLMAnalyzeTool, LLMKnowledgeExtractTool]:
        try:
            registry.register(tool_class())
        except TypeError:
            pass
    
    print(f"✓ Registered {len(registry.list_tools())} tools")
    
    config = ExploreAgentConfig(
        name="TestExploreAgent",
        max_iterations=3,
    )
    
    agent = ExploreAgent(config=config, tool_registry=registry)
    agent.holder_id = holder_id
    
    print(f"✓ Agent created: {agent.name}")
    print(f"✓ Holder ID: {agent.holder_id}")
    print(f"✓ Max iterations: {config.max_iterations}")
    
    return agent


async def run_exploration(agent: ExploreAgent, topic: str):
    """Step 4: Run actual exploration."""
    print("\n" + "="*60)
    print(f"STEP 4: Run Exploration")
    print("="*60)
    
    print(f"Topic: {topic}")
    print(f"Starting exploration...")
    
    try:
        result = await agent.run(topic)
        
        print(f"\n✓ Exploration completed")
        print(f"✓ Success: {result.success}")
        print(f"✓ Iterations used: {result.iterations_used}")
        print(f"✓ Content length: {len(result.content)} chars")
        
        if result.content:
            print(f"\nPreview: {result.content[:200]}...")
        
        return result
    except Exception as e:
        print(f"\n⚠️  Exploration error: {e}")
        print("This is expected without proper LLM provider setup")
        from core.agents.ca_agent import AgentResult
        return AgentResult(
            content=f"Mock exploration result for: {topic}",
            success=False,
            iterations_used=0
        )


def verify_kg_writes(topic: str, neo4j_enabled: bool = False):
    """Step 5: Verify KG has new knowledge nodes."""
    print("\n" + "="*60)
    print(f"STEP 5: Verify KG Writes")
    print("="*60)
    
    if neo4j_enabled:
        print("Neo4j mode: Checking Neo4j KG...")
        try:
            client = Neo4jClient(
                uri="bolt://localhost:7687",
                username="neo4j",
                password=os.environ.get("NEO4J_PASSWORD", "neo4j")
            )
            repo = KGRepository(client)
            
            nodes = asyncio.run(repo.query_knowledge(topic, limit=10))
            print(f"✓ Found {len(nodes)} nodes in Neo4j")
            
            for node in nodes:
                print(f"  - {node.get('topic', 'Unknown')}: {node.get('status', 'Unknown')}")
            
            return len(nodes) > 0
        except Exception as e:
            print(f"⚠️  Neo4j not available, falling back to JSON check: {e}")
    
    print("JSON mode: Checking knowledge_graph.json...")
    kg_path = Path("knowledge/state.json")
    
    if not kg_path.exists():
        print("⚠️  KG file not found")
        return False
    
    import json
    with open(kg_path) as f:
        kg_data = json.load(f)
    
    topics = kg_data.get("topics", {})
    topic_found = topic in topics
    
    print(f"✓ KG has {len(topics)} topics")
    print(f"✓ Topic '{topic}' found: {topic_found}")
    
    if topic_found:
        topic_data = topics[topic]
        print(f"  Status: {topic_data.get('status', 'Unknown')}")
        print(f"  Relations: {len(topic_data.get('relations', []))}")
    
    return topic_found


def verify_queue_done(topic_id: int):
    """Step 6: Verify queue item marked done."""
    print("\n" + "="*60)
    print(f"STEP 6: Verify Queue Status")
    print("="*60)
    
    storage = QueueStorage()
    
    completed = storage.get_completed_items(limit=10)
    completed_ids = [item['id'] for item in completed]
    
    print(f"✓ Completed items: {len(completed)}")
    print(f"✓ Topic {topic_id} completed: {topic_id in completed_ids}")
    
    return topic_id in completed_ids


def main():
    """Run full E2E exploration test."""
    print("\n" + "#"*60)
    print("# REAL E2E EXPLORATION TEST")
    print("#"*60)
    
    has_api_key = check_env_vars()
    
    if not has_api_key:
        print("\n⚠️  Running in MOCK MODE (no API keys)")
        print("Set BOCHA_API_KEY, SERPER_API_KEY, VOLCENGINE_API_KEY for real test")
    
    test_topic = f"E2E Test: AI Agent Self-Reflection {os.urandom(4).hex()}"
    
    topic_id = inject_curiosity_topic(test_topic)
    
    holder_id = f"e2e_test_{os.urandom(4).hex()}"
    claimed_topic = claim_topic(topic_id, holder_id)
    
    agent = setup_explorer_agent(holder_id)
    
    result = asyncio.run(run_exploration(agent, test_topic))
    
    kg_ok = verify_kg_writes(test_topic, neo4j_enabled=False)
    
    queue_ok = verify_queue_done(topic_id)
    
    print("\n" + "="*60)
    print("E2E TEST SUMMARY")
    print("="*60)
    
    results = {
        "Inject Topic": True,
        "Claim Topic": True,
        "Setup Agent": True,
        "Run Exploration": result.success,
        "KG Write": kg_ok,
        "Queue Done": queue_ok,
    }
    
    for step, ok in results.items():
        status = "✅" if ok else "❌"
        print(f"{status} {step}: {'PASS' if ok else 'FAIL'}")
    
    passed = sum(results.values())
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} steps passed")
    
    if passed == total:
        print("\n🎉 REAL E2E TEST PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} steps failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())