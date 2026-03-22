"""
ReasoningCompressor - 认知跳跃压缩模块

核心职责：
1. 判断当前探索结果应该"完整展示"还是"压缩结论"
2. 生成不同压缩级别的输出格式
3. 基于 topic 特征、用户状态、发现质量决定压缩策略

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
设计原则（weNix 确认，2026-03-22）：
  "结论优先，按需展开" — AI 输出应默认给结论，
  用户主动要求时再展开推理链。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

认知跳跃原则（来自 Mind the Gap 论文）：
- 专家的标志：跳过显然步骤，给出结论
- 新手的标志：步步推理，但容易在细节中迷失

R1D3-researcher 的目标：学会像专家一样——在适当时机跳跃，只在必要时展示桥接步骤
"""
import re
from enum import Enum
from typing import Optional
from dataclasses import dataclass


class CompressionLevel(Enum):
    """压缩级别"""
    FULL = "full"           # 完整推理链（所有 Layer）
    BRIDGED = "bridged"     # 桥接压缩（核心结论 + 关键依据）
    JUMP = "jump"           # 认知跳跃（只有结论 + 一句话依据）
    SILENT = "silent"       # 不输出（低价值发现）


@dataclass
class CompressionDecision:
    level: CompressionLevel
    reason: str
    confidence: float  # 0.0-1.0
    jump_candidates: list[str] = None  # 可跳过的推理步骤
    bridge_summary: str = ""  # 桥接总结（bridged/jump 时用）


