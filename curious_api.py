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
        topic_copy["quality"] = quality_map.get(name, None)
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

        add_curiosity(
            topic=topic,
            reason=str(data.get("reason", "Web UI 注入")),
            relevance=final_score,
            depth=depth
        )

        # ===== T-9 集成点 开始 =====
        # 【集成点 6】inject_priority: source=r1d3 时优先处理
        config = get_config()
        from core.knowledge_graph import update_curiosity_score
        source = data.get("source", "default")
        priority_cfg = get_config().exploration.injection_priority

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

    if not args.no_browser:
        def open_browser():
            time.sleep(1.5)
            webbrowser.open(url)
        threading.Thread(target=open_browser, daemon=True).start()

    app.run(host=args.host, port=args.port, debug=False, threaded=True)


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


if __name__ == "__main__":
    main()
