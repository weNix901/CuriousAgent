"""
Tests for ReasoningCompressor - 认知跳跃压缩模块测试
"""
import pytest
import time
from unittest.mock import patch, MagicMock

from core.reasoning_compressor import (
    CompressionLevel,
    CompressionDecision,
    ReasoningCompressor
)


class TestCompressionLevel:
    """测试压缩级别枚举"""
    
    def test_compression_level_values(self):
        """测试压缩级别的值"""
        assert CompressionLevel.FULL.value == "full"
        assert CompressionLevel.BRIDGED.value == "bridged"
        assert CompressionLevel.JUMP.value == "jump"
        assert CompressionLevel.SILENT.value == "silent"
    
    def test_compression_level_comparison(self):
        """测试压缩级别可以比较"""
        levels = [CompressionLevel.FULL, CompressionLevel.BRIDGED, 
                  CompressionLevel.JUMP, CompressionLevel.SILENT]
        # 确保所有级别都是唯一的
        assert len(set(levels)) == 4


class TestCompressionDecision:
    """测试压缩决策数据类"""
    
    def test_basic_creation(self):
        """测试基本创建"""
        decision = CompressionDecision(
            level=CompressionLevel.JUMP,
            reason="测试原因",
            confidence=0.75
        )
        assert decision.level == CompressionLevel.JUMP
        assert decision.reason == "测试原因"
        assert decision.confidence == 0.75
        assert decision.jump_candidates is None
        assert decision.bridge_summary == ""
    
    def test_creation_with_optional_fields(self):
        """测试带可选字段的创建"""
        decision = CompressionDecision(
            level=CompressionLevel.BRIDGED,
            reason="桥接压缩",
            confidence=0.80,
            jump_candidates=["step1", "step2"],
            bridge_summary="核心发现摘要"
        )
        assert decision.jump_candidates == ["step1", "step2"]
        assert decision.bridge_summary == "核心发现摘要"


class TestReasoningCompressorInit:
    """测试 ReasoningCompressor 初始化"""
    
    def test_default_initialization(self):
        """测试默认初始化"""
        compressor = ReasoningCompressor()
        assert compressor.user_tracker['message_timestamps'] == []
        assert compressor.user_tracker['last_topic_requested'] is None
        assert compressor.user_tracker['mode'] == 'browsing'
    
    def test_custom_initialization(self):
        """测试自定义初始化"""
        tracker = {
            'message_timestamps': [1234567890],
            'last_topic_requested': 'test_topic',
            'mode': 'active'
        }
        compressor = ReasoningCompressor(user_activity_tracker=tracker)
        assert compressor.user_tracker['message_timestamps'] == [1234567890]
        assert compressor.user_tracker['last_topic_requested'] == 'test_topic'
        assert compressor.user_tracker['mode'] == 'active'


