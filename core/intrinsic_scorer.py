"""
IntrinsicScorer - ICM 启发的内在评分器

职责：计算话题的内在探索价值

设计原则：
- LLM 是主要计算方式（语义理解、综合推理）
- 图谱统计作为辅助输入（冷启动、LLM 不可用时降级）
"""


class IntrinsicScorer:
    """
    ICM 启发的内在评分器
    
    计算话题的内在探索价值，基于三个信号：
    1. 预测误差 (pred_error): 当前理解的不确定性
    2. 图谱密度 (graph_density): 知识网络中的位置重要性
    3. 新颖性 (novelty): 与已知知识的语义重叠度
    """
    
    def __init__(self, knowledge_graph, exploration_history, config=None, llm_client=None):
        """
        初始化内在评分器
        
        Args:
            knowledge_graph: 知识图谱对象或字典
            exploration_history: 探索历史记录
            config: 配置字典（可选）
            llm_client: LLM 客户端实例（可选，不传则自动初始化）
        """
        self.kg = knowledge_graph
        self.history = exploration_history
        self.config = config or {}
        self.llm = llm_client or self._init_llm()
    
    def _init_llm(self):
        """
        初始化 LLM 客户端
        
        Returns:
            LLMClient 实例
        """
        from core.llm_client import LLMClient
        return LLMClient()
    
    def score(self, topic: str) -> dict:
        """
        计算话题的内在评分
        
        Args:
            topic: 待评估的话题名称
            
        Returns:
            {
                'total': float,           # 0-10 总分
                'signals': {
                    'pred_error': float,  # 0-10 预测误差
                    'graph_density': float, # 0-10 图谱密度
                    'novelty': float,     # 0-10 新颖性
                },
                'weights': {              # 各信号权重
                    'pred_error': 0.4,
                    'graph_density': 0.3,
                    'novelty': 0.3,
                },
                'reasoning': str,         # 评分理由
                'context': dict           # 上下文信息
            }
        """
        # 1. 收集上下文
        context = self._gather_context(topic)
        
        # 2. LLM 评估信号
        llm_result = self._llm_assess_signals(topic, context)
        
        # 3. 计算加权总分
        weights = {
            'pred_error': 0.4,
            'graph_density': 0.3,
            'novelty': 0.3,
        }
        
        total = (
            llm_result['pred_error'] * weights['pred_error'] +
            llm_result['graph_density'] * weights['graph_density'] +
            llm_result['novelty'] * weights['novelty']
        )
        
        # 4. 返回完整结果
        return {
            'total': total,
            'signals': {
                'pred_error': llm_result['pred_error'],
                'graph_density': llm_result['graph_density'],
                'novelty': llm_result['novelty'],
            },
            'weights': weights,
            'reasoning': llm_result['reasoning'],
            'context': context
        }
    
    def _gather_context(self, topic: str) -> dict:
        """
        收集图谱上下文，作为 LLM 评估的辅助信息
        
        Args:
            topic: 话题名称
            
        Returns:
            包含话题历史、相关话题和摘要的上下文字典
        """
        records = self.history.get(topic, [])
        history_summary = {
            'explore_count': len(records),
            'avg_insight_quality': sum(r.get('insight_quality', 5) for r in records) / len(records) if records else 0,
            'last_explore': records[-1].get('timestamp') if records else None,
        }
        
        related_topics = self._get_related_topics(topic)
        
        related_summaries = []
        for related in related_topics[:5]:
            topic_data = self.kg.get('topics', {}).get(related, {})
            if topic_data:
                related_summaries.append({
                    'topic': related,
                    'summary': topic_data.get('summary', '')[:200]
                })
        
        return {
            'topic': topic,
            'history': history_summary,
            'related_count': len(related_topics),
            'related_topics': related_topics,
            'related_summaries': related_summaries,
        }
    
    def _get_related_topics(self, topic: str) -> list:
        """
        获取与话题相关的节点列表
        
        Args:
            topic: 话题名称
            
        Returns:
            相关话题名称列表
        """
        relations = self.kg.get('relations', [])
        related = set()
        for rel in relations:
            if topic in rel:
                related.update([r for r in rel if r != topic])
        return list(related)
    
    def _llm_assess_signals(self, topic: str, context: dict) -> dict:
        """
        使用 LLM 评估三个内在信号
        
        LLM 会综合语义理解、历史数据、图谱关系做出判断
        
        Args:
            topic: 待评估的话题名称
            context: _gather_context 返回的上下文字典
            
        Returns:
            {
                'pred_error': float,      # 0-10 预测误差
                'graph_density': float,   # 0-10 图谱密度
                'novelty': float,         # 0-10 新颖性
                'reasoning': str          # 评分理由
            }
        """
        import json
        
        # 构造 prompt
        prompt = f"""
你是一个用于评估 AI Agent 好奇心优先级的评分系统。

请评估以下话题的内在探索价值，给出三个信号的评分（1-10分）：

【待评估话题】
{topic}

【探索历史】
- 探索次数: {context['history']['explore_count']}
- 平均洞察质量: {context['history']['avg_insight_quality']:.1f}/10
- 上次探索: {context['history']['last_explore'] or '从未'}

【知识图谱上下文】
- 相关话题数: {context['related_count']}
- 相关话题列表: {', '.join(context['related_topics'][:10]) if context['related_topics'] else '无'}

【相关话题摘要】
{chr(10).join([f"- {s['topic']}: {s['summary'][:100]}..." for s in context['related_summaries']]) if context['related_summaries'] else '无相关摘要'}

请评估以下三个信号（1-10分，10=最高）：

1. **预测误差 (pred_error)**: 我们当前对这个话题的理解程度
   - 从未探索过 -> 高误差 (8-10)
   - 探索过但 insight 质量低/不一致 -> 中高误差 (6-8)
   - 探索过且 insight 质量高 -> 低误差 (1-4)
   - 需要探索来消除认知不确定性 -> 误差高

2. **图谱密度 (graph_density)**: 该话题在知识网络中的位置重要性
   - 与许多核心话题关联 -> 密度低 (1-3)，因为了解充分
   - 孤立节点，连接少 -> 密度高 (7-10)，知识空白
   - 处于知识边疆 -> 密度高，值得探索

3. **新颖性 (novelty)**: 与已知知识库的语义重叠度
   - 全新概念，从未涉及 -> 高新颖 (8-10)
   - 与已知话题高度相似 -> 低新颖 (1-3)
   - 需考虑语义相似，非字面匹配

请以 JSON 格式返回（不要其他文字）：
{{
    "pred_error": 评分,
    "graph_density": 评分,
    "novelty": 评分,
    "reasoning": "简要的评分理由"
}}
"""
        
        try:
            # 调用 LLM
            response = self.llm.chat(prompt)
            
            # 解析 JSON 响应
            result = json.loads(response)
            
            # 验证并裁剪评分到 0-10 范围
            return {
                'pred_error': max(0, min(10, float(result.get('pred_error', 5)))),
                'graph_density': max(0, min(10, float(result.get('graph_density', 5)))),
                'novelty': max(0, min(10, float(result.get('novelty', 5)))),
                'reasoning': result.get('reasoning', '')
            }
            
        except Exception as e:
            # LLM 失败时，降级到纯统计方法
            print(f"LLM assessment failed: {e}, falling back to stats")
            return self._fallback_stats_assessment(topic, context)
    
    def _fallback_stats_assessment(self, topic: str, context: dict) -> dict:
        """
        纯统计降级方案（LLM 不可用时）
        
        Args:
            topic: 待评估的话题名称
            context: _gather_context 返回的上下文字典
            
        Returns:
            {
                'pred_error': float,
                'graph_density': float,
                'novelty': float,
                'reasoning': str
            }
        """
        history = context['history']
        
        # 1. 预测误差（统计版）
        if history['explore_count'] == 0:
            pred_error = 10.0
        else:
            avg_quality = history['avg_insight_quality']
            decay = min(history['explore_count'] * 1.5, 5)
            pred_error = max(0, 10 - avg_quality - decay)
        
        # 2. 图谱密度（统计版）
        related_count = context['related_count']
        if related_count == 0:
            density = 10.0
        elif related_count >= 10:
            density = 0.0
        else:
            density = 10 - related_count
        
        # 3. 新颖性（统计版）
        if history['explore_count'] == 0 and related_count == 0:
            novelty = 10.0
        else:
            novelty = max(0, 10 - history['explore_count'] * 2 - related_count * 0.5)
        
        return {
            'pred_error': pred_error,
            'graph_density': density,
            'novelty': novelty,
            'reasoning': '[Fallback] Stats-based assessment (LLM unavailable)'
        }
