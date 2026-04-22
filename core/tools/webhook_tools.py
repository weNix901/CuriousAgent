"""Webhook tools for pushing discoveries to R1D3."""
import json
import logging
import time
from typing import Any

import requests

from core.tools.base import Tool

logger = logging.getLogger(__name__)


class PushWebhookTool(Tool):
    """Tool for pushing discovery webhook to R1D3."""

    @property
    def name(self) -> str:
        return "push_webhook"

    @property
    def description(self) -> str:
        return "Push discovery notification to R1D3 webhook for real-time sync"

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
            from core.config import get_ca_config

            config = get_ca_config()
            webhook_cfg = config.behavior.get("webhook", {})
            
            if not webhook_cfg.get("enabled", False):
                return json.dumps({"success": False, "error": "webhook disabled"})

            url = webhook_cfg.get("r1d3_url", "")
            timeout = webhook_cfg.get("timeout_seconds", 10)
            retry_count = webhook_cfg.get("retry_count", 3)
            retry_delay = webhook_cfg.get("retry_delay_seconds", 5)

            if not url:
                return json.dumps({"success": False, "error": "no webhook URL configured"})

            payload = {
                "topic": topic,
                "quality": quality,
                "completeness_score": completeness_score,
                "source_type": source_type,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }

            for attempt in range(retry_count):
                try:
                    resp = requests.post(
                        url,
                        json=payload,
                        timeout=timeout,
                        headers={"Content-Type": "application/json"}
                    )
                    if resp.status_code == 200:
                        logger.info(f"Webhook pushed successfully: {topic}")
                        return json.dumps({"success": True, "topic": topic, "status": resp.status_code})
                    else:
                        logger.warning(f"Webhook failed: {resp.status_code}, attempt {attempt + 1}")
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Webhook error: {e}, attempt {attempt + 1}")
                
                if attempt < retry_count - 1:
                    time.sleep(retry_delay)

            return json.dumps({"success": False, "error": "all retries failed"})

        except Exception as e:
            logger.error(f"Webhook tool error: {e}")
            return json.dumps({"success": False, "error": str(e)})


def push_discovery_webhook(topic: str, quality: float = 0.0, completeness_score: int = 0, source_type: str = "explore") -> bool:
    """Synchronous helper for pushing webhook."""
    tool = PushWebhookTool()
    result = tool.execute(topic=topic, quality=quality, completeness_score=completeness_score, source_type=source_type)
    try:
        data = json.loads(result)
        return data.get("success", False)
    except:
        return False