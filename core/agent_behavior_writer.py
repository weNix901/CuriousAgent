"""Agent Behavior Writer - Convert discoveries to behavior rules"""
import os
import re
from pathlib import Path
from datetime import datetime

BEHAVIOR_FILE = "/root/.openclaw/workspace-researcher/curious-agent-behaviors.md"
MEMORY_CURIOUS_DIR = "/root/.openclaw/workspace-researcher/memory/curious"
QUALITY_THRESHOLD = 7.0

TYPE_TO_SECTION = {
    "metacognition_strategy": "## 💡 元认知策略",
    "reasoning_strategy": "## 🧠 推理策略",
    "confidence_rule": "## 📊 置信度规则",
    "self_check_rule": "## 🪞 自我检查规则",
    "proactive_behavior": "## 🔍 主动行为",
    "tool_discovery": "## 🤖 工具发现",
    "framework_discovery": "## 🤖 工具发现",
    "conversation_strategy": "## 💬 会话策略",
}

BLACKLIST_KEYWORDS = ["news", "event", "price", "stock"]


class AgentBehaviorWriter:
    """Convert high-quality discoveries to behavior rules"""

    def __init__(self, quality_threshold: float = QUALITY_THRESHOLD):
        self.quality_threshold = quality_threshold
        self.write_log = []
        self._llm_client = None

    def _get_llm_client(self):
        if self._llm_client is None:
            from core.llm_client import LLMClient
            self._llm_client = LLMClient()
        return self._llm_client
    
    def process(self, topic: str, findings: dict, quality: float, sources: list) -> dict:
        """Process exploration results and generate behavior rules"""
        if quality < self.quality_threshold:
            return {"applied": False, "reason": f"quality {quality} < threshold {self.quality_threshold}"}
        
        # Check blacklist
        topic_lower = topic.lower()
        if any(kw in topic_lower for kw in BLACKLIST_KEYWORDS):
            return {"applied": False, "reason": "topic in blacklist"}
        
        discovery_type = self._classify_discovery(topic, findings)
        if not discovery_type:
            return {"applied": False, "reason": "discovery type not actionable"}
        
        rule = self._generate_behavior_rule(topic, findings, sources, discovery_type)
        if not rule:
            return {"applied": False, "reason": "failed to generate behavior rule"}
        
        section = TYPE_TO_SECTION.get(discovery_type, "## 📌 其他规则")
        write_ok = self._append_to_file(section, rule)
        self._sync_to_memory(topic, findings, quality, sources, discovery_type)
        
        if write_ok:
            self.write_log.append({
                "timestamp": datetime.now().isoformat(),
                "topic": topic,
                "section": section,
                "quality": quality
            })
        
        return {
            "applied": write_ok,
            "section": section,
            "rule_generated": rule[:100] + "..." if len(rule) > 100 else rule,
            "trigger_reason": f"type={discovery_type}, quality={quality}",
            "sources": sources[:2]
        }
    
    def _classify_discovery(self, topic: str, findings: dict) -> str | None:
        TYPES = [
            "metacognition_strategy",
            "reasoning_strategy",
            "confidence_rule",
            "self_check_rule",
            "proactive_behavior",
            "tool_discovery",
        ]

        try:
            llm = self._get_llm_client()
            prompt = f"""Classify this exploration finding into exactly ONE type.

Topic: {topic}
Summary: {findings.get('summary', '')[:300]}

Type definitions (choose the BEST match):
- reasoning_strategy: Focus on reasoning steps, chain-of-thought, deliberation, planning algorithms, decision-making processes
- metacognition_strategy: Self-monitoring, self-assessment, confidence calibration, reflection on own thinking, Monitor-Generate-Verify loops
- proactive_behavior: Curiosity-driven exploration, self-initiated actions, anticipatory behavior, novel situation handling
- tool_discovery: New framework, library, SDK, or tool introduction with installation/usage details
- self_check_rule: Verification steps, validation logic, error detection/correction mechanisms
- confidence_rule: Confidence assessment methods, uncertainty quantification, calibration techniques

Output: ONLY the type name, nothing else. Default to "reasoning_strategy" if uncertain."""
            response = llm.chat(prompt).strip()
            if response in TYPES:
                return response
        except Exception as e:
            print(f"[BehaviorWriter] LLM classification failed: {e}")

        topic_lower = topic.lower()
        summary_lower = findings.get("summary", "").lower()

        if any(k in topic_lower for k in [
            "metacognition", "self-monitoring", "self-reflection",
            "self-assessment", "monitor-generate", "self-verification"
        ]):
            return "metacognition_strategy"

        if any(k in topic_lower for k in [
            "reasoning", "planning", "chain-of-thought", "cot", "reflexion"
        ]):
            return "reasoning_strategy"

        if "confidence" in topic_lower or "calibration" in topic_lower:
            return "confidence_rule"

        if any(k in topic_lower for k in ["verification", "self-check", "validate"]):
            return "self_check_rule"

        if any(k in topic_lower for k in ["curiosity", "exploration", "proactive"]):
            return "proactive_behavior"

        if any(k in topic_lower for k in ["framework", "tool", "library", "sdk"]):
            if any(k in summary_lower for k in ["install", "pip", "import", "github"]):
                return "tool_discovery"

        return None
    
    def _generate_behavior_rule(self, topic: str, findings: dict, sources: list, discovery_type: str) -> str:
        """Generate behavior rule markdown"""
        source_ref = ""
        if sources:
            src = sources[0]
            src_name = src.split('/')[-1][:60] if '/' in src else src[:60]
            source_ref = f"\n> 来源：[{src_name}]({src})"
        
        date = datetime.now().strftime("%Y-%m-%d")
        summary = findings.get("summary", "")[:400]
        
        templates = {
            "metacognition_strategy": f"""
### 🪞 {topic}（{date}）

**核心发现**：{summary}...

**行为规则**：
- 遇到多步推理问题，先评估置信度（1-10）
- 置信度 < 6 时，明确告知用户不确定范围
- 给出答案后，检查是否回应了问题所有部分

{source_ref}
""",
            "tool_discovery": f"""
### 🤖 {topic}（{date}）

**简介**：{summary}...

{source_ref}
""",
        }
        
        return templates.get(discovery_type, f"""
### 📌 {topic}（{date}）

**发现**：{summary}...

{source_ref}
""")
    
    def _append_to_file(self, section: str, rule: str) -> bool:
        """Append rule to behavior file"""
        try:
            Path(BEHAVIOR_FILE).parent.mkdir(parents=True, exist_ok=True)
            
            if not Path(BEHAVIOR_FILE).exists():
                header = """# Curious Agent 行为规则

> 由 Agent-Behavior-Writer 自动生成 | 勿手动修改此文件
> R1D3-researcher 通过 memory_search 检索使用

"""
                Path(BEHAVIOR_FILE).write_text(header, encoding="utf-8")
            
            content = Path(BEHAVIOR_FILE).read_text(encoding="utf-8")
            
            # Check for duplicates
            topic_line = rule.strip().split("\n")[0]
            topic_base = topic_line.replace("###", "").strip()
            if topic_base in content:
                return False
            
            # Find section and append
            if section in content:
                content = content.replace(section, section + "\n" + rule)
            else:
                content += "\n" + section + "\n" + rule
            
            Path(BEHAVIOR_FILE).write_text(content, encoding="utf-8")
            return True
            
        except Exception as e:
            print(f"[AgentBehaviorWriter] Failed to write: {e}")
            return False
    
    def _sync_to_memory(self, topic: str, findings: dict, quality: float, sources: list, discovery_type: str):
        """Sync to memory/curious/ with behavior-rule tag"""
        try:
            Path(MEMORY_CURIOUS_DIR).mkdir(parents=True, exist_ok=True)
            
            date = datetime.now().strftime("%Y-%m-%d")
            slug = re.sub(r'[^\w\s-]', '', topic)[:60].strip().replace(' ', '-')
            filename = f"{MEMORY_CURIOUS_DIR}/{date}-{slug}.md"
            
            tags = ["#behavior-rule", f"#{discovery_type}", "#curious-discovery"]
            
            content = f"""# [behavior] {topic}

<!-- memory_search_tags: {','.join(tags)} -->

**好奇心指数**: {quality}
**发现类型**: {discovery_type}
**探索时间**: {date}
**来源**: {sources[0] if sources else 'N/A'}

---

## 行为规则

{findings.get('summary', '')}
"""
            Path(filename).write_text(content, encoding="utf-8")
        except Exception as e:
            print(f"[AgentBehaviorWriter] Memory sync failed: {e}")
