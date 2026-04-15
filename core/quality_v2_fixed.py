"""
Quality V2 Assessor - 修复版

使用懒加载模式，自动获取 KG 实例
"""

import logging
import threading
from typing import Dict
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class QualityV2Assessor:
    """
    质量评估器 v2 - 修复 G4
    
    使用懒加载模式，自动获取 KG 实例
    """
    
    def __init__(self, llm_client):
        self._llm = llm_client
        self._kg_module = None
        self._lock = threading.Lock()
    
    @property
    def kg(self):
        """懒加载 KG 模块"""
        if self._kg_module is None:
            with self._lock:
                if self._kg_module is None:
                    try:
                        from core import knowledge_graph as kg_module
                        self._kg_module = kg_module
                    except ImportError:
                        pass
        return self._kg_module
    
    def assess_quality(
        self,
        topic: str,
        findings: Dict,
        knowledge_graph=None,
    ) -> float:
        """
        评估探索质量
        
        Args:
            topic: 话题
            findings: 探索结果
            knowledge_graph: 可选，如果不传则使用懒加载的实例
            
        Returns:
            float: 质量分数 0-10
        """
        try:
            # 优先使用传入的，否则用懒加载的
            kg = knowledge_graph or self.kg
            
            # 获取之前的内容摘要
            prev_summary = self._get_previous_summary(topic, kg)
            
            # 计算语义新颖度
            novelty = self._calculate_novelty(
                prev_summary, 
                findings.get("summary", "")
            )
            
            # 计算信息增益
            info_gain = self._calculate_info_gain(topic, findings, kg)
            
            # 综合评分
            quality = self._compute_quality_score(novelty, info_gain)
            
            return quality
            
        except Exception as e:
            print(f"[QualityV2] Error assessing {topic}: {e}")
            return 0.0
    
    def _get_previous_summary(self, topic: str, kg) -> str:
        """获取之前的内容摘要"""
        try:
            if kg is None:
                return ""
            
            # 从KG获取
            topic_data = kg.get_topic(topic)
            if topic_data:
                return topic_data.get("summary", "")
            
            return ""
            
        except Exception as e:
            logger.warning(f"Failed to get previous summary for '{topic}': {e}", exc_info=True)
            return ""
    
    def _calculate_novelty(self, prev_summary: str, new_summary: str) -> float:
        """计算语义新颖度"""
        if not prev_summary:
            return 1.0
        
        if not new_summary:
            return 0.0
        
        # 使用文本相似度
        similarity = SequenceMatcher(None, prev_summary, new_summary).ratio()
        novelty = 1.0 - similarity
        
        return max(0.0, min(1.0, novelty))
    
    def _calculate_info_gain(self, topic: str, findings: Dict, kg) -> float:
        """计算信息增益"""
        summary_length = len(findings.get("summary", ""))
        sources_count = len(findings.get("sources", []))
        
        # 归一化
        length_score = min(1.0, summary_length / 1000)
        sources_score = min(1.0, sources_count / 5)
        
        return (length_score + sources_score) / 2
    
    def _compute_quality_score(self, novelty: float, info_gain: float) -> float:
        """计算最终质量分"""
        base_score = novelty * 6 + info_gain * 4
        return round(base_score, 1)
