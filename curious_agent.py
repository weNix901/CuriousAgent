#!/usr/bin/env python3
"""
Curious Agent MVP - 好奇 Agent
入口 + 调度器

用法:
  python3 curious_agent.py              # 运行一轮探索
  python3 curious_agent.py --daemon    # 守护进程模式（每30分钟探索一次）
  python3 curious_agent.py --status     # 查看当前状态
  python3 curious_agent.py --inject "topic"  # 注入新好奇心
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone

# Add core to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio

from core import knowledge_graph as kg
from core.curiosity_engine import CuriosityEngine
from core.explorer import Explorer
from core.reasoning_compressor import ReasoningCompressor, CompressionLevel
from core.curiosity_decomposer import CuriosityDecomposer
from core.quality_v2 import QualityV2Assessor
from core.provider_registry import init_default_providers
from core.exceptions import ClarificationNeeded


VALID_DEPTHS = {"shallow", "medium", "deep"}


def run_one_cycle(depth: str = "medium") -> dict:
    if depth not in VALID_DEPTHS:
        raise ValueError(f"Invalid depth '{depth}'. Must be one of: {', '.join(sorted(VALID_DEPTHS))}")
    
    from core.meta_cognitive_monitor import MetaCognitiveMonitor
    from core.meta_cognitive_controller import MetaCognitiveController
    from core.event_bus import EventBus
    from core.llm_manager import LLMManager
    from core.config import get_config
    
    # Load config and initialize LLMManager
    config = get_config()
    llm_config = {
        "providers": {},
        "selection_strategy": "capability"
    }
    for p in config.llm.get("providers", []):
        llm_config["providers"][p.name] = {
            "api_url": p.api_url,
            "timeout": p.timeout,
            "enabled": p.enabled,
            "models": [
                {"model": m.model, "weight": m.weight, "capabilities": m.capabilities, "max_tokens": m.max_tokens}
                for m in p.models
            ]
        }
    
    engine = CuriosityEngine()
    
    engine.generate_initial_curiosities()
    engine.rescore_all()
    
    next_curiosity = engine.select_next()
    if not next_curiosity:
        return {"status": "idle", "message": "No pending curiosities"}
    
    topic = next_curiosity["topic"]
    
    llm_manager = LLMManager.get_instance(llm_config)
    
    registry = init_default_providers()
    state = kg.get_state()
    decomposer = CuriosityDecomposer(
        llm_client=llm_manager,
        provider_registry=registry,
        kg=state
    )
    
    # Initialize monitor early for potential parent exploration (Bug #26)
    monitor = MetaCognitiveMonitor(llm_client=llm_manager)

    # Bug #26 fix: Explore parent topic first before decomposition
    parent_state = state.get("knowledge", {}).get("topics", {}).get(topic, {})
    if not parent_state.get("known"):
        print(f"[Explorer] Parent '{topic}' not yet explored, exploring first...")
        kg.update_curiosity_status(topic, "exploring")
        parent_explorer = Explorer(exploration_depth=depth)
        parent_result = parent_explorer.explore({"topic": topic, "score": next_curiosity.get("score", 5.0)})

        parent_findings = {
            "summary": parent_result.get("findings", ""),
            "sources": parent_result.get("sources", []),
            "papers": parent_result.get("papers", [])
        }
        kg.add_knowledge(topic, depth=5, summary=parent_findings["summary"], sources=parent_findings["sources"])

        parent_quality = monitor.assess_exploration_quality(topic, parent_findings)
        monitor.record_exploration(topic, parent_quality, marginal_return=0.0, notified=False)

        print(f"[Explorer] Parent '{topic}' explored (Q={parent_quality:.1f})")

    try:
        subtopics = asyncio.run(decomposer.decompose(topic))
        
        if subtopics:
            subtopics_sorted = sorted(subtopics, key=lambda x: (x.get("signal_strength") != "strong", -x.get("total_count", 0)))
            best = subtopics_sorted[0]
            explore_topic = best["sub_topic"]
            
            print(f"[Decomposer] '{topic}' -> '{explore_topic}' ({best.get('signal_strength', 'unknown')})")
            print(f"[Decomposer] Enqueuing {len(subtopics)-1} sibling candidates")

            for sibling in subtopics_sorted[1:]:
                s_topic = sibling["sub_topic"]
                s_strength = sibling.get("signal_strength", "unknown")
                s_relevance = 7.0 if s_strength == "strong" else (6.0 if s_strength == "medium" else 5.0)
                s_depth = 6.0 if s_strength == "strong" else (5.5 if s_strength == "medium" else 5.0)
                kg.add_curiosity(topic=s_topic, reason=f"Sibling of: {topic}", relevance=float(s_relevance), depth=float(s_depth), original_topic=topic)
                kg.add_child(topic, s_topic)
                print(f"[Decomposer]   + Sibling: '{s_topic}' ({s_strength})")

            next_curiosity["original_topic"] = topic
            next_curiosity["topic"] = explore_topic
            next_curiosity["decomposition"] = best
            
            # v0.2.5: 立即写入父子关系（Bug #7 fix）
            kg.add_child(topic, explore_topic)
        else:
            explore_topic = topic
            # v0.2.5: 非 decomposition 路径也写入父子关系（Bug #7 完整修复）
            if next_curiosity.get("original_topic"):
                parent = next_curiosity["original_topic"]
                if parent != topic:
                    kg.add_child(parent, topic)

    except ClarificationNeeded as e:
        print(f"[Decomposer] Clarification needed for '{e.topic}': {e.reason}")
        kg.mark_topic_done(e.topic, f"Needs clarification: {e.reason}")
        EventBus.emit("decomposer.clarification_needed", {
            "topic": e.topic,
            "alternatives": e.alternatives,
            "reason": e.reason
        })
        return {"status": "clarification_needed", "topic": e.topic, "reason": e.reason}
    
    topic = next_curiosity["topic"]
    controller = MetaCognitiveController(monitor)
    
    allowed, reason = controller.should_explore(topic)
    if not allowed:
        print(f"[MGV] Exploration blocked: {topic} — {reason}")
        kg.mark_topic_done(topic, reason)
        EventBus.emit("exploration.blocked", {"topic": topic, "reason": reason})
        return {"status": "blocked", "topic": topic, "reason": reason}
    
    explorer = Explorer(exploration_depth=depth)

    # v0.2.5: 设置 exploring 状态以便 parent 追踪
    kg.update_curiosity_status(topic, "exploring")

    from core.three_phase_explorer import ThreePhaseExplorer
    three_phase = ThreePhaseExplorer(explorer, monitor, llm_manager)

    if next_curiosity.get("score", 5.0) >= 5.0:
        result = three_phase.explore(next_curiosity)
        if result.get("status") == "already_known":
            print(f"[ThreePhaseExplorer] Topic already known: {topic}")
            return {"status": "blocked", "topic": topic, "reason": "Already known with high confidence"}
        if "findings" in result:
            result = {
                "topic": topic,
                "action": result.get("plan_used", [{}])[0].get("action", "explore") if result.get("plan_used") else "explore",
                "findings": result["findings"].get("findings", result["findings"].get("summary", "")),
                "sources": result["findings"].get("sources", []),
                "papers": result["findings"].get("papers", []),
                "score": next_curiosity.get("score", 5.0)
            }
    else:
        result = explorer.explore(next_curiosity)

    findings = {
        "summary": result.get("findings", ""),
        "sources": result.get("sources", []),
        "papers": result.get("papers", [])
    }
    
    # ===== T-2 集成点 开始 =====
    # 【集成点 2】QualityV2Assessor 替代简单评分
    quality_assessor = QualityV2Assessor()
    try:
        quality = quality_assessor.assess_quality(topic, findings, kg)
    except Exception as e:
        print(f"[T-2] QualityV2 failed: {e}, falling back to monitor")
        quality = monitor.assess_exploration_quality(topic, findings)
    # ===== T-2 集成点 结束 =====
    marginal = monitor.compute_marginal_return(topic, quality)
    exploration_count = monitor.get_explore_count(topic)

    kg.mark_topic_done(topic, f"Exploration done (Q={quality:.1f}, marginal={marginal:.2f})")

    # 应用认知跳跃压缩（基于当前 quality）
    compressor = ReasoningCompressor()
    compression = compressor.compress(
        topic=topic,
        quality=quality,
        marginal_return=marginal,
        exploration_count=exploration_count,
        depth=depth,
        layer_count=result.get("action", "").count("+") + 1,
        findings=result.get("findings", "")
    )
    compression_level = compression.level
    
    # 通知决策：quality >= 7.0 且 非 SILENT 压缩
    should_notify = (quality >= 7.0) and (compression.level != CompressionLevel.SILENT)
    notified = False
    formatted = ""
    
    if should_notify:
        formatted = compressor.format_output(result, compression)
        
        EventBus.emit("discovery.high_quality", {
            "topic": topic,
            "quality": quality,
            "formatted": formatted,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        EventBus.emit("notification.external", {
            "topic": topic,
            "quality": quality,
            "message": formatted
        })
        
        kg.update_last_exploration_notified(topic, True)
        notified = True
    elif compression.level == CompressionLevel.SILENT:
        # SILENT 级别：记录但不通知
        print(f"[ReasoningCompressor] SILENT 跳过: {topic} (Q={quality:.1f}, marginal={marginal:.2f})")
    else:
        # 质量不足（< 7.0）但非 SILENT：静默记录，不推送
        pass
    
    monitor.record_exploration(topic, quality, marginal, notified=notified)

    # Track competence for gap-driven exploration (Bug #28 fix)
    from core.competence_tracker import CompetenceTracker
    tracker = CompetenceTracker()
    tracker.update_competence(topic, quality)

    if quality >= 7.0:
        from core.agent_behavior_writer import AgentBehaviorWriter
        writer = AgentBehaviorWriter()
        write_result = writer.process(topic, findings, quality, findings.get("sources", []))
        if write_result["applied"]:
            print(f"[BehaviorWriter] ✓ Written to {write_result['section']}: {topic}")
    
    continue_allowed, continue_reason = controller.should_continue(topic)
    
    if continue_allowed:
        kg.add_curiosity(
            topic,
            reason=f"Marginal:{marginal:.2f}, Quality:{quality:.1f}",
            relevance=quality / 10.0,
            depth=quality / 10.0 * 5
        )
    else:
        kg.mark_topic_done(topic, continue_reason)
        EventBus.emit("exploration.completed", {
            "topic": topic,
            "reason": continue_reason,
            "final_quality": quality
        })
    
    auto_queued = 0
    if depth in ("medium", "deep"):
        keywords = engine._extract_keywords(findings["summary"])
        if keywords:
            auto_queued = engine.auto_queue_topics(keywords, parent_topic=topic)
    
    # 使用压缩后的 formatted（若 should_notify=False 则为空）
    final_formatted = formatted if should_notify else explorer.format_for_user(result)

    return {
        "status": "success",
        "topic": topic,
        "result": result,
        "formatted": final_formatted,
        "quality": quality,
        "marginal_return": marginal,
        "notified": notified,
        "continue": continue_allowed,
        "auto_queued": auto_queued
    }


def print_status():
    """打印当前状态"""
    state = kg.get_state()
    summary = kg.get_knowledge_summary()
    
    print("=" * 50)
    print("👁️  Curious Agent MVP - 状态面板")
    print("=" * 50)
    print(f"🕒 最后更新: {state.get('last_update', '未知')}")
    print(f"📚 知识节点: {summary['total_topics']} 个")
    print(f"   - 已知: {summary['known_count']}")
    print(f"   - 未知: {summary['total_topics'] - summary['known_count']}")
    print(f"❓ 待探索好奇心: {summary['pending_curiosities']} 项")
    print(f"🗺️  探索历史: {summary['recent_explorations']} 条")
    print()
    
    pending = [i for i in state["curiosity_queue"] if i["status"] == "pending"]
    if pending:
        print("🔥 Top 好奇心队列:")
        for i, item in enumerate(sorted(pending, key=lambda x: x["score"], reverse=True)[:5], 1):
            status_icon = "⏳" if item["status"] == "pending" else "🔄" if item["status"] == "investigating" else "✅"
            print(f"   {i}. [{item['score']:.1f}] {status_icon} {item['topic']}")
            print(f"      → {item['reason']}")
    
    recent = state.get("exploration_log", [])
    if recent:
        print()
        print("📋 最近探索:")
        for log in recent[-3:]:
            icon = "📬" if log["notified_user"] else "📭"
            print(f"   {icon} [{log['action']}] {log['topic']}")
            print(f"      {log['findings'][:80]}...")
    
    print("=" * 50)


def _scoring_weights_to_dict(weights) -> dict:
    """Convert DreamAgentScoringWeights dataclass to dict."""
    return {
        "relevance": weights.relevance,
        "frequency": weights.frequency,
        "recency": weights.recency,
        "quality": weights.quality,
        "surprise": weights.surprise,
        "cross_domain": weights.cross_domain,
    }


def daemon_mode(interval_minutes: int = 30):
    """
    Three-Agent Daemon Mode (v0.2.6).

    Starts SpiderAgent, DreamAgent, and SleepPruner in dedicated threads.
    Agents communicate via queue for inter-agent messaging.

    Features:
    - F1: Three-agent architecture (SpiderAgent, DreamAgent, SleepPruner)
    - F7: High-priority queue with 5s timeout
    - F8: Three-layer randomization for distant pair selection
    - Graceful shutdown on Ctrl+C
    - Feature toggle support via config
    - PID file check to prevent multiple instances
    """
    import signal
    import os

    # ─── PID file check：防止多个 daemon 实例并发运行 ────────────
    pid_file = "/tmp/curious_agent_daemon.pid"
    if os.path.exists(pid_file):
        try:
            with open(pid_file) as f:
                old_pid = int(f.read().strip())
            # 检查旧 PID 是否还活着
            try:
                os.kill(old_pid, 0)  # signal 0 不杀死，只检查存活
                print(f"[daemon] PID {old_pid} is already running. Exiting.")
                print(f"[daemon] If the old daemon is dead, remove {pid_file}")
                return
            except OSError:
                print(f"[daemon] Stale PID file (process {old_pid} is dead). Removing.")
                os.remove(pid_file)
        except (ValueError, IOError):
            print("[daemon] Corrupt PID file. Removing.")
            os.remove(pid_file)

    # 写入当前 PID
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))
    print(f"[daemon] PID {os.getpid()} registered in {pid_file}")

    # Graceful shutdown: save state before exiting
    import signal as sig_module
    def _graceful_shutdown(signum, frame):
        print(f"\n[daemon] Received signal {signum}, saving state before exit...")
        try:
            from core import knowledge_graph as kg_safe
            kg_safe._save_state(kg_safe._load_state())
            print("[daemon] State saved.")
        except Exception as e:
            print(f"[daemon] Error saving state: {e}")
        cleanup_pid()
        raise SystemExit(0)

    sig_module.signal(sig_module.SIGTERM, _graceful_shutdown)
    sig_module.signal(sig_module.SIGINT, _graceful_shutdown)

    def cleanup_pid():
        if os.path.exists(pid_file):
            os.remove(pid_file)

    from core.daemon.explore_daemon import ExploreDaemon, ExploreDaemonConfig
    from core.daemon.dream_daemon import DreamDaemon, DreamDaemonConfig
    from core.tools.registry import ToolRegistry
    from core.tools.queue_tools import QueueStorage

    from core.config import get_config
    cfg = get_config()
    feature_flags = getattr(cfg, 'feature_flags', {})
    three_agent_enabled = feature_flags.get('three_agent_daemon', True)

    if not three_agent_enabled:
        print("[v0.2.6] Three-agent daemon disabled, falling back to legacy mode")
        cleanup_pid()
        _daemon_mode_legacy(interval_minutes)
        return
    
    # Read daemon config from config.json
    explore_daemon_cfg = cfg.daemon.get('explore')
    dream_daemon_cfg = cfg.daemon.get('dream')
    agent_explore_cfg = cfg.agents.get('explore')
    agent_dream_cfg = cfg.agents.get('dream')
    
    print(f"🚀 Curious Agent 进入三代理守护进程模式 (v0.2.9)")
    print(f"   Config: ExploreDaemon poll={explore_daemon_cfg.poll_interval_seconds}s, DreamDaemon interval={dream_daemon_cfg.interval_seconds}s")
    print("   ExploreDaemon: 持续探索代理 (ReAct nanobot)")
    print("   DreamDaemon: 创意洞察代理 (多周期 nanobot)")
    print("   SleepPruner: 周期修剪代理")
    print("   按 Ctrl+C 停止")
    print()
    
    seeds = cfg.knowledge.get("root_seeds", [
        "transformer attention",
        "gradient descent",
        "backpropagation",
        "softmax",
        "RL reward signal",
        "uncertainty quantification"
    ])
    kg.init_root_pool(seeds)
    print(f"[v0.2.9] Root pool initialized with {len(seeds)} seeds")
    
    # Initialize new agents
    tool_registry = ToolRegistry()
    queue_storage = QueueStorage()
    queue_storage.initialize()
    
    # KGRepository: wraps sync KG functions as async for tool compatibility
    import asyncio
    
    class KGRepository:
        """Async wrapper for sync knowledge_graph functions."""
        async def add_to_knowledge_graph(self, topic, content="", metadata=None, relations=None):
            kg.add_knowledge(topic=topic, depth=metadata.get("depth", 5) if metadata else 5,
                           summary=content, sources=metadata.get("sources", []) if metadata else None,
                           quality=metadata.get("quality") if metadata else None)
            return topic
        
        async def query_knowledge(self, topic, limit=5):
            return []
        
        async def query_knowledge_by_status(self, status, limit=5):
            return []
        
        async def query_knowledge_by_heat(self, limit=5):
            return []
        
        async def get_node_relations(self, topic):
            return []
    
    kg_repo = KGRepository()
    
    # Register tools for ExploreAgent (ReAct loop)
    from core.tools.search_tools import SearchWebTool, FetchPageTool, ProcessPaperTool
    from core.tools.kg_tools import QueryKGTool, AddToKGTool, UpdateKGStatusTool, UpdateKGMetadataTool, GetNodeRelationsTool
    from core.tools.queue_tools import AddToQueueTool, ClaimQueueTool, GetQueueTool, MarkDoneTool, MarkFailedTool
    from core.tools.llm_tools import LLMAnalyzeTool, LLMSummarizeTool
    
    tool_registry.register(SearchWebTool())
    tool_registry.register(FetchPageTool())
    tool_registry.register(ProcessPaperTool())
    tool_registry.register(QueryKGTool(repository=kg_repo))
    tool_registry.register(AddToKGTool(repository=kg_repo))
    tool_registry.register(UpdateKGStatusTool(repository=kg_repo))
    tool_registry.register(UpdateKGMetadataTool(repository=kg_repo))
    tool_registry.register(GetNodeRelationsTool(repository=kg_repo))
    tool_registry.register(AddToQueueTool(storage=queue_storage))
    tool_registry.register(ClaimQueueTool(storage=queue_storage))
    tool_registry.register(GetQueueTool(storage=queue_storage))
    tool_registry.register(MarkDoneTool(storage=queue_storage))
    tool_registry.register(MarkFailedTool(storage=queue_storage))
    tool_registry.register(LLMAnalyzeTool())
    tool_registry.register(LLMSummarizeTool())
    print(f"[v0.2.9] Registered {len(tool_registry)} tools")
    
    # ExploreDaemon: continuous exploration using ExploreAgent (ReAct nanobot)
    from core.agents.explore_agent import ExploreAgent, ExploreAgentConfig
    explore_config = ExploreAgentConfig(
        name="ExploreAgent",
        model=agent_explore_cfg.model,
        max_iterations=agent_explore_cfg.max_iterations
    )
    explore_agent = ExploreAgent(config=explore_config, tool_registry=tool_registry)
    explore_daemon = ExploreDaemon(
        explore_agent=explore_agent,
        queue_storage=queue_storage,
        config=explore_daemon_cfg
    )
    
    # DreamDaemon: heartbeat-triggered dreaming using DreamAgent (multi-cycle nanobot)
    # DreamDaemon.start() is async, so run it in a separate thread
    import threading
    from pathlib import Path
    from core.agents.dream_agent import DreamAgentConfig as DreamAgentAgentConfig
    dream_agent_config = DreamAgentAgentConfig(
        name="DreamAgent",
        scoring_weights=_scoring_weights_to_dict(agent_dream_cfg.scoring_weights),
        min_score_threshold=agent_dream_cfg.min_score_threshold,
        min_recall_count=agent_dream_cfg.min_recall_count,
    )
    dream_daemon = DreamDaemon(
        workspace=Path("."),
        config=dream_daemon_cfg,
        agent_config=dream_agent_config,
    )
    
    def run_dream_daemon_async():
        asyncio.run(dream_daemon.start())
    
    dream_thread = threading.Thread(target=run_dream_daemon_async, name="DreamDaemon", daemon=True)
    
    # Keep SleepPruner for now
    from core.sleep_pruner import SleepPruner
    sleep_pruner = SleepPruner(
        name="SleepPruner",
        initial_interval_minutes=240,
        max_interval_minutes=1440
    )
    
    shutdown_requested = False
    
    def handle_shutdown(signum, frame):
        nonlocal shutdown_requested
        print("\n[v0.2.9] Shutdown signal received, stopping agents...")
        shutdown_requested = True
        explore_daemon.stop()
        sleep_pruner.stop()
        dream_daemon.stop()
        cleanup_pid()
    
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    print("[v0.2.9] Starting agents...")
    # Start ExploreDaemon and SleepPruner (Thread-based)
    for agent in [explore_daemon, sleep_pruner]:
        agent.start()
        print(f"[v0.2.9]   ✓ {agent.name} started")
    # Start DreamDaemon in its own thread (async)
    dream_thread.start()
    print(f"[v0.2.9]   ✓ DreamDaemon started (thread)")
    
    print("[v0.2.6] All agents running. Monitoring status...")
    print()
    
    # v0.2.9: Health monitoring
    last_explored_check_time = time.time()
    stuck_check_interval = 60  # Check every 60 seconds
    
    cycle_count = 0
    while not shutdown_requested:
        cycle_count += 1
        current_time = time.time()
        
        # Check ExploreDaemon (Thread-based)
        explore_alive = explore_daemon.is_alive() if hasattr(explore_daemon, 'is_alive') else explore_daemon._running
        
        # Check DreamDaemon (async, uses _running flag)
        dream_running = getattr(dream_daemon, '_running', False)
        
        # Check SleepPruner (Thread-based)
        sleep_alive = sleep_pruner.is_alive() if hasattr(sleep_pruner, 'is_alive') else True
        
        # Check ExploreDaemon health every 60 seconds
        if current_time - last_explored_check_time >= stuck_check_interval:
            if not explore_daemon.is_alive():
                print(f"[v0.2.9] ⚠️ ExploreDaemon dead! Restarting...")
                explore_daemon.stop()
                explore_daemon.join(timeout=5.0)
                explore_daemon = ExploreDaemon(
                    explore_agent=explore_agent,
                    queue_storage=queue_storage,
                    config=explore_daemon_cfg
                )
                explore_daemon.start()
                print("[v0.2.9] ✓ ExploreDaemon restarted")
            last_explored_check_time = current_time
        
        # Revive stuck items periodically
        if cycle_count % 60 == 0:
            try:
                from core import knowledge_graph as kg_main
                revived = kg_main.revive_stuck_items(timeout_seconds=300)
                if revived > 0:
                    print(f"[v0.2.9] Revived {revived} stuck items")
            except Exception as e:
                print(f"[v0.2.9] Error reviving stuck items: {e}")
        
        if cycle_count % 10 == 0:
            print(f"\n{'='*50}")
            print(f"🔄 监控循环 #{cycle_count // 10} @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*50}")
            print(f"[v0.2.9] ExploreDaemon: alive={explore_alive}")
            print(f"[v0.2.9] DreamDaemon: running={dream_running}")
            print(f"[v0.2.9] SleepPruner: alive={sleep_alive}")
            print(f"[v0.2.9] SleepPruner status: {sleep_pruner.get_status()}")
        
        time.sleep(1.0)
    
    print("[v0.2.9] Stopping agents...")
    
    # Stop ExploreDaemon (Thread)
    explore_daemon.stop()
    explore_daemon.join(timeout=5.0)
    print("[v0.2.9] ✓ ExploreDaemon stopped")
    
    # Stop DreamDaemon (the thread will be stopped when the process exits)
    dream_daemon.stop()
    print("[v0.2.9] ✓ DreamDaemon stop signaled")
    
    # Stop SleepPruner (Thread)
    sleep_pruner.stop()
    sleep_pruner.join(timeout=5.0)
    print("[v0.2.9] ✓ SleepPruner stopped")
    
    print("[v0.2.9] All agents stopped. Exiting.")


def _daemon_mode_legacy(interval_minutes: int = 30):
    """Legacy daemon mode (pre-v0.2.6) for fallback."""
    print(f"🚀 Curious Agent 进入守护进程模式 (每 {interval_minutes} 分钟探索一次)")
    print("   按 Ctrl+C 停止")
    print()
    
    from core.config import get_config
    cfg = get_config()
    seeds = cfg.knowledge.get("root_seeds", [
        "transformer attention",
        "gradient descent",
        "backpropagation",
        "softmax",
        "RL reward signal",
        "uncertainty quantification"
    ])
    kg.init_root_pool(seeds)
    print(f"[v0.2.5] Root pool initialized with {len(seeds)} seeds")
    
    cycle_count = 0
    while True:
        cycle_count += 1
        print(f"\n{'='*50}")
        print(f"🔄 探索循环 #{cycle_count} @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*50}")
        
        outcome = run_one_cycle()
        
        if outcome["status"] == "idle":
            print(f"💤 {outcome['message']}")
        elif outcome["status"] in ("clarification_needed", "blocked"):
            topic_or_reason = outcome.get("topic") or outcome.get("reason", "")
            print(f"⚠️  {outcome['status']}: {topic_or_reason}")
        elif outcome["status"] == "success":
            result = outcome["result"]
            print(f"✅ 完成: {result['topic']}")
            print(f"   方式: {result['action']}")
            print(f"   分数: {result['score']}")
            print(f"   通知用户: {'是' if outcome['notified'] else '否'}")
            
            if outcome["notified"]:
                print(f"\n📬 飞书通知已触发（见下方内容）:")
                print("-" * 40)
                print(outcome["formatted"][:300])
        
        time.sleep(interval_minutes * 60)


def resolve_alpha(args) -> float:
    """解析 alpha 值，优先级：--pure-curious > --alpha > --motivation > default"""
    if getattr(args, 'pure_curious', False):
        return 0.0
    if getattr(args, 'alpha', None) is not None and args.alpha != 0.5:
        return args.alpha
    if getattr(args, 'motivation', None) == 'human':
        return 0.7
    if getattr(args, 'motivation', None) == 'curious':
        return 0.3
    return 0.5


def inject_curiosity(topic: str, relevance: float = 7.0, depth: float = 6.0, reason: str = "", alpha: float = 0.5):
    """注入新的好奇心项，使用融合评分"""
    if not reason:
        reason = f"用户主动注入: {topic}"
    
    engine = CuriosityEngine()
    score_result = engine.score_topic(topic, alpha=alpha)
    kg.add_curiosity(topic, reason, score_result['final_score'], depth)
    
    print(f"✅ 已注入好奇心: {topic}")
    print(f"   融合评分: {score_result['final_score']:.2f} (α={alpha})")
    print(f"   - 人工评分: {score_result['human_score']:.2f}")
    print(f"   - 内在评分: {score_result['intrinsic_score']:.2f}")
    print(f"   原因: {reason}")


def delete_curiosity(topic: str, force: bool = False):
    """删除队列条目"""
    success = kg.remove_curiosity(topic, force=force)
    if success:
        print(f"✅ 已删除: {topic}")
    else:
        print(f"❌ 删除失败: {topic} (可能不存在或状态不允许删除，使用 --force 强制删除)")


def list_pending():
    """列出待探索条目"""
    pending = kg.list_pending()
    if not pending:
        print("📭 没有待探索的条目")
        return
    
    print(f"📋 待探索条目 ({len(pending)} 项):")
    for i, item in enumerate(pending, 1):
        print(f"   {i}. [{item.get('score', 'N/A'):.1f}] {item['topic']}")


def _get_config_mode() -> str:
    """T-13: Read exploration mode from config.json (legacy, for backward compat)"""
    try:
        from core.config import get_config
        cfg = get_config()
        # Legacy: try old location first
        if hasattr(cfg, 'exploration') and hasattr(cfg.exploration, 'mode'):
            return cfg.exploration.mode
        return "daemon"
    except Exception:
        return "daemon"


def _get_config_interval() -> int:
    """T-13: Read daemon interval from config.json (legacy, for backward compat)"""
    try:
        from core.config import get_config
        cfg = get_config()
        # Legacy: try old location first, then new location
        if hasattr(cfg, 'exploration') and hasattr(cfg.exploration, 'daemon_interval_minutes'):
            return cfg.exploration.daemon_interval_minutes
        if hasattr(cfg, 'daemon') and 'explore' in cfg.daemon:
            return cfg.daemon['explore'].poll_interval_seconds // 60
        return 5
    except Exception:
        return 5


def _run_api_only():
    """T-13: Start API server only, no daemon loop"""
    from curious_api import app
    print("Starting Curious Agent API server (api_only mode)...")
    app.run(host="0.0.0.0", port=4848, debug=False)


def run_explore_agent(topic: str) -> dict:
    """Run ExploreAgent on a specific topic."""
    import asyncio
    from core.agents.explore_agent import ExploreAgent, ExploreAgentConfig
    from core.tools.registry import ToolRegistry
    from core.config import get_config
    
    cfg = get_config()
    agent_cfg = cfg.agents.get('explore')
    
    print(f"[ExploreAgent] Starting exploration of: {topic}")
    print(f"   Config: model={agent_cfg.model}, max_iterations={agent_cfg.max_iterations}")
    
    tool_registry = ToolRegistry()
    config = ExploreAgentConfig(
        name="explore_agent",
        model=agent_cfg.model,
        max_iterations=agent_cfg.max_iterations
    )
    agent = ExploreAgent(config=config, tool_registry=tool_registry)
    
    result = asyncio.run(agent.run(topic))
    
    print(f"[ExploreAgent] Completed: {result.success}")
    print(f"[ExploreAgent] Iterations used: {result.iterations_used}")
    print(f"[ExploreAgent] Content: {result.content[:200]}...")
    
    return {
        "status": "success" if result.success else "failed",
        "topic": topic,
        "iterations": result.iterations_used,
        "content": result.content
    }


def run_dream_agent() -> dict:
    """Run DreamAgent to generate insight topics."""
    from core.agents.dream_agent import DreamAgent, DreamAgentConfig
    from core.tools.registry import ToolRegistry
    from core.config import get_config
    
    cfg = get_config()
    agent_cfg = cfg.agents.get('dream')
    weights_raw = getattr(agent_cfg, 'scoring_weights', {}) or {}
    
    print("[DreamAgent] Starting insight generation...")
    print(f"   Config: min_score_threshold={agent_cfg.min_score_threshold}")
    
    tool_registry = ToolRegistry()
    config = DreamAgentConfig(
        name="dream_agent",
        scoring_weights=weights_raw,
        min_score_threshold=agent_cfg.min_score_threshold,
        min_recall_count=agent_cfg.min_recall_count,
    )
    agent = DreamAgent(config=config, tool_registry=tool_registry)
    
    result = agent.run()
    
    print(f"[DreamAgent] Generated {len(result.topics_generated)} topics")
    print(f"[DreamAgent] Candidates: {result.candidates_selected}")
    
    return {
        "status": "success" if result.success else "failed",
        "topics_generated": result.topics_generated,
        "candidates_selected": result.candidates_selected,
        "content": result.content
    }


def start_explore_daemon():
    """Start ExploreDaemon for continuous exploration."""
    import asyncio
    from core.agents.explore_agent import ExploreAgent, ExploreAgentConfig
    from core.daemon.explore_daemon import ExploreDaemon, ExploreDaemonConfig
    from core.tools.registry import ToolRegistry
    from core.tools.queue_tools import QueueStorage
    from core.config import get_config
    
    cfg = get_config()
    explore_daemon_cfg = cfg.daemon.get('explore')
    agent_explore_cfg = cfg.agents.get('explore')
    
    print("[ExploreDaemon] Starting continuous exploration daemon...")
    print(f"   Config: poll_interval={explore_daemon_cfg.poll_interval_seconds}s, max_retries={explore_daemon_cfg.max_retries}")
    
    tool_registry = ToolRegistry()
    agent_config = ExploreAgentConfig(
        name="explore_agent",
        model=agent_explore_cfg.model,
        max_iterations=agent_explore_cfg.max_iterations
    )
    agent = ExploreAgent(config=agent_config, tool_registry=tool_registry)
    
    queue_storage = QueueStorage()
    queue_storage.initialize()
    daemon_config = explore_daemon_cfg
    
    daemon = ExploreDaemon(
        explore_agent=agent,
        queue_storage=queue_storage,
        config=daemon_config
    )
    
    daemon.start()
    print("[ExploreDaemon] Daemon started. Press Ctrl+C to stop.")
    
    try:
        daemon.join()
    except KeyboardInterrupt:
        print("[ExploreDaemon] Stopping...")
        daemon.stop()
        daemon.join(timeout=5.0)
    
    return {"status": "stopped"}


def start_dream_daemon():
    """Start DreamDaemon for heartbeat-triggered dreaming."""
    import asyncio
    from pathlib import Path
    from core.agents.dream_agent import DreamAgentConfig as DreamAgentAgentConfig
    from core.daemon.dream_daemon import DreamDaemon, DreamDaemonConfig
    from core.config import get_config

    cfg = get_config()
    dream_daemon_cfg = cfg.daemon.get('dream')
    agent_dream_cfg = cfg.agents.get('dream')

    print("[DreamDaemon] Starting heartbeat-triggered dream daemon...")
    print(f"   Config: interval={dream_daemon_cfg.interval_seconds}s")

    agent_config = DreamAgentAgentConfig(
        name="DreamAgent",
        scoring_weights=_scoring_weights_to_dict(agent_dream_cfg.scoring_weights),
        min_score_threshold=agent_dream_cfg.min_score_threshold,
        min_recall_count=agent_dream_cfg.min_recall_count,
    )

    daemon = DreamDaemon(
        workspace=Path("."),
        config=dream_daemon_cfg,
        agent_config=agent_config,
    )

    asyncio.run(daemon.start())
    print("[DreamDaemon] Daemon started. Press Ctrl+C to stop.")
    
    try:
        # Keep running until interrupted
        import signal
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[DreamDaemon] Stopping...")
        daemon.stop()
    
    return {"status": "stopped"}


def main():
    parser = argparse.ArgumentParser(description="Curious Agent MVP")
    parser.add_argument("--daemon", action="store_true", help="守护进程模式（覆盖 config.mode）")
    parser.add_argument("--api-only", action="store_true", help="仅启动 API 服务，不运行 daemon（覆盖 config.mode）")
    parser.add_argument("--mode", choices=["daemon", "api_only", "hybrid"], default=None, help="运行模式（覆盖 config.exploration.mode）")
    parser.add_argument("--interval", type=int, default=None, help="守护进程探索间隔(分钟，默认读 config）")
    parser.add_argument("--status", action="store_true", help="查看状态")
    parser.add_argument("--inject", type=str, help="注入新好奇心 topic")
    parser.add_argument("--score", type=float, default=7.0, help="注入时的 relevance 分数")
    parser.add_argument("--depth", type=float, default=6.0, help="注入时的 depth 分数")
    parser.add_argument("--reason", type=str, default="", help="注入原因")
    parser.add_argument("--run", action="store_true", help="运行一轮探索")
    parser.add_argument("--run-depth", type=str, default="medium", choices=["shallow", "medium", "deep"], help="运行时的探索深度")
    parser.add_argument("--alpha", type=float, default=0.5, help="人工信号权重 (0.0-1.0)，默认 0.5")
    parser.add_argument("--motivation", type=str, choices=["human", "curious"], help="预设 alpha: human=0.7, curious=0.3")
    parser.add_argument("--pure-curious", action="store_true", help="纯探索模式 (alpha=0.0)")
    parser.add_argument("--delete", type=str, help="删除指定话题")
    parser.add_argument("--force", action="store_true", help="强制删除（忽略状态）")
    parser.add_argument("--list-pending", action="store_true", help="列出待探索条目")
    parser.add_argument("--explore", type=str, help="运行 ExploreAgent 探索指定话题")
    parser.add_argument("--dream", action="store_true", help="运行 DreamAgent 生成洞察话题")
    parser.add_argument("--daemon-explore", action="store_true", help="启动 ExploreDaemon 持续探索")
    parser.add_argument("--daemon-dream", action="store_true", help="启动 DreamDaemon 心跳触发梦境")
    
    args = parser.parse_args()
    
    alpha = resolve_alpha(args)
    
    if args.status:
        print_status()
    elif args.list_pending:
        list_pending()
    elif args.delete:
        delete_curiosity(args.delete, force=args.force)
    elif args.explore:
        result = run_explore_agent(args.explore)
        print(f"\n✅ ExploreAgent result: {result['status']}")
    elif args.dream:
        result = run_dream_agent()
        print(f"\n✅ DreamAgent result: {result['status']}")
        if result['topics_generated']:
            print(f"   Generated topics: {result['topics_generated']}")
    elif args.daemon_explore:
        start_explore_daemon()
    elif args.daemon_dream:
        start_dream_daemon()
    elif args.inject:
        inject_curiosity(args.inject, args.score, args.depth, args.reason, alpha=alpha)
    elif args.daemon:
        daemon_interval = args.interval or _get_config_interval()
        daemon_mode(daemon_interval)
    elif args.api_only:
        _run_api_only()
    elif args.run:
        result = run_one_cycle(depth=args.run_depth)
        if result["status"] == "idle":
            print(f"💤 {result['message']}")
        elif result["status"] == "blocked":
            print(f"🚫 {result.get('topic', 'Unknown')} blocked: {result.get('reason', 'unknown')}")
        elif result["status"] == "clarification_needed":
            print(f"🤔 需要澄清: {result.get('topic', 'Unknown')} — {result.get('reason', '')}")
        else:
            print(result.get("formatted", ""))
    else:
        # T-13: Default — read mode from config
        mode = args.mode or _get_config_mode()
        if mode in ("daemon", "hybrid"):
            daemon_interval = args.interval or _get_config_interval()
            print(f"[T-13] Default mode={mode}, running daemon (interval={daemon_interval}min)")
            daemon_mode(daemon_interval)
        else:
            # api_only: just print status and exit
            print(f"[T-13] Default mode=api_only, showing status")
            print_status()
            result = run_one_cycle(depth=args.run_depth)
            if result["status"] == "success":
                print("\n📋 本轮探索结果:")
                print(result["formatted"])


if __name__ == "__main__":
    main()
