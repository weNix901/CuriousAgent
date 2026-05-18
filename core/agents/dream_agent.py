"""DreamAgent - Multi-cycle architecture for insight generation."""
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Dict
from urllib.parse import urlparse

from core.agents.ca_agent import CAAgent, CAAgentConfig, AgentResult
from core.tools.registry import ToolRegistry
from core.tools.queue_tools import QueueStorage
from core import knowledge_graph_compat as knowledge_graph
from core.kg.repository_factory import get_kg_factory
import numpy as np

logger = logging.getLogger(__name__)


DREAM_AGENT_TOOLS = [
    "kg_query",
    "kg_query_related",
    "kg_query_ancestors",
    "kg_query_children",
    "kg_query_anomalies",
    "kg_query_co_occurrence",
    "queue_write",
    "queue_read",
    "queue_status",
    "llm_candidate_identify",
    "llm_embed",
    "llm_score",
]


@dataclass
class ScoredCandidate:
    """Candidate with 6-dimension scores."""
    topic: str
    total_score: float
    scores: Dict[str, float]
    recall_count: int = 0


@dataclass
class DreamResult(AgentResult):
    """Result from DreamAgent execution."""
    candidates_selected: List[str] = field(default_factory=list)
    topics_generated: List[str] = field(default_factory=list)
    source_url_topics: List[str] = field(default_factory=list)
    l5_relations_created: int = 0
    l5_pairs_evaluated: int = 0
    l5_nodes_scanned: int = 0


@dataclass
class DreamAgentConfig(CAAgentConfig):
    """Configuration for DreamAgent with 6-dimension scoring."""
    scoring_weights: Dict[str, float] = field(default_factory=lambda: {
        "relevance": 0.25,
        "frequency": 0.15,
        "recency": 0.15,
        "quality": 0.20,
        "surprise": 0.15,
        "cross_domain": 0.10
    })
    min_score_threshold: float = 0.5
    min_recall_count: int = 1
    tools: List[str] = field(default_factory=lambda: DREAM_AGENT_TOOLS.copy())
    max_iterations: int = 1


