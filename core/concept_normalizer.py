"""Concept normalizer for knowledge point deduplication.

知识点去重核心模块：概念规范化器

设计理念：知识点是客观存在的概念，多语言只是对同一概念的不同表述窗口。
- "agent上下文管理" 和 "agent context management" → 同一概念
- "agent记忆" 和 "agent上下文" → 不同概念

检测策略：
1. 文本规范化：空格/大小写/标点变体
2. 核心概念映射：中英文翻译对应
3. embedding验证：语义相似度确认
"""
import re
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DeduplicationConfig:
    """Configuration for concept deduplication."""
    enabled: bool = True
    # 文本规范化阈值（完全匹配）
    normalize_exact_match: bool = True
    # embedding阈值
    embedding_threshold_high: float = 0.95  # 高置信度合并（跨源同概念）
    embedding_threshold_medium: float = 0.85  # 中置信度（需要核心词验证）
    embedding_threshold_low: float = 0.75  # 低置信度（不合并）
    # 来源重叠阈值
    source_overlap_threshold: int = 1  # 至少1个共同URL
    # 自动合并阈值
    auto_merge_threshold: float = 0.95


# 核心概念中英文映射表
# 这些是常见技术概念的翻译对应
CONCEPT_TRANSLATION_MAP: Dict[str, Set[str]] = {
    # Agent相关
    "上下文": {"context", "context window", "上下文窗口"},
    "记忆": {"memory", "recall", "回忆"},
    "轨迹": {"trajectory", "trace", "轨迹"},
    "注意力": {"attention", "attention mechanism", "注意力机制"},
    "规划": {"planning", "plan", "规划"},
    "推理": {"reasoning", "inference", "推理"},
    "执行": {"execution", "execute", "执行"},
    "反思": {"reflection", "reflect", "反思"},
    "工具": {"tool", "工具调用", "tool calling"},
    
    # LLM相关
    "提示": {"prompt", "提示词", "prompting"},
    "嵌入": {"embedding", "嵌入向量", "vector"},
    "微调": {"fine-tuning", "fine tune", "微调"},
    "预训练": {"pre-training", "pretrain", "预训练"},
    "推理": {"inference", "推理"},
    
    # 架构相关
    "架构": {"architecture", "架构设计"},
    "模块": {"module", "module", "模块"},
    "层": {"layer", "层"},
    "节点": {"node", "节点"},
    "边": {"edge", "边"},
    "图": {"graph", "图谱"},
    
    # 系统相关
    "系统": {"system", "系统"},
    "框架": {"framework", "框架"},
    "引擎": {"engine", "引擎"},
    "服务": {"service", "服务"},
    "接口": {"interface", "接口", "API"},
    
    # 数据相关
    "数据": {"data", "数据"},
    "存储": {"storage", "存储"},
    "检索": {"retrieval", "检索", "search"},
    "索引": {"index", "索引"},
    "缓存": {"cache", "缓存"},
    
    # 通用概念
    "管理": {"management", "管理", "manager"},
    "控制": {"control", "控制", "controller"},
    "优化": {"optimization", "优化", "optimize"},
    "分析": {"analysis", "分析", "analyze"},
    "设计": {"design", "设计"},
    "实现": {"implementation", "实现", "implement"},
    "模型": {"model", "模型"},
    "算法": {"algorithm", "算法"},
    "方法": {"method", "methodology", "方法"},
    "技术": {"technology", "technique", "技术"},
    "应用": {"application", "应用", "apply"},
}

# 反向映射：英文→中文
ENGLISH_TO_CHINESE_MAP: Dict[str, str] = {}
for chinese, english_set in CONCEPT_TRANSLATION_MAP.items():
    for english in english_set:
        ENGLISH_TO_CHINESE_MAP[english.lower()] = chinese


