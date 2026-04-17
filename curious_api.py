"""
Curious Agent API Server
提供 RESTful API 和静态文件服务
"""
import argparse
import json
import os
import queue as queue_mod
import sqlite3
import sys
import threading
import time
import traceback
import uuid
import webbrowser
from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_from_directory, g
from core.config import get_config

app = Flask(__name__)

# UI 静态文件目录
UI_DIR = os.path.join(os.path.dirname(__file__), "ui")


# =============================================================================
# Hook Audit Middleware (v0.3.1)
# =============================================================================

HOOK_ENDPOINTS = {
    "/api/knowledge/confidence",
    "/api/knowledge/learn",
    "/api/kg/overview",
    "/api/knowledge/check",
    "/api/knowledge/record",
}

_audit_db_path = os.path.join(os.path.dirname(__file__), "knowledge", "hook_audit.db")
_audit_log_path = os.path.join(os.path.dirname(__file__), "logs", "hook_access.log")
_audit_queue = queue_mod.Queue(maxsize=10000)
_audit_thread = None


def _ensure_audit_db():
    """Initialize audit database tables."""
    os.makedirs(os.path.dirname(_audit_db_path), exist_ok=True)
    conn = sqlite3.connect(_audit_db_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS hook_calls (
        id TEXT PRIMARY KEY, timestamp TEXT NOT NULL,
        direction TEXT NOT NULL DEFAULT 'inbound', hook_name TEXT NOT NULL,
        hook_type TEXT NOT NULL, hook_event TEXT NOT NULL,
        agent_id TEXT NOT NULL DEFAULT 'r1d3', agent_session TEXT,
        endpoint TEXT NOT NULL, method TEXT NOT NULL DEFAULT 'GET',
        request_headers TEXT, request_payload TEXT, request_raw_topic TEXT,
        status TEXT NOT NULL DEFAULT 'success', status_code INTEGER NOT NULL DEFAULT 200,
        response_payload TEXT, latency_ms INTEGER NOT NULL DEFAULT 0,
        confidence_level TEXT, knowledge_injected INTEGER DEFAULT 0,
        injection_snippet TEXT, related_topic TEXT, related_queue_item TEXT,
        ca_trace_id TEXT, error_message TEXT,
        created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hook_calls_agent_time ON hook_calls(agent_id, timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hook_calls_hook_time ON hook_calls(hook_name, timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hook_calls_status ON hook_calls(status)")
    conn.commit()
    conn.close()


def _audit_worker():
    """Background daemon thread that writes audit records to DB and log file."""
    os.makedirs(os.path.dirname(_audit_log_path), exist_ok=True)
    db = sqlite3.connect(_audit_db_path, check_same_thread=False)
    log_file = open(_audit_log_path, "a", encoding="utf-8")

    while True:
        try:
            record = _audit_queue.get(timeout=1)
        except queue_mod.Empty:
            continue
        if record is None:
            break
        try:
            db.execute(
                """INSERT INTO hook_calls (id, timestamp, direction, hook_name, hook_type,
                   hook_event, agent_id, agent_session, endpoint, method, request_headers,
                   request_payload, request_raw_topic, status, status_code, response_payload,
                   latency_ms, confidence_level, knowledge_injected, injection_snippet,
                   related_topic, related_queue_item, ca_trace_id, error_message)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (record["id"], record["timestamp"], record["direction"],
                 record["hook_name"], record["hook_type"], record["hook_event"],
                 record["agent_id"], record.get("agent_session"),
                 record["endpoint"], record["method"],
                 record.get("request_headers"), record.get("request_payload"),
                 record.get("request_raw_topic"),
                 record["status"], record["status_code"],
                 record.get("response_payload"), record["latency_ms"],
                 record.get("confidence_level"), record.get("knowledge_injected", 0),
                 record.get("injection_snippet"), record.get("related_topic"),
                 record.get("related_queue_item"), record.get("ca_trace_id"),
                 record.get("error_message")),
            )
            db.commit()
            log_line = (
                f"[{record['timestamp']}] {record['hook_name']:<16} {record['agent_id']}"
                f"  → {record['method']} {record['endpoint']}"
                f"  ← {record['status_code']} {record['latency_ms']}ms"
                f" {record.get('request_raw_topic', '')[:60]}"
            )
            log_file.write(log_line + "\n")
            log_file.flush()
        except Exception as e:
            print(f"[audit] write failed: {e}")
        finally:
            _audit_queue.task_done()


def _is_hook_endpoint(path):
    """Check if the request path matches one of the Hook endpoints."""
    if path.startswith("/api/kg/confidence/"):
        return True
    return path in HOOK_ENDPOINTS


def _build_audit_record(req, resp, latency_ms):
    """Build audit record from request and response."""
    headers = {
        k: v for k, v in dict(req.headers).items()
        if k.lower() in ("x-openclaw-agent-id", "x-openclaw-hook-name",
                         "x-openclaw-hook-event", "x-openclaw-hook-type",
                         "x-openclaw-session-id")
    }
    hook_name = headers.get("X-OpenClaw-Hook-Name", "unknown")
    hook_type = headers.get("X-OpenClaw-Hook-Type", "unknown")
    hook_event = headers.get("X-OpenClaw-Hook-Event", "unknown")

    req_payload = None
    try:
        if req.is_json and req.data and len(req.data) < 4096:
            req_payload = req.get_data(as_text=True)
    except Exception:
        pass

    resp_payload = None
    try:
        if resp.is_json and len(resp.get_data(as_text=True)) < 4096:
            resp_payload = resp.get_data(as_text=True)
    except Exception:
        pass

    raw_topic = req.args.get("topic", "")
    if not raw_topic and req_payload:
        try:
            parsed = json.loads(req_payload)
            raw_topic = parsed.get("topic", "")
        except Exception:
            pass

    return {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "direction": "inbound",
        "hook_name": hook_name,
        "hook_type": hook_type,
        "hook_event": hook_event,
        "agent_id": headers.get("X-OpenClaw-Agent-Id", "unknown"),
        "agent_session": headers.get("X-OpenClaw-Session-Id"),
        "endpoint": req.path,
        "method": req.method,
        "request_headers": json.dumps(headers),
        "request_payload": req_payload,
        "request_raw_topic": raw_topic,
        "status": "success" if resp.status_code < 400 else "error",
        "status_code": resp.status_code,
        "response_payload": resp_payload,
        "latency_ms": int(latency_ms),
        "confidence_level": None,
        "knowledge_injected": 0,
        "injection_snippet": None,
        "related_topic": None,
        "related_queue_item": None,
        "ca_trace_id": None,
        "error_message": None,
    }


@app.before_request
def record_request_start():
    """Record request start time for latency calculation."""
    g.start_time = time.time()


@app.after_request
def audit_hook_requests(response):
    """Audit Hook endpoint requests after they complete."""
    if not _is_hook_endpoint(request.path):
        return response
    try:
        start = getattr(g, 'start_time', time.time())
        latency_ms = int((time.time() - start) * 1000)
        record = _build_audit_record(request, response, latency_ms)
        try:
            _audit_queue.put_nowait(record)
        except queue_mod.Full:
            print("[audit] queue full, dropping record")
    except Exception as e:
        print(f"[audit] error: {e}")
    return response


# Start audit worker thread at module load
_audit_thread = threading.Thread(target=_audit_worker, daemon=True, name="audit-worker")
_audit_thread.start()


# =============================================================================
# Audit API Endpoints (v0.3.1)
# =============================================================================

def _get_audit_db():
    """Get audit database connection with row factory."""
    conn = sqlite3.connect(_audit_db_path)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/api/audit/hooks")
def api_audit_hooks():
    """Query Hook call records (paginated, filtered)."""
    try:
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
        hook = request.args.get("hook")
        agent = request.args.get("agent")
        status = request.args.get("status")

        query = "SELECT * FROM hook_calls WHERE 1=1"
        params = []
        if hook:
            query += " AND hook_name = ?"
            params.append(hook)
        if agent:
            query += " AND agent_id = ?"
            params.append(agent)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = _get_audit_db()
        rows = conn.execute(query, params).fetchall()

        count_query = query.replace("SELECT *", "SELECT COUNT(*)").replace(
            " ORDER BY timestamp DESC LIMIT ? OFFSET ?", ""
        )
        total = conn.execute(count_query, params[:-2]).fetchone()[0]
        conn.close()

        return jsonify({
            "total": total,
            "records": [dict(r) for r in rows]
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/audit/hooks/<hook_id>")
def api_audit_hook_detail(hook_id):
    """Single Hook call detail."""
    try:
        conn = _get_audit_db()
        row = conn.execute("SELECT * FROM hook_calls WHERE id = ?", (hook_id,)).fetchone()
        conn.close()
        if not row:
            return jsonify({"error": "not found"}), 404
        return jsonify(dict(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/audit/hooks/stats")
def api_audit_hooks_stats():
    """Hook call statistics."""
    try:
        conn = _get_audit_db()

        by_hook = {}
        rows = conn.execute("""
            SELECT hook_name,
                   COUNT(*) as total,
                   SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as success,
                   SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) as error,
                   AVG(latency_ms) as avg_latency
            FROM hook_calls GROUP BY hook_name
        """).fetchall()
        for r in rows:
            by_hook[r["hook_name"]] = {
                "total": r["total"], "success": r["success"],
                "error": r["error"], "avg_latency_ms": int(r["avg_latency"] or 0)
            }

        by_agent = {}
        rows = conn.execute("""
            SELECT agent_id,
                   COUNT(*) as total,
                   SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as success,
                   SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) as error
            FROM hook_calls GROUP BY agent_id
        """).fetchall()
        for r in rows:
            by_agent[r["agent_id"]] = {
                "total": r["total"], "success": r["success"], "error": r["error"]
            }

        overall = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as success,
                   SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) as error,
                   AVG(latency_ms) as avg_latency
            FROM hook_calls
        """).fetchone()

        conn.close()
        return jsonify({
            "by_hook": by_hook,
            "by_agent": by_agent,
            "overall": {
                "total": overall["total"],
                "success_rate": overall["success"] / max(overall["total"], 1),
                "avg_latency_ms": int(overall["avg_latency"] or 0)
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/audit/webhooks")
def api_audit_webhooks():
    """Webhook push records (v0.3.1 placeholder)."""
    return jsonify({"webhooks": [], "note": "Reserved for future webhook support"})


@app.route("/api/audit/agent/<agent_id>/activity")
def api_audit_agent_activity(agent_id):
    """Complete activity timeline for an Agent."""
    try:
        limit = int(request.args.get("limit", 50))
        conn = _get_audit_db()
        rows = conn.execute("""
            SELECT id, timestamp, hook_name, endpoint, method, status,
                   latency_ms, request_raw_topic, confidence_level
            FROM hook_calls
            WHERE agent_id = ?
            ORDER BY timestamp DESC LIMIT ?
        """, (agent_id, limit)).fetchall()
        conn.close()

        return jsonify({
            "agent_id": agent_id,
            "total_calls": len(rows),
            "activities": [dict(r) for r in rows]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/audit/sessions/<session_id>")
def api_audit_sessions(session_id):
    """All Hook calls within a Session."""
    try:
        conn = _get_audit_db()
        rows = conn.execute("""
            SELECT * FROM hook_calls
            WHERE agent_session = ?
            ORDER BY timestamp ASC
        """, (session_id,)).fetchall()
        conn.close()

        hook_calls = [dict(r) for r in rows]
        knowledge_injected = [
            {"hook": r["hook_name"], "topic": r["request_raw_topic"]}
            for r in rows if r.get("knowledge_injected")
        ]

        return jsonify({
            "session_id": session_id,
            "hook_calls": hook_calls,
            "knowledge_injected": knowledge_injected
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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


@app.route("/api/knowledge/confidence", methods=["GET"])
def api_knowledge_confidence():
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


@app.route("/api/knowledge/explore", methods=["POST"])
def api_knowledge_explore():
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


@app.route("/api/knowledge/synthesize", methods=["POST"])
def api_knowledge_synthesize():
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


@app.route("/api/discoveries/unshared", methods=["GET"])
def api_discoveries_unshared():
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


@app.route("/api/discoveries/mark_shared", methods=["POST"])
def api_discoveries_mark_shared():
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

    # v0.3.1: Initialize audit database and ensure directories exist
    _ensure_audit_db()
    os.makedirs(os.path.join(os.path.dirname(__file__), "logs"), exist_ok=True)

    # v0.3.1: Initialize trace databases
    from core.trace.explorer_trace import TraceWriter
    TraceWriter()

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
    import traceback
    from core.knowledge_graph import get_spreading_activation_trace, get_root_technologies

    try:
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
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/kg/roots")
def api_kg_roots():
    """返回所有根技术，按 root_score 降序"""
    import traceback
    from core.knowledge_graph import get_root_technologies

    try:
        roots = get_root_technologies()
        return jsonify({
            "roots": roots,
            "total": len(roots)
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/kg/overview")
def api_kg_overview():
    """Get KG overview for frontend visualization."""
    try:
        from core.kg.repository_factory import get_kg_factory
        
        kg_factory = get_kg_factory()
        overview = kg_factory.get_graph_overview_sync()
        
        return jsonify({
            "status": "ok",
            "nodes": overview["nodes"],
            "edges": overview["edges"]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/kg/nodes/<path:node_id>")
def api_kg_node_detail(node_id):
    """Get single KG node full details."""
    try:
        from core import knowledge_graph as kg
        
        state = kg.get_state()
        node = state["knowledge"]["topics"].get(node_id)
        if not node:
            return jsonify({"error": "not found"}), 404
        
        explore_count = kg.get_topic_explore_count(node_id)
        
        return jsonify({
            "id": node_id,
            "quality": node.get("quality", 0),
            "status": node.get("status", "unexplored"),
            "summary": node.get("summary", ""),
            "sources": node.get("sources", []),
            "parents": node.get("parents", []),
            "children": node.get("children", []),
            "cites": node.get("cites", []),
            "cited_by": node.get("cited_by", []),
            "explains": node.get("explains", []),
            "exploration_count": explore_count,
            "depth": node.get("depth", 0),
            "is_root_candidate": node.get("is_root_candidate", False),
            "created_at": node.get("created_at", ""),
            "last_updated": node.get("last_updated", ""),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/kg/edges")
def api_kg_edges():
    """Get edges for a specific node or all edges."""
    try:
        from core import knowledge_graph as kg
        
        node_filter = request.args.get("node")
        state = kg.get_state()
        topics = state["knowledge"]["topics"]
        edges = []
        
        for name, node in topics.items():
            if node_filter and name != node_filter:
                for child in node.get("children", []):
                    if child == node_filter:
                        edges.append({"from": name, "to": child, "type": "child_of"})
                for cited in node.get("cites", []):
                    if cited == node_filter:
                        edges.append({"from": name, "to": cited, "type": "cites"})
                continue
            for child in node.get("children", []):
                edges.append({"from": name, "to": child, "type": "child_of"})
            for cited in node.get("cites", []):
                edges.append({"from": name, "to": cited, "type": "cites"})
        
        return jsonify({"node": node_filter, "edges": edges})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/kg/subgraph")
def api_kg_subgraph():
    """Get subgraph from a root topic with specified depth."""
    try:
        from core import knowledge_graph as kg
        
        root = request.args.get("root", "")
        depth = int(request.args.get("depth", 2))
        if not root:
            return jsonify({"error": "root parameter required"}), 400
        
        state = kg.get_state()
        topics = state["knowledge"]["topics"]
        visited = set()
        nodes = []
        edges = []
        
        def _walk(topic, current_depth):
            if topic in visited or current_depth > depth:
                return
            visited.add(topic)
            if topic in topics:
                node = topics[topic]
                nodes.append({
                    "id": topic,
                    "quality": node.get("quality", 0),
                    "status": node.get("status", "unexplored"),
                    "depth_level": current_depth,
                })
                for child in node.get("children", []):
                    edges.append({"from": topic, "to": child, "type": "child_of"})
                    _walk(child, current_depth + 1)
        
        _walk(root, 0)
        return jsonify({"root": root, "depth": depth, "nodes": nodes, "edges": edges})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/kg/stats")
def api_kg_stats():
    """Get KG statistics summary from Neo4j."""
    try:
        from core.kg.repository_factory import get_kg_factory
        
        kg_factory = get_kg_factory()
        stats = kg_factory.get_stats_sync()
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/kg/quality-distribution")
def api_kg_quality_distribution():
    """Get KG quality distribution."""
    try:
        from core import knowledge_graph as kg
        
        state = kg.get_state()
        topics = state["knowledge"]["topics"]
        dist = {"high": [], "medium": [], "low": [], "none": []}
        
        for name, node in topics.items():
            q = node.get("quality", None)
            if q is None or q == 0:
                dist["none"].append(name)
            elif q >= 7:
                dist["high"].append(name)
            elif q >= 5:
                dist["medium"].append(name)
            else:
                dist["low"].append(name)
        
        return jsonify({k: {"count": len(v), "topics": v} for k, v in dist.items()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
        return jsonify({"status": "error", "error": str(e)}), 500


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
        holder_id = data.get("holder_id", "api_caller")
        success = queue.mark_done(item_id, holder_id)
        
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
        holder_id = data.get("holder_id", "api_caller")
        success = queue.mark_failed(item_id, holder_id, reason=reason, requeue=requeue)
        
        return jsonify({
            "status": "ok" if success else "failed",
            "marked_failed": success
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/queue/<int:item_id>")
def api_queue_item(item_id):
    """Get single queue item detail."""
    try:
        from core.tools.queue_tools import QueueStorage
        
        queue = QueueStorage()
        queue.initialize()
        item = queue.get_item(item_id)
        
        if not item:
            return jsonify({"error": "not found"}), 404
        return jsonify(item)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/queue/by-topic/<path:topic>")
def api_queue_by_topic(topic):
    """Get queue items by topic."""
    try:
        from core.tools.queue_tools import QueueStorage
        
        queue = QueueStorage()
        queue.initialize()
        items = queue.get_items_by_topic(topic)
        
        return jsonify({"topic": topic, "items": items})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


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


# =============================================================================
# Static File Serving for WebUI (v0.3.1)
# =============================================================================

@app.route("/ui/<path:filename>")
def serve_ui_file(filename):
    """Serve static files from ui/ directory."""
    return send_from_directory(UI_DIR, filename)


@app.route("/css/<path:filename>")
def serve_css_file(filename):
    """Serve CSS files from ui/css/ directory."""
    return send_from_directory(os.path.join(UI_DIR, "css"), filename)


@app.route("/js/<path:filename>")
def serve_js_file(filename):
    """Serve JS files from ui/js/ directory."""
    return send_from_directory(os.path.join(UI_DIR, "js"), filename)


@app.route("/views/<path:filename>")
def serve_views_file(filename):
    """Serve view HTML files from ui/views/ directory."""
    return send_from_directory(os.path.join(UI_DIR, "views"), filename)


# =============================================================================
# Traces API (v0.3.1)
# =============================================================================

_TRACES_DB_PATH = os.path.join(os.path.dirname(__file__), "knowledge", "traces.db")


def _get_traces_db():
    conn = sqlite3.connect(_TRACES_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/api/explorer/active")
def api_explorer_active():
    """Get active explorer traces."""
    try:
        conn = _get_traces_db()
        rows = conn.execute(
            "SELECT * FROM explorer_traces WHERE status = 'running' ORDER BY started_at DESC"
        ).fetchall()
        conn.close()
        return jsonify({"active_traces": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/explorer/recent")
def api_explorer_recent():
    """Get recent explorer traces."""
    try:
        limit = int(request.args.get("limit", 20))
        conn = _get_traces_db()
        rows = conn.execute(
            "SELECT * FROM explorer_traces WHERE status != 'running' ORDER BY started_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return jsonify({"traces": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/explorer/trace/<trace_id>")
def api_explorer_trace(trace_id):
    """Get single explorer trace with all steps."""
    try:
        conn = _get_traces_db()
        trace = conn.execute(
            "SELECT * FROM explorer_traces WHERE trace_id = ?", (trace_id,)
        ).fetchone()
        steps = conn.execute(
            "SELECT * FROM trace_steps WHERE trace_id = ? ORDER BY step_num ASC", (trace_id,)
        ).fetchall()
        conn.close()
        if not trace:
            return jsonify({"error": "not found"}), 404
        return jsonify({"trace": dict(trace), "steps": [dict(s) for s in steps]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dream/active")
def api_dream_active():
    """Get active dream trace."""
    try:
        conn = _get_traces_db()
        rows = conn.execute(
            "SELECT * FROM dream_traces WHERE status = 'running' ORDER BY started_at DESC LIMIT 1"
        ).fetchall()
        conn.close()
        return jsonify({"active": len(rows) > 0, "trace": dict(rows[0]) if rows else None})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dream/traces")
def api_dream_traces():
    """Get recent dream traces."""
    try:
        limit = int(request.args.get("limit", 20))
        conn = _get_traces_db()
        rows = conn.execute(
            "SELECT * FROM dream_traces ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return jsonify({"traces": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dream/trace/<trace_id>")
def api_dream_trace(trace_id):
    """Get single dream trace."""
    try:
        conn = _get_traces_db()
        trace = conn.execute(
            "SELECT * FROM dream_traces WHERE trace_id = ?", (trace_id,)
        ).fetchone()
        conn.close()
        if not trace:
            return jsonify({"error": "not found"}), 404
        return jsonify(dict(trace))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dream/stats")
def api_dream_stats():
    """Get dream statistics."""
    try:
        import glob
        insights_dir = os.path.join(os.path.dirname(__file__), "knowledge", "dream_insights")
        insight_files = glob.glob(os.path.join(insights_dir, "*.json"))
        insight_types = {}
        for f in insight_files:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                t = data.get("insight_type", "unknown")
                insight_types[t] = insight_types.get(t, 0) + 1

        conn = _get_traces_db()
        total = conn.execute("SELECT COUNT(*) FROM dream_traces").fetchone()[0]
        avg_l1 = conn.execute("SELECT AVG(l1_count) FROM dream_traces").fetchone()[0] or 0
        avg_l2 = conn.execute("SELECT AVG(l2_count) FROM dream_traces").fetchone()[0] or 0
        avg_l3 = conn.execute("SELECT AVG(l3_count) FROM dream_traces").fetchone()[0] or 0
        avg_l4 = conn.execute("SELECT AVG(l4_count) FROM dream_traces").fetchone()[0] or 0
        conn.close()

        return jsonify({
            "total_dreams": total,
            "total_insights": len(insight_files),
            "avg_l1_candidates": int(avg_l1),
            "avg_l2_scored": int(avg_l2),
            "avg_l3_filtered": int(avg_l3),
            "avg_l4_topics": int(avg_l4),
            "insight_by_type": insight_types,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Decomposition API (v0.3.1)
# =============================================================================

@app.route("/api/decomposition/tree/<path:root_topic>")
def api_decomposition_tree(root_topic):
    """Get decomposition tree from a root topic."""
    try:
        from core import knowledge_graph as kg
        
        state = kg.get_state()
        topics = state["knowledge"]["topics"]

        def _build_tree(topic, depth=0):
            if depth > 4 or topic not in topics:
                return None
            node = topics[topic]
            children = []
            for child in node.get("children", []):
                ct = _build_tree(child, depth + 1)
                if ct:
                    children.append(ct)
            return {
                "id": topic,
                "status": node.get("status", "unexplored"),
                "children": children,
            }

        tree = _build_tree(root_topic)
        return jsonify({"root": root_topic, "tree": tree})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/decomposition/stats")
def api_decomposition_stats():
    """Get decomposition statistics."""
    try:
        from core import knowledge_graph as kg
        
        state = kg.get_state()
        topics = state["knowledge"]["topics"]
        total_decomposed = 0
        by_depth = {}
        total_children = 0

        for name, node in topics.items():
            children = node.get("children", [])
            if children:
                total_decomposed += 1
                total_children += len(children)
                by_depth[str(len(children))] = by_depth.get(str(len(children)), 0) + 1

        return jsonify({
            "total_decomposed": total_decomposed,
            "by_depth": by_depth,
            "avg_children_per_topic": round(total_children / max(total_decomposed, 1), 1)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# System Health API (v0.3.1)
# =============================================================================

@app.route("/api/system/health")
def api_system_health():
    """Get system health status."""
    try:
        def _get_system_info():
            cpu_pct = 0.0
            mem_pct = 0.0
            mem_avail_mb = 0
            try:
                with open('/proc/stat') as f:
                    parts = f.readline().split()
                    idle = int(parts[4])
                    total = sum(int(p) for p in parts[1:])
                    cpu_pct = round((1 - idle / max(total, 1)) * 100, 1)
            except Exception:
                pass
            try:
                with open('/proc/meminfo') as f:
                    lines = f.readlines()
                    mem_total = int(lines[0].split()[1]) * 1024
                    mem_avail = int(lines[2].split()[1]) * 1024
                    mem_pct = round((1 - mem_avail / max(mem_total, 1)) * 100, 1)
                    mem_avail_mb = mem_avail // (1024 * 1024)
            except Exception:
                pass
            return {"cpu_percent": cpu_pct, "memory_percent": mem_pct, "memory_available_mb": mem_avail_mb}

        api_pid = os.getpid()
        uptime = 0
        try:
            uptime = int(time.time() - os.path.getmtime("/proc/%d/stat" % api_pid))
        except Exception:
            pass

        from core.tools.queue_tools import QueueStorage
        qs = QueueStorage()
        qs.initialize()
        queue_stats = qs.get_all_stats()

        from core import knowledge_graph as kg
        state = kg.get_state()
        topics = state["knowledge"]["topics"]

        recent_errors = []
        if os.path.exists(_audit_log_path):
            with open(_audit_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    if "← 5" in line or "error" in line.lower():
                        recent_errors.append(line.strip())
                recent_errors = recent_errors[-10:]

        sys_info = _get_system_info()
        return jsonify({
            "ca_api": {"status": "up", "uptime_seconds": uptime, "port": 4848},
            "system": sys_info,
            "queue": queue_stats,
            "kg": {
                "total_nodes": len(topics),
                "storage": "json",
            },
            "recent_errors": recent_errors,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Provider Heatmap API (v0.3.1)
# =============================================================================

@app.route("/api/providers/heatmap")
def api_providers_heatmap():
    """Get provider heatmap."""
    try:
        heatmap_path = os.path.join(os.path.dirname(__file__), "knowledge", "provider_heatmap.json")
        if os.path.exists(heatmap_path):
            with open(heatmap_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"heatmap": {}, "best_providers": {}, "updated_at": None}

        try:
            from core.search_quota import get_quota_manager
            cfg = get_config()
            quota = cfg.knowledge.get("search").daily_quota
            qm = get_quota_manager()
            serper = qm.get_status("serper", quota.serper, quota.enabled)
            bocha = qm.get_status("bocha", quota.bocha, quota.enabled)
            data["quota"] = {
                "bocha": {"used": bocha.used, "limit": bocha.limit, "remaining": bocha.remaining},
                "serper": {"used": serper.used, "limit": serper.limit, "remaining": serper.remaining},
            }
        except Exception:
            pass

        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/providers/record", methods=["POST"])
def api_providers_record():
    """Record provider verification result."""
    try:
        from core.provider_heatmap import get_heatmap
        
        data = request.get_json() or {}
        language = data.get("language", "")
        domain = data.get("domain", "")
        provider_results = data.get("provider_results", {})

        hm = get_heatmap()
        hm.record_verification(language, domain, provider_results)

        heatmap_path = os.path.join(os.path.dirname(__file__), "knowledge", "provider_heatmap.json")
        os.makedirs(os.path.dirname(heatmap_path), exist_ok=True)
        with open(heatmap_path, "w", encoding="utf-8") as f:
            json.dump({"heatmap": dict(hm._heatmap), "updated_at": datetime.now(timezone.utc).isoformat()}, f)

        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Timeline API (v0.3.1)
# =============================================================================

@app.route("/api/timeline")
def api_timeline():
    """Get global event timeline."""
    try:
        import glob
        limit = int(request.args.get("limit", 100))
        events = []

        try:
            conn = _get_audit_db()
            rows = conn.execute(
                "SELECT timestamp, hook_name, endpoint, status, latency_ms FROM hook_calls ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
            for r in rows:
                events.append({
                    "timestamp": r["timestamp"],
                    "type": "hook_call",
                    "emoji": "🔗",
                    "summary": f"{r['hook_name']} → {r['endpoint']} → {r['status']}",
                    "detail_url": "/api/audit/hooks",
                })
            conn.close()
        except Exception:
            pass

        try:
            conn = _get_traces_db()
            rows = conn.execute(
                "SELECT started_at, topic, status, total_steps, quality_score FROM explorer_traces ORDER BY started_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            for r in rows:
                emoji = "✅" if r["status"] == "done" else ("❌" if r["status"] == "failed" else "🔄")
                events.append({
                    "timestamp": r["started_at"],
                    "type": f"exploration_{r['status']}",
                    "emoji": emoji,
                    "summary": f"探索{'完成' if r['status'] == 'done' else '中'}: {r['topic']}, {r['total_steps']} steps",
                    "detail_url": "/api/explorer/trace/",
                })
            conn.close()
        except Exception:
            pass

        try:
            insights_dir = os.path.join(os.path.dirname(__file__), "knowledge", "dream_insights")
            for f in sorted(glob.glob(os.path.join(insights_dir, "*.json")), reverse=True)[:limit]:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    events.append({
                        "timestamp": data.get("created_at", ""),
                        "type": "insight",
                        "emoji": "💡",
                        "summary": f"洞察: {data.get('insight_type', '')} from {', '.join(data.get('source_topics', []))}",
                        "detail_url": "",
                    })
        except Exception:
            pass

        events.sort(key=lambda x: x["timestamp"], reverse=True)
        return jsonify({"events": events[:limit], "total": len(events)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =============================================================================
# External Agent API (v0.3.1)
# =============================================================================

_agent_registry = {
    "r1d3": {
        "agent_id": "r1d3",
        "agent_name": "R1D3 Researcher",
        "connected_at": "2026-04-15T22:00:00Z",
        "hooks_used": ["knowledge-query", "knowledge-learn", "knowledge-bootstrap", "knowledge-gate", "knowledge-inject"],
    }
}


@app.route("/api/agents")
def api_agents():
    """Get connected agents list."""
    try:
        conn = _get_audit_db()
        agents = []
        for agent_id, info in _agent_registry.items():
            row = conn.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as success,
                       AVG(latency_ms) as avg_latency
                FROM hook_calls WHERE agent_id = ?
            """, (agent_id,)).fetchone()

            last_seen = conn.execute(
                "SELECT MAX(timestamp) FROM hook_calls WHERE agent_id = ?", (agent_id,)
            ).fetchone()[0]

            agents.append({
                **info,
                "last_seen_at": last_seen,
                "total_calls": row["total"],
                "success_rate": row["success"] / max(row["total"], 1),
                "avg_latency_ms": int(row["avg_latency"] or 0),
            })
        conn.close()
        return jsonify({"agents": agents})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agents/<agent_id>")
def api_agent_detail(agent_id):
    """Get agent details with activity timeline."""
    try:
        info = _agent_registry.get(agent_id)
        if not info:
            return jsonify({"error": "not found"}), 404

        conn = _get_audit_db()
        rows = conn.execute("""
            SELECT timestamp, hook_name, endpoint, method, status,
                   latency_ms, request_raw_topic, status_code
            FROM hook_calls WHERE agent_id = ?
            ORDER BY timestamp DESC LIMIT 100
        """, (agent_id,)).fetchall()
        conn.close()

        return jsonify({
            **info,
            "activity_timeline": [dict(r) for r in rows]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    main()
