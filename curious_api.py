#!/usr/bin/env python3
"""
curious_api.py — Curious Agent REST API 服务器 (Flask)

提供:
  GET  /api/curious/state       → 完整状态
  POST /api/curious/run         → 运行一轮探索
  POST /api/curious/inject      → 注入好奇心
  GET  /                        → Web 界面

启动:
  python3 curious_api.py
  python3 curious_api.py --port 4848
"""
import argparse
import os
import sys
import threading
import time
import webbrowser

from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder=None)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(SCRIPT_DIR, "knowledge", "state.json")
UI_DIR = os.path.join(SCRIPT_DIR, "ui")
sys.path.insert(0, SCRIPT_DIR)


# ── State helpers ──────────────────────────────────────────────

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"knowledge": {"topics": {}}, "curiosity_queue": [],
                "exploration_log": [], "last_update": None}
    try:
        import json
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"knowledge": {"topics": {}}, "curiosity_queue": [],
                "exploration_log": [], "last_update": None}


# ── Routes ────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(UI_DIR, "index.html")

@app.route("/ui/<path:filename>")
def ui_static(filename):
    return send_from_directory(UI_DIR, filename)

@app.route("/api/curious/state")
def api_state():
    return jsonify(load_state())

@app.route("/api/curious/run", methods=["POST"])
def api_run():
    try:
        from core.curiosity_engine import CuriosityEngine
        from core.explorer import Explorer

        engine = CuriosityEngine()
        explorer = Explorer()
        engine.generate_initial_curiosities()
        engine.rescore_all()
        next_item = engine.select_next()

        if not next_item:
            return jsonify({"status": "idle", "message": "好奇心队列为空"})

        result = explorer.explore(next_item)
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

        from core.knowledge_graph import add_curiosity
        add_curiosity(
            topic=topic,
            reason=str(data.get("reason", "Web UI 注入")),
            relevance=float(data.get("relevance", 7.0)),
            depth=float(data.get("depth", 6.0))
        )
        return jsonify({"status": "ok", "topic": topic})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ── Main ──────────────────────────────────────────────────────

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

    # threaded=True for concurrent request handling
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
