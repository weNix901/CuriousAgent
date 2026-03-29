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
        # ===== Decomposition（与 curious_agent.py run_one_cycle 同步） =====
        try:
            from core.curiosity_decomposer import CuriosityDecomposer
            from core.llm_manager import LLMManager
            from core.provider_registry import init_default_providers
            from core import knowledge_graph as kg_module
            from core.config import get_config

            config = get_config()
            llm_config_async = {"providers": {}, "selection_strategy": "capability"}
            for p in config.llm_providers:
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
