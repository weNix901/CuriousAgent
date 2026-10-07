"""
Tests for IntrinsicScorer - ICM 启发的内在评分器
"""
import pytest
from unittest.mock import Mock, patch


class TestIntrinsicScorer:
    """IntrinsicScorer 测试类"""
    
    def test_scorer_initialization(self):
        """测试 IntrinsicScorer 可以正确初始化"""
        from core.intrinsic_scorer import IntrinsicScorer
        
        scorer = IntrinsicScorer(knowledge_graph={}, exploration_history={})
        assert scorer is not None
        assert scorer.kg == {}
        assert scorer.history == {}
    
    def test_scorer_initialization_with_config(self):
        """测试 IntrinsicScorer 使用配置初始化"""
        from core.intrinsic_scorer import IntrinsicScorer
        
        config = {"test_key": "test_value"}
        scorer = IntrinsicScorer(
            knowledge_graph={"topics": {}},
            exploration_history={},
            config=config
        )
        assert scorer.config == config
    
    def test_scorer_initialization_with_llm_client(self):
        """测试 IntrinsicScorer 使用传入的 LLM 客户端初始化"""
        from core.intrinsic_scorer import IntrinsicScorer
        
        mock_llm = Mock()
        scorer = IntrinsicScorer(
            knowledge_graph={},
            exploration_history={},
            llm_client=mock_llm
        )
        assert scorer.llm == mock_llm
    
    def test_score_returns_dict(self):
        """测试 score() 返回字典格式"""
        from core.intrinsic_scorer import IntrinsicScorer
        
        scorer = IntrinsicScorer(knowledge_graph={}, exploration_history={})
        result = scorer.score("test topic")
        
        assert isinstance(result, dict)
        assert 'total' in result
        assert 'signals' in result
        assert 'weights' in result
        assert 'reasoning' in result
        assert 'context' in result
    
    def test_score_returns_valid_total(self):
        """测试 score() 返回有效的总分"""
        from core.intrinsic_scorer import IntrinsicScorer
        
        scorer = IntrinsicScorer(knowledge_graph={}, exploration_history={})
        result = scorer.score("test topic")
        
        assert isinstance(result['total'], (int, float))
        assert 0 <= result['total'] <= 10
    
    def test_score_returns_valid_signals(self):
        """测试 score() 返回有效的信号字典"""
        from core.intrinsic_scorer import IntrinsicScorer
        
        scorer = IntrinsicScorer(knowledge_graph={}, exploration_history={})
        result = scorer.score("test topic")
        
        signals = result['signals']
        assert 'pred_error' in signals
        assert 'graph_density' in signals
        assert 'novelty' in signals
        
        # 所有信号值应在 0-10 范围内
        for signal_name, value in signals.items():
            assert isinstance(value, (int, float)), f"{signal_name} should be numeric"
            assert 0 <= value <= 10, f"{signal_name} should be in range 0-10"
    
    def test_score_returns_valid_weights(self):
        """测试 score() 返回正确的权重"""
        from core.intrinsic_scorer import IntrinsicScorer
        
        scorer = IntrinsicScorer(knowledge_graph={}, exploration_history={})
        result = scorer.score("test topic")
        
        weights = result['weights']
        assert weights['pred_error'] == 0.4
        assert weights['graph_density'] == 0.3
        assert weights['novelty'] == 0.3
    
    def test_gather_context_returns_dict(self):
        """测试 _gather_context 返回正确的字典结构"""
        from core.intrinsic_scorer import IntrinsicScorer
        
        # 准备测试数据
        kg = {
            'topics': {
                'related_topic_1': {'summary': 'A' * 300},  # 超过 200 字符
                'related_topic_2': {'summary': 'Short summary'},
            },
            'relations': [['test_topic', 'related_topic_1'], ['test_topic', 'related_topic_2']]
        }
        history = {
            'test_topic': [
                {'insight_quality': 7, 'timestamp': '2024-01-01'},
                {'insight_quality': 8, 'timestamp': '2024-01-02'},
            ]
        }
        
        scorer = IntrinsicScorer(knowledge_graph=kg, exploration_history=history)
        result = scorer._gather_context('test_topic')
        
        # 验证返回结构
        assert isinstance(result, dict)
        assert result['topic'] == 'test_topic'
        
        # 验证 history 结构
        assert 'history' in result
        assert result['history']['explore_count'] == 2
        assert result['history']['avg_insight_quality'] == 7.5
        assert result['history']['last_explore'] == '2024-01-02'
        
        # 验证 related_count 和 related_topics
        assert result['related_count'] == 2
        assert 'related_topic_1' in result['related_topics']
        assert 'related_topic_2' in result['related_topics']
        
        # 验证 related_summaries
        assert len(result['related_summaries']) == 2
        # 摘要应截断到 200 字符
        for summary_item in result['related_summaries']:
            assert 'topic' in summary_item
            assert 'summary' in summary_item
            assert len(summary_item['summary']) <= 200
    
    def test_gather_context_for_new_topic(self):
        """测试 _gather_context 对新话题返回空历史"""
        from core.intrinsic_scorer import IntrinsicScorer
        
        kg = {'topics': {}, 'relations': []}
        history = {}  # 空历史
        
        scorer = IntrinsicScorer(knowledge_graph=kg, exploration_history=history)
        result = scorer._gather_context('brand_new_topic')
        
        # 验证新话题的处理
        assert result['topic'] == 'brand_new_topic'
        assert result['history']['explore_count'] == 0
        assert result['history']['avg_insight_quality'] == 0
        assert result['history']['last_explore'] is None
        assert result['related_count'] == 0
        assert result['related_topics'] == []
        assert result['related_summaries'] == []
    
    # ========== _llm_assess_signals Tests ==========
    
    def test_llm_assess_signals_returns_scores(self):
        """测试 _llm_assess_signals 正常解析 LLM 响应"""
        from core.intrinsic_scorer import IntrinsicScorer
        import json
        
        # 模拟 LLM 返回有效 JSON
        mock_llm = Mock()
        mock_llm.chat.return_value = json.dumps({
            'pred_error': 7.5,
            'graph_density': 6.0,
            'novelty': 8.5,
            'reasoning': 'Test reasoning'
        })
        
        scorer = IntrinsicScorer(
            knowledge_graph={'topics': {}, 'relations': []},
            exploration_history={},
            llm_client=mock_llm
        )
        
        context = scorer._gather_context('test_topic')
        result = scorer._llm_assess_signals('test_topic', context)
        
        # 验证返回结构
        assert isinstance(result, dict)
        assert 'pred_error' in result
        assert 'graph_density' in result
        assert 'novelty' in result
        assert 'reasoning' in result
        
        # 验证值正确解析
        assert result['pred_error'] == 7.5
        assert result['graph_density'] == 6.0
        assert result['novelty'] == 8.5
        assert result['reasoning'] == 'Test reasoning'
        
        # 验证 LLM 被调用
        mock_llm.chat.assert_called_once()
    
    def test_llm_assess_signals_clips_high_values(self):
        """测试 _llm_assess_signals 裁剪超出范围的值（上界）"""
        from core.intrinsic_scorer import IntrinsicScorer
        import json
        
        # 模拟 LLM 返回超出范围的值
        mock_llm = Mock()
        mock_llm.chat.return_value = json.dumps({
            'pred_error': 15.0,  # 超过 10
            'graph_density': 12.5,  # 超过 10
            'novelty': 100.0,  # 远超 10
            'reasoning': 'High values test'
        })
        
        scorer = IntrinsicScorer(
            knowledge_graph={'topics': {}, 'relations': []},
            exploration_history={},
            llm_client=mock_llm
        )
        
        context = scorer._gather_context('test_topic')
        result = scorer._llm_assess_signals('test_topic', context)
        
        # 所有值应被裁剪到 10
        assert result['pred_error'] == 10.0
        assert result['graph_density'] == 10.0
        assert result['novelty'] == 10.0
    
    def test_llm_assess_signals_clips_low_values(self):
        """测试 _llm_assess_signals 裁剪超出范围的值（下界）"""
        from core.intrinsic_scorer import IntrinsicScorer
        import json
        
        # 模拟 LLM 返回负值
        mock_llm = Mock()
        mock_llm.chat.return_value = json.dumps({
            'pred_error': -5.0,  # 低于 0
            'graph_density': -10.0,  # 远低于 0
            'novelty': -0.5,  # 略低于 0
            'reasoning': 'Low values test'
        })
        
        scorer = IntrinsicScorer(
            knowledge_graph={'topics': {}, 'relations': []},
            exploration_history={},
            llm_client=mock_llm
        )
        
        context = scorer._gather_context('test_topic')
        result = scorer._llm_assess_signals('test_topic', context)
        
        # 所有值应被裁剪到 0
        assert result['pred_error'] == 0.0
        assert result['graph_density'] == 0.0
        assert result['novelty'] == 0.0
    
    def test_llm_assess_signals_fallback_on_exception(self):
        """测试 _llm_assess_signals 在 LLM 异常时调用 fallback"""
        from core.intrinsic_scorer import IntrinsicScorer
        
        # 模拟 LLM 抛出异常
        mock_llm = Mock()
        mock_llm.chat.side_effect = Exception("LLM API error")
        
        # 模拟 fallback 方法
        mock_fallback = Mock(return_value={
            'pred_error': 10.0,
            'graph_density': 10.0,
            'novelty': 10.0,
            'reasoning': '[Fallback] Stats-based assessment'
        })
        
        scorer = IntrinsicScorer(
            knowledge_graph={'topics': {}, 'relations': []},
            exploration_history={},
            llm_client=mock_llm
        )
        # 注入 mock fallback
        scorer._fallback_stats_assessment = mock_fallback
        
        context = scorer._gather_context('test_topic')
        result = scorer._llm_assess_signals('test_topic', context)
        
        # 验证 fallback 被调用
        mock_fallback.assert_called_once_with('test_topic', context)
        
        # 验证返回 fallback 结果
        assert result['pred_error'] == 10.0
        assert '[Fallback]' in result['reasoning']
    
    def test_llm_assess_signals_fallback_on_invalid_json(self):
        """测试 _llm_assess_signals 在无效 JSON 响应时调用 fallback"""
        from core.intrinsic_scorer import IntrinsicScorer
        
        # 模拟 LLM 返回无效 JSON
        mock_llm = Mock()
        mock_llm.chat.return_value = "This is not valid JSON"
        
        # 模拟 fallback 方法
        mock_fallback = Mock(return_value={
            'pred_error': 5.0,
            'graph_density': 5.0,
            'novelty': 5.0,
            'reasoning': '[Fallback] Stats-based assessment'
        })
        
        scorer = IntrinsicScorer(
            knowledge_graph={'topics': {}, 'relations': []},
            exploration_history={},
            llm_client=mock_llm
        )
        scorer._fallback_stats_assessment = mock_fallback
        
        context = scorer._gather_context('test_topic')
        result = scorer._llm_assess_signals('test_topic', context)
        
        # 验证 fallback 被调用
        mock_fallback.assert_called_once()
    
    def test_llm_assess_signals_uses_default_for_missing_keys(self):
        """测试 _llm_assess_signals 对缺失的键使用默认值 5"""
        from core.intrinsic_scorer import IntrinsicScorer
        import json
        
        # 模拟 LLM 返回部分缺失的 JSON
        mock_llm = Mock()
        mock_llm.chat.return_value = json.dumps({
            'pred_error': 7.0,
            # graph_density 缺失
            'novelty': 8.0,
            'reasoning': 'Partial data'
        })
        
        scorer = IntrinsicScorer(
            knowledge_graph={'topics': {}, 'relations': []},
            exploration_history={},
            llm_client=mock_llm
        )
        
        context = scorer._gather_context('test_topic')
        result = scorer._llm_assess_signals('test_topic', context)
        
        # 缺失的键应使用默认值 5
        assert result['pred_error'] == 7.0
        assert result['graph_density'] == 5.0  # 默认值
        assert result['novelty'] == 8.0
    
    # ========== score() Integration Tests ==========
    
    def test_score_calls_gather_context_and_llm_assess(self):
        """测试 score() 调用 _gather_context 和 _llm_assess_signals"""
        from core.intrinsic_scorer import IntrinsicScorer
        
        mock_llm = Mock()
        scorer = IntrinsicScorer(
            knowledge_graph={'topics': {}, 'relations': []},
            exploration_history={},
            llm_client=mock_llm
        )
        
        # Mock _gather_context 和 _llm_assess_signals
        mock_context = {
            'topic': 'test_topic',
            'history': {'explore_count': 0, 'avg_insight_quality': 0, 'last_explore': None},
            'related_count': 0,
            'related_topics': [],
            'related_summaries': []
        }
        mock_llm_result = {
            'pred_error': 7.0,
            'graph_density': 6.0,
            'novelty': 8.0,
            'reasoning': 'Test reasoning'
        }
        
        scorer._gather_context = Mock(return_value=mock_context)
        scorer._llm_assess_signals = Mock(return_value=mock_llm_result)
        
        result = scorer.score('test_topic')
        
        # 验证调用链
        scorer._gather_context.assert_called_once_with('test_topic')
        scorer._llm_assess_signals.assert_called_once_with('test_topic', mock_context)
    
    def test_score_calculates_total_correctly(self):
        """测试 score() 正确计算总分"""
        from core.intrinsic_scorer import IntrinsicScorer
        
        mock_llm = Mock()
        scorer = IntrinsicScorer(
            knowledge_graph={'topics': {}, 'relations': []},
            exploration_history={},
            llm_client=mock_llm
        )
        
        # Mock 返回值
        mock_context = {'topic': 'test_topic', 'history': {}, 'related_count': 0, 'related_topics': [], 'related_summaries': []}
        mock_llm_result = {
            'pred_error': 7.0,
            'graph_density': 6.0,
            'novelty': 8.0,
            'reasoning': 'Test reasoning'
        }
        
        scorer._gather_context = Mock(return_value=mock_context)
        scorer._llm_assess_signals = Mock(return_value=mock_llm_result)
        
        result = scorer.score('test_topic')
        
        # 验证总分计算: 7.0*0.4 + 6.0*0.3 + 8.0*0.3 = 2.8 + 1.8 + 2.4 = 7.0
        expected_total = 7.0 * 0.4 + 6.0 * 0.3 + 8.0 * 0.3
        assert result['total'] == expected_total
    
    def test_score_returns_all_required_fields(self):
        """测试 score() 返回所有必需字段"""
        from core.intrinsic_scorer import IntrinsicScorer
        
        mock_llm = Mock()
        scorer = IntrinsicScorer(
            knowledge_graph={'topics': {}, 'relations': []},
            exploration_history={},
            llm_client=mock_llm
        )
        
        mock_context = {'topic': 'test_topic', 'history': {}, 'related_count': 0, 'related_topics': [], 'related_summaries': []}
        mock_llm_result = {
            'pred_error': 5.0,
            'graph_density': 5.0,
            'novelty': 5.0,
            'reasoning': 'Test reasoning'
        }
        
        scorer._gather_context = Mock(return_value=mock_context)
        scorer._llm_assess_signals = Mock(return_value=mock_llm_result)
        
        result = scorer.score('test_topic')
        
        # 验证所有必需字段
        assert 'total' in result
        assert 'signals' in result
        assert 'weights' in result
        assert 'reasoning' in result
        assert 'context' in result
        
        # 验证 signals 结构
        assert 'pred_error' in result['signals']
        assert 'graph_density' in result['signals']
        assert 'novelty' in result['signals']
        
        # 验证 weights 结构
        assert result['weights']['pred_error'] == 0.4
        assert result['weights']['graph_density'] == 0.3
        assert result['weights']['novelty'] == 0.3
    
    def test_score_includes_context_in_result(self):
        """测试 score() 在结果中包含 context"""
        from core.intrinsic_scorer import IntrinsicScorer
        
        mock_llm = Mock()
        scorer = IntrinsicScorer(
            knowledge_graph={'topics': {}, 'relations': []},
            exploration_history={},
            llm_client=mock_llm
        )
        
        mock_context = {
            'topic': 'test_topic',
            'history': {'explore_count': 2, 'avg_insight_quality': 7.5, 'last_explore': '2024-01-01'},
            'related_count': 3,
            'related_topics': ['topic_a', 'topic_b', 'topic_c'],
            'related_summaries': []
        }
        mock_llm_result = {
            'pred_error': 5.0,
            'graph_density': 5.0,
            'novelty': 5.0,
            'reasoning': 'Test reasoning'
        }
        
        scorer._gather_context = Mock(return_value=mock_context)
        scorer._llm_assess_signals = Mock(return_value=mock_llm_result)
        
        result = scorer.score('test_topic')
        
        # 验证 context 被包含在结果中
        assert result['context'] == mock_context
    
    def test_score_includes_reasoning_from_llm(self):
        """测试 score() 在结果中包含 LLM 的 reasoning"""
        from core.intrinsic_scorer import IntrinsicScorer
        
        mock_llm = Mock()
        scorer = IntrinsicScorer(
            knowledge_graph={'topics': {}, 'relations': []},
            exploration_history={},
            llm_client=mock_llm
        )
        
        mock_context = {'topic': 'test_topic', 'history': {}, 'related_count': 0, 'related_topics': [], 'related_summaries': []}
        mock_llm_result = {
            'pred_error': 5.0,
            'graph_density': 5.0,
            'novelty': 5.0,
            'reasoning': 'This is a detailed reasoning from LLM'
        }
        
        scorer._gather_context = Mock(return_value=mock_context)
        scorer._llm_assess_signals = Mock(return_value=mock_llm_result)
        
        result = scorer.score('test_topic')
        
        # 验证 reasoning 来自 LLM 结果
        assert result['reasoning'] == 'This is a detailed reasoning from LLM'