class ConceptNormalizer:
    """知识点概念规范化器。
    
    功能：
    1. 文本规范化：去除空格、大小写、标点差异
    2. 核心概念提取：从topic中提取核心概念词
    3. 翻译映射：识别中英文表述的同一概念
    """
    
    def __init__(self, config: DeduplicationConfig = None):
        self.config = config or DeduplicationConfig()
        self._translation_map = CONCEPT_TRANSLATION_MAP
        self._reverse_map = ENGLISH_TO_CHINESE_MAP
    
    def normalize_text(self, topic: str) -> str:
        """文本规范化：去除空格、统一大小写、去除标点"""
        if not topic:
            return ""
        
        normalized = topic.replace(" ", "").replace("\t", "").replace("-", "")
        normalized = normalized.lower()
        normalized = re.sub(r'[^\w\u4e00-\u9fff]', '', normalized)
        
        return normalized
    
    def extract_core_concepts(self, topic: str) -> List[str]:
        """从topic中提取核心概念词"""
        if not topic:
            return []
        
        concepts = []
        
        for chinese in self._translation_map.keys():
            if chinese in topic:
                concepts.append(chinese)
        
        words = re.split(r'[\s\-_]+', topic.lower())
        for word in words:
            if word in self._reverse_map:
                chinese_equivalent = self._reverse_map[word]
                if chinese_equivalent not in concepts:
                    concepts.append(chinese_equivalent)
        
        return concepts
    
    def get_canonical_concept(self, topic: str) -> str:
        """获取topic的规范化概念标识"""
        concepts = self.extract_core_concepts(topic)
        
        if concepts:
            sorted_concepts = sorted(concepts, key=lambda x: -len(x))
            return "+".join(sorted_concepts)
        
        return self.normalize_text(topic)
    
    def are_translated_concepts(self, concept_a: str, concept_b: str) -> bool:
        """判断两个概念是否是翻译对应"""
        if concept_a == concept_b:
            return True
        
        if concept_a in self._translation_map:
            english_equivs = self._translation_map[concept_a]
            if concept_b in self._translation_map:
                return concept_a == concept_b
            concept_b_lower = concept_b.lower()
            if concept_b_lower in english_equivs or concept_b_lower in self._reverse_map:
                return self._reverse_map.get(concept_b_lower) == concept_a
        
        concept_a_lower = concept_a.lower()
        if concept_a_lower in self._reverse_map:
            chinese_a = self._reverse_map[concept_a_lower]
            if concept_b in self._translation_map:
                return chinese_a == concept_b
            concept_b_lower = concept_b.lower()
            if concept_b_lower in self._reverse_map:
                return chinese_a == self._reverse_map[concept_b_lower]
        
        return False
    
    def concepts_overlap(self, concepts_a: List[str], concepts_b: List[str]) -> bool:
        """判断两个概念列表是否有重叠的核心概念"""
        if not concepts_a or not concepts_b:
            return False
        
        for ca in concepts_a:
            for cb in concepts_b:
                if self.are_translated_concepts(ca, cb):
                    return True
        
        return False
    
    def compute_concept_similarity(
        self, 
        topic_a: str, 
        topic_b: str,
        embedding_similarity: Optional[float] = None
    ) -> Tuple[float, str]:
        """计算两个topic的概念相似度，返回(分数, 类型)"""
        norm_a = self.normalize_text(topic_a)
        norm_b = self.normalize_text(topic_b)
        
        if norm_a == norm_b:
            return (1.0, "naming_variant")
        
        concepts_a = self.extract_core_concepts(topic_a)
        concepts_b = self.extract_core_concepts(topic_b)
        
        if self.concepts_overlap(concepts_a, concepts_b):
            overlap_count = sum(
                1 for ca in concepts_a for cb in concepts_b 
                if self.are_translated_concepts(ca, cb)
            )
            max_concepts = max(len(concepts_a), len(concepts_b))
            concept_overlap_ratio = overlap_count / max_concepts
            
            if embedding_similarity is not None:
                if embedding_similarity >= self.config.embedding_threshold_medium:
                    return (min(concept_overlap_ratio + 0.3, 1.0), "translated_concept")
            
            return (concept_overlap_ratio, "translated_concept")
        
        if embedding_similarity is not None:
            if embedding_similarity >= self.config.embedding_threshold_high:
                return (embedding_similarity, "semantic_similar")
            if embedding_similarity >= self.config.embedding_threshold_medium:
                return (embedding_similarity * 0.8, "semantic_similar")
        
        return (0.0, "different_concept")
    
    def should_merge(
        self,
        topic_a: str,
        topic_b: str,
        node_a: Optional[Dict] = None,
        node_b: Optional[Dict] = None,
        embedding_similarity: Optional[float] = None
    ) -> Tuple[bool, str, float]:
        """判断两个知识点是否应该合并，返回(是否合并, 类型, 置信度)"""
        similarity, match_type = self.compute_concept_similarity(
            topic_a, topic_b, embedding_similarity
        )
        
        if match_type == "naming_variant":
            return (True, "naming_variant", 1.0)
        
        if match_type == "translated_concept":
            if embedding_similarity is None:
                return (True, "translated_concept", similarity)
            if embedding_similarity >= self.config.embedding_threshold_medium:
                return (True, "translated_concept", similarity)
        
        if node_a and node_b:
            sources_a = set(node_a.get("source_urls", []) or [])
            sources_b = set(node_b.get("source_urls", []) or [])
            overlap = sources_a & sources_b
            
            if len(overlap) >= self.config.source_overlap_threshold:
                if embedding_similarity and embedding_similarity >= self.config.embedding_threshold_medium:
                    return (True, "same_source_variant", similarity)
        
        if match_type == "semantic_similar":
            return (False, "different_concept", similarity)
        
        return (False, "different_concept", similarity)