class ReasoningCompressor:
    """
    认知跳跃压缩器
    
    判断逻辑：
    
    JUMP (认知跳跃)：
    - 用户处于"浏览模式"（消息频率低）
    - topic 已被多次探索，边际收益递减
    - 发现质量高（>8.0）但重复性强
    
    BRIDGED (桥接压缩)：
    - topic 是新探索但复杂度中等
    - 用户最近活跃，希望了解详情
    - 发现质量中等，需要一些支撑
    
    FULL (完整链路)：
    - 用户直接询问该 topic
    - 发现质量极高（>9.0）且是新发现
    - topic 是 deep 深度探索
    
    SILENT (静默)：
    - 发现质量极低（<5.0）
    - topic 已被充分探索，边际收益接近零
    """

    # 高频已知 topics（多次探索后，边际收益递减）
    HIGH_EXPLORATION_TOPICS = {
        "metacognition", "self-reflection", "curiosity-driven",
        "agent planning", "chain-of-thought", "cognitive architecture"
    }
    
    # 用户活跃阈值（消息/5分钟）
    USER_ACTIVE_THRESHOLD = 2
    
    # 压缩触发词（用户消息中包含这些词 → 用户想看细节）
    DETAIL_TRIGGERS = {"详细", "展开", "具体", "怎么", "why", "how", "explain", "detail", "具体是"}
    
    # 跳跃触发词（用户消息中包含这些词 → 用户只要结论）
    JUMP_TRIGGERS = {"结论", "summary", "简短", "简单说", "就", "只要结论", "压缩"}

    def __init__(self, user_activity_tracker: dict = None):
        """
        Args:
            user_activity_tracker: 用户活跃状态追踪
                {
                    'message_timestamps': [timestamp, ...],  # 最近消息时间戳
                    'last_topic_requested': str,           # 用户主动询问的 topic
                    'mode': 'active' | 'browsing'          # 用户模式
                }
        """
        self.user_tracker = user_activity_tracker or {
            'message_timestamps': [],
            'last_topic_requested': None,
            'mode': 'browsing'
        }

    # === 核心决策入口 ===
    
    def compress(
        self,
        topic: str,
        quality: float,
        marginal_return: float,
        exploration_count: int,
        depth: str,  # "shallow" | "medium" | "deep"
        user_requested: bool = False,
        layer_count: int = 1,
        findings: str = ""
    ) -> CompressionDecision:
        """
        判断给定探索结果应该以什么级别输出
        
        Args:
            topic: 话题
            quality: 探索质量 (0-10)
            marginal_return: 边际收益
            exploration_count: 该 topic 被探索的次数
            depth: 探索深度
            user_requested: 用户是否主动询问该 topic
            layer_count: 实际运行的 layer 数量
            findings: 原始发现文本
            
        Returns:
            CompressionDecision: 包含压缩级别和理由
        """
        # 规则 0: 用户明确要求详细 → FULL
        if self._user_wants_detail():
            return CompressionDecision(
                level=CompressionLevel.FULL,
                reason="用户明确要求详细展开",
                confidence=0.95
            )
        
        # 规则 0b: 用户明确只要结论 → JUMP
        if self._user_wants_jump():
            return CompressionDecision(
                level=CompressionLevel.JUMP,
                reason="用户明确要求简短结论",
                confidence=0.95
            )
        
        # 规则 1: 用户主动询问该 topic → FULL
        if user_requested:
            return CompressionDecision(
                level=CompressionLevel.FULL,
                reason=f"用户主动询问 topic: {topic}",
                confidence=0.90
            )
        
        # 规则 2: 极低质量发现 → SILENT
        if quality < 5.0 and marginal_return < 0.1:
            return CompressionDecision(
                level=CompressionLevel.SILENT,
                reason=f"发现质量低（{quality:.1f}）且边际收益接近零",
                confidence=0.85
            )
        
        # 规则 3: 高质量 + 新 topic + deep 探索 → FULL
        if quality >= 8.5 and exploration_count <= 1 and depth == "deep":
            return CompressionDecision(
                level=CompressionLevel.FULL,
                reason=f"高质量新发现（{quality:.1f}）+ deep 探索，值得完整展示",
                confidence=0.80
            )
        
        # 规则 4: 多次探索 + 低边际收益 → JUMP
        if exploration_count >= 2 and marginal_return < 0.3:
            return CompressionDecision(
                level=CompressionLevel.JUMP,
                reason=f"该 topic 已探索 {exploration_count} 次，边际收益递减（{marginal_return:.2f}）",
                confidence=0.75,
                bridge_summary=self._generate_bridge_summary(topic, findings, quality)
            )
        
        # 规则 5: 高频已知 topic → BRIDGED
        if self._is_high_exploration_topic(topic) and exploration_count >= 1:
            return CompressionDecision(
                level=CompressionLevel.BRIDGED,
                reason=f"「{topic}」是高频已知领域，压缩展示核心结论",
                confidence=0.70,
                bridge_summary=self._generate_bridge_summary(topic, findings, quality)
            )
        
        # 规则 6: 中等质量 + 中等探索 → BRIDGED
        if 5.0 <= quality < 8.5 and exploration_count == 1:
            return CompressionDecision(
                level=CompressionLevel.BRIDGED,
                reason=f"中等质量（{quality:.1f}）新发现，桥接展示",
                confidence=0.65,
                bridge_summary=self._generate_bridge_summary(topic, findings, quality)
            )
        
        # 规则 7: 用户浏览模式 + 高质量 → BRIDGED（不给完整链路打扰用户）
        if self._is_user_browsing() and quality >= 7.0:
            return CompressionDecision(
                level=CompressionLevel.BRIDGED,
                reason="用户浏览模式 + 高质量发现，压缩减少打扰",
                confidence=0.70,
                bridge_summary=self._generate_bridge_summary(topic, findings, quality)
            )
        
        # 默认: BRIDGED
        return CompressionDecision(
            level=CompressionLevel.BRIDGED,
            reason="默认压缩策略",
            confidence=0.50,
            bridge_summary=self._generate_bridge_summary(topic, findings, quality)
        )

    # === 输出格式化 ===

    def format_output(
        self,
        result: dict,
        decision: CompressionDecision,
        include_sources: bool = True
    ) -> str:
        """
        根据压缩决策格式化输出
        
        Args:
            result: Explorer.explore() 返回的结果
            decision: compress() 返回的压缩决策
            include_sources: 是否包含来源链接
            
        Returns:
            str: 格式化后的输出文本
        """
        level = decision.level
        
        if level == CompressionLevel.SILENT:
            return ""  # 不输出
        
        if level == CompressionLevel.JUMP:
            return self._format_jump(result, decision)
        
        if level == CompressionLevel.BRIDGED:
            return self._format_bridged(result, decision, include_sources)
        
        # FULL: 使用原有的完整格式
        return self._format_full(result)

    def _format_jump(self, result: dict, decision: CompressionDecision) -> str:
        """JUMP 级别：结论 + 一句话依据"""
        topic = result.get("topic", "未知")
        score = result.get("score", 0)
        findings = result.get("findings", "")
        
        # 提取核心结论（第一句话或第一个发现点）
        core_conclusion = self._extract_core_conclusion(findings)
        
        # 格式：📌 结论 + 一句话
        emoji = "🔥" if score >= 8.0 else "💡"
        lines = [
            f"{emoji} **{topic}**",
            "",
        ]
        
        if decision.bridge_summary:
            lines.append(decision.bridge_summary[:150])
        elif core_conclusion:
            lines.append(core_conclusion[:150])
        
        lines.append("")
        lines.append(f"（探索指数 {score:.0f} | 认知跳跃模式）")
        
        return "\n".join(lines)

    def _format_bridged(self, result: dict, decision: CompressionDecision, include_sources: bool) -> str:
        """BRIDGED 级别：核心结论 + 关键依据（省略中间推理）"""
        topic = result.get("topic", "未知")
        score = result.get("score", 0)
        findings = result.get("findings", "")
        sources = result.get("sources", [])
        
        # 提取关键发现点（最多 2 个，避免信息过载）
        key_points = self._extract_key_points(findings, max_points=2)
        
        emoji = "🔥" if score >= 8.0 else "💡"
        lines = [
            f"{emoji} **{topic}**",
            "",
        ]
        
        if decision.bridge_summary:
            lines.append(decision.bridge_summary[:300])
        else:
            for point in key_points:
                lines.append(f"• {point[:200]}")
        
        lines.append("")
        lines.append(f"（探索指数 {score:.0f} | 详细展开请追问）")
        
        if include_sources and sources:
            lines.append("")
            lines.append("📚 关键来源:")
            for s in sources[:2]:
                if s:
                    lines.append(f"- {s[:80]}")
        
        return "\n".join(lines)

    def _format_full(self, result: dict) -> str:
        """FULL 级别：完整推理链（回退到 Explorer 的原有格式）"""
        # 构建完整格式（不依赖 Explorer 实例，避免循环导入）
        level = "🔬" if result.get("score", 0) >= 8.0 else "💡"
        action = result.get("action", "exploration")
        score = result.get("score", 0)
        topic = result.get("topic", "未知")
        findings = result.get("findings", "")
        sources = result.get("sources", [])

        lines = [
            f"{level} **探索发现**",
            "",
            f"**主题**: {topic}",
            f"**方式**: {action} | **好奇心指数**: {score}",
            "",
            "---",
            findings,
        ]
        if sources:
            lines.append("")
            lines.append("📚 **来源**:")
            for s in sources[:3]:
                if s:
                    lines.append(f"- {s}")
        return "\n".join(lines)

    # === 辅助方法 ===

    def _user_wants_detail(self) -> bool:
        """检查用户是否明确要求详细展开"""
        # TODO: 接入用户消息追踪
        return False

    def _user_wants_jump(self) -> bool:
        """检查用户是否明确只要结论"""
        # TODO: 接入用户消息追踪
        return False

    def _is_user_browsing(self) -> bool:
        """判断用户是否处于浏览模式（低消息频率）"""
        return self.user_tracker.get('mode') == 'browsing'

    def _is_high_exploration_topic(self, topic: str) -> bool:
        """判断是否为高频已知 topic"""
        topic_lower = topic.lower()
        return any(
            kw in topic_lower 
            for kw in self.HIGH_EXPLORATION_TOPICS
        )

    def _generate_bridge_summary(self, topic: str, findings: str, quality: float) -> str:
        """生成桥接总结（bridged/jump 级别的依据摘要）"""
        if not findings:
            return ""
        
        # 提取第一个 "【】" 包围的章节作为核心发现
        sections = re.findall(r'【([^】]+)】', findings)
        if sections:
            # 取第一个核心章节
            first_section = sections[0]
            # 找到该章节的完整内容
            pattern = f"【{re.escape(first_section)}】(.*?)(?=【|$)"
            match = re.search(pattern, findings, re.DOTALL)
            if match:
                content = match.group(1).strip()
                # 取前 100 字
                return content[:200]
        
        # 回退：取 findings 的前 200 字
        return findings[:200].strip()

    def _extract_core_conclusion(self, findings: str) -> str:
        """从 findings 中提取核心结论"""
        if not findings:
            return ""
        
        # 尝试找到第一个 "核心发现" 或关键句子
        lines = findings.split('\n')
        for line in lines:
            line = line.strip()
            # 跳过空行、标题行
            if not line or line.startswith('【') or line.startswith('—'):
                continue
            # 取第一个实质性句子
            if len(line) > 20:
                return line
        
        return findings[:150] if findings else ""

    def _extract_key_points(self, findings: str, max_points: int = 2) -> list[str]:
        """从 findings 中提取关键发现点"""
        if not findings:
            return []
        
        points = []
        
        # 方法1: 找 "【】" 包围的章节
        sections = re.findall(r'【([^】]+)】(.*?)(?=【|$)', findings, re.DOTALL)
        for section_title, section_content in sections[:max_points]:
            content = section_content.strip()
            # 取章节内容的前 150 字
            if content:
                points.append(f"{section_title}: {content[:150]}")
        
        # 方法2: 如果没找到，用第一段
        if not points:
            first_para = findings.split('\n\n')[0] if '\n\n' in findings else findings
            if len(first_para) > 30:
                points.append(first_para[:200])
        
        return points[:max_points]

    # === 用户状态更新 ===
    
    def update_user_activity(self, message_count: int = 1) -> None:
        """
        更新用户活跃状态
        
        当收到用户消息时调用，更新用户模式判断
        """
        tracker = self.user_tracker
        
        # 更新消息计数
        tracker['message_timestamps'].append(__import__('time').time())
        
        # 只保留最近 5 分钟的消息
        import time
        cutoff = time.time() - 300
        tracker['message_timestamps'] = [
            t for t in tracker['message_timestamps'] if t > cutoff
        ]
        
        # 判断模式
        recent_count = len(tracker['message_timestamps'])
        if recent_count >= self.USER_ACTIVE_THRESHOLD:
            tracker['mode'] = 'active'
        else:
            tracker['mode'] = 'browsing'

    def set_user_topic_request(self, topic: str) -> None:
        """设置用户主动询问的 topic"""
        self.user_tracker['last_topic_requested'] = topic

    def get_user_mode(self) -> str:
        """获取当前用户模式"""
        return self.user_tracker.get('mode', 'browsing')