class DreamAgent(CAAgent):
    """DreamAgent with multi-cycle architecture (L1-L4 linear pipeline)."""

    def __init__(self, config: DreamAgentConfig, tool_registry: ToolRegistry):
        super().__init__(config=config, tool_registry=tool_registry)
        self._scoring_weights = config.scoring_weights
        self._min_score_threshold = config.min_score_threshold
        self._min_recall_count = config.min_recall_count
        self.holder_id = str(uuid.uuid4()) if 'uuid' in globals() else None

    def run(self, input_data: str = "") -> DreamResult:
        """Execute L0→L1→L2→L3→L4 linear pipeline."""
        from core.trace.dream_trace import DreamTraceWriter
        
        trace_writer = DreamTraceWriter()
        trace_id = trace_writer.start_trace()
        overall_start = time.time()
        
        l0_start = time.time()
        l0_result = self._l0_reorganize()
        l0_duration = int((time.time() - l0_start) * 1000)
        
        l1_start = time.time()
        candidates = self._l1_light_sleep()
        l1_duration = int((time.time() - l1_start) * 1000)
        
        l2_start = time.time()
        scored = self._l2_deep_sleep(candidates)
        l2_duration = int((time.time() - l2_start) * 1000)
        
        l3_start = time.time()
        filtered = self._l3_filtering(scored)
        l3_duration = int((time.time() - l3_start) * 1000)
        
        l4_start = time.time()
        topics = self._l4_rem_sleep(filtered)
        l4_duration = int((time.time() - l4_start) * 1000)
        
        total_duration = int((time.time() - overall_start) * 1000)
        
        trace_writer.finish_trace(
            trace_id=trace_id,
            l1_candidates=candidates,
            l1_count=len(candidates),
            l1_duration_ms=l1_duration,
            l2_scored=[{"topic": s.topic, "total_score": s.total_score, "scores": s.scores} for s in scored],
            l2_count=len(scored),
            l2_duration_ms=l2_duration,
            l3_filtered=[f.topic for f in filtered],
            l3_count=len(filtered),
            l3_duration_ms=l3_duration,
            l4_topics=topics,
            l4_count=len(topics),
            l4_duration_ms=l4_duration,
            insights_generated=[{"l0_reorganization": l0_result}],
            total_duration_ms=total_duration,
        )
        
        return DreamResult(
            content=f"DreamAgent reorganized {l0_result['relations_created']} relations, generated {len(topics)} topics",
            success=len(topics) > 0 or l0_result['relations_created'] > 0,
            iterations_used=1,
            candidates_selected=[c.topic for c in filtered],
            topics_generated=topics,
            l5_relations_created=l0_result["relations_created"],
            l5_pairs_evaluated=sum(l0_result.get("phase_stats", {}).values()),
            l5_nodes_scanned=l0_result["nodes_scanned"],
        )

    def _l1_light_sleep(self) -> List[str]:
        """L1: Candidate selection from ExplorationLog + KG anomalies."""
        candidates: List[str] = []
        
        # 1. Get exploration log entries from last 7 days
        recent_explorations = knowledge_graph.get_recent_explorations(within_hours=7 * 24)
        for entry in recent_explorations:
            topic = entry.get("topic", "")
            if topic and topic not in candidates:
                candidates.append(topic)
        
        # Load state.json for dormant and quality checks
        state = knowledge_graph.get_state()
        topics = state["knowledge"]["topics"]
        
        # 2. Get dormant topics from state.json (not Neo4j - no dormant marker there)
        # Dormant = completed topics that haven't been dreamed recently (> 30 days)
        # or topics with very low quality (< 3.0) that need re-examination
        meta_cognitive = state.get("meta_cognitive", {})
        completed_topics = meta_cognitive.get("completed_topics", {})
        for topic, completion_data in completed_topics.items():
            if topic not in candidates:
                # Check if not dreamed recently (dormant)
                topic_data = topics.get(topic, {})
                dreamed_at = topic_data.get("dreamed_at")
                if dreamed_at:
                    try:
                        dreamed_dt = datetime.fromisoformat(dreamed_at)
                        age_days = (datetime.now(timezone.utc) - dreamed_dt).days
                        if age_days > 30:  # Dormant if not dreamed in 30 days
                            candidates.append(topic)
                    except (ValueError, TypeError):
                        candidates.append(topic)  # Invalid date = treat as dormant
                else:
                    candidates.append(topic)  # Never dreamed = dormant
        
        # 3. Get nodes with high citation count but low quality
        for name, data in topics.items():
            citation_count = len(data.get("cites", [])) + len(data.get("cited_by", []))
            quality = data.get("quality", 0.0)
            if citation_count > 5 and quality < 5.0 and name not in candidates:
                candidates.append(name)
        
        # 4. Jaccard deduplication (already done by collecting unique names)
        # Limit to 100 candidates per cycle to keep memory manageable
        return candidates[:100]

    def _l2_deep_sleep(self, candidates: List[str]) -> List[ScoredCandidate]:
        """L2: 6-dimension scoring (Relevance, Frequency, Recency, Quality, Surprise, CrossDomain)."""
        scored: List[ScoredCandidate] = []
        state = knowledge_graph.get_state()
        topics = state["knowledge"]["topics"]
        
        for candidate in candidates:
            scores: Dict[str, float] = {}
            
            # 1. Relevance: based on recent recall frequency
            recall_count = knowledge_graph.get_topic_explore_count(candidate)
            max_expected_recall = 10.0
            scores["relevance"] = min(recall_count / max_expected_recall, 1.0)
            
            # 2. Frequency: how often the topic appears in exploration log
            frequency = sum(1 for e in knowledge_graph.get_recent_explorations(within_hours=7*24) 
                          if e.get("topic", "") == candidate)
            max_expected_freq = 5.0
            scores["frequency"] = min(frequency / max_expected_freq, 1.0)
            
            # 3. Recency: exponential decay based on last access
            topic_data = topics.get(candidate, {})
            last_updated = topic_data.get("last_updated", None)
            if last_updated:
                try:
                    last_dt = datetime.fromisoformat(last_updated)
                    age_days = (datetime.now(timezone.utc) - last_dt).days
                    # Half-life = 14 days
                    recency = np.exp(-np.log(2) * age_days / 14)
                except (ValueError, TypeError):
                    recency = 0.5
            else:
                recency = 0.5
            scores["recency"] = recency
            
            # 4. Quality: existing quality score from knowledge graph
            quality = topic_data.get("quality", 0.0)
            scores["quality"] = quality
            
            # 5. Surprise: how unexpected is this topic based on existing connections
            # Use state.json relations (children + cites) instead of Neo4j
            children = topic_data.get("children", []) or []
            cites = topic_data.get("cites", []) or []
            connections = set(children + cites)
            expected = set()
            for neighbor in connections:
                neighbor_data = topics.get(neighbor, {})
                neighbor_children = neighbor_data.get("children", []) or []
                neighbor_cites = neighbor_data.get("cites", []) or []
                expected.update(neighbor_children + neighbor_cites)
            surprise = 1.0 - (len(connections) / len(expected) if expected else 0.5)
            scores["surprise"] = surprise
            
            # 6. CrossDomain: number of different domains the topic connects to
            # Use state.json depth instead of Neo4j (get_topic_depth returns 0.0 for missing nodes)
            depth = topic_data.get("depth", 5.0) or 5.0
            max_expected_depth = 10.0
            scores["cross_domain"] = min(depth / max_expected_depth, 1.0)
            
            # Calculate weighted total score
            total_score = sum(
                self._scoring_weights[dim] * scores[dim]
                for dim in self._scoring_weights
            )
            
            scored.append(ScoredCandidate(
                topic=candidate,
                total_score=total_score,
                scores=scores,
                recall_count=recall_count
            ))
        
        # Sort by total score descending and keep top 20
        scored.sort(key=lambda x: -x.total_score)
        return scored[:20]

    def _l3_filtering(self, scored_candidates: List[ScoredCandidate]) -> List[ScoredCandidate]:
        """L3: Threshold gating (minScore>=0.8, minRecallCount>=3)."""
        return [
            c for c in scored_candidates
            if c.total_score >= self._min_score_threshold
            and c.recall_count >= self._min_recall_count
        ]

    def _extract_topics_from_source_urls(self, min_quality: float = 7.0) -> List[tuple]:
        kg_factory = get_kg_factory()
        nodes = kg_factory.get_all_nodes_sync(limit=50)
        
        url_topics = []
        seen_urls = set()
        
        for node in nodes:
            quality = node.get("quality", 0) or 0
            if quality < min_quality:
                continue
            
            node_topic = node.get("topic", "")
            sources = node.get("sources", []) or []
            
            for url in sources:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                
                topic = self._fetch_and_extract_topic(url)
                if topic and len(topic) > 5:
                    url_topics.append((topic, node_topic, url))
        
        return url_topics[:15]

    def _fetch_and_extract_topic(self, url: str) -> str:
        try:
            import requests
            response = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
            if response.status_code != 200:
                return self._parse_url_domain(url)
            
            html = response.text
            title = self._extract_title_from_html(html)
            if title and len(title) > 5:
                return title[:80]
            
            return self._parse_url_domain(url)
        except Exception:
            return self._parse_url_domain(url)

    def _extract_title_from_html(self, html: str) -> str:
        import re
        
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
            title = re.sub(r'\s*[-_|]\s*(arxiv|csdn|blog|segmentfault|知乎|博客).*$', '', title, flags=re.IGNORECASE)
            return title.strip()
        
        h1_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html, re.IGNORECASE)
        if h1_match:
            return h1_match.group(1).strip()
        
        meta_match = re.search(r'<meta[^>]*name=["\']title["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if meta_match:
            return meta_match.group(1).strip()
        
        return ""

    def _parse_url_domain(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            domain_parts = domain.split('.')
            main_domain = domain_parts[0] if len(domain_parts) > 1 else domain
            
            if main_domain in ['www', 'm', 'blog', 'devpress']:
                main_domain = domain_parts[1] if len(domain_parts) > 1 else ""
            
            if main_domain and main_domain not in ['arxiv', 'github', 'csdn', 'qq', 'com', 'cn', 'org', 'net']:
                return f"{main_domain} related research"
            
            return ""
        except Exception:
            return ""

    def _l4_rem_sleep(self, filtered_candidates: List[ScoredCandidate]) -> List[str]:
        queue = QueueStorage()
        queue.initialize()
        
        topics_added: List[str] = []
        for candidate in filtered_candidates:
            pending = queue.get_pending_items()
            if any(item["topic"] == candidate.topic for item in pending):
                continue
                
            priority = int(candidate.total_score * 10)
            queue.add_item(
                topic=candidate.topic,
                priority=priority,
                metadata={
                    "source": "dream_agent",
                    "score": candidate.total_score,
                    "scores": candidate.scores
                }
            )
            topics_added.append(candidate.topic)
        
        source_url_topics = self._extract_topics_from_source_urls(min_quality=7.0)
        for topic_tuple in source_url_topics:
            topic, source_node, url = topic_tuple
            
            pending = queue.get_pending_items()
            if any(item["topic"] == topic for item in pending):
                continue
            
            queue.add_item(
                topic=topic,
                priority=6,
                metadata={
                    "source": "dream_agent_source_url",
                    "source_kg_node": source_node,
                    "source_url": url
                }
            )
            topics_added.append(topic)
            
            if source_node != topic:
                self._create_cites_edge(source_node, topic)
        
        return topics_added

    def _l0_reorganize(self) -> dict:
        """L0: Knowledge reorganization — runs BEFORE candidate selection.
        
        Four-phase zero-to-low-cost pipeline:
        1. Source co-citation: nodes sharing source URLs → RELATED_TO
        2. Content embedding: node summaries with high cosine similarity → RELATED_TO  
        3. Graph structure: same parent → IS_SIBLING_OF, overlapping sources → RELATED_TO
        4. LLM verification: borderline content pairs verified with actual node content
        
        Returns: {"relations_created": int, "phase_stats": dict}
        """
        import asyncio
        import numpy as np
        from core import knowledge_graph_compat as kg
        from core.kg.repository_factory import get_kg_factory
        
        state = kg.get_state()
        topics = state.get("knowledge", {}).get("topics", {})
        relations = state.get("knowledge", {}).get("relations", {})
        
        already_connected = set()
        for key, rel in relations.items():
            already_connected.add(key)
            already_connected.add(f"{rel.get('to','')}|{rel.get('from','')}")
        
        def _create_rel(a: str, b: str, rel_type: str = "RELATED_TO"):
            key = f"{a}|{b}"
            if key in already_connected or f"{b}|{a}" in already_connected:
                return False
            try:
                kg.add_child(a, b)
                key_a = f"{a}|{b}"
                already_connected.add(key_a)
                already_connected.add(f"{b}|{a}")
                return True
            except Exception as e:
                logger.warning(f"[DreamAgent L0] Failed to create relation {a[:40]}↔{b[:40]}: {e}")
                return False
        
        total_created = 0
        phase_stats = {}
        embed_svc = None
        
        # ── Phase 1: Source Co-citation (zero cost) ──
        source_nodes = {}
        _noise_prefixes = ("stress_", "test_", "parent_", "child_", "isolated_", "topic_", "dormant_", "active_", "never_", "old_", "recent_")
        for topic, data in topics.items():
            if any(topic.startswith(p) for p in _noise_prefixes):
                continue
            sources = data.get("sources", []) or []
            if isinstance(sources, str):
                sources = [sources]
            for src in sources:
                if not src or "example.com" in src or "test.com" in src:
                    continue
                source_nodes.setdefault(src, []).append(topic)
        
        co_cited = 0
        for src, node_list in source_nodes.items():
            if len(node_list) < 2:
                continue
            for i in range(len(node_list)):
                for j in range(i + 1, len(node_list)):
                    if _create_rel(node_list[i], node_list[j], "RELATED_TO"):
                        co_cited += 1
                        logger.debug(f"[DreamAgent L0] Source co-citation: {node_list[i][:40]} ↔ {node_list[j][:40]} (src={src[:50]})")
        
        total_created += co_cited
        phase_stats["source_co_citation"] = co_cited
        logger.info(f"[DreamAgent L0] Phase1 source co-citation: {co_cited} relations")
        
        # ── Phase 2: Content Embedding (low cost) ──
        content_created = 0
        try:
            from core.embedding_service import EmbeddingService
            embed_svc = EmbeddingService()
            
            meaningful = []
            for topic, data in topics.items():
                quality = data.get("quality", 0) or 0
                if quality < 5:
                    continue
                content_parts = []
                for field in ("summary", "definition", "core", "context"):
                    val = data.get(field, "")
                    if isinstance(val, str) and len(val) > 20:
                        content_parts.append(val[:200])
                if not content_parts:
                    continue
                content = " ".join(content_parts)[:600]
                meaningful.append((topic, content))
            
            if len(meaningful) >= 2:
                texts = [c for _, c in meaningful]
                embeddings = embed_svc.embed(texts)
                
                for i in range(len(meaningful)):
                    for j in range(i + 1, len(meaningful)):
                        sim = embed_svc.cosine_similarity(embeddings[i], embeddings[j]) if hasattr(embed_svc, 'cosine_similarity') else float(np.dot(embeddings[i], embeddings[j]) / (np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[j]) + 1e-8))
                        if sim >= 0.85:
                            if _create_rel(meaningful[i][0], meaningful[j][0], "RELATED_TO"):
                                content_created += 1
                                logger.debug(f"[DreamAgent L0] Content embedding: {meaningful[i][0][:40]} ↔ {meaningful[j][0][:40]} (sim={sim:.3f})")
            
        except Exception as e:
            logger.warning(f"[DreamAgent L0] Phase2 embedding failed: {e}")
        
        total_created += content_created
        phase_stats["content_embedding"] = content_created
        logger.info(f"[DreamAgent L0] Phase2 content embedding: {content_created} relations")
        
        # ── Phase 3: Graph Structure (zero cost) ──
        structure_created = 0
        
        # 3a: Same parent → sibling relation
        parent_children = {}
        for topic, data in topics.items():
            parent = data.get("parent_topic")
            if parent and parent in topics:
                parent_children.setdefault(parent, []).append(topic)
        
        for parent, children in parent_children.items():
            if len(children) < 2:
                continue
            for i in range(len(children)):
                for j in range(i + 1, len(children)):
                    if _create_rel(children[i], children[j], "IS_SIBLING_OF"):
                        structure_created += 1
        
        phase_stats["graph_structure"] = structure_created
        total_created += structure_created
        if structure_created > 0:
            logger.info(f"[DreamAgent L0] Phase3 graph structure: {structure_created} relations ({len(parent_children)} parent groups)")
        
        # ── Phase 4: LLM Content Verification (moderate cost) ──
        llm_created = 0
        try:
            if not embed_svc:
                raise RuntimeError("Embedding service not available")
            
            from core.llm_client import LLMClient
            llm = LLMClient()
            
            # Find remaining orphans after previous phases
            node_rel_count = {}
            for key, rel in relations.items():
                frm = rel.get("from", "")
                to = rel.get("to", "")
                node_rel_count[frm] = node_rel_count.get(frm, 0) + 1
                node_rel_count[to] = node_rel_count.get(to, 0) + 1
            
            remaining_orphans = []
            for topic, data in topics.items():
                quality = data.get("quality", 0) or 0
                if quality < 5:
                    continue
                if node_rel_count.get(topic, 0) > 0:
                    continue
                remaining_orphans.append((topic, data))
            
            # Try to connect remaining orphans using LLM with content
            for orphan_topic, orphan_data in remaining_orphans[:5]:
                orphan_content = self._node_content(orphan_data)
                if not orphan_content:
                    continue
                
                best_candidates = []
                for cand_topic, cand_data in topics.items():
                    if cand_topic == orphan_topic:
                        continue
                    cand_quality = cand_data.get("quality", 0) or 0
                    if cand_quality < 5:
                        continue
                    cand_content = self._node_content(cand_data)
                    if not cand_content:
                        continue
                    try:
                        emb = embed_svc.embed([orphan_content[:300], cand_content[:300]])
                        sim = embed_svc.cosine_similarity(emb[0], emb[1]) if hasattr(embed_svc, 'cosine_similarity') else 0.5
                    except Exception:
                        sim = 0.5
                    if 0.5 <= sim < 0.85:
                        best_candidates.append((cand_topic, sim, cand_content))
                
                best_candidates.sort(key=lambda x: x[1], reverse=True)
                
                for cand_topic, sim, cand_content in best_candidates[:2]:
                    if self._llm_verify_content(llm, orphan_topic, orphan_content, cand_topic, cand_content, sim):
                        if _create_rel(orphan_topic, cand_topic, "RELATED_TO"):
                            llm_created += 1
                            logger.info(f"[DreamAgent L0] LLM verified: {orphan_topic[:40]} ↔ {cand_topic[:40]} (sim={sim:.3f})")
        except Exception as e:
            logger.warning(f"[DreamAgent L0] Phase4 LLM verification failed: {e}")
        
        total_created += llm_created
        phase_stats["llm_verified"] = llm_created
        
        if total_created > 0:
            logger.info(f"[DreamAgent L0] Reorganization complete: {total_created} total relations ({phase_stats})")
        
        return {
            "relations_created": total_created,
            "nodes_scanned": len(topics),
            "phase_stats": phase_stats,
        }
    
    def _node_content(self, data: dict) -> str:
        parts = []
        for field in ("definition", "core", "summary", "context"):
            val = data.get(field, "")
            if isinstance(val, str) and len(val.strip()) > 10:
                parts.append(val.strip()[:300])
        return "\n\n".join(parts[:2]) if parts else ""
    
    def _llm_verify_content(self, llm, topic_a: str, content_a: str, topic_b: str, content_b: str, similarity: float) -> bool:
        prompt = f"""You are a knowledge graph curator. Determine if these two knowledge points are semantically related.

Topic A: {topic_a}
Content of A: {content_a[:400]}

Topic B: {topic_b}
Content of B: {content_b[:400]}

Similarity score from embedding: {similarity:.2f}

Consider:
- Do they belong to the same domain or research area?
- Does one concept build upon, extend, or relate to the other?
- Would connecting them in a knowledge graph add navigational value?

Reply with ONLY 'yes' or 'no'."""
        try:
            response = llm.chat(prompt, max_tokens=5).strip().lower()
            return response.startswith("yes")
        except Exception:
            return similarity >= 0.7
    
    def _create_cites_edge(self, source_topic: str, target_topic: str) -> bool:
        try:
            import core.knowledge_graph_compat as kg
            kg.add_citation(source_topic, target_topic)
            return True
        except Exception:
            return False