class TestCompressMethod:
    """测试 compress() 方法的核心决策逻辑"""
    
    @pytest.fixture
    def compressor(self):
        """提供默认的压缩器实例"""
        return ReasoningCompressor()
    
    def test_user_requested_topic_returns_full(self, compressor):
        """测试：用户主动询问 → FULL"""
        decision = compressor.compress(
            topic="test topic",
            quality=7.0,
            marginal_return=0.5,
            exploration_count=1,
            depth="medium",
            user_requested=True
        )
        assert decision.level == CompressionLevel.FULL
        assert "用户主动询问" in decision.reason
        assert decision.confidence == 0.90
    
    def test_low_quality_and_low_marginal_returns_silent(self, compressor):
        """测试：低质量 + 低边际收益 → SILENT"""
        decision = compressor.compress(
            topic="low quality topic",
            quality=4.5,
            marginal_return=0.05,
            exploration_count=3,
            depth="shallow",
            user_requested=False
        )
        assert decision.level == CompressionLevel.SILENT
        assert "质量低" in decision.reason
        assert decision.confidence == 0.85
    
    def test_high_quality_new_deep_exploration_returns_full(self, compressor):
        """测试：高质量(≥8.5) + 新topic + deep → FULL"""
        decision = compressor.compress(
            topic="new discovery",
            quality=9.0,
            marginal_return=0.8,
            exploration_count=1,
            depth="deep",
            user_requested=False
        )
        assert decision.level == CompressionLevel.FULL
        assert "高质量新发现" in decision.reason
        assert decision.confidence == 0.80
    
    def test_multiple_explorations_low_marginal_returns_jump(self, compressor):
        """测试：多次探索(≥2) + 低边际收益(<0.3) → JUMP"""
        decision = compressor.compress(
            topic="familiar topic",
            quality=7.5,
            marginal_return=0.2,
            exploration_count=2,
            depth="medium",
            user_requested=False
        )
        assert decision.level == CompressionLevel.JUMP
        assert "已探索" in decision.reason
        assert "边际收益递减" in decision.reason
        assert decision.bridge_summary is not None
    
    def test_high_exploration_topic_returns_bridged(self, compressor):
        """测试：高频已知topic → BRIDGED"""
        decision = compressor.compress(
            topic="metacognition in AI",  # 在 HIGH_EXPLORATION_TOPICS 中
            quality=7.0,
            marginal_return=0.5,
            exploration_count=1,
            depth="medium",
            user_requested=False
        )
        assert decision.level == CompressionLevel.BRIDGED
        assert "高频已知领域" in decision.reason
    
    def test_medium_quality_first_exploration_returns_bridged(self, compressor):
        """测试：中等质量 + 首次探索 → BRIDGED"""
        decision = compressor.compress(
            topic="medium topic",
            quality=6.5,
            marginal_return=0.5,
            exploration_count=1,
            depth="medium",
            user_requested=False
        )
        assert decision.level == CompressionLevel.BRIDGED
        assert "中等质量" in decision.reason
    
    def test_browsing_mode_high_quality_returns_bridged(self, compressor):
        """测试：浏览模式 + 高质量发现 → BRIDGED"""
        # 确保是浏览模式（默认就是）
        decision = compressor.compress(
            topic="interesting topic",
            quality=8.0,
            marginal_return=0.6,
            exploration_count=1,
            depth="medium",
            user_requested=False
        )
        assert decision.level == CompressionLevel.BRIDGED
    
    def test_default_returns_bridged(self, compressor):
        """测试：默认情况 → BRIDGED"""
        decision = compressor.compress(
            topic="default topic",
            quality=5.0,
            marginal_return=0.5,
            exploration_count=0,
            depth="shallow",
            user_requested=False
        )
        assert decision.level == CompressionLevel.BRIDGED
        assert decision.reason == "默认压缩策略"
    
    def test_quality_boundary_5_0(self, compressor):
        """测试：质量边界值 5.0"""
        # quality = 5.0, marginal_return = 0.1 (刚好不满足 SILENT 条件)
        decision = compressor.compress(
            topic="boundary test",
            quality=5.0,
            marginal_return=0.1,
            exploration_count=0,
            depth="shallow"
        )
        # 不应该是 SILENT
        assert decision.level != CompressionLevel.SILENT
    
    def test_exploration_count_boundary(self, compressor):
        """测试：探索次数边界"""
        # exploration_count = 1, quality = 8.5, depth = deep → FULL
        decision = compressor.compress(
            topic="boundary count",
            quality=8.5,
            marginal_return=0.5,
            exploration_count=1,
            depth="deep"
        )
        assert decision.level == CompressionLevel.FULL


