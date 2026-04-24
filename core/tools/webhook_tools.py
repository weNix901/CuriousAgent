"""Webhook tools for pushing discoveries to R1D3 via OpenClaw hooks."""
import json
import logging
import time
from typing import Any

import requests

from core.tools.base import Tool

logger = logging.getLogger(__name__)


class PushWebhookTool(Tool):
    """Tool for pushing discovery webhook to R1D3 via OpenClaw hooks."""

    @property
    def name(self) -> str:
        return "push_webhook"

    @property
    def description(self) -> str:
        return "Push discovery notification to R1D3 via OpenClaw /hooks/wake or /hooks/agent"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic name that was discovered"
                },
                "quality": {
                    "type": "number",
                    "description": "Quality score of the discovery"
                },
                "completeness_score": {
                    "type": "integer",
                    "description": "Completeness score (1-6)"
                },
                "source_type": {
                    "type": "string",
                    "description": "Source type: explore, deep_read, dream"
                }
            },
            "required": ["topic"]
        }

    async def execute(self, **kwargs: Any) -> str:
        topic = kwargs.get("topic", "")
        quality = kwargs.get("quality", 0.0)
        completeness_score = kwargs.get("completeness_score", 0)
        source_type = kwargs.get("source_type", "explore")

        if not topic:
            return json.dumps({"success": False, "error": "topic required"})

        try:
            from core.config import get_config

            config = get_config()
            webhook_cfg = config.behavior.get("webhook")
            notification_cfg = config.behavior.get("notification")
            
            if not webhook_cfg or not webhook_cfg.enabled:
                return json.dumps({"success": False, "error": "webhook disabled"})

            host = webhook_cfg.openclaw_host
            token = webhook_cfg.token
            timeout = webhook_cfg.timeout_seconds
            retry_count = webhook_cfg.retry_count
            retry_delay = webhook_cfg.retry_delay_seconds

            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"

            results = []

            # Always call /hooks/wake to notify R1D3 of new knowledge
            wake_url = f"{host}/hooks/wake"
            wake_payload = {
                "text": f"CA 探索完成：{topic} (quality={quality:.1f}, source={source_type})",
                "mode": "now"
            }
            wake_result = self._post_with_retry(wake_url, wake_payload, headers, timeout, retry_count, retry_delay)
            results.append({"endpoint": "wake", "success": wake_result})

            # Conditionally call /hooks/agent to push notification to user
            notification_enabled = notification_cfg.enabled if notification_cfg else False
            min_quality = notification_cfg.min_quality if notification_cfg else 7.0
            
            if notification_enabled and quality >= min_quality:
                agent_url = f"{host}/hooks/agent"
                agent_payload = {
                    "message": f"CA 发现了新知识「{topic}」，质量评分 {quality:.1f}",
                    "name": "researcher",
                    "deliver": "channel:feishu"
                }
                agent_result = self._post_with_retry(agent_url, agent_payload, headers, timeout, retry_count, retry_delay)
                results.append({"endpoint": "agent", "success": agent_result})

            success = any(r["success"] for r in results)
            return json.dumps({"success": success, "topic": topic, "results": results})

        except Exception as e:
            logger.error(f"Webhook tool error: {e}")
            return json.dumps({"success": False, "error": str(e)})

    def _post_with_retry(self, url: str, payload: dict, headers: dict, timeout: int, retry_count: int, retry_delay: int) -> bool:
        for attempt in range(retry_count):
            try:
                resp = requests.post(url, json=payload, timeout=timeout, headers=headers)
                if resp.status_code == 200:
                    logger.info(f"Webhook {url} success: {payload.get('text', payload.get('message', ''))[:50]}")
                    return True
                else:
                    logger.warning(f"Webhook {url} failed: {resp.status_code}, attempt {attempt + 1}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Webhook {url} error: {e}, attempt {attempt + 1}")
            
            if attempt < retry_count - 1:
                time.sleep(retry_delay)
        
        return False


def push_discovery_webhook(topic: str, quality: float = 0.0, completeness_score: int = 0, source_type: str = "explore") -> bool:
    """Synchronous helper for pushing webhook."""
    import asyncio
    tool = PushWebhookTool()
    result = asyncio.run(tool.execute(topic=topic, quality=quality, completeness_score=completeness_score, source_type=source_type))
    try:
        data = json.loads(result)
        return data.get("success", False)
    except:
        return False