"""
API 层迁移 - 重构 api_inject 和关键端点
"""

from flask import Flask, request, jsonify
from core.repositories import LineageInfo
from core.repositories.queue_repository import Actor


def register_v2_routes(app: Flask, queue_service, state_machine):
    """注册 v2 API 路由"""
    
    @app.route("/api/v2/curious/inject", methods=["POST"])
    def api_v2_inject():
        """v2 版本的 inject API"""
        try:
            data = request.get_json()
            
            if not data or "topic" not in data:
                return jsonify({"error": "Missing topic"}), 400
            
            topic = data["topic"]
            parent = data.get("parent")
            source = data.get("source", "api")
            reason = data.get("reason", "API injection")
            score = data.get("score", 5.0)
            depth = data.get("depth", 5.0)
            
            # 创建 lineage
            lineage = LineageInfo(
                parent_topic=parent,
                injected_by=source,
                original_reason=reason,
                exploration_path=[parent] if parent else [],
            )
            
            # 入队
            item = queue_service.enqueue(
                topic=topic,
                lineage=lineage,
                score=score,
                depth=depth,
                actor=Actor.SYSTEM,
                reason=reason,
            )
            
            return jsonify({
                "id": item.id,
                "topic": item.topic,
                "status": item.status.value,
                "lineage": item.lineage.to_dict(),
            }), 201
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @app.route("/api/v2/curious/queue/stats", methods=["GET"])
    def api_v2_queue_stats():
        """队列统计"""
        try:
            stats = queue_service.get_stats()
            return jsonify(stats), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @app.route("/api/v2/curious/queue/claim", methods=["POST"])
    def api_v2_claim():
        """手动 claim 任务（调试用）"""
        try:
            data = request.get_json() or {}
            agent_id = data.get("agent_id", "manual")
            
            item = queue_service.claim_next(agent_id=agent_id)
            
            if item:
                return jsonify({
                    "id": item.id,
                    "topic": item.topic,
                    "status": item.status.value,
                }), 200
            else:
                return jsonify({"message": "No items available"}), 404
                
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @app.route("/api/v2/state/<topic>", methods=["GET"])
    def api_v2_get_state(topic: str):
        """获取话题状态"""
        try:
            state_info = state_machine.get_state(topic)
            
            if state_info:
                return jsonify({
                    "topic": state_info.topic,
                    "state": state_info.state,
                    "history": [h.to_dict() for h in state_info.history],
                }), 200
            else:
                return jsonify({"message": "Topic not found"}), 404
                
        except Exception as e:
            return jsonify({"error": str(e)}), 500


def create_compat_inject(queue_service, old_impl=None):
    """创建兼容版本的 inject 函数"""
    
    def api_inject_v2_compat():
        """兼容旧代码的 inject"""
        from flask import request, jsonify
        
        try:
            data = request.get_json()
            
            if not data or "topic" not in data:
                return jsonify({"error": "Missing topic"}), 400
            
            # 提取参数
            topic = data["topic"]
            parent = data.get("parent")
            source = data.get("source", "api")
            reason = data.get("reason", "API injection")
            score = data.get("score", 5.0)
            depth = data.get("depth", 5.0)
            
            # 创建 lineage
            lineage = LineageInfo(
                parent_topic=parent,
                injected_by=source,
                original_reason=reason,
                exploration_path=[parent] if parent else [],
            )
            
            # 入队
            item = queue_service.enqueue(
                topic=topic,
                lineage=lineage,
                score=score,
                depth=depth,
                actor=Actor.SYSTEM,
                reason=reason,
            )
            
            # 返回兼容格式
            return jsonify({
                "success": True,
                "topic": item.topic,
                "status": item.status.value,
                "id": item.id,
            }), 201
            
        except Exception as e:
            # 如果新实现失败，尝试旧实现
            if old_impl:
                return old_impl()
            return jsonify({"error": str(e)}), 500
    
    return api_inject_v2_compat
