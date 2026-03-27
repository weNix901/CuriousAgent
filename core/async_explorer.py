"""
async_explorer.py - T-10: 异步探索器

inject 优先触发时不阻塞 API 响应，在独立线程中执行探索。
"""

import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_explorer_instance = None
_quality_assessor_instance = None
_cached_depth = None


def _get_instances(depth: float = 6.0):
    global _explorer_instance, _quality_assessor_instance, _cached_depth
    depth_map = {3.0: "shallow", 6.0: "medium", 9.0: "deep"}
    depth_str = depth_map.get(depth, "medium")
    if _explorer_instance is None or _cached_depth != depth_str:
        from core.explorer import Explorer
        from core.llm_client import LLMClient
        from core.quality_v2 import QualityV2Assessor
        llm = LLMClient()
        _explorer_instance = Explorer(exploration_depth=depth_str)
        _quality_assessor_instance = QualityV2Assessor(llm)
        _cached_depth = depth_str
    return _explorer_instance, _quality_assessor_instance


def _explore_in_thread(topic: str, score: float, depth: float):
    """在线程中执行探索，完成后更新状态"""
    try:
        logger.info(f"[T-10] Async exploration started for {topic} (depth={depth})")
        explorer, quality_assessor = _get_instances(depth)
        curiosity_item = {
            "topic": topic,
            "score": score,
            "depth": depth,
            "status": "pending",
            "reason": "async_r1d3_injection"
        }
        result = explorer.explore(curiosity_item)

        from core.knowledge_graph import add_exploration_result, update_curiosity_status
        # Explorer.explore() returns findings as a string (summary text)
        # QualityV2 expects a dict, wrap appropriately
        findings_str = result.get("findings", "") or ""
        findings_dict = {"summary": findings_str, "sources": result.get("sources", [])}
        quality = quality_assessor.assess_quality(
            topic=topic,
            findings=findings_dict,
            knowledge_graph=None
        )
        add_exploration_result(topic, result, quality)
        update_curiosity_status(topic, "done")
        logger.info(f"[T-10] Async exploration completed for {topic}, quality={quality}")
    except Exception as e:
        import traceback
        logger.error(f"[T-10] Async exploration failed for {topic}: {e}")
        logger.error(f"[T-10] Traceback: {traceback.format_exc()}")
        try:
            from core.knowledge_graph import update_curiosity_status
            update_curiosity_status(topic, "paused")
        except Exception:
            pass


def trigger_async_exploration(topic: str, score: Optional[float] = None, depth: float = 6.0):
    """
    T-10: 立即触发异步探索
    
    在独立线程中执行，不阻塞 API 响应。
    被 curious_api.py 的 api_inject() 调用（集成点 6）。
    """
    thread = threading.Thread(
        target=_explore_in_thread,
        args=(topic, score, depth),
        daemon=True,
        name=f"async-explorer-{topic[:30]}"
    )
    thread.start()
    logger.info(f"[T-10] Triggered async exploration thread for {topic}")
