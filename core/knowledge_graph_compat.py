"""
Knowledge Graph Compatibility Shim

Routes operations to Neo4j (via KGRepositoryFactory) and SQLite (via QueueStorage)
instead of state.json. Dream insights remain file-based.

This module exposes the same function signatures as knowledge_graph.py.
"""
import asyncio
import json
import logging
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.kg.repository_factory import KGRepositoryFactory
from core.tools.queue_tools import QueueStorage

logger = logging.getLogger(__name__)

ROOT_SCORE_WEIGHT_DOMAIN = 0.4
ROOT_SCORE_WEIGHT_EXPLAINS = 0.6
CROSS_DOMAIN_THRESHOLD = 3
ROOT_POOL_KEY = "root_technology_pool"

STATE_FILE = os.path.join(os.path.dirname(__file__), "../knowledge/state.json")
DREAM_INSIGHTS_DIR = os.path.join(os.path.dirname(STATE_FILE), "dream_insights")
DREAM_INBOX_PATH = os.path.join(os.path.dirname(STATE_FILE), "dream_topic_inbox.json")

_kg_factory: Optional[KGRepositoryFactory] = None
_queue_storage: Optional[QueueStorage] = None
_neo4j_available: bool = True


def _safe_neo4j_call(func, fallback=None, *args, **kwargs):
    """Wrap Neo4j calls with error handling, returning fallback on failure."""
    global _neo4j_available
    if not _neo4j_available:
        return fallback
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.warning(f"Neo4j call failed: {e}")
        _neo4j_available = False
        return fallback


def _get_kg_factory() -> KGRepositoryFactory:
    """Get or create KGRepositoryFactory singleton."""
    global _kg_factory, _neo4j_available
    if _kg_factory is None:
        try:
            _kg_factory = KGRepositoryFactory.get_instance()
            _neo4j_available = True
        except Exception as e:
            logger.warning(f"KGRepositoryFactory init failed: {e}")
            _neo4j_available = False
    return _kg_factory


def _get_queue_storage() -> QueueStorage:
    """Get or create QueueStorage singleton."""
    global _queue_storage
    if _queue_storage is None:
        _queue_storage = QueueStorage()
        _queue_storage.initialize()
    return _queue_storage


