"""
Curious Agent API Server
提供 RESTful API 和静态文件服务
"""
import argparse
import os
import sys
import threading
import time
import webbrowser

from flask import Flask, jsonify, request, send_from_directory
from core.config import get_config

app = Flask(__name__)

# UI 静态文件目录
UI_DIR = os.path.join(os.path.dirname(__file__), "ui")


@app.route("/")
def index():
    return send_from_directory(UI_DIR, "index.html")


@app.route("/api/quota/status")
def api_quota_status():
    """Get current search API quota status."""
    try:
        from core.search_quota import get_quota_manager
        from core.config import get_config
        
        cfg = get_config()
        quota = cfg.knowledge.get("search").daily_quota
        qm = get_quota_manager()
        
        serper = qm.get_status("serper", quota.serper, quota.enabled)
        bocha = qm.get_status("bocha", quota.bocha, quota.enabled)
        
        return jsonify({
            "enabled": quota.enabled,
            "reset_hour": quota.reset_hour,
            "providers": {
                "serper": {
                    "used": serper.used,
                    "limit": serper.limit,
                    "remaining": serper.remaining
                },
                "bocha": {
                    "used": bocha.used,
                    "limit": bocha.limit,
                    "remaining": bocha.remaining
                }
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/quota/reset", methods=["POST"])
def api_quota_reset():
    """Reset quota for a specific provider or all providers."""
    try:
        from core.search_quota import get_quota_manager
        
        data = request.get_json() or {}
        provider = data.get("provider")  # "serper", "bocha", or None for all
        
        qm = get_quota_manager()
        qm.reset(provider)
        
        return jsonify({
            "status": "success",
            "message": f"Quota reset for {provider or 'all providers'}"
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/curious/state")
def api_state():
    from core import knowledge_graph as kg
    state = kg.get_state()
    summary = kg.get_knowledge_summary()
    topics = state.get("knowledge", {}).get("topics", {})
    
    mc = state.get("meta_cognitive", {})
    quality_map = mc.get("last_quality", {})
    topics_with_quality = {}
    for name, v in topics.items():
        topic_copy = dict(v)
        topic_copy["quality"] = v.get("quality") or quality_map.get(name)
        topics_with_quality[name] = topic_copy
    
    return jsonify({
        "status": "ok",
        "knowledge": {**summary, "topics": topics_with_quality},
        "curiosity_queue": state.get("curiosity_queue", []),
        "exploration_log": state.get("exploration_log", []),
        "last_update": state.get("last_update")
    })


@app.route("/api/curious/run", methods=["POST"])
def api_run():
    try:
        from core.curiosity_engine import CuriosityEngine
        from core.explorer import Explorer
        from core.knowledge_graph import add_curiosity, get_top_curiosities

        data = request.get_json() if request.is_json else {}
        topic = data.get("topic", "").strip()
        depth = data.get("depth", "medium")

        if depth not in ["shallow", "medium", "deep"]:
            return jsonify({"error": f"invalid depth: {depth}"}), 400

        engine = CuriosityEngine()
        explorer = Explorer(exploration_depth=depth)

        if topic:
            result = engine.score_topic(topic, alpha=0.5)
            final_score = result['final_score']
            add_curiosity(
                topic=topic,
                reason="API run injection",
                relevance=final_score,
                depth=7.0
            )
            next_item = {
                "topic": topic,
                "reason": "API run injection",
                "score": final_score,
                "relevance": final_score,
                "depth": 7.0,
                "status": "pending"
            }
        else:
            engine.generate_initial_curiosities()
            engine.rescore_all()
            next_item = engine.select_next()

        if not next_item:
            return jsonify({"status": "idle", "message": "好奇心队列为空"})

        result = explorer.explore(next_item)

        from core.knowledge_graph import mark_topic_done
        mark_topic_done(result["topic"], "API exploration completed")

        from core.agent_behavior_writer import AgentBehaviorWriter
        from core.meta_cognitive_monitor import MetaCognitiveMonitor

        monitor = MetaCognitiveMonitor(llm_client=None)
        findings = {
            "summary": result.get("findings", ""),
            "sources": result.get("sources", []),
            "papers": result.get("papers", [])
        }
        quality = monitor.assess_exploration_quality(result["topic"], findings)
        monitor.record_exploration(result["topic"], quality, marginal_return=0.0, notified=False)

        if quality >= 7.0:
            writer = AgentBehaviorWriter()
            writer.process(result["topic"], findings, quality, result.get("sources", []))

        # G3-Fix: Remove decomposition from API, move to Daemon SpiderAgent
        # Add topic to DreamInbox for Daemon to process decomposition
        from core import knowledge_graph as kg
        kg.add_to_dream_inbox(result["topic"], source_insight="API exploration completed - needs decomposition")
        print(f"[API] Topic '{result['topic']}' queued for decomposition in Daemon")

        return jsonify({
            "status": "success",
            "topic": result["topic"],
            "action": result["action"],
            "score": result["score"],
            "findings": result["findings"],
            "notified": result["notified"],
            "sources": result["sources"],
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/curious/inject", methods=["POST"])
def api_inject():
    try:
        data = request.get_json() or {}
        topic = str(data.get("topic", "")).strip()
        if not topic:
            return jsonify({"error": "topic is required"}), 400

        alpha = float(data.get("alpha", 0.5))
        mode = data.get("mode", "fusion")

        from core.curiosity_engine import CuriosityEngine
        from core.knowledge_graph import add_curiosity

        engine = CuriosityEngine()

        if mode == "intrinsic":
            result = engine.intrinsic_scorer.score(topic)
            final_score = result['total']
        else:
            result = engine.score_topic(topic, alpha=alpha)
            final_score = result['final_score']

        depth = data.get("depth", 6.0)
        if isinstance(depth, str):
            depth_map = {"shallow": 3.0, "medium": 6.0, "deep": 9.0}
            depth = depth_map.get(depth, 6.0)
        else:
            depth = float(depth)

        # === Phase 2: parent link 在入口处立即写入 KG ===
        from core import knowledge_graph as kg_module
        parent = data.get("parent")
        if parent:
            # Step 1: 建占位 KG 节点（即使还没探索，KG 里也要有记录）
            kg_module.add_knowledge(topic=topic, depth=depth, summary="")
            # Step 2: 立即建立父子关系
            kg_module.add_child(parent, topic)
            print(f"[Phase2] Linked '{topic}' -> '{parent}' in KG")
        # === Phase 2 结束 ===

        # === v0.2.9: 只写入 SQLite 队列（ExploreDaemon 专用）===
        from core.tools.queue_tools import QueueStorage
        qs = QueueStorage()
        qs.initialize()
        qs.add_item(topic=topic, priority=data.get("priority", 5), metadata={
            "reason": str(data.get("reason", "Web UI 注入")),
            "score": final_score,
            "depth": depth
        })
        # === END ===

        # ===== T-9 集成点 开始 =====
        # 【集成点 6】inject_priority: source=r1d3 时优先处理
        config = get_config()
        from core.knowledge_graph import update_curiosity_score
        source = data.get("source", "default")
        priority_cfg = get_config().behavior.get("injection")

        priority_triggered = False
        if priority_cfg.enabled and source in priority_cfg.priority_sources:
            effective_score = final_score + priority_cfg.boost_score
            update_curiosity_score(topic, effective_score)

            if priority_cfg.trigger_immediate:
                from core.async_explorer import trigger_async_exploration
                trigger_async_exploration(topic, score=effective_score, depth=depth)
                priority_triggered = True
                print(f"[T-9] Priority injection for {topic}, async triggered")

        # 修改返回值
        result_data = {
            "status": "ok",
            "topic": topic,
            "score": final_score,
            "alpha": alpha,
            "mode": mode
        }
        if priority_triggered:
            result_data["priority"] = True
            result_data["async_triggered"] = True
        # ===== T-9 集成点 结束 =====

        return jsonify(result_data)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/curious/trigger", methods=["POST"])
def api_trigger():
    try:
        data = request.get_json() or {}
        topic = str(data.get("topic", "")).strip()
        depth = data.get("depth", "medium")

        if not topic:
            return jsonify({"error": "topic is required"}), 400

        if depth not in ["shallow", "medium", "deep"]:
            return jsonify({"error": f"invalid depth: {depth}"}), 400

        time_estimates = {
            "shallow": "30秒",
            "medium": "3-5分钟",
            "deep": "10-15分钟"
        }

        def run_exploration_async():
            try:
                from core.curiosity_engine import CuriosityEngine
                from core.explorer import Explorer
                from core.knowledge_graph import add_curiosity, mark_topic_done
                import time as time_module

                add_curiosity(
                    topic=topic,
                    reason="API trigger",
                    relevance=8.0,
                    depth=7.0
                )

                time_module.sleep(0.5)

                engine = CuriosityEngine()
                explorer = Explorer(exploration_depth=depth)
                next_item = {
                    "topic": topic,
                    "reason": "API trigger",
                    "score": 8.0,
                    "relevance": 8.0,
                    "depth": 7.0,
                    "status": "pending"
                }
                result = explorer.explore(next_item)
                mark_topic_done(topic, "API trigger exploration completed")
                print(f"[Async] Exploration completed: {topic}, notified: {result.get('notified', False)}")

            except Exception as e:
                print(f"[Async] Exploration failed: {e}")
                import traceback
                traceback.print_exc()

        thread = threading.Thread(target=run_exploration_async, daemon=True)
        thread.start()

        return jsonify({
            "status": "accepted",
            "topic": topic,
            "depth": depth,
            "estimated_time": time_estimates.get(depth, "未知"),
            "message": "探索已启动，完成后将通过现有机制通知"
        }), 202

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


import re
import urllib.parse

def normalize_topic(topic: str) -> str:
    topic = urllib.parse.unquote(topic)
    topic = re.sub(r'\s+', ' ', topic)
    return topic.strip()


@app.route("/api/curious/queue", methods=["DELETE"])
def api_delete_queue_item():
    try:
        # Try to get JSON body, but don't fail if there's none (DELETE often uses query params)
        data = {}
        if request.is_json:
            data = request.get_json() or {}
        topic = data.get("topic", "") or request.args.get("topic", "")
        topic = normalize_topic(topic)
        force = data.get("force", False) or request.args.get("force", "false").lower() == "true"

        if not topic:
            return jsonify({"error": "topic is required"}), 400

        from core.knowledge_graph import remove_curiosity
        success = remove_curiosity(topic, force=force)

        if success:
            return jsonify({"status": "success", "topic": topic, "deleted": True})
        else:
            return jsonify({"status": "error", "message": "Topic not found or cannot be deleted"}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/curious/queue/pending", methods=["GET"])
def api_list_pending():
    try:
        from core.knowledge_graph import list_pending
        pending = list_pending()
        return jsonify({"status": "success", "count": len(pending), "items": pending})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/metacognitive/state")
def api_metacognitive_state():
    from core import knowledge_graph as kg
    state = kg.get_state()
    mc = kg.get_meta_cognitive_state()
    return jsonify({
        "status": "ok",
        "meta_cognitive": mc,
        "summary": {
            "completed_topics": len(mc.get("completed_topics", {})),
            "total_explorations": sum(mc.get("explore_counts", {}).values()),
            "topics_with_history": len(mc.get("explore_counts", {}))
        }
    })


@app.route("/api/metacognitive/check")
def api_metacognitive_check():
    from core import knowledge_graph as kg
    from core.meta_cognitive_monitor import MetaCognitiveMonitor
    from core.meta_cognitive_controller import MetaCognitiveController
    topic = normalize_topic(request.values.get("topic", ""))
    if not topic:
        return jsonify({"error": "topic parameter required"}), 400
    monitor = MetaCognitiveMonitor()
    controller = MetaCognitiveController(monitor)
    summary = controller.get_decision_summary(topic)
    return jsonify({
        "status": "ok",
        "topic": topic,
        "decision": summary
    })


@app.route("/api/metacognitive/history/<topic>")
def api_metacognitive_history(topic):
    from core import knowledge_graph as kg
    topic = normalize_topic(topic)
    state = kg.get_state()
    mc = state.get("meta_cognitive", {})
    logs = [log for log in mc.get("exploration_log", []) if log.get("topic") == topic]
    return jsonify({
        "status": "ok",
        "topic": topic,
        "history": logs,
        "count": kg.get_topic_explore_count(topic),
        "completed": kg.is_topic_completed(topic)
    })


@app.route("/api/metacognitive/topics/completed")
def api_metacognitive_completed():
    from core import knowledge_graph as kg
    mc = kg.get_meta_cognitive_state()
    completed = mc.get("completed_topics", {})
    return jsonify({
        "status": "ok",
        "completed_topics": [{"topic": topic, **data} for topic, data in completed.items()]
    })


@app.route("/api/r1d3/confidence", methods=["GET"])
def api_r1d3_confidence():
    """R1D3 queries confidence level for a topic"""
    try:
        from core.api.r1d3_tools import R1D3ToolHandler
        
        topic = request.args.get("topic", "").strip()
        if not topic:
            return jsonify({"error": "topic parameter is required"}), 400
        
        handler = R1D3ToolHandler()
        result = handler.curious_check_confidence(topic)
        
        return jsonify({
            "status": "ok",
            "result": result
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/r1d3/inject", methods=["POST"])
def api_r1d3_inject():
    """R1D3 triggers directed exploration"""
    try:
        from core.api.r1d3_tools import R1D3ToolHandler
        
        data = request.get_json() or {}
        topic = data.get("topic", "").strip()
        
        if not topic:
            return jsonify({"error": "topic is required"}), 400
        
        context = data.get("context", "")
        depth = data.get("depth", "medium")
        source = data.get("source", "r1d3")
        
        if depth not in ["shallow", "medium", "deep"]:
            return jsonify({"error": f"invalid depth: {depth}"}), 400
        
        handler = R1D3ToolHandler()
        result = handler.curious_agent_inject(topic, context, depth, source)
        
        return jsonify({
            "status": "ok",
            "result": result
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/r1d3/synthesize", methods=["POST"])
def api_r1d3_synthesize():
    """R1D3 triggers Layer 3 insight synthesis"""
    try:
        from core.insight_synthesizer import InsightSynthesizer
        
        data = request.get_json() or {}
        topic = data.get("topic", "").strip()
        sub_topic_results = data.get("sub_topic_results", {})
        
        if not topic:
            return jsonify({"error": "topic is required"}), 400
        
        if not sub_topic_results:
            return jsonify({"error": "sub_topic_results is required"}), 400
        
        synthesizer = InsightSynthesizer()
        insights = synthesizer.synthesize(topic, sub_topic_results)
        
        return jsonify({
            "status": "ok",
            "topic": topic,
            "insights_count": len(insights),
            "insights": [
                {
                    "id": i.id,
                    "hypothesis": i.hypothesis,
                    "type": i.type,
                    "reasoning": i.reasoning,
                    "confidence": i.confidence,
                    "supporting_snippets": i.supporting_snippets
                }
                for i in insights
            ]
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/r1d3/discoveries/unshared", methods=["GET"])
def api_r1d3_unshared_discoveries():
    """Get unshared discoveries for R1D3 to consume"""
    try:
        from core.sync.r1d3_sync import R1D3Sync
        
        sync = R1D3Sync()
        discoveries = sync.get_unshared_discoveries()
        
        return jsonify({
            "status": "ok",
            "count": len(discoveries),
            "discoveries": discoveries
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/r1d3/discoveries/mark_shared", methods=["POST"])
def api_r1d3_mark_shared():
    """Mark a discovery as shared"""
    try:
        from core.sync.r1d3_sync import R1D3Sync
        
        data = request.get_json() or {}
        filename = data.get("filename", "").strip()
        
        if not filename:
            return jsonify({"error": "filename is required"}), 400
        
        sync = R1D3Sync()
        success = sync.mark_discovery_shared(filename)
        
        if success:
            return jsonify({
                "status": "ok",
                "message": f"Discovery {filename} marked as shared"
            })
        else:
            return jsonify({
                "status": "error",
                "error": f"Failed to mark {filename} as shared"
            }), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


def main():
    import signal
    parser = argparse.ArgumentParser(description="Curious Agent API Server")
    parser.add_argument("--port", type=int, default=4848)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    url = f"http://10.1.0.13:{args.port}/"

    print(f"""
╔══════════════════════════════════════════╗
║    👁️  Curious Agent Web UI              ║
╠══════════════════════════════════════════╣
║  🌐 {url}
║  📡 API: {url}api/curious/state
║  📁 静态: {UI_DIR}/
║  🚪 端口: {args.port}
╚══════════════════════════════════════════╝
    """)

    # v0.2.6 fix: SIGTERM handler for graceful restart
    # When OpenClaw's management script kills us, wait for async threads first
    shutdown_requested = threading.Event()
    _server_ref = [None]  # mutable container for server reference

    def _monitor_shutdown(srv):
        """Background thread: waits for shutdown signal, then stops the server."""
        # v0.2.6 fix: No more timeout - only shutdown on actual SIGTERM/SIGINT
        # (the old 5-min restart script no longer exists, so no auto-restart needed)
        shutdown_requested.wait()  # Wait forever until signal is set
        print(f"[curious_api] Shutdown monitor triggered (requested={shutdown_requested.is_set()})")
        try:
            srv.shutdown()
        except Exception:
            pass

    def handle_sigterm(signum, frame):
        """SIGTERM handler: signal OpenClaw's restart script that we received the signal."""
        print("[curious_api] SIGTERM received, initiating graceful shutdown...")
        shutdown_requested.set()

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)

    def open_browser():
        time.sleep(1.5)
        webbrowser.open(url)

    threading.Thread(target=open_browser, daemon=True).start()

    # Use make_server so we can control shutdown
    from werkzeug.serving import make_server
    srv = make_server(args.host, args.port, app, threaded=True)
    _server_ref[0] = srv
    print(f"[curious_api] Serving on {args.host}:{args.port}")

    # Start shutdown monitor thread
    monitor = threading.Thread(target=_monitor_shutdown, args=(srv,), daemon=True, name="shutdown-monitor")
    monitor.start()

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("[curious_api] KeyboardInterrupt, shutting down...")
        shutdown_requested.set()
        srv.shutdown()

    # Graceful shutdown: wait for async exploration threads (up to 25s)
    # OpenClaw gives ~60s TimeoutStopSec, so 25s is safe
    print("[curious_api] Waiting for exploration threads to finish...")
    try:
        from core.async_explorer import wait_for_active_threads
        waited = wait_for_active_threads(timeout=25.0)
        print(f"[curious_api] Waited for {waited} thread(s), done.")
    except Exception as e:
        print(f"[curious_api] Thread join error: {e}")

    print("[curious_api] Exiting gracefully.")
    sys.exit(0)


@app.route("/api/kg/trace/<path:topic>")
def api_kg_trace(topic: str):
    """使用扩散激活算法向上追溯 topic 的因果链到根技术"""
    from core.knowledge_graph import get_spreading_activation_trace, get_root_technologies

    topic = topic.strip()

    result = get_spreading_activation_trace(topic)

    root_technologies = get_root_technologies()

    return jsonify({
        "topic": topic,
        "origin": result["origin"],
        "activation_map": result["activation_map"],
        "ordered_trace": result["ordered_trace"],
        "root_technologies": result["root_technologies"],
        "cross_subgraph_connections": result["cross_subgraph_connections"]
    })


@app.route("/api/kg/roots")
def api_kg_roots():
    """返回所有根技术，按 root_score 降序"""
    from core.knowledge_graph import get_root_technologies

    roots = get_root_technologies()
    return jsonify({
        "roots": roots,
        "total": len(roots)
    })


@app.route("/api/kg/overview")
def api_kg_overview():
    """返回 KG 全局视图数据（节点+边）"""
    from core.knowledge_graph import get_kg_overview

    return jsonify(get_kg_overview())


@app.route("/api/kg/promote", methods=["POST"])
def api_kg_promote():
    """手动将 topic 升为根候选（R1D3 或人工调用）"""
    from core.knowledge_graph import promote_to_root_candidate

    data = request.get_json()
    topic = data.get("topic", "").strip()
    domains = data.get("domains", [])

    if not topic:
        return jsonify({"error": "topic is required"}), 400

    promote_to_root_candidate(topic, domains)
    return jsonify({"status": "ok", "topic": topic})


# === v0.2.6 API Extensions (F13) ===

@app.route("/api/kg/dream_insights")
def api_kg_dream_insights():
    """Get all dream insights."""
    from core import knowledge_graph as kg
    insights = kg.get_all_dream_insights()
    return jsonify({"insights": insights})


@app.route("/api/kg/dream_insights/<topic>")
def api_kg_dream_insights_topic(topic: str):
    """Get dream insights for specific topic."""
    from core import knowledge_graph as kg
    insights = kg.get_dream_insights(topic)
    return jsonify({"insights": insights})


@app.route("/api/kg/dormant")
def api_kg_dormant():
    """Get all dormant nodes."""
    from core import knowledge_graph as kg
    nodes = kg.get_dormant_nodes()
    return jsonify({"dormant_nodes": nodes})


@app.route("/api/kg/reactivate", methods=["POST"])
def api_kg_reactivate():
    """Reactivate a dormant node."""
    from core import knowledge_graph as kg
    data = request.get_json()
    topic = data.get("topic", "").strip()

    if not topic:
        return jsonify({"error": "topic is required"}), 400

    kg.reactivate(topic)
    return jsonify({"status": "ok", "topic": topic})





@app.route("/api/kg/confidence/<path:topic>")
def api_kg_confidence(topic: str):
    """Get confidence interval for topic."""
    from core.meta_cognitive_monitor import MetaCognitiveMonitor

    monitor = MetaCognitiveMonitor()
    low, high = monitor.get_confidence_interval(topic)

    return jsonify({
        "topic": topic,
        "confidence_low": low,
        "confidence_high": high
    })


@app.route("/api/kg/frontier")
def api_kg_frontier():
    """Get knowledge frontier."""
    from core.meta_cognitive_monitor import MetaCognitiveMonitor

    monitor = MetaCognitiveMonitor()
    frontiers = monitor.detect_frontier()

    return jsonify({"frontiers": frontiers})


@app.route("/api/kg/calibration")
def api_kg_calibration():
    """Get overall calibration error."""
    from core.meta_cognitive_monitor import MetaCognitiveMonitor

    monitor = MetaCognitiveMonitor()
    error = monitor.get_calibration_error()

    verdict = "well_calibrated" if error < 0.1 else "overconfident" if error > 0.3 else "moderate"

    return jsonify({
        "calibration_error": error,
        "verdict": verdict
    })


# =============================================================================
# Knowledge API Endpoints (v0.3.0 Cognitive Framework)
# =============================================================================

@app.route("/api/knowledge/check", methods=["POST"])
def api_knowledge_check():
    """Query KG confidence and guidance for a topic."""
    try:
        from core.hooks.cognitive_hook import CognitiveHook
        from core.kg.repository_factory import KGRepositoryFactory
        from core.config import get_config
        
        data = request.get_json() or {}
        topic = data.get("topic", "").strip()
        
        if not topic:
            return jsonify({"error": "topic is required"}), 400
        
        config = get_config()
        hook_config = {
            "confidence_threshold": config.hooks.confidence_threshold,
            "auto_inject_unknowns": config.hooks.auto_inject_unknowns,
            "search_before_llm": config.hooks.search_before_llm,
        }
        
        cognitive_hook = CognitiveHook(hook_config)
        kg_factory = KGRepositoryFactory.get_instance()
        
        kg_node = kg_factory.get_node_sync(topic)
        
        if kg_node:
            kg_confidence = kg_node.get("confidence", 0.0)
            gaps = kg_node.get("gaps", [])
        else:
            kg_confidence = 0.0
            gaps = ["No knowledge graph entry found"]
        
        guidance = cognitive_hook.check_confidence(topic, kg_confidence, gaps)
        
        return jsonify({
            "success": True,
            "result": {
                "topic": topic,
                "confidence": kg_confidence,
                "level": guidance.level.value,
                "gaps": gaps,
                "guidance": guidance.guidance_message,
                "should_search": guidance.should_search,
                "should_inject": guidance.should_inject,
            }
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/knowledge/learn", methods=["POST"])
def api_knowledge_learn():
    """Inject unknown topic to CA queue."""
    try:
        from core.hooks.cognitive_hook import CognitiveHook, AnswerStrategy
        from core.config import get_config
        
        data = request.get_json() or {}
        topic = data.get("topic", "").strip()
        strategy_str = data.get("strategy", "llm_answer")
        
        if not topic:
            return jsonify({"error": "topic is required"}), 400
        
        config = get_config()
        hook_config = {
            "confidence_threshold": config.hooks.confidence_threshold,
            "auto_inject_unknowns": config.hooks.auto_inject_unknowns,
            "search_before_llm": config.hooks.search_before_llm,
        }
        
        cognitive_hook = CognitiveHook(hook_config)
        
        strategy_map = {
            "kg_answer": AnswerStrategy.KG_ANSWER,
            "search_answer": AnswerStrategy.SEARCH_ANSWER,
            "llm_answer": AnswerStrategy.LLM_ANSWER,
        }
        strategy = strategy_map.get(strategy_str, AnswerStrategy.LLM_ANSWER)
        
        result = cognitive_hook.inject_unknown(
            topic=topic,
            context=f"Manually injected via API for exploration",
            strategy=strategy,
            priority=False,
        )
        
        return jsonify({
            "success": True,
            "result": {
                "queue_id": result["queue_id"],
                "topic": result["topic"],
                "status": result["status"],
                "estimated_exploration": result["estimated_exploration"],
            }
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/knowledge/analytics", methods=["GET"])
def api_knowledge_analytics():
    """Get interaction statistics."""
    try:
        from core.hooks.cognitive_hook import CognitiveHook
        from core.config import get_config
        
        config = get_config()
        hook_config = {
            "confidence_threshold": config.hooks.confidence_threshold,
            "auto_inject_unknowns": config.hooks.auto_inject_unknowns,
            "search_before_llm": config.hooks.search_before_llm,
        }
        
        cognitive_hook = CognitiveHook(hook_config)
        stats = cognitive_hook.get_stats()
        
        return jsonify({
            "kg_hits": stats.get("kg_hits", 0),
            "search_hits": stats.get("search_hits", 0),
            "llm_fallbacks": stats.get("llm_fallbacks", 0),
            "topics_learned": stats.get("topics_injected", 0),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/knowledge/record", methods=["POST"])
def api_knowledge_record():
    """Record search results to KG."""
    try:
        from core.kg.repository_factory import KGRepositoryFactory
        
        data = request.get_json() or {}
        topic = data.get("topic", "").strip()
        content = data.get("content", "").strip()
        sources = data.get("sources", [])
        
        if not topic:
            return jsonify({"error": "topic is required"}), 400
        if not content:
            return jsonify({"error": "content is required"}), 400
        
        kg_factory = KGRepositoryFactory.get_instance()
        
        queue_id = kg_factory.create_knowledge_node_sync(
            topic=topic,
            content=content,
            source_urls=sources,
            metadata={"source": "api_record"}
        )
        
        return jsonify({
            "success": True,
            "result": {
                "node_id": queue_id,
                "topic": topic,
            }
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/curious/quality/assertion", methods=["POST"])
def assess_quality_assertion():
    """Test assertion-based quality assessment"""
    data = request.get_json()
    topic = data.get('topic')
    findings = data.get('findings', {})
    
    from core.config import get_config
    from core.embedding_service import EmbeddingService, EmbeddingConfig
    from core.assertion_index import AssertionIndex
    from core.quality_v2 import QualityV2Assessor
    from core.llm_client import LLMClient
    from core.kg_graph import KGGraph
    
    config = get_config()
    llm = LLMClient()
    embedding_service = EmbeddingService(config.knowledge.get("embedding"))
    assertion_index = AssertionIndex()
    kg = KGGraph()
    
    assessor = QualityV2Assessor(
        llm,
        embedding_service=embedding_service,
        assertion_index=assertion_index,
        knowledge_graph=kg
    )
    
    quality = assessor.assess_quality(topic, findings, kg)
    
    return jsonify({
        'topic': topic,
        'quality': quality,
        'method': 'assertion_based'
    })


@app.route("/api/agents/explore", methods=["POST"])
def api_agents_explore():
    """Run ExploreAgent on a specific topic."""
    try:
        import asyncio
        from core.agents.explore_agent import ExploreAgent, ExploreAgentConfig
        from core.tools.registry import ToolRegistry
        
        data = request.get_json() or {}
        topic = data.get("topic", "").strip()
        
        if not topic:
            return jsonify({"error": "topic is required"}), 400
        
        # Read from config
        cfg = get_config()
        agent_cfg = cfg.agents.get("explore", {})
        
        tool_registry = ToolRegistry()
        config = ExploreAgentConfig(
            name="explore_agent",
            model=agent_cfg.get("model", "volcengine"),
            max_iterations=agent_cfg.get("max_iterations", 10),
        )
        agent = ExploreAgent(config=config, tool_registry=tool_registry)
        
        result = asyncio.run(agent.run(topic))
        
        return jsonify({
            "status": "success" if result.success else "failed",
            "topic": topic,
            "iterations": result.iterations_used,
            "content": result.content
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/agents/dream", methods=["POST"])
def api_agents_dream():
    """Run DreamAgent to generate insight topics."""
    try:
        from core.agents.dream_agent import DreamAgent, DreamAgentConfig
        from core.tools.registry import ToolRegistry
        
        # Read from config
        cfg = get_config()
        agent_cfg = cfg.agents.get("dream", {})
        weights_raw = agent_cfg.get("scoring_weights", {})
        
        tool_registry = ToolRegistry()
        config = DreamAgentConfig(
            name="dream_agent",
            scoring_weights=weights_raw or {
                "relevance": 0.25, "frequency": 0.15, "recency": 0.15,
                "quality": 0.20, "surprise": 0.15, "cross_domain": 0.10
            },
            min_score_threshold=agent_cfg.get("min_score_threshold", 0.8),
            min_recall_count=agent_cfg.get("min_recall_count", 3),
        )
        agent = DreamAgent(config=config, tool_registry=tool_registry)
        
        result = agent.run()
        
        return jsonify({
            "status": "success" if result.success else "failed",
            "topics_generated": result.topics_generated,
            "candidates_selected": result.candidates_selected,
            "content": result.content
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/agents/daemon/explore", methods=["POST"])
def api_agents_daemon_explore():
    """Start ExploreDaemon for continuous exploration."""
    try:
        import threading
        from core.agents.explore_agent import ExploreAgent, ExploreAgentConfig
        from core.daemon.explore_daemon import ExploreDaemon, ExploreDaemonConfig
        from core.tools.registry import ToolRegistry
        from core.tools.queue_tools import QueueStorage
        
        # Read config from config.json
        cfg = get_config()
        daemon_cfg = cfg.daemon.get("explore")
        agent_cfg = cfg.agents.get("explore")
        poll_interval = daemon_cfg.poll_interval_seconds
        max_retries = daemon_cfg.max_retries
        retry_delay = daemon_cfg.retry_delay_seconds
        
        tool_registry = ToolRegistry()
        agent_config = ExploreAgentConfig(
            name="explore_agent",
            model=agent_cfg.model,
            max_iterations=agent_cfg.max_iterations
        )
        agent = ExploreAgent(config=agent_config, tool_registry=tool_registry)
        
        queue_storage = QueueStorage()
        queue_storage.initialize()
        daemon_config = ExploreDaemonConfig(
            poll_interval_seconds=poll_interval,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay
        )
        
        daemon = ExploreDaemon(
            explore_agent=agent,
            queue_storage=queue_storage,
            config=daemon_config
        )
        
        daemon.start()
        
        return jsonify({
            "status": "started",
            "daemon_name": "explore_daemon",
            "poll_interval_seconds": poll_interval,
            "max_retries": max_retries,
            "retry_delay_seconds": retry_delay
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/agents/daemon/dream", methods=["POST"])
def api_agents_daemon_dream():
    """Start DreamDaemon for heartbeat-triggered dreaming."""
    try:
        import asyncio
        from pathlib import Path
        from core.agents.dream_agent import DreamAgentConfig as DreamAgentAgentConfig
        from core.daemon.dream_daemon import DreamDaemon, DreamDaemonConfig

        cfg = get_config()
        daemon_cfg = cfg.daemon.get("dream")
        agent_dream_cfg = cfg.agents.get("dream")

        interval_s = daemon_cfg.interval_seconds
        # Allow override via request body
        data = request.get_json() or {}
        if "interval_s" in data:
            interval_s = data["interval_s"]

        def _sw_to_dict(w):
            return {"relevance": w.relevance, "frequency": w.frequency,
                    "recency": w.recency, "quality": w.quality,
                    "surprise": w.surprise, "cross_domain": w.cross_domain}

        agent_config = DreamAgentAgentConfig(
            name="DreamAgent",
            scoring_weights=_sw_to_dict(agent_dream_cfg.scoring_weights),
            min_score_threshold=agent_dream_cfg.min_score_threshold,
            min_recall_count=agent_dream_cfg.min_recall_count,
        )
        daemon_config = DreamDaemonConfig(interval_seconds=interval_s, enabled=True)

        daemon = DreamDaemon(
            workspace=Path("."),
            config=daemon_config,
            agent_config=agent_config,
        )

        threading.Thread(target=lambda: asyncio.run(daemon.start()), daemon=True).start()

        return jsonify({
            "status": "started",
            "daemon_name": "dream_daemon",
            "interval_seconds": interval_s
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/agents/status", methods=["GET"])
def api_agents_status():
    """Get status of running agents."""
    try:
        from core.tools.queue_tools import QueueStorage
        
        queue_storage = QueueStorage()
        pending = queue_storage.get_pending_items()
        
        return jsonify({
            "status": "ok",
            "queue_pending_count": len(pending),
            "agents": {
                "explore_agent": "available",
                "dream_agent": "available",
                "explore_daemon": "available",
                "dream_daemon": "available"
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()


# Queue API endpoints
@app.route("/api/queue", methods=["GET"])
def api_queue_status():
    """Get queue status - pending, claimed, completed items."""
    try:
        from core.tools.queue_tools import QueueStorage
        
        queue = QueueStorage()
        queue.initialize()
        
        pending = queue.get_pending_items()
        completed = queue.get_completed_items(limit=20)
        
        stats = {
            "pending": len(pending),
            "completed": len(completed),
        }
        
        return jsonify({
            "status": "ok",
            "stats": stats,
            "pending": pending,
            "recent_completed": completed
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/queue/add", methods=["POST"])
def api_queue_add():
    """Add topic to queue."""
    try:
        from core.tools.queue_tools import QueueStorage
        
        data = request.get_json() or {}
        topic = data.get("topic", "").strip()
        priority = data.get("priority", 5)
        metadata = data.get("metadata", {})
        
        if not topic:
            return jsonify({"error": "topic is required"}), 400
            
        queue = QueueStorage()
        queue.initialize()
        
        item_id = queue.add_item(topic, priority=priority, metadata=metadata)
        
        return jsonify({
            "status": "ok",
            "item_id": item_id,
            "topic": topic
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/queue/claim", methods=["POST"])
def api_queue_claim():
    """Atomic claim a pending item."""
    try:
        from core.tools.queue_tools import QueueStorage
        
        data = request.get_json() or {}
        holder_id = data.get("holder_id", "")
        timeout_s = data.get("timeout_s", 300)
        
        if not holder_id:
            return jsonify({"error": "holder_id is required"}), 400
            
        queue = QueueStorage()
        queue.initialize()
        
        item = queue.claim_pending(holder_id=holder_id, timeout_seconds=timeout_s)
        
        if item:
            return jsonify({
                "status": "claimed",
                "item": item
            })
        else:
            return jsonify({
                "status": "idle",
                "item": None
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/queue/done", methods=["POST"])
def api_queue_done():
    """Mark item as done."""
    try:
        from core.tools.queue_tools import QueueStorage
        
        data = request.get_json() or {}
        item_id = data.get("item_id")
        
        if item_id is None:
            return jsonify({"error": "item_id is required"}), 400
            
        queue = QueueStorage()
        queue.initialize()
        success = queue.mark_done(item_id)
        
        return jsonify({
            "status": "ok" if success else "failed",
            "marked_done": success
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/queue/failed", methods=["POST"])
def api_queue_failed():
    """Mark item as failed."""
    try:
        from core.tools.queue_tools import QueueStorage
        
        data = request.get_json() or {}
        item_id = data.get("item_id")
        reason = data.get("reason", "unknown")
        requeue = data.get("requeue", False)
        
        if item_id is None:
            return jsonify({"error": "item_id is required"}), 400
            
        queue = QueueStorage()
        queue.initialize()
        success = queue.mark_failed(item_id, reason=reason, requeue=requeue)
        
        return jsonify({
            "status": "ok" if success else "failed",
            "marked_failed": success
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


# Discoveries API endpoints
@app.route("/api/discoveries", methods=["GET"])
def api_discoveries_list():
    """List all discoveries."""
    try:
        import os
        import json
        from pathlib import Path
        
        shared_knowledge = Path(__file__).parent / "shared_knowledge" / "ca" / "discoveries"
        if not shared_knowledge.exists():
            return jsonify({"status": "ok", "discoveries": [], "count": 0})
            
        discoveries = []
        for json_file in shared_knowledge.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data["filename"] = json_file.name
                    discoveries.append(data)
            except (json.JSONDecodeError, IOError):
                continue
            
        # Sort by created_at descending
        discoveries.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return jsonify({
            "status": "ok",
            "discoveries": discoveries,
            "count": len(discoveries)
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/discoveries/<id>/share", methods=["POST"])
def api_discoveries_share(id):
    """Mark discovery as shared."""
    try:
        import os
        import json
        from pathlib import Path
        from datetime import datetime, timezone
        
        shared_knowledge = Path(__file__).parent / "shared_knowledge" / "ca" / "discoveries"
        discovery_file = shared_knowledge / f"{id}.json"
        
        if not discovery_file.exists():
            return jsonify({"error": "Discovery not found"}), 404
            
        with open(discovery_file, "r+", encoding="utf-8") as f:
            data = json.load(f)
            data["shared"] = True
            data["shared_at"] = datetime.now(timezone.utc).isoformat()
            f.seek(0)
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.truncate()
            
        return jsonify({
            "status": "ok",
            "marked_shared": True,
            "discovery_id": id
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


# Auth API endpoints
@app.route("/api/auth/register", methods=["POST"])
def api_auth_register():
    """Register new API key for consumer."""
    try:
        import os
        import json
        import secrets
        from pathlib import Path
        from datetime import datetime, timezone
        
        data = request.get_json() or {}
        consumer = data.get("consumer", "").strip()
        
        if not consumer:
            return jsonify({"error": "consumer name is required"}), 400
            
        # Generate API key
        api_key = f"ca_{secrets.token_hex(16)}"
        
        # Load existing keys
        api_keys_file = Path(__file__).parent / "knowledge" / "api_keys.json"
        api_keys_file.parent.mkdir(parents=True, exist_ok=True)
        
        api_keys = {}
        if api_keys_file.exists():
            with open(api_keys_file, "r", encoding="utf-8") as f:
                api_keys = json.load(f)
                
        api_keys[api_key] = {
            "consumer": consumer,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "enabled": True
        }
        
        with open(api_keys_file, "w", encoding="utf-8") as f:
            json.dump(api_keys, f, indent=2, ensure_ascii=False)
            
        return jsonify({
            "status": "ok",
            "api_key": api_key,
            "consumer": consumer
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


if __name__ == "__main__":
    main()