class ConceptDeduplicator:
    """知识点去重器：集成ConceptNormalizer和EmbeddingService"""
    
    def __init__(
        self, 
        config: DeduplicationConfig = None,
        embedding_service = None,
        kg_repository = None
    ):
        self.config = config or DeduplicationConfig()
        self.normalizer = ConceptNormalizer(self.config)
        self._embedding_service = embedding_service
        self._kg_repository = kg_repository
    
    async def check_duplicate_in_kg(
        self, 
        topic: str,
        threshold: float = 0.85
    ) -> Optional[Tuple[str, float, str]]:
        """检查KG中是否存在重复知识点"""
        if not self._kg_repository:
            logger.warning("KG repository not available for duplicate check")
            return None
        
        try:
            all_nodes = await self._get_all_kg_nodes()
        except Exception as e:
            logger.error(f"Failed to get KG nodes: {e}")
            return None
        
        best_match = None
        best_similarity = 0.0
        best_type = "different_concept"
        
        for node in all_nodes:
            existing_topic = node.get("topic", "")
            if not existing_topic:
                continue
            
            embedding_sim = None
            if self._embedding_service:
                try:
                    embeddings = self._embedding_service.embed([topic, existing_topic])
                    embedding_sim = self._embedding_service.cosine_similarity(
                        embeddings[0], embeddings[1]
                    )
                except Exception as e:
                    logger.warning(f"Embedding failed: {e}")
            
            should_merge, merge_type, similarity = self.normalizer.should_merge(
                topic, existing_topic, None, node, embedding_sim
            )
            
            if should_merge and similarity > best_similarity:
                best_match = existing_topic
                best_similarity = similarity
                best_type = merge_type
        
        if best_match and best_similarity >= threshold:
            return (best_match, best_similarity, best_type)
        
        return None
    
    async def check_duplicate_in_queue(
        self, 
        topic: str,
        queue_items: List[Dict],
        threshold: float = 0.85
    ) -> Optional[Tuple[str, float, str]]:
        """检查Queue中是否存在重复主题（轻量检测）"""
        best_match = None
        best_similarity = 0.0
        best_type = "different_concept"
        
        for item in queue_items:
            existing_topic = item.get("topic", "")
            if not existing_topic:
                continue
            
            similarity, match_type = self.normalizer.compute_concept_similarity(
                topic, existing_topic
            )
            
            if similarity > best_similarity:
                best_match = existing_topic
                best_similarity = similarity
                best_type = match_type
        
        if best_type in ("naming_variant", "translated_concept"):
            return (best_match, best_similarity, best_type)
        
        return None
    
    async def _get_all_kg_nodes(self) -> List[Dict]:
        """获取所有KG节点"""
        if hasattr(self._kg_repository, 'query_all_nodes'):
            return await self._kg_repository.query_all_nodes()
        
        nodes = []
        
        for status in ["done", "pending", "dormant"]:
            try:
                status_nodes = await self._kg_repository.query_knowledge_by_status(
                    status=status, limit=100
                )
                nodes.extend(status_nodes)
            except Exception:
                pass
        
        try:
            hot_nodes = await self._kg_repository.query_knowledge_by_heat(limit=100)
            nodes.extend(hot_nodes)
        except Exception:
            pass
        
        seen_topics = set()
        unique_nodes = []
        for node in nodes:
            topic = node.get("topic", "")
            if topic and topic not in seen_topics:
                seen_topics.add(topic)
                unique_nodes.append(node)
        
        return unique_nodes


# 单例实例（可选）
_default_normalizer: Optional[ConceptNormalizer] = None


def get_default_normalizer() -> ConceptNormalizer:
    global _default_normalizer
    if _default_normalizer is None:
        _default_normalizer = ConceptNormalizer()
    return _default_normalizer


__all__ = [
    "DeduplicationConfig",
    "ConceptNormalizer",
    "ConceptDeduplicator",
    "CONCEPT_TRANSLATION_MAP",
    "get_default_normalizer",
]