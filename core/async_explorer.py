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


def _get_instances():
    global _explorer_instance, _quality_assessor_instance
    if _explorer_instance is None:
        from core.explorer import Explorer
        from core.quality_v2 import QualityV2Assessor
        _explorer_instance = Explorer()
        _quality_assessor_instance = QualityV2Assessor()
    return _explorer_instance, _quality_assessor_instance


def _explore_in_thread(topic: str, score: float):
    """在线程中执行探索，完成后更新状态"""
    try:
        logger.info(f"[T-10] Async exploration started for {topic}")
        explorer, quality_assessor = _get_instances()
        result = explorer.explore(topic, depth="medium")

        from core.knowledge_graph import add_exploration_result, update_curiosity_status
        quality = quality_assessor.assess_quality(
            topic=topic,
            findings=result.get("findings", {}),
            knowledge_graph=None
        )
        add_exploration_result(topic, result, quality)
        update_curiosity_status(topic, "done")
        logger.info(f"[T-10] Async exploration completed for {topic}, quality={quality}")
    except Exception as e:
        logger.error(f"[T-10] Async exploration failed for {topic}: {e}")
        try:
            from core.knowledge_graph import update_curiosity_status
            update_curiosity_status(topic, "paused")
        except Exception:
            pass


def trigger_async_exploration(topic: str, score: Optional[float] = None):
    """
    T-10: 立即触发异步探索
    
    在独立线程中执行，不阻塞 API 响应。
    被 curious_api.py 的 api_inject() 调用（集成点 6）。
    """
    thread = threading.Thread(
        target=_explore_in_thread,
        args=(topic, score),
        daemon=True,
        name=f"async-explorer-{topic[:30]}"
    )
    thread.start()
    logger.info(f"[T-10] Triggered async exploration thread for {topic}")