class TestFormatOutput:
    """测试 format_output() 方法"""
    
    @pytest.fixture
    def sample_result(self):
        """提供示例结果数据"""
        return {
            "topic": "Test Topic",
            "score": 8.5,
            "action": "deep_exploration",
            "findings": "【核心发现】这是一个重要的发现。\n\n【详细分析】这里有详细的分析内容。",
            "sources": ["https://example.com/1", "https://example.com/2"]
        }
    
    @pytest.fixture
    def compressor(self):
        return ReasoningCompressor()
    
    def test_silent_level_returns_empty_string(self, compressor, sample_result):
        """测试：SILENT 级别返回空字符串"""
        decision = CompressionDecision(
            level=CompressionLevel.SILENT,
            reason="低质量",
            confidence=0.85
        )
        output = compressor.format_output(sample_result, decision)
        assert output == ""
    
    def test_jump_format_structure(self, compressor, sample_result):
        """测试：JUMP 级别格式结构"""
        decision = CompressionDecision(
            level=CompressionLevel.JUMP,
            reason="认知跳跃",
            confidence=0.75,
            bridge_summary="核心结论摘要"
        )
        output = compressor.format_output(sample_result, decision)
        
        # 检查包含必要元素
        assert "🔥" in output  # 高质量 emoji
        assert "Test Topic" in output
        assert "核心结论摘要" in output
        assert "认知跳跃模式" in output
        assert "探索指数 8" in output
    
    def test_bridged_format_structure(self, compressor, sample_result):
        """测试：BRIDGED 级别格式结构"""
        decision = CompressionDecision(
            level=CompressionLevel.BRIDGED,
            reason="桥接压缩",
            confidence=0.70,
            bridge_summary="桥接摘要内容"
        )
        output = compressor.format_output(sample_result, decision, include_sources=True)
        
        # 检查包含必要元素
        assert "🔥" in output
        assert "Test Topic" in output
        assert "桥接摘要内容" in output
        assert "详细展开请追问" in output
        assert "📚 关键来源:" in output
        assert "https://example.com/1" in output
    
    def test_bridged_without_sources(self, compressor, sample_result):
        """测试：BRIDGED 级别不包含来源"""
        decision = CompressionDecision(
            level=CompressionLevel.BRIDGED,
            reason="桥接压缩",
            confidence=0.70
        )
        output = compressor.format_output(sample_result, decision, include_sources=False)
        
        assert "📚 关键来源:" not in output
    
    def test_full_format_structure(self, compressor, sample_result):
        """测试：FULL 级别格式结构"""
        decision = CompressionDecision(
            level=CompressionLevel.FULL,
            reason="完整展示",
            confidence=0.90
        )
        output = compressor.format_output(sample_result, decision)
        
        # 检查包含必要元素
        assert "🔬" in output  # 高质量 emoji
        assert "探索发现" in output
        assert "Test Topic" in output
        assert "deep_exploration" in output
        assert "好奇心指数" in output
        assert "【核心发现】" in output
        assert "📚 **来源**:" in output
    
    def test_low_score_uses_different_emoji(self, compressor):
        """测试：低分使用不同的 emoji"""
        result = {
            "topic": "Low Score Topic",
            "score": 6.0,
            "action": "exploration",
            "findings": "普通发现",
            "sources": []
        }
        decision = CompressionDecision(
            level=CompressionLevel.JUMP,
            reason="测试",
            confidence=0.5
        )
        output = compressor.format_output(result, decision)
        assert "💡" in output  # 低质量 emoji