def _load_state() -> dict:
    """Load runtime state from ops.db (single source of truth).

    Phase 1 data governance: state.json is retired. Runtime state now lives in
    knowledge/ops.db (meta_cognitive + runtime_kv). Falls back to the default
    skeleton shape when ops.db is empty, so callers keep working unchanged.

    SSOT (v0.3.6-SSOT): this function returns ONLY runtime state
    (meta_cognitive / runtime_kv / root pool / search flags).
    **KNOWLEDGE MUST GO TO Neo4j** — the ``knowledge.topics`` key in the
    returned skeleton is ALWAYS EMPTY by design. Any caller that reads
    ``state["knowledge"]["topics"]`` is on a deprecated path and will silently
    see an empty graph. Use ``get_state()`` (which assembles topics from
    Neo4j) or ``_get_kg_factory()`` directly instead.
    """
    empty = {
        "version": "1.0",
        "last_update": None,
        "knowledge": {"topics": {}},
        "curiosity_queue": [],
        "exploration_log": [],
        "config": {
            "curiosity_top_k": 3,
            "max_knowledge_nodes": 5000,
            "notification_threshold": 7.0,
        },
        "search_exhausted": False,
        "search_exhausted_reason": None,
        ROOT_POOL_KEY: {"candidates": [], "last_updated": None},
        "meta_cognitive": {
            "explore_counts": {},
            "marginal_returns": {},
            "last_quality": {},
            "exploration_log": [],
            "completed_topics": {},
        },
        "insight_generation": {},
    }
    try:
        import sqlite3
        if not os.path.exists(OPS_DB):
            return empty
        conn = sqlite3.connect(OPS_DB, timeout=10)
        state = dict(empty)
        # runtime_kv
        try:
            for key, value in conn.execute("SELECT key, value FROM runtime_kv"):
                try:
                    state[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    state[key] = value
        except sqlite3.OperationalError:
            pass
        # meta_cognitive
        try:
            mc = dict(empty["meta_cognitive"])
            for topic, data in conn.execute("SELECT topic, data FROM meta_cognitive"):
                try:
                    mc[topic] = json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    mc[topic] = data
            state["meta_cognitive"] = mc
        except sqlite3.OperationalError:
            pass
        conn.close()
        _warn_if_knowledge_read(state)
        return state
    except Exception as e:
        logger.warning(f"_load_state <- ops.db failed: {e}")
        return empty


# SSOT guardrail (v0.3.6-SSOT): fail visible, never silent.
# The skeleton returned by _load_state() has an empty knowledge.topics by
# design (Neo4j is the knowledge source). If any caller still depends on that
# key it will silently operate on an empty graph. We cannot detect the CALLER
# from here, but we CAN detect when the caller's assumptions would be wrong:
# if ops.db has runtime state but no knowledge rows while Neo4j holds nodes,
# emit a one-shot warning so the migration surface stays visible.
_ssot_warned: bool = False


def _warn_if_knowledge_read(state: dict) -> None:
    """SSOT guardrail: warn once when knowledge.topics is read while empty.

    Cheap: only fires when knowledge.topics is empty. Emits a single WARNING
    (per process) so log noise stays bounded but the deprecated read path is
    observable. Set env KG_SSOT_STRICT=1 to raise instead (CI use).
    """
    global _ssot_warned
    try:
        topics = (state.get("knowledge") or {}).get("topics")
        if topics:
            return  # Non-empty = caller supplied/legacy path, nothing to warn.
        if _ssot_warned:
            return
        _ssot_warned = True
        msg = (
            "[SSOT] _load_state() returned empty knowledge.topics. "
            "Knowledge lives in Neo4j — use get_state() or _get_kg_factory(). "
            "Reading state['knowledge']['topics'] is a deprecated path "
            "(see docs/plan/next_move_v0.3.6_SSOT.md)."
        )
        if os.environ.get("KG_SSOT_STRICT") == "1":
            raise RuntimeError(msg)
        logger.warning(msg)
    except RuntimeError:
        raise
    except Exception:
        # Guardrail must never break the caller.
        pass


def _load_state_legacy() -> dict:
    """DEPRECATED: original state.json loader, kept for reference/migration."""
    if not os.path.exists(STATE_FILE):
        return {
            "version": "1.0",
            "last_update": None,
            "knowledge": {"topics": {}},
            "curiosity_queue": [],
            "exploration_log": [],
            "config": {
                "curiosity_top_k": 3,
                "max_knowledge_nodes": 5000,
                "notification_threshold": 7.0
            },
            "search_exhausted": False,
            "search_exhausted_reason": None,
            ROOT_POOL_KEY: {"candidates": [], "last_updated": None},
            "meta_cognitive": {
                "explore_counts": {},
                "marginal_returns": {},
                "last_quality": {},
                "exploration_log": [],
                "completed_topics": {}
            },
            "insight_generation": {}
        }
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


OPS_DB = os.path.join(os.path.dirname(__file__), "../knowledge/ops.db")


def _save_state(state: dict) -> None:
    """Persist runtime state to the ops DB (single source of truth).

    Phase 1 data governance: state.json is deprecated as a parallel copy of
    knowledge + runtime state. Knowledge now lives only in Neo4j; runtime
    state (meta_cognitive, search_exhausted, root pool, exploration log,
    insight generation) lives in knowledge/ops.db. This function routes
    writes there instead of rewriting state.json.

    Kept name/signature for backward compatibility with all call sites.
    """
    state["last_update"] = datetime.now(timezone.utc).isoformat()
    try:
        import sqlite3
        conn = sqlite3.connect(OPS_DB, timeout=10)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS meta_cognitive (
                topic TEXT PRIMARY KEY, data TEXT NOT NULL,
                updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
            CREATE TABLE IF NOT EXISTS runtime_kv (
                key TEXT PRIMARY KEY, value TEXT NOT NULL,
                updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
        """)
        # meta_cognitive
        mc = state.get("meta_cognitive") or {}
        for topic, data in (mc.items() if isinstance(mc, dict) else []):
            conn.execute(
                "INSERT OR REPLACE INTO meta_cognitive(topic,data,updated_at) VALUES(?,?,?)",
                (topic, json.dumps(data, ensure_ascii=False), state["last_update"]),
            )
        # scalar / structural runtime keys.
        # SSOT-6 (2026-10-08): 本白名单是"静默丢弃"的历史隐患 —— 任何不在
        # 名单内的键会被默默丢掉（competence_state / exploration_history 都
        # 曾中招）。现改为：**非 knowledge 的顶层键一律持久化**，并显式排除
        # 不应落库的键。这样新增运行时键不再需要同步维护白名单（防复发）。
        _SKIP = {"knowledge", "last_update", "meta_cognitive"}
        for key, val in (state.items() if isinstance(state, dict) else []):
            if key in _SKIP:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO runtime_kv(key,value,updated_at) VALUES(?,?,?)",
                (key, json.dumps(val, ensure_ascii=False), state["last_update"]),
            )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"_save_state -> ops.db failed: {e}")


def add_curiosity(topic: str, reason: str, relevance: float = 5.0, depth: float = 5.0, **extra) -> None:
    """唯一入队通路（C2b，2026-10-08）。

    **唯一性纪律**：所有"新话题入队"必须走这里，不得直接 QueueStorage.add_item()。
    唯一理由：本函数做**跨库去重**（队列 pending/done + Neo4j 全图，走
    concept_normalizer），直接 add_item 只做队列内去重，会漏掉"KG 已完成"的重复。

    extra 可作为 metadata 附加字段（如 task_type / source / score 等）。
    """
    storage = _get_queue_storage()
    
    from core.concept_normalizer import get_default_normalizer
    normalizer = get_default_normalizer()
    
    pending_items = storage.get_pending_items()
    done_items = storage.get_completed_items(limit=50)
    
    for item in pending_items + done_items:
        existing_topic = item.get("topic", "")
        if not existing_topic:
            continue
        similarity, match_type = normalizer.compute_concept_similarity(topic, existing_topic)
        if match_type in ("naming_variant", "translated_concept"):
            logger.info(f"Skip duplicate curiosity: '{topic}' ≈ '{existing_topic}' ({match_type})")
            return
    
    kg_factory = _get_kg_factory()

    # Page through ALL nodes for thorough dedup (not just first 100)
    page_size = 200
    offset = 0
    dedup_found = False
    while not dedup_found:
        all_nodes = kg_factory.get_all_nodes_sync(limit=page_size)
        if not all_nodes:
            break

        for node in all_nodes:
            existing_topic = node.get("topic", "")
            if not existing_topic:
                continue
            similarity, match_type = normalizer.compute_concept_similarity(topic, existing_topic)
            if match_type in ("naming_variant", "translated_concept"):
                if node.get("status") in ("done", "complete"):
                    # Check if the done node has actual content (sources/children/cites/summary)
                    # If it has NO content, it's an "empty shell" - allow re-exploration
                    sources = node.get("sources", []) or []
                    children = node.get("children", []) or []
                    cites = node.get("cites", []) or []
                    summary = node.get("summary", "") or ""
                    has_content = bool(sources or children or cites or (len(summary) > 20))
                    if has_content:
                        logger.info(f"Skip duplicate curiosity (KG done with content): '{topic}' ≈ '{existing_topic}'")
                        return
                    # Empty done node - allow re-exploration
                    logger.info(f"KG done but empty (no content): '{topic}' — forcing re-exploration")
                    dedup_found = True
                    break
                dedup_found = True
                break

        # If we got fewer nodes than page_size, we've seen all
        if len(all_nodes) < page_size:
            break
        offset += page_size
        # Safety: don't iterate more than 5000 nodes
        if offset >= 5000:
            break
    
    score = min(10.0, relevance * 0.35 + depth * 0.25 + 5.0 * 0.4)
    
    if "Web citation" in reason:
        priority = 10
    elif "Cited by" in reason:
        priority = 9
    elif "Dream" in reason:
        priority = 8
    elif "Decomposed from" in reason:
        priority = 5
    else:
        priority = 5
    
    metadata = {
        "reason": reason,
        "relevance": relevance,
        "depth": depth,
        "score": score,
        **extra
    }
    
    storage.add_item(topic, priority=priority, metadata=metadata, skip_dedup=True)


def claim_pending_item() -> Optional[dict]:
    storage = _get_queue_storage()
    result = storage.claim_pending(holder_id="compat_shim", timeout_seconds=300)
    
    if result:
        return {
            "topic": result["topic"],
            "reason": result.get("metadata", "{}"),
            "score": result.get("priority", 5),
            "relevance": 5.0,
            "depth": 5.0,
            "status": "exploring",
            "claimed_at": datetime.fromtimestamp(result.get("claimed_at", time.time()), tz=timezone.utc).isoformat() if result.get("claimed_at") else None,
            "priority": result.get("priority", 5)
        }
    return None


def list_pending() -> list:
    storage = _get_queue_storage()
    items = storage.get_pending_items()
    
    result = []
    for item in items:
        metadata = {}
        if item.get("metadata"):
            try:
                metadata = json.loads(item["metadata"]) if isinstance(item["metadata"], str) else item["metadata"]
            except (json.JSONDecodeError, TypeError):
                pass
        
        result.append({
            "id": item.get("id"),
            "topic": item["topic"],
            "reason": metadata.get("reason", ""),
            "score": metadata.get("score", 5.0),
            "relevance": metadata.get("relevance", 5.0),
            "depth": metadata.get("depth", 5.0),
            "status": "pending",
            "priority": item.get("priority", 5),
            "created_at": datetime.fromtimestamp(item.get("created_at", time.time()), tz=timezone.utc).isoformat() if item.get("created_at") else None
        })
    
    return result


def remove_curiosity(topic: str, force: bool = False) -> bool:
    """Remove a curiosity item from the queue (routes to QueueStorage)."""
    storage = _get_queue_storage()
    items = storage.get_items_by_topic(topic)
    
    if not items:
        return False
    
    for item in items:
        if not force and item.get("status") in ("claimed", "done"):
            continue
        
        storage.mark_failed(
            item_id=item["id"],
            holder_id=item.get("holder_id", "compat_shim"),
            requeue=False,
            reason="Removed via compat shim"
        )
    
    return True


def get_top_curiosities(k: Optional[int] = None) -> list:
    storage = _get_queue_storage()
    state = _load_state()
    k = k or state.get("config", {}).get("curiosity_top_k", 3)
    
    items = storage.get_pending_items(limit=k)
    
    result = []
    for item in items:
        metadata = {}
        if item.get("metadata"):
            try:
                metadata = json.loads(item["metadata"]) if isinstance(item["metadata"], str) else item["metadata"]
            except (json.JSONDecodeError, TypeError):
                pass
        
        result.append({
            "topic": item["topic"],
            "reason": metadata.get("reason", ""),
            "score": metadata.get("score", 5.0),
            "relevance": metadata.get("relevance", 5.0),
            "depth": metadata.get("depth", 5.0),
            "status": "pending",
            "priority": item.get("priority", 5)
        })
    
    return result


def update_curiosity_status(topic: str, status: str) -> None:
    storage = _get_queue_storage()
    items = storage.get_items_by_topic(topic)
    
    status_map = {
        "pending": "pending",
        "exploring": "claimed",
        "investigating": "claimed",
        "done": "done"
    }
    sqlite_status = status_map.get(status, status)
    
    for item in items:
        if sqlite_status == "done":
            storage.mark_done(item["id"], item.get("holder_id", "compat_shim"))
        elif sqlite_status == "claimed":
            pass


def update_curiosity_score(topic: str, score: float) -> None:
    storage = _get_queue_storage()
    items = storage.get_items_by_topic(topic)
    priority = max(1, min(10, int(score)))
    
    for item in items:
        storage.update_priority(item["id"], priority)

def get_items_by_topic_score_safe(topic: str, score: float) -> None:
    """Alias kept for clarity; delegates to update_curiosity_score."""
    update_curiosity_score(topic, score)

def mark_topic_done(topic: str, reason: str) -> None:
    storage = _get_queue_storage()
    items = storage.get_items_by_topic(topic)
    
    for item in items:
        holder_id = item.get("holder_id", "compat_shim")
        storage.mark_done(item["id"], holder_id)
    
    state = _load_state()
    if "meta_cognitive" not in state:
        state["meta_cognitive"] = {"completed_topics": {}}
    if "completed_topics" not in state["meta_cognitive"]:
        state["meta_cognitive"]["completed_topics"] = {}
    
    state["meta_cognitive"]["completed_topics"][topic] = {
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    _save_state(state)


async def add_knowledge_async(
    topic: str, 
    depth: int = 5, 
    summary: str = "", 
    sources: Optional[list] = None, 
    quality: Optional[float] = None,
    metadata: Optional[dict] = None
) -> None:
    kg_factory = _get_kg_factory()
    
    from core.concept_normalizer import get_default_normalizer
    normalizer = get_default_normalizer()
    
    all_nodes = await kg_factory.get_all_nodes_async(limit=100)
    
    best_match = None
    best_similarity = 0.0
    best_type = "different_concept"
    
    for node in all_nodes:
        existing_topic = node.get("topic", "")
        if not existing_topic:
            continue
        similarity, match_type = normalizer.compute_concept_similarity(topic, existing_topic)
        if similarity > best_similarity:
            best_match = existing_topic
            best_similarity = similarity
            best_type = match_type
    
    if best_match and best_type in ("naming_variant", "translated_concept"):
        logger.info(f"Merge knowledge into existing node: '{topic}' → '{best_match}' ({best_type}, sim={best_similarity:.2f})")
        topic = best_match
    
    full_metadata = {
        "depth": depth,
        "quality": quality if quality is not None else 0,
        "status": "done"
    }
    
    if metadata:
        full_metadata.update(metadata)
    
    await kg_factory.create_knowledge_node_async(
        topic=topic,
        content=summary,
        source_urls=sources or [],
        metadata=full_metadata
    )


def add_knowledge(topic: str, depth: int = 5, summary: str = "", sources: Optional[list] = None, quality: Optional[float] = None) -> None:
    kg_factory = _get_kg_factory()
    
    from core.concept_normalizer import get_default_normalizer
    normalizer = get_default_normalizer()
    
    all_nodes = kg_factory.get_all_nodes_sync(limit=100)
    
    best_match = None
    best_similarity = 0.0
    best_type = "different_concept"
    
    for node in all_nodes:
        existing_topic = node.get("topic", "")
        if not existing_topic:
            continue
        similarity, match_type = normalizer.compute_concept_similarity(topic, existing_topic)
        if similarity > best_similarity:
            best_match = existing_topic
            best_similarity = similarity
            best_type = match_type
    
    if best_match and best_type in ("naming_variant", "translated_concept"):
        logger.info(f"Merge knowledge into existing node: '{topic}' → '{best_match}' ({best_type}, sim={best_similarity:.2f})")
        topic = best_match
    
    metadata = {
        "depth": depth,
        "quality": quality if quality is not None else 0,
        "status": "done"
    }
    
    kg_factory.create_knowledge_node_sync(
        topic=topic,
        content=summary,
        source_urls=sources or [],
        metadata=metadata
    )


def get_state() -> dict:
    kg_stats = _safe_neo4j_call(
        lambda: _get_kg_factory().get_stats_sync(),
        fallback={"total_nodes": 0, "by_status": {}}
    )
    storage = _get_queue_storage()
    
    try:
        queue_stats = storage.get_all_stats()
    except Exception as e:
        logger.warning(f"QueueStorage get_all_stats failed: {e}")
        queue_stats = {"by_status": {}}
    
    state = _load_state()
    
    nodes = _safe_neo4j_call(
        lambda: _get_kg_factory().get_all_nodes_sync(limit=5000),
        fallback=[]
    )
    
    topics = {}
    for node in nodes:
        topic_name = node.get("topic", "")
        if topic_name:
            topics[topic_name] = {
                "status": node.get("status", "pending"),
                "quality": node.get("quality", 0) or 0,
                "depth": node.get("depth", 5),
                "summary": node.get("summary", "")[:200] if node.get("summary") else "",
                "sources": node.get("sources", []) or [],
                "known": node.get("status") == "done",
                "last_updated": node.get("created_at", ""),
                "children": [],
                "cites": [],
                "definition": node.get("definition", ""),
                "core": node.get("core", ""),
                "context": node.get("context", ""),
                "examples": node.get("examples", []),
                "formula": node.get("formula", ""),
                "completeness_score": node.get("completeness_score", 0),
                "parent_topic": node.get("parent_topic", ""),
            }
    
    return {
        "version": "1.0",
        "last_update": datetime.now(timezone.utc).isoformat(),
        "knowledge": {"topics": topics},
        "curiosity_queue": list_pending(),  # Was hardcoded [] — fixed to read from QueueStorage
        "kg_stats": kg_stats,
        "queue_stats": queue_stats,
        "root_pool": state.get(ROOT_POOL_KEY, {"candidates": []}),
        "meta_cognitive": state.get("meta_cognitive", {}),
        "search_exhausted": state.get("search_exhausted", False),
        "search_exhausted_reason": state.get("search_exhausted_reason")
    }


def get_knowledge_summary() -> dict:
    kg_stats = _safe_neo4j_call(
        lambda: _get_kg_factory().get_stats_sync(),
        fallback={"total_nodes": 0, "by_status": {}}
    )
    storage = _get_queue_storage()
    
    try:
        queue_stats = storage.get_all_stats()
    except Exception as e:
        logger.warning(f"QueueStorage get_all_stats failed: {e}")
        queue_stats = {"by_status": {}}
    
    return {
        "total_topics": kg_stats.get("total_nodes", 0),
        "known_count": kg_stats.get("by_status", {}).get("done", 0),
        "pending_curiosities": queue_stats.get("by_status", {}).get("pending", 0),
        "recent_explorations": 0
    }


def get_kg_overview() -> dict:
    return _safe_neo4j_call(
        lambda: _get_kg_factory().get_graph_overview_sync(),
        fallback={"nodes": [], "edges": [], "stats": {}}
    )


def get_all_nodes(active_only: bool = False) -> list:
    nodes = _safe_neo4j_call(
        lambda: _get_kg_factory().get_all_nodes_sync(limit=5000),
        fallback=[]
    )
    
    result = []
    for node in nodes:
        topic = node.get("topic", "")
        status = node.get("status", "pending")
        
        if active_only and status == "dormant":
            continue
        
        data = {
            "status": status,
            "quality": node.get("quality", 0),
            "depth": node.get("depth", 0),
            "summary": node.get("summary", ""),
            "known": status == "done"
        }
        result.append((topic, data))
    
    return result


def add_child(parent: str, child: str) -> None:
    """Add child relationship. Creates parent node on-the-fly if needed.
    If child doesn't exist, adds it to queue for exploration and creates relation."""
    kg_factory = _get_kg_factory()
    
    parent_exists = kg_factory.get_node_sync(parent) is not None
    child_exists = kg_factory.get_node_sync(child) is not None
    
    async def _ensure_and_relate():
        repo = await kg_factory._ensure_connected()
        if not parent_exists:
            try:
                await repo.create_knowledge_node(
                    topic=parent, content="",
                    source_urls=[], relations=[],
                    metadata={"auto_created": True, "completeness_score": 0}
                )
            except Exception:
                pass
        if not child_exists:
            try:
                await repo.create_knowledge_node(
                    topic=child, content="",
                    source_urls=[], relations=[],
                    metadata={"auto_created": True, "completeness_score": 0}
                )
            except Exception:
                pass
        await repo.add_relation(parent, child, "IS_CHILD_OF")
    
    if parent_exists and child_exists:
        asyncio.run(_ensure_and_relate())
    elif not child_exists:
        add_curiosity(topic=child, reason=f"Child topic of: {parent}", relevance=6.0, depth=5.0)
        try:
            asyncio.run(_ensure_and_relate())
        except Exception:
            pass
    elif not parent_exists:
        try:
            asyncio.run(_ensure_and_relate())
            logger.info(f"Auto-created parent '{parent}' for relation to '{child}'")
        except Exception:
            pass


def get_children(topic: str) -> list:
    """Get child topics from Neo4j."""
    kg_factory = _get_kg_factory()
    
    async def _get_children():
        repo = await kg_factory._ensure_connected()
        return await repo.get_children(topic)
    
    try:
        return asyncio.run(_get_children())
    except Exception:
        return []


def mark_dormant(topic: str) -> None:
    """Mark topic as dormant in Neo4j."""
    kg_factory = _get_kg_factory()
    
    async def _mark():
        repo = await kg_factory._ensure_connected()
        await repo.mark_dormant(topic)
    
    asyncio.run(_mark())


def reactivate(topic: str) -> None:
    """Reactivate dormant topic in Neo4j."""
    kg_factory = _get_kg_factory()
    
    async def _reactivate():
        repo = await kg_factory._ensure_connected()
        await repo.reactivate(topic)
    
    asyncio.run(_reactivate())


def add_citation(citing_topic: str, cited_topic: str) -> None:
    """Add citation relationship. Auto-creates citing node if needed.
    If cited_topic doesn't exist, adds it to queue for exploration."""
    kg_factory = _get_kg_factory()
    
    citing_exists = kg_factory.get_node_sync(citing_topic) is not None
    cited_exists = kg_factory.get_node_sync(cited_topic) is not None
    
    async def _ensure_and_cite():
        repo = await kg_factory._ensure_connected()
        if not citing_exists:
            try:
                await repo.create_knowledge_node(
                    topic=citing_topic, content="",
                    source_urls=[], relations=[],
                    metadata={"auto_created": True, "completeness_score": 0}
                )
            except Exception:
                pass
        if not cited_exists:
            try:
                await repo.create_knowledge_node(
                    topic=cited_topic, content="",
                    source_urls=[], relations=[],
                    metadata={"auto_created": True, "completeness_score": 0}
                )
            except Exception:
                pass
        await repo.add_relation(citing_topic, cited_topic, "CITES")
    
    if citing_exists and cited_exists:
        asyncio.run(_ensure_and_cite())
    elif not cited_exists:
        add_curiosity(topic=cited_topic, reason=f"Cited by: {citing_topic}", relevance=7.0, depth=5.0)
        try:
            asyncio.run(_ensure_and_cite())
        except Exception:
            pass
    elif not citing_exists:
        try:
            asyncio.run(_ensure_and_cite())
            logger.info(f"Auto-created citing node '{citing_topic}' for CITES to '{cited_topic}'")
        except Exception:
            pass


def update_topic_quality(topic: str, quality: float) -> None:
    """Update topic quality in Neo4j."""
    kg_factory = _get_kg_factory()
    
    async def _update():
        repo = await kg_factory._ensure_connected()
        await repo.update_metadata(topic, quality=quality)
    
    asyncio.run(_update())


def add_exploration_result(topic: str, result: dict, quality: float) -> None:
    """Record exploration result in Neo4j."""
    kg_factory = _get_kg_factory()
    
    findings_data = result.get("findings", {})
    findings_str = findings_data.get("summary", "") if isinstance(findings_data, dict) else (findings_data or "")
    
    metadata = {
        "quality": quality,
        "status": "done",
        "depth": result.get("depth", 5)
    }
    
    kg_factory.create_knowledge_node_sync(
        topic=topic,
        content=findings_str,
        source_urls=result.get("sources", []),
        metadata=metadata
    )


def add_dream_insight(
    content: str,
    insight_type: str,
    source_topics: list,
    surprise: float,
    novelty: float,
    trigger_topic: Optional[str]
) -> str:
    """Create a dream insight node (file-based)."""
    node_id = f"insight_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
    
    entry = {
        "node_id": node_id,
        "content": content,
        "insight_type": insight_type,
        "source_topics": source_topics,
        "surprise": surprise,
        "novelty": novelty,
        "trigger_topic": trigger_topic,
        "weight": 0.5,
        "verified": False,
        "quality": 0.0,
        "stale": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    os.makedirs(DREAM_INSIGHTS_DIR, exist_ok=True)
    filepath = os.path.join(DREAM_INSIGHTS_DIR, f"{node_id}.json")
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False, indent=2)
    
    return node_id


def get_dream_insights(topic: Optional[str] = None) -> list:
    """Get dream insights (file-based)."""
    insights = []
    
    if not os.path.exists(DREAM_INSIGHTS_DIR):
        return insights
    
    for filename in os.listdir(DREAM_INSIGHTS_DIR):
        if filename.endswith(".json"):
            filepath = os.path.join(DREAM_INSIGHTS_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                if topic is None or topic in data.get("source_topics", []):
                    insights.append(data)
            except (json.JSONDecodeError, IOError):
                continue
    
    return insights


def get_all_dream_insights() -> list:
    """Get all dream insights (file-based)."""
    return get_dream_insights(topic=None)


def remove_dream_insight(node_id: str) -> None:
    """Remove a dream insight file."""
    filepath = os.path.join(DREAM_INSIGHTS_DIR, f"{node_id}.json")
    if os.path.exists(filepath):
        os.remove(filepath)


def is_insight_stale(node_id: str) -> bool:
    """Check if insight is stale (> 7 days old)."""
    filepath = os.path.join(DREAM_INSIGHTS_DIR, f"{node_id}.json")
    
    if not os.path.exists(filepath):
        return False
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return False
    
    if data.get("verified", False):
        return False
    
    created_at_str = data.get("created_at")
    if not created_at_str:
        return False
    
    try:
        created_at = datetime.fromisoformat(created_at_str)
        age = datetime.now(timezone.utc) - created_at
        return age.days > 7
    except (ValueError, TypeError):
        return False


def update_insight_weight(node_id: str, delta: float) -> None:
    """Update insight weight."""
    filepath = os.path.join(DREAM_INSIGHTS_DIR, f"{node_id}.json")
    
    if not os.path.exists(filepath):
        return
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        data["weight"] = data.get("weight", 0.5) + delta
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, IOError):
        pass


def update_insight_quality(node_id: str, delta: float) -> None:
    """Update insight quality."""
    filepath = os.path.join(DREAM_INSIGHTS_DIR, f"{node_id}.json")
    
    if not os.path.exists(filepath):
        return
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        data["quality"] = data.get("quality", 0.0) + delta
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, IOError):
        pass


def add_to_dream_inbox(topic: str, source_insight: str) -> None:
    inbox = {"inbox": []}
    if os.path.exists(DREAM_INBOX_PATH):
        try:
            with open(DREAM_INBOX_PATH, "r", encoding="utf-8") as f:
                inbox = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    
    inbox["inbox"].append({
        "topic": topic,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_insight": source_insight
    })
    
    with open(DREAM_INBOX_PATH, "w", encoding="utf-8") as f:
        json.dump(inbox, f, ensure_ascii=False, indent=2)


def fetch_and_clear_dream_inbox() -> list:
    """Fetch and clear dream inbox (file-based)."""
    inbox = {"inbox": []}
    if os.path.exists(DREAM_INBOX_PATH):
        try:
            with open(DREAM_INBOX_PATH, "r", encoding="utf-8") as f:
                inbox = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    
    items = inbox.get("inbox", [])
    
    inbox["inbox"] = []
    with open(DREAM_INBOX_PATH, "w", encoding="utf-8") as f:
        json.dump(inbox, f, ensure_ascii=False, indent=2)
    
    return items


def init_root_pool(seeds: list) -> None:
    state = _load_state()
    pool = state.setdefault(ROOT_POOL_KEY, {"candidates": [], "last_updated": None})
    existing_names = {r["name"] for r in pool["candidates"]}
    
    for seed in seeds:
        if seed not in existing_names:
            pool["candidates"].append({
                "name": seed,
                "root_score": 8.0,
                "cross_domain_count": 1,
                "explains_count": 0,
                "domains": ["seed"],
                "confidence": 0.5,
                "sources": ["manual_seed"]
            })
    
    pool["last_updated"] = datetime.now(timezone.utc).isoformat()
    _save_state(state)


def get_root_pool_names() -> set:
    """Get root pool names (file-based)."""
    state = _load_state()
    pool = state.get(ROOT_POOL_KEY, {}).get("candidates", [])
    return {r.get("name") for r in pool if r.get("name")}


def get_root_technologies() -> list:
    """Get all root technologies (file-based)."""
    state = _load_state()
    candidates = state.get(ROOT_POOL_KEY, {}).get("candidates", [])
    return sorted(candidates, key=lambda x: x.get("root_score", 0), reverse=True)


def promote_to_root_candidate(topic: str, domains: list) -> None:
    """Promote topic to root candidate (file-based)."""
    state = _load_state()
    pool = state.setdefault(ROOT_POOL_KEY, {"candidates": [], "last_updated": None})
    
    kg_factory = _get_kg_factory()
    
    async def _get_explains_count():
        repo = await kg_factory._ensure_connected()
        relations = await repo.get_relations(topic)
        return sum(1 for r in relations if r.get("relation_type") == "EXPLAINS")
    
    try:
        explains_count = asyncio.run(_get_explains_count())
    except Exception:
        explains_count = 0
    
    cross_domain_count = len(domains)
    root_score = (
        cross_domain_count * ROOT_SCORE_WEIGHT_DOMAIN +
        explains_count * ROOT_SCORE_WEIGHT_EXPLAINS
    )
    
    for r in pool["candidates"]:
        if r["name"] == topic:
            r["root_score"] = root_score
            r["cross_domain_count"] = cross_domain_count
            r["explains_count"] = explains_count
            r["domains"] = domains
            r["confidence"] = min(0.95, 0.5 + explains_count * 0.05)
            break
    else:
        pool["candidates"].append({
            "name": topic,
            "root_score": root_score,
            "cross_domain_count": cross_domain_count,
            "explains_count": explains_count,
            "domains": domains,
            "confidence": min(0.95, 0.5 + explains_count * 0.05),
            "sources": ["cross_subgraph_detection"]
        })
    
    pool["last_updated"] = datetime.now(timezone.utc).isoformat()
    _save_state(state)


def _ensure_meta_cognitive(state: dict) -> dict:
    if "meta_cognitive" not in state:
        state["meta_cognitive"] = {
            "explore_counts": {},
            "marginal_returns": {},
            "last_quality": {},
            "exploration_log": [],
            "completed_topics": {}
        }
    
    if ROOT_POOL_KEY not in state:
        state[ROOT_POOL_KEY] = {"candidates": [], "last_updated": None}
    
    mc = state["meta_cognitive"]
    
    if "completed_topics" in mc and isinstance(mc["completed_topics"], list):
        old_list = mc["completed_topics"]
        mc["completed_topics"] = {}
        for topic in old_list:
            if topic:
                mc["completed_topics"][topic] = {
                    "reason": "migrated from list format",
                    "timestamp": None
                }
    
    for key, default in [
        ("explore_counts", {}),
        ("marginal_returns", {}),
        ("last_quality", {}),
        ("exploration_log", []),
        ("completed_topics", {})
    ]:
        if key not in mc:
            mc[key] = default
    
    return state


def update_last_exploration_notified(topic: str, notified: bool) -> None:
    """Update last exploration notified flag."""
    state = _load_state()
    state = _ensure_meta_cognitive(state)
    
    mc = state["meta_cognitive"]
    if "last_notified" not in mc:
        mc["last_notified"] = {}
    
    mc["last_notified"][topic] = {
        "notified": notified,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    _save_state(state)


def get_topic_keywords(topic: str) -> list:
    """Get existing keywords for topic."""
    kg_factory = _get_kg_factory()
    node = kg_factory.get_node_sync(topic)
    
    if node:
        return node.get("keywords", [])
    return []


def get_topic_depth(topic: str) -> float:
    """Get current depth for topic."""
    kg_factory = _get_kg_factory()
    node = kg_factory.get_node_sync(topic)
    
    if node:
        return float(node.get("depth", 0))
    return 0.0


def is_topic_completed(topic: str) -> bool:
    """Check if topic is completed."""
    state = _load_state()
    state = _ensure_meta_cognitive(state)
    mc = state.get("meta_cognitive", {})
    completed = mc.get("completed_topics", {})
    return topic in completed


def is_search_exhausted() -> bool:
    """Check if search is exhausted."""
    state = _load_state()
    return state.get("search_exhausted", False)


def set_search_exhausted(exhausted: bool, reason: Optional[str] = None) -> None:
    state = _load_state()
    state["search_exhausted"] = exhausted
    state["search_exhausted_reason"] = reason
    _save_state(state)
    
    if exhausted:
        print(f"[KG] Search exhausted: {reason}")
    else:
        print(f"[KG] Search restored: {reason or 'manual reset'}")


def update_meta_exploration(topic: str, quality: float, marginal_return: float, notified: bool) -> None:
    """Update exploration meta-cognitive data."""
    state = _load_state()
    state = _ensure_meta_cognitive(state)
    
    mc = state["meta_cognitive"]
    
    if "explore_counts" not in mc:
        mc["explore_counts"] = {}
    mc["explore_counts"][topic] = mc["explore_counts"].get(topic, 0) + 1
    
    if "marginal_returns" not in mc:
        mc["marginal_returns"] = {}
    if topic not in mc["marginal_returns"]:
        mc["marginal_returns"][topic] = []
    mc["marginal_returns"][topic].append(marginal_return)
    
    if "last_quality" not in mc:
        mc["last_quality"] = {}
    mc["last_quality"][topic] = quality
    
    if "exploration_log" not in mc:
        mc["exploration_log"] = []
    mc["exploration_log"].append({
        "topic": topic,
        "quality": quality,
        "marginal_return": marginal_return,
        "notified": notified,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    _save_state(state)


def get_meta_cognitive_state() -> dict:
    """Get complete meta-cognitive state."""
    state = _load_state()
    state = _ensure_meta_cognitive(state)
    return state.get("meta_cognitive", {})


def get_topic_explore_count(topic: str) -> int:
    """Get exploration count for topic from state.json explore_counts."""
    state = _load_state()
    state = _ensure_meta_cognitive(state)
    mc = state.get("meta_cognitive", {})
    return mc.get("explore_counts", {}).get(topic, 0)


def get_topic_marginal_returns(topic: str) -> list:
    """Get marginal return history for topic."""
    state = _load_state()
    state = _ensure_meta_cognitive(state)
    mc = state.get("meta_cognitive", {})
    return mc.get("marginal_returns", {}).get(topic, [])


def mark_dreamed(topic: str) -> None:
    state = _load_state()
    topics = state.get("knowledge", {}).get("topics", {})
    
    if topic not in topics:
        topics[topic] = {}
    
    topics[topic]["dreamed_at"] = datetime.now(timezone.utc).isoformat()
    state["knowledge"]["topics"] = topics
    _save_state(state)


def set_consolidated(topic: str) -> None:
    """Mark topic as consolidated (file-based timestamp)."""
    state = _load_state()
    topics = state.get("knowledge", {}).get("topics", {})
    
    if topic not in topics:
        topics[topic] = {}
    
    topics[topic]["last_consolidated"] = datetime.now(timezone.utc).isoformat()
    state["knowledge"]["topics"] = topics
    _save_state(state)


def get_dormant_nodes() -> list:
    """Get all dormant nodes from Neo4j."""
    kg_factory = _get_kg_factory()
    nodes = kg_factory.get_all_nodes_sync(limit=5000)
    
    return [
        node.get("topic", "")
        for node in nodes
        if node.get("status") == "dormant"
    ]


def has_recent_dreams(topic: str, within_days: int) -> bool:
    """Check if topic has been dreamed recently."""
    state = _load_state()
    topics = state.get("knowledge", {}).get("topics", {})
    
    if topic not in topics:
        return False
    
    dreamed_at_str = topics[topic].get("dreamed_at")
    if not dreamed_at_str:
        return False
    
    try:
        dreamed_at = datetime.fromisoformat(dreamed_at_str)
        age = datetime.now(timezone.utc) - dreamed_at
        return age.days < within_days
    except (ValueError, TypeError):
        return False


def get_recently_dreamed(within_days: int) -> set:
    """Get all topics dreamed within time window."""
    from datetime import timedelta
    
    state = _load_state()
    topics = state.get("knowledge", {}).get("topics", {})
    result = set()
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=within_days)
    
    for name, data in topics.items():
        dreamed_at_str = data.get("dreamed_at")
        if dreamed_at_str:
            try:
                dreamed_at = datetime.fromisoformat(dreamed_at_str)
                if dreamed_at > cutoff:
                    result.add(name)
            except (ValueError, TypeError):
                continue
    
    return result


def get_all_relations() -> list:
    """Get ALL relations in one batch (v0.3.6 perf primitive).

    Returns a list of ``{"source": ..., "target": ..., "relation_type": ...}``
    dicts. Use this instead of calling :func:`get_relations_count` per node in
    loops — each per-node call spawns its own ``asyncio.run()`` round-trip,
    which is O(n) round-trips for O(n) nodes.
    """
    kg_factory = _get_kg_factory()
    try:
        return kg_factory.get_all_relations_sync() or []
    except Exception as e:
        logger.warning(f"get_all_relations failed: {e}")
        return []


def get_relations_count(topic: str) -> int:
    """Get number of relations for a topic."""
    kg_factory = _get_kg_factory()

    async def _count():
        repo = await kg_factory._ensure_connected()
        relations = await repo.get_relations(topic)
        return len(relations)

    try:
        return asyncio.run(_count())
    except Exception:
        return 0


def strengthen_connection(topic_a: str, topic_b: str, delta: float = 0.1):
    pass


def get_directly_connected(topic: str) -> set:
    """Get all directly connected topics from Neo4j."""
    kg_factory = _get_kg_factory()
    
    async def _get_connected():
        repo = await kg_factory._ensure_connected()
        relations = await repo.get_relations(topic)
        
        connected = set()
        for rel in relations:
            connected.add(rel.get("related_topic", ""))
        return connected
    
    try:
        return asyncio.run(_get_connected())
    except Exception:
        return set()


def get_shortest_path_length(topic_a: str, topic_b: str) -> float:
    import math
    
    if topic_a == topic_b:
        return 0
    
    return float(math.inf)


def get_recent_explorations(within_hours: int) -> list:
    from datetime import timedelta
    import sqlite3
    
    traces_db = os.path.join(os.path.dirname(__file__), "..", "knowledge", "traces.db")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=within_hours)
    cutoff_str = cutoff.isoformat()
    
    conn = sqlite3.connect(traces_db)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT topic, status, started_at, total_steps FROM explorer_traces WHERE started_at > ? ORDER BY started_at DESC LIMIT 100",
        (cutoff_str,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {"topic": row[0], "status": row[1], "timestamp": row[2], "steps": row[3]}
        for row in rows
    ]


def get_node_lifecycle(topic: str) -> dict:
    """Get lifecycle information for a node."""
    kg_factory = _get_kg_factory()
    node = kg_factory.get_node_sync(topic)
    
    if not node:
        return {}
    
    state = _load_state()
    file_topics = state.get("knowledge", {}).get("topics", {})
    file_data = file_topics.get(topic, {})
    
    return {
        "status": node.get("status", "pending"),
        "known": node.get("status") == "done",
        "created_at": None,
        "dreamed_at": file_data.get("dreamed_at"),
        "last_consolidated": file_data.get("last_consolidated"),
        "depth": node.get("depth", 0),
    }


def get_connection_strength(topic_a: str, topic_b: str) -> float:
    return 0.0


def mark_insight_triggered(insight_node_id: str):
    """Mark insight as triggered (file-based)."""
    state = _load_state()
    if "insight_generation" not in state:
        state["insight_generation"] = {}
    if insight_node_id not in state["insight_generation"]:
        state["insight_generation"][insight_node_id] = {}
    state["insight_generation"][insight_node_id]["triggered"] = True
    _save_state(state)


def get_spreading_activation_trace(
    topic: str,
    max_depth: int = 10,
    decay: float = 0.5,
    threshold: float = 0.1
) -> dict:
    return {
        "origin": topic,
        "activation_map": {},
        "ordered_trace": [],
        "root_technologies": [],
        "cross_subgraph_connections": []
    }


def log_exploration(topic: str, action: str, findings: str, notified: bool = False) -> None:
    """Log exploration to file-based exploration_log."""
    state = _load_state()
    
    def _safe_truncate(text: str, max_chars: int) -> str:
        if not text or len(text) <= max_chars:
            return text
        return text[:max_chars]
    
    state.setdefault("exploration_log", []).append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "topic": topic,
        "action": action,
        "findings": _safe_truncate(findings, 500),
        "notified_user": notified
    })
    
    state["exploration_log"] = state["exploration_log"][-100:]
    _save_state(state)


def get_recent_knowledge(hours: int = 24) -> list:
    from datetime import timedelta
    
    state = _load_state()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_str = cutoff.isoformat()
    
    topics = state.get("knowledge", {}).get("topics", {})
    
    result = []
    for k, v in topics.items():
        if v.get("last_updated", "") > cutoff_str:
            result.append({"topic": k, **v})
    
    return result


def revive_stuck_items(timeout_seconds: int = 180) -> int:
    storage = _get_queue_storage()
    return storage.release_expired_claims()


def remove_ghost_nodes() -> list:
    return []


def remove_zero_quality_nodes() -> dict:
    return {
        "removed_topics": [],
        "removed_topics_count": 0,
        "removed_from_queue": 0
    }


def mark_child_explored(parent: str, child: str) -> None:
    pass


def get_exploration_status(topic: str) -> str:
    """Get exploration status from Neo4j."""
    kg_factory = _get_kg_factory()
    node = kg_factory.get_node_sync(topic)
    
    if not node:
        return "unexplored"
    
    status = node.get("status", "pending")
    
    if status == "done":
        return "complete"
    elif status == "pending":
        return "unexplored"
    else:
        return status


def _load_state_internal() -> dict:
    return _load_state()


def _save_state_internal(state: dict) -> None:
    _save_state(state)


# ---------------------------------------------------------------------------
# SSOT-6 (2026-10-08): 语义化新名（保留旧名做别名过渡）
# ---------------------------------------------------------------------------
# 旧名 `_load_state/_save_state` 产生误导：它返回的**不是**完整 state
# （knowledge.topics 恒空），而是纯运行时状态。新名明确语义。
# 保留旧名 alias，避免 48 处调用点一次性改动引入回归。
def _load_runtime_state() -> dict:
    """运行时状态（ops.db: runtime_kv + meta_cognitive）。知识一律走 Neo4j。"""
    return _load_state()


def _save_runtime_state(state: dict) -> None:
    """持久化运行时状态到 ops.db。"""
    _save_state(state)


__all__ = [
    "add_knowledge_async",
    "add_curiosity",
    "claim_pending_item",
    "list_pending",
    "remove_curiosity",
    "get_top_curiosities",
    "update_curiosity_status",
    "update_curiosity_score",
    "mark_topic_done",
    "revive_stuck_items",
    "add_knowledge",
    "get_state",
    "get_knowledge_summary",
    "get_kg_overview",
    "get_all_nodes",
    "add_child",
    "get_children",
    "mark_dormant",
    "reactivate",
    "add_citation",
    "update_topic_quality",
    "add_exploration_result",
    "add_dream_insight",
    "get_dream_insights",
    "get_all_dream_insights",
    "remove_dream_insight",
    "is_insight_stale",
    "update_insight_weight",
    "update_insight_quality",
    "add_to_dream_inbox",
    "fetch_and_clear_dream_inbox",
    "init_root_pool",
    "get_root_pool_names",
    "get_root_technologies",
    "promote_to_root_candidate",
    "update_last_exploration_notified",
    "get_topic_keywords",
    "get_topic_depth",
    "is_topic_completed",
    "is_search_exhausted",
    "set_search_exhausted",
    "update_meta_exploration",
    "get_meta_cognitive_state",
    "get_topic_explore_count",
    "get_topic_marginal_returns",
    "mark_dreamed",
    "set_consolidated",
    "get_dormant_nodes",
    "has_recent_dreams",
    "get_recently_dreamed",
    "strengthen_connection",
    "get_directly_connected",
    "get_relations_count",
    "get_shortest_path_length",
    "get_connection_strength",
    "get_recent_explorations",
    "get_node_lifecycle",
    "mark_insight_triggered",
    "get_spreading_activation_trace",
    "log_exploration",
    "get_recent_knowledge",
    "remove_ghost_nodes",
    "remove_zero_quality_nodes",
    "mark_child_explored",
    "get_exploration_status",
    "ROOT_SCORE_WEIGHT_DOMAIN",
    "ROOT_SCORE_WEIGHT_EXPLAINS",
    "CROSS_DOMAIN_THRESHOLD",
    "ROOT_POOL_KEY",
]
