"""
async_explorer.py - T-10: 异步探索器

inject 优先触发时不阻塞 API 响应，在独立线程中执行探索。
"""

import logging
import threading
from typing import Optional

from core.embedding_service import EmbeddingService
from core.assertion_index import AssertionIndex
from core import knowledge_graph_compat as kg_module

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
        from core.config import EmbeddingConfig
        embedding_config = EmbeddingConfig()
        embedding_service = EmbeddingService(embedding_config)
        assertion_index = AssertionIndex()
        _explorer_instance = Explorer(exploration_depth=depth_str)
        _quality_assessor_instance = QualityV2Assessor(
            llm,
            embedding_service=embedding_service,
            assertion_index=assertion_index,
            knowledge_graph=kg_module
        )
        _cached_depth = depth_str
    return _explorer_instance, _quality_assessor_instance


def _explore_in_thread(topic: str, score: float, depth: float):
    """在线程中执行探索，完成后更新状态"""
    # === Phase 3: async 路径也要正确更新队列 status ===
    from core.knowledge_graph_compat import update_curiosity_status
    try:
        update_curiosity_status(topic, "exploring")
    except Exception as e:
        logger.warning(f"Failed to update status for '{topic}': {e}", exc_info=True)
    # === Phase 3 结束 ===

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

        from core.knowledge_graph_compat import add_exploration_result, update_curiosity_status
        from core import knowledge_graph_compat as kg_module
        # Explorer.explore() returns findings as a string (summary text)
        # QualityV2 expects a dict, wrap appropriately
        findings_str = result.get("findings", "") or ""
        findings_dict = {"summary": findings_str, "sources": result.get("sources", [])}
        quality = quality_assessor.assess_quality(
            topic=topic,
            findings=findings_dict,
            knowledge_graph=kg_module  # G4-Fix: 传入 kg_module 实例，不是 None
        )
        add_exploration_result(topic, result, quality)
        # ===== Decomposition（与 curious_agent.py run_one_cycle 同步） =====
        try:
            from core.curiosity_decomposer import CuriosityDecomposer
            from core.llm_manager import LLMManager
            from core.provider_registry import init_default_providers
            from core import knowledge_graph_compat as kg_module
            from core.config import get_config

            config = get_config()
            llm_config_async = {"providers": {}, "selection_strategy": "capability"}
            for p in config.llm.get("providers", []):
                llm_config_async["providers"][p.name] = {
                    "api_url": p.api_url,
                    "timeout": p.timeout,
                    "enabled": p.enabled,
                    "models": [
                        {"model": m.model, "weight": m.weight, "capabilities": m.capabilities, "max_tokens": m.max_tokens}
                        for m in p.models
                    ]
                }
            llm_manager_async = LLMManager.get_instance(llm_config_async)
            registry_async = init_default_providers()
            state_async = kg_module.get_state()

            decomposer_async = CuriosityDecomposer(
                llm_client=llm_manager_async,
                provider_registry=registry_async,
                kg=state_async
            )

            import asyncio
            subtopics_async = asyncio.run(decomposer_async.decompose(topic))

            if subtopics_async:
                subtopics_sorted_async = sorted(
                    subtopics_async,
                    key=lambda x: (x.get("signal_strength") != "strong", -x.get("total_count", 0))
                )
                best_async = subtopics_sorted_async[0]
                explore_topic_async = best_async["sub_topic"]
                kg_module.add_child(topic, explore_topic_async)

                for sibling in subtopics_sorted_async[1:]:
                    s_topic_async = sibling["sub_topic"]
                    s_strength_async = sibling.get("signal_strength", "unknown")
                    s_relevance_async = 7.0 if s_strength_async == "strong" else (6.0 if s_strength_async == "medium" else 5.0)
                    s_depth_async = 6.0 if s_strength_async == "strong" else (5.5 if s_strength_async == "medium" else 5.0)
                    kg_module.add_child(topic, s_topic_async)
                    kg_module.add_curiosity(
                        topic=s_topic_async,
                        reason=f"Sibling of: {topic}",
                        relevance=float(s_relevance_async),
                        depth=float(s_depth_async),
                        original_topic=topic
                    )
                logger.info(f"[T-10] Decomposed '{topic}' into {len(subtopics_async)} subtopics")
            else:
                logger.info(f"[T-10] No subtopics for '{topic}'")

        except Exception as e_decomp:
            logger.error(f"[T-10] Decomposition failed for '{topic}': {e_decomp}")
        # ===== Decomposition 结束 =====

        update_curiosity_status(topic, "done")
        logger.info(f"[T-10] Async exploration completed for {topic}, quality={quality}")
    except Exception as e:
        import traceback
        logger.error(f"[T-10] Async exploration failed for {topic}: {e}")
        logger.error(f"[T-10] Traceback: {traceback.format_exc()}")
        try:
            from core.knowledge_graph_compat import update_curiosity_status
            update_curiosity_status(topic, "paused")
        except Exception as e:
            logger.warning(f"Failed to set paused status for '{topic}': {e}", exc_info=True)
    finally:
        # v0.2.6 fix: remove self from active threads tracker
        import threading as t
        current = t.current_thread()
        with _active_threads_lock:
            if current in _active_threads:
                _active_threads.remove(current)


# Global thread tracker for graceful shutdown
_active_threads: list = []
_active_threads_lock = threading.Lock()


def trigger_async_exploration(topic: str, score: Optional[float] = None, depth: float = 6.0):
    """
    T-10: 立即触发异步探索
    
    在独立线程中执行，不阻塞 API 响应。
    被 curious_api.py 的 api_inject() 调用（集成点 6）。
    
    修复 (v0.2.6): 使用 non-daemon 线程 + SIGTERM 时等待完成。
    """
    thread = threading.Thread(
        target=_explore_in_thread,
        args=(topic, score, depth),
        daemon=False,  # v0.2.6 fix: non-daemon so SIGTERM handler can join()
        name=f"async-explorer-{topic[:30]}"
    )
    with _active_threads_lock:
        _active_threads.append(thread)
    thread.start()
    logger.info(f"[T-10] Triggered async exploration thread for {topic}")


def wait_for_active_threads(timeout: float = 30.0) -> int:
    """
    v0.2.6: 等待所有活跃探索线程完成。
    被 curious_api.py 的 SIGTERM handler 调用。
    返回等待完成的线程数。
    """
    with _active_threads_lock:
        threads = list(_active_threads)
    
    waited = 0
    for t in threads:
        remaining = timeout - waited
        if remaining <= 0:
            break
        t.join(timeout=remaining)
        waited += 1
    
    with _active_threads_lock:
        _active_threads.clear()
    
    return waited