class TestHelperMethods:
    """测试辅助方法"""
    
    def test_is_user_browsing(self):
        """测试 _is_user_browsing()"""
        # 浏览模式
        compressor = ReasoningCompressor({
            'message_timestamps': [],
            'mode': 'browsing'
        })
        assert compressor._is_user_browsing() is True
        
        # 活跃模式
        compressor.user_tracker['mode'] = 'active'
        assert compressor._is_user_browsing() is False
    
    def test_is_high_exploration_topic(self):
        """测试 _is_high_exploration_topic()"""
        compressor = ReasoningCompressor()
        
        # 高频已知 topic
        assert compressor._is_high_exploration_topic("metacognition") is True
        assert compressor._is_high_exploration_topic("Self-Reflection") is True  # 大小写不敏感
        assert compressor._is_high_exploration_topic("agent planning") is True
        
        # 未知 topic
        assert compressor._is_high_exploration_topic("random topic") is False
        assert compressor._is_high_exploration_topic("unknown subject") is False
    
    def test_generate_bridge_summary_with_brackets(self):
        """测试 _generate_bridge_summary() 提取【】内容"""
        compressor = ReasoningCompressor()
        findings = "【核心发现】这是核心内容。\n\n【次要发现】这是次要内容。"
        summary = compressor._generate_bridge_summary("topic", findings, 8.0)
        assert "这是核心内容" in summary
    
    def test_generate_bridge_summary_fallback(self):
        """测试 _generate_bridge_summary() 回退到前200字"""
        compressor = ReasoningCompressor()
        findings = "这是一段没有【】标记的发现内容。" * 10
        summary = compressor._generate_bridge_summary("topic", findings, 8.0)
        assert len(summary) <= 200
        assert "这是一段没有" in summary
    
    def test_generate_bridge_summary_empty(self):
        """测试 _generate_bridge_summary() 处理空内容"""
        compressor = ReasoningCompressor()
        summary = compressor._generate_bridge_summary("topic", "", 8.0)
        assert summary == ""
    
    def test_extract_core_conclusion(self):
        """测试 _extract_core_conclusion()"""
        compressor = ReasoningCompressor()
        
        # 正常内容
        findings = "【标题】\n\n这是核心结论句子，足够长。\n这是第二句。"
        conclusion = compressor._extract_core_conclusion(findings)
        assert "这是核心结论句子" in conclusion
        
        # 空内容
        assert compressor._extract_core_conclusion("") == ""
        
        # 短内容
        assert compressor._extract_core_conclusion("短") == "短"
    
    def test_extract_key_points_with_sections(self):
        """测试 _extract_key_points() 提取章节"""
        compressor = ReasoningCompressor()
        findings = "【章节一】内容一。\n\n【章节二】内容二。\n\n【章节三】内容三。"
        points = compressor._extract_key_points(findings, max_points=2)
        
        assert len(points) == 2
        assert "章节一" in points[0]
        assert "章节二" in points[1]
    
    def test_extract_key_points_fallback(self):
        """测试 _extract_key_points() 回退到第一段"""
        compressor = ReasoningCompressor()
        # 第一段必须超过30个字符才会被添加
        findings = "这是第一段内容，包含足够多的字符以满足长度要求，现在已经超过三十个字符了。\n\n这是第二段。"
        points = compressor._extract_key_points(findings, max_points=2)

        assert len(points) == 1
        assert "这是第一段内容" in points[0]
    
    def test_extract_key_points_empty(self):
        """测试 _extract_key_points() 处理空内容"""
        compressor = ReasoningCompressor()
        points = compressor._extract_key_points("", max_points=2)
        assert points == []


class TestUserActivity:
    """测试用户活动追踪方法"""
    
    def test_update_user_activity_adds_timestamp(self):
        """测试 update_user_activity() 添加时间戳"""
        compressor = ReasoningCompressor()
        initial_count = len(compressor.user_tracker['message_timestamps'])
        
        compressor.update_user_activity(message_count=1)
        
        assert len(compressor.user_tracker['message_timestamps']) == initial_count + 1
    
    def test_update_user_activity_removes_old_timestamps(self):
        """测试 update_user_activity() 清理旧时间戳"""
        old_time = time.time() - 400  # 超过5分钟
        compressor = ReasoningCompressor({
            'message_timestamps': [old_time],
            'mode': 'browsing'
        })
        
        compressor.update_user_activity(message_count=1)
        
        # 旧时间戳应该被清理
        assert old_time not in compressor.user_tracker['message_timestamps']
    
    def test_update_user_activity_changes_mode_to_active(self):
        """测试：足够多的消息将模式改为 active"""
        recent_time = time.time() - 10  # 10秒前
        compressor = ReasoningCompressor({
            'message_timestamps': [recent_time, recent_time],  # 2条消息，达到阈值
            'mode': 'browsing'
        })
        
        compressor.update_user_activity(message_count=1)
        
        assert compressor.user_tracker['mode'] == 'active'
    
    def test_update_user_activity_keeps_browsing_mode(self):
        """测试：消息不足保持 browsing 模式"""
        compressor = ReasoningCompressor({
            'message_timestamps': [],  # 0条消息
            'mode': 'browsing'
        })

        compressor.update_user_activity(message_count=0)  # 添加1条后总共1条

        # 1 < 2 (阈值)，应该保持 browsing
        assert compressor.user_tracker['mode'] == 'browsing'
    
    def test_set_user_topic_request(self):
        """测试 set_user_topic_request()"""
        compressor = ReasoningCompressor()
        
        compressor.set_user_topic_request("requested_topic")
        
        assert compressor.user_tracker['last_topic_requested'] == "requested_topic"
    
    def test_get_user_mode(self):
        """测试 get_user_mode()"""
        compressor = ReasoningCompressor({
            'mode': 'active'
        })
        
        assert compressor.get_user_mode() == 'active'
        
        # 测试默认值
        compressor.user_tracker.pop('mode')
        assert compressor.get_user_mode() == 'browsing'


