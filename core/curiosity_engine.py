"""
好奇心引擎 - 核心决策模块
决定：什么值得探索？优先级是什么？
"""
import re
from datetime import datetime, timezone
from typing import Optional

from . import knowledge_graph as kg
from .intrinsic_scorer import IntrinsicScorer


# 停用词表（领域相关）
STOPWORDS = {
    # 通用商业/SEO词
    "AI Strategy", "AI Business", "Digital Marketing", "CTO", "COO",
    "Chief Technology Officer", "Customer Loyalty", "Operations",
    # 搜索结果噪音词
    "SegmentFault", "CentOS", "Segmentation fault",
    # 单字母/截断
    "Agen", "TeST", "LL", "AI",
}

# 研究关键词（用于语义相关性检查）
RESEARCH_KEYWORDS = {
    "agent", "llm", "memory", "planning", "reasoning", "reflection",
    "metacognition", "curiosity", "autonomous", "world model", "cognitive",
    "framework", "architecture", "training", "arxiv", "reinforcement",
    "chain-of-thought", "prompt", "embedding", "attention", "transformer",
}


class CuriosityEngine:
    """
    好奇心引擎
    
    核心思路：
    1. 追踪"已知"与"未知"的边界
    2. 在边界处生成好奇心
    3. 基于多维度评分决定探索优先级
    """
    
    # 用户 / 项目背景（可动态扩展）
    USER_INTERESTS = [
        "AI agent autonomy",
        "metacognition",
        "curiosity-driven exploration", 
        "cognitive architecture",
        "generative agents",
        "self-improving AI",
    ]
    
    def __init__(self, config=None):
        self.state = kg.get_state()
        self.config = config or {}
        # Initialize intrinsic scorer with knowledge graph and exploration history
        self.intrinsic_scorer = IntrinsicScorer(
            knowledge_graph=self.state.get("knowledge", {}),
            exploration_history=self._get_exploration_history(),
            config=config
        )
        from .competence_tracker import CompetenceTracker
        self.competence_tracker = CompetenceTracker()
    
    def _get_exploration_history(self) -> dict:
        """从知识图谱获取探索历史"""
        state = kg.get_state()
        history = {}
        # 从 exploration_log 中提取历史
        for log in state.get("exploration_log", []):
            topic = log.get("topic")
            if topic:
                if topic not in history:
                    history[topic] = []
                history[topic].append({
                    "insight_quality": log.get("insight_quality", 5),
                    "timestamp": log.get("timestamp"),
                    "findings": log.get("findings", {})
                })
        return history
    
    def score_topic(self, topic: str, alpha: float = 0.5) -> dict:
        """
        融合评分：人工信号 + 内在信号
        
        Args:
            topic: 话题名称
            alpha: 人工信号权重（0.0-1.0），默认 0.5
        
        Returns:
            {
                'final_score': float,      # 融合后总分
                'human_score': float,      # 人工评分
                'intrinsic_score': float,  # 内在评分
                'alpha': float,            # 使用的权重
                'signals': dict,           # 内在信号详情
            }
        """
        # 人工评分（原有逻辑）
        human_score = self.compute_curiosity_score(topic, 5.0, 5.0)
        
        # 内在评分（新增）
        intrinsic_result = self.intrinsic_scorer.score(topic)
        intrinsic_score = intrinsic_result['total']
        
        # 融合
        final_score = human_score * alpha + intrinsic_score * (1 - alpha)
        
        return {
            'final_score': round(final_score, 2),
            'human_score': round(human_score, 2),
            'intrinsic_score': round(intrinsic_score, 2),
            'alpha': alpha,
            'signals': intrinsic_result.get('signals', {}),
            'weights': intrinsic_result.get('weights', {}),
        }
    
    def generate_initial_curiosities(self) -> int:
        """DISABLED: 硬编码 topics 会覆盖手动注入的队列项。
        队列初始化应该通过直接注入或种子文件完成。
        """
        return 0  # 已禁用 - 队列由外部注入填充


    def compute_curiosity_score(self, topic: str, base_relevance: float, base_depth: float) -> float:
        """
        动态评分：
        Score = Relevance × Recency × Depth × Surprise
        
        - Relevance: 与用户兴趣的匹配度
        - Recency: 多久没更新（越久越高，模拟"遗忘"效应）
        - Depth: 知识缺口深度
        - Surprise: 意外程度（新领域 vs 已知领域）
        """
        # Relevance: 匹配用户兴趣关键词
        relevance = base_relevance
        topic_lower = topic.lower()
        for interest in self.USER_INTERESTS:
            if any(kw in topic_lower for kw in interest.lower().split()):
                relevance = min(10.0, relevance + 1.5)
        
        # Recency: 检查知识图谱中该 topic 的更新时间
        state = kg.get_state()
        last_updated = None
        for t, v in state["knowledge"]["topics"].items():
            if t.lower() in topic_lower or topic_lower in t.lower():
                last_updated = v.get("last_updated")
                break
        
        recency = 5.0  # 默认
        if last_updated:
            try:
                last_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                hours_old = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
                recency = min(10.0, hours_old / 24)  # 每天 +1 分，上限 10
            except (ValueError, TypeError):
                recency = 5.0
        
        # Depth: 知识缺口
        depth = base_depth
        
        # Surprise: 越少人知道越有价值（简化：用该 topic 在图谱中的存在度）
        known = 0
        for t in state["knowledge"]["topics"]:
            if t.lower() in topic_lower or topic_lower in t.lower():
                known += 1
        surprise = 10.0 if known == 0 else max(1.0, 10.0 - known * 2)
        
        score = relevance * 0.35 + recency * 0.25 + depth * 0.25 + surprise * 0.15
        return round(score, 2)
    
    def rescore_all(self) -> None:
        """重新评分所有待处理的好奇心项"""
        state = kg.get_state()
        updated = 0
        for item in state["curiosity_queue"]:
            if item["status"] == "pending":
                new_score = self.compute_curiosity_score(
                    item["topic"],
                    item.get("relevance", 5.0),
                    item.get("depth", 5.0)
                )
                if abs(new_score - item["score"]) > 0.5:
                    item["score"] = new_score
                    updated += 1
        if updated > 0:
            kg._save_state(state)
        return updated
    
    def select_next(self) -> Optional[dict]:
        candidates = kg.get_top_curiosities(k=10)
        if not candidates:
            count = self.generate_initial_curiosities()
            if count > 0:
                candidates = kg.get_top_curiosities(k=10)
            else:
                return None

        scored_candidates = []
        for item in candidates:
            topic = item["topic"]

            if kg.is_topic_completed(topic):
                continue

            competence = self.competence_tracker.assess_competence(topic)

            exploration_value = (
                item.get("score", 5.0) *
                (1 - competence["score"]) *
                item.get("relevance", 5.0) / 10.0
            )

            scored_candidates.append({
                **item,
                "exploration_value": exploration_value,
                "competence": competence
            })

        scored_candidates.sort(key=lambda x: x["exploration_value"], reverse=True)
        return scored_candidates[0] if scored_candidates else None
    
    def add_contextual_curiosity(self, context: str) -> None:
        """
        基于用户对话上下文自动生成好奇心
        
        从上下文提取关键词 → 扩展为好奇心项
        """
        # 简单关键词提取
        words = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}', context)
        for phrase in words[:5]:
            if len(phrase) > 6:
                kg.add_curiosity(
                    topic=phrase,
                    reason=f"从对话上下文发现: {context[:80]}",
                    relevance=7.0,
                    depth=6.0
                )
    
    def _extract_keywords(self, text: str) -> list:
        """
        从文本中提取关键词（带过滤）
        
        提取规则：
        1. 预处理：清理换行符
        2. 大写开头的短语（如 "ReAct framework", "Chain-of-Thought"）
        3. 过滤短词（< 4 字符）
        4. 停用词过滤
        5. 去重
        6. 限制数量（最多 10 个）
        """
        if not text:
            return []
        
        # 预处理：清理换行符
        text = text.replace('\n', ' ').replace('\r', ' ')
        
        # 提取大写开头的短语（1-3 个词）
        keywords = re.findall(r'[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2}', text)
        
        # 过滤：短词、停用词、去重
        seen = set()
        filtered = []
        for kw in keywords:
            # 长度过滤
            if len(kw) < 4:
                continue
            # 停用词过滤
            if kw in STOPWORDS:
                continue
            # 去重
            kw_lower = kw.lower()
            if kw_lower not in seen:
                seen.add(kw_lower)
                filtered.append(kw)
        
        # 限制数量
        return filtered[:10]
    
    def _is_research_related(self, keyword: str) -> bool:
        """检查关键词是否与 AI/Agent 研究相关"""
        kw_lower = keyword.lower()
        return any(rk in kw_lower for rk in RESEARCH_KEYWORDS)
    
    def auto_queue_topics(self, topics: list, parent_topic: str) -> int:
        """
        自动将发现的关键词加入好奇心队列
        
        Args:
            topics: 要添加的主题列表
            parent_topic: 父主题（用于生成 reason）
            
        Returns:
            实际添加的数量
        """
        if not topics:
            return 0
        
        state = kg.get_state()
        existing_pending = {
            item["topic"].lower() 
            for item in state["curiosity_queue"] 
            if item["status"] == "pending"
        }
        
        added = 0
        for topic in topics:
            # 跳过空字符串
            if not topic or not topic.strip():
                continue
            
            topic = topic.strip()
            
            # 跳过空字符串
            if not topic:
                continue
            
            # 跳过已存在的待处理项
            if topic.lower() in existing_pending:
                continue
            
            # 语义相关性检查
            if not self._is_research_related(topic):
                continue
            
            # 预估评分门槛（使用融合评分）
            score_result = self.score_topic(topic, alpha=0.5)
            if score_result['final_score'] < 5.0:
                continue
            
            # 添加到队列
            reason = f"auto: found in {parent_topic}"
            kg.add_curiosity(
                topic=topic,
                reason=reason,
                relevance=score_result['final_score'],
                depth=5.0
            )
            added += 1
            existing_pending.add(topic.lower())
        
        return added