class TestConstants:
    """测试类常量"""
    
    def test_high_exploration_topics(self):
        """测试 HIGH_EXPLORATION_TOPICS 集合"""
        expected_topics = {
            "metacognition", "self-reflection", "curiosity-driven",
            "agent planning", "chain-of-thought", "cognitive architecture"
        }
        assert ReasoningCompressor.HIGH_EXPLORATION_TOPICS == expected_topics
    
    def test_user_active_threshold(self):
        """测试 USER_ACTIVE_THRESHOLD 阈值"""
        assert ReasoningCompressor.USER_ACTIVE_THRESHOLD == 2
    
    def test_detail_triggers(self):
        """测试 DETAIL_TRIGGERS 集合"""
        triggers = ReasoningCompressor.DETAIL_TRIGGERS
        assert "详细" in triggers
        assert "explain" in triggers
        assert "how" in triggers
    
    def test_jump_triggers(self):
        """测试 JUMP_TRIGGERS 集合"""
        triggers = ReasoningCompressor.JUMP_TRIGGERS
        assert "结论" in triggers
        assert "summary" in triggers
        assert "简短" in triggers


class TestEdgeCases:
    """测试边界情况"""

    @pytest.fixture
    def compressor(self):
        """提供默认的压缩器实例"""
        return ReasoningCompressor()

    def test_compress_with_empty_topic(self, compressor):
        """测试：空 topic 处理"""
        decision = compressor.compress(
            topic="",
            quality=7.0,
            marginal_return=0.5,
            exploration_count=1,
            depth="medium"
        )
        # 应该返回一个有效的决策，不会崩溃
        assert isinstance(decision, CompressionDecision)
    
    def test_compress_with_very_high_quality(self, compressor):
        """测试：极高 quality 值"""
        decision = compressor.compress(
            topic="extreme",
            quality=10.0,  # 超过正常范围
            marginal_return=0.9,
            exploration_count=0,
            depth="deep"
        )
        # 10.0 >= 8.5，应该触发 FULL
        assert decision.level == CompressionLevel.FULL
    
    def test_compress_with_zero_marginal_return(self, compressor):
        """测试：零边际收益"""
        decision = compressor.compress(
            topic="zero marginal",
            quality=3.0,  # < 5.0
            marginal_return=0.0,  # < 0.1
            exploration_count=3,
            depth="shallow"
        )
        assert decision.level == CompressionLevel.SILENT
    
    def test_format_output_with_missing_fields(self, compressor):
        """测试：结果缺少字段"""
        result = {
            "topic": "Incomplete",
            # 缺少 score, action, findings, sources
        }
        decision = CompressionDecision(
            level=CompressionLevel.JUMP,
            reason="测试",
            confidence=0.5
        )
        output = compressor.format_output(result, decision)
        # 应该正常处理，不会崩溃
        assert "Incomplete" in output
    
    def test_format_output_with_very_long_findings(self, compressor):
        """测试：超长的 findings"""
        result = {
            "topic": "Long",
            "score": 8.0,
            "action": "exploration",
            "findings": "A" * 10000,  # 非常长
            "sources": ["url"] * 10
        }
        decision = CompressionDecision(
            level=CompressionLevel.BRIDGED,
            reason="测试",
            confidence=0.5
        )
        output = compressor.format_output(result, decision)
        # 输出应该被截断
        assert len(output) < 5000


# 确保模块可以被导入和基本使用
def test_module_import():
    """测试模块可以正常导入"""
    from core.reasoning_compressor import (
        CompressionLevel,
        CompressionDecision,
        ReasoningCompressor
    )
    assert CompressionLevel is not None
    assert CompressionDecision is not None
    assert ReasoningCompressor is not None
