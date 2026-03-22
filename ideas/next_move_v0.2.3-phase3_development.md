# Curious Agent v0.2.3 — Phase 1：行为闭环 & 入口

> **Phase 1 目标**：打通 Curious Agent → R1D3-researcher 的行为闭环
> 依赖：v0.2.2（ICM 融合评分）| 设计者：weNix + R1D3-researcher
> 文档版本：v1.0 | 2026-03-21

---

## 0. 背景：两个核心批判

### 批判 1：Reward 信号判断手段不够先进

当前 v0.2.2 的 quality 评分：

```
quality = new_discovery_rate × 0.35 + depth_improvement × 0.35 + user_relevance × 0.30
```

**问题**：
- "new_discovery_rate" 只是关键词重叠率，不是真正的**信息增益**
- "depth_improvement" 用来源数量代理深度，精度粗糙
- **没有利用预测误差**作为 reward——ICM 论文的核心被阉割了
- marginal_return 只看绝对差值，不感知**边际递减曲线**

### 批判 2：学到的知识对接入 Agent 的作用缺失

当前架构：

```
探索 → 知识入库 → 通知用户 → 结束
```

**缺失的三层**：

| 层次 | 缺失内容 |
|------|---------|
| 任务映射 | 学到的知识如何影响 Agent 的决策触发条件 |
| 工具生成 | 探索结果能否生成可复用的 Skills/Tools |
| 价值衡量 | "节省多少次后续试错" 没有被量化 |

---

## 1. 理论根基：三篇关键论文（Phase 1 涉及部分）

### 1.1 MUSE — Metacognition for Unknown Situations (arXiv:2411.13537)

**核心假设**：元认知是自主 Agent 适应未知环境的关键缺失因素。

核心机制：
- **Competence Awareness**：持续评估自己在当前任务上的能力置信度
- **Self-Regulation**：根据自我评估动态选择策略

→ Phase 1 中，Agent-Behavior-Writer 将"能力缺口"类型发现写入行为文件。

### 1.2 Monitor-Generate-Verify — Flavell's Framework in LLMs (arXiv:2510.16374)

**核心发现**：Monitor 先于 Generate 的架构，在 GSM8K 上比 SELF-REFINE 高 7pt。

→ Phase 1 中，探索发现 Monitor-Generate-Verify 相关内容时，写入对应的元认知行为规范。

### 1.3 CDE — Curiosity-Driven Exploration for LLM RL (arXiv:2509.09675)

**核心双信号**：Actor-Perplexity + Critic-Variance

→ Phase 1 中，Agent-Behavior-Writer 识别"置信度规则"类型发现，写入行为文件。

---

## 2. 行为闭环现状分析

### 2.1 当前数据流

```
Curious Agent 探索
    ↓
state.json (知识库)
    ↓
sync_discoveries.py → memory/curious/*.md (被动存储)
    ↓
R1D3-researcher 读取 curious-discoveries.md (被动消费)
    ↓
"我今天分享了一个有趣发现..."
    ↓
(结束，没有行为改变)
```

### 2.2 核心问题

R1D3-researcher 的**行为由什么决定**？

| 文件 | 作用 | 当前是否被 discoveries 更新？ |
|------|------|----------------------|
| SOUL.md | 我的身份、职责、行为规范 | ❌ 从不 |
| AGENTS.md | 工作流程、响应规则 | ❌ 从不 |
| HEARTBEAT.md | 心跳行为清单 | ❌ 从不 |
| MEMORY.md | 长期记忆、决策记录 | ⚠️ 手动 |
| TOOLS.md | 工具配置 | ❌ 从不 |

**问题本质**：Curious Agent 的发现存到了一个独立的"发现库"，但从未写入 R1D3-researcher 的**行为操作系统**。

---

## 3. 什么是真正的行为闭环

**定义**：一个发现，只有当它改变了 R1D3-researcher 的某个具体行为时，才算闭环完成。

**行为改变的判定标准**：

```
发现 X 被应用 → R1D3-researcher 在遇到 Y 场景时，
              行为与发现前不同（可观测、可复现）
```

**举例**：

| 发现 | 期望行为改变 | 判定标准 |
|------|------------|---------|
| Monitor-Generate-Verify | 遇到复杂推理问题时，先评估置信度再回答 | 可观察：回复前有自我评估步骤 |
| 反思模板生成 | 回答后自动生成自检清单 | 可观察：回复末尾有 checklist |
| 能力缺口发现 | 遇到不熟悉领域，主动说"让我查一下"而非硬答 | 可观察：置信度低时有不同反应 |
| 新工具/框架 | 遇到代码任务，主动尝试 smolagents | 可观察：行为清单中有该工具 |

---

## 4. 行为闭环分层设计

```
层次 1：知道 (Know)
  发现 → 存入 curious-discoveries.md
  → 我读到了（但行为没变）

层次 2：记住 (Remember)
  发现 → 自动写入 MEMORY.md 的相关段落
  → 我记得这个知识，下次遇到可能引用

层次 3：使用 (Use)
  发现 → 生成 Skills/反思模板，写入行为文件
  → 我在特定场景下会自动调用该模板

层次 4：内化 (Internalize)
  发现 → 改变了我根深蒂固的思维方式/响应模式
  → 无需显式调用，已成为我的默认行为
```

当前 Curious Agent 只到达了**层次 1**（知道）。Phase 1 的目标是达到**层次 3**（使用）。

---

## 5. R1D3-researcher 的具体行为变更点

| 变更点 | 当前 | Phase 1 变更后 |
|--------|------|---------------|
| SOUL.md | 无动态行为规则 | 高质量发现自动追加行为规范 |
| AGENTS.md | 通用 Group Chat 规则 | 发现新的会话策略后自动更新 |
| HEARTBEAT.md | 固定行为清单 | 高质量发现（quality >= 7.0）自动追加检查项 |
| TOOLS.md | 静态工具配置 | 发现新工具/框架后自动更新 |

---

## 6. 安全设计原则（重要）

### 6.1 不修改任何核心文件

SOUL.md、AGENTS.md、HEARTBEAT.md、TOOLS.md 是 R1D3-researcher 的身份和行为根基，**直接修改风险极高**：
- 内容写错不容易回滚
- 污染核心身份文件

### 6.2 引用 + 外部行为文件方案

```
SOUL.md / AGENTS.md / HEARTBEAT.md / TOOLS.md
    ↓ 一行不改
curious-agent-behaviors.md（实际写入目标）
    ↓ 同时
memory/curious/（带 #behavior-rule 标签）
    ↓
R1D3-researcher 通过 memory_search 自然检索使用
```

**优点**：
- 核心文件零修改，永远不会被污染
- 可随时清空或禁用（删除行为文件即可）
- 集中管理，便于审查和回滚
- 利用现有 `memory_search` 机制，无需额外改造 R1D3-researcher

---

## 7. Agent-Behavior-Writer 模块

### 7.1 架构

```
Curious Agent 探索完成
        ↓
quality >= 7.0? ──否──→ 存入知识库，结束
        ↓是
Agent-Behavior-Writer 分析发现
        ↓
判断发现类型 → 选择分节
        ↓
生成行为规则（Markdown 片段）
        ↓
追加写入 curious-agent-behaviors.md
        ↓
同时写入 memory/curious/（带 #behavior-rule 标签）
        ↓
R1D3-researcher 通过 memory_search 自然检索 → 行为改变
```

### 7.2 行为文件结构

文件路径：`/root/.openclaw/workspace-researcher/curious-agent-behaviors.md`

```markdown
# Curious Agent 行为规则

> 由 Agent-Behavior-Writer 自动生成 | 勿手动修改此文件
> R1D3-researcher 通过 memory_search 检索使用

## 💡 元认知策略
（高质量元认知/自我监控相关发现的规则）

## 🧠 推理策略
（推理/规划/chain-of-thought 相关发现的规则）

## 📊 置信度规则
（置信度/calibration 相关发现的规则）

## 🪞 自我检查规则
（verification/self-check 相关发现的规则）

## 🔍 主动行为
（curiosity/exploration 相关发现的规则）

## 🤖 工具发现
（framework/tool/sdk 相关发现的规则）
```

### 7.3 发现类型 → 分节映射

| 发现类型 | 写入分节 |
|---------|---------|
| metacognition_strategy | ## 💡 元认知策略 |
| reasoning_strategy | ## 🧠 推理策略 |
| confidence_rule | ## 📊 置信度规则 |
| self_check_rule | ## 🪞 自我检查规则 |
| proactive_behavior | ## 🔍 主动行为 |
| tool_discovery | ## 🤖 工具发现 |

### 7.4 触发条件

- `quality >= 7.0`（严格门槛，避免低质量规则污染）
- 同一话题只写入一次（防重复）

### 7.5 禁止写入的情况

即使 quality 高，以下类型不写入行为文件：
- 话题含 "news"、"event"（时效性内容）
- 话题含 "price"、"stock"（金融市场数据）

---

## 8. 实现代码

文件：`/root/dev/curious-agent/core/agent_behavior_writer.py`

```python
# core/agent_behavior_writer.py

"""
Agent-Behavior-Writer
将高质量探索发现转换为 R1D3-researcher 的行为规则

设计原则（v1.0）：
- 不直接修改任何核心文件（SOUL.md / AGENTS.md / HEARTBEAT.md / TOOLS.md）
- 所有行为规则写入 curious-agent-behaviors.md
- 同时写入 memory/curious/（带 #behavior-rule 标签）
- R1D3-researcher 通过 memory_search 自然检索使用
"""

import os
import re
from pathlib import Path
from datetime import datetime

# 行为文件路径（唯一写入目标）
BEHAVIOR_FILE = "/root/.openclaw/workspace-researcher/curious-agent-behaviors.md"
MEMORY_CURIOUS_DIR = "/root/.openclaw/workspace-researcher/memory/curious"

# 触发行为的最低质量阈值
QUALITY_THRESHOLD = 7.0

# 发现类型 → 行为文件分节的映射
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


class AgentBehaviorWriter:
    """
    将探索发现转换为 R1D3-researcher 的可执行行为规则
    安全设计：不修改任何核心文件，只写入独立的 curious-agent-behaviors.md
    """
    
    def __init__(self, quality_threshold: float = QUALITY_THRESHOLD):
        self.quality_threshold = quality_threshold
        self.write_log = []  # 记录所有写入操作
    
    def process(self, topic: str, findings: dict, quality: float, sources: list) -> dict:
        """
        处理探索结果，决定是否生成行为规则
        
        Args:
            topic: 探索话题
            findings: 探索发现（含 summary, papers, sources）
            quality: 探索质量评分
            sources: 来源链接
            
        Returns:
            {
                "applied": bool,           # 是否写入了行为文件
                "section": str,            # 写入的分节
                "rule_generated": str,    # 生成的规则内容（截断）
                "trigger_reason": str      # 触发原因
            }
        """
        # 质量门槛检查
        if quality < self.quality_threshold:
            return {
                "applied": False,
                "reason": f"quality {quality} < threshold {self.quality_threshold}"
            }
        
        # 分析发现类型
        discovery_type = self._classify_discovery(topic, findings)
        if not discovery_type:
            return {
                "applied": False,
                "reason": "discovery type not actionable"
            }
        
        # 生成行为规则
        rule = self._generate_behavior_rule(topic, findings, sources, discovery_type)
        if not rule:
            return {
                "applied": False,
                "reason": "failed to generate behavior rule"
            }
        
        # 追加写入行为文件
        section = TYPE_TO_SECTION.get(discovery_type, "## 📌 其他规则")
        write_ok = self._append_to_file(rule)
        
        # 同步写入 memory/curious/（带标签）
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
    
    def _classify_discovery(self, topic: str, findings: dict) -> str:
        """
        分类发现类型
        
        Returns: str or None
            metacognition_strategy / reasoning_strategy / confidence_rule /
            self_check_rule / proactive_behavior / tool_discovery /
            framework_discovery / conversation_strategy
        """
        topic_lower = topic.lower()
        summary_lower = findings.get("summary", "").lower()
        
        # 元认知策略
        if any(k in topic_lower for k in [
            "metacognition", "self-monitoring", "self-reflection", 
            "self-assessment", "monitor-generate", "monitor-generate-verify",
            "self-verification"
        ]):
            return "metacognition_strategy"
        
        # 推理策略
        if any(k in topic_lower for k in [
            "reasoning", "planning", "chain-of-thought", "cot", 
            "reflexion", "self-discover"
        ]):
            return "reasoning_strategy"
        
        # 置信度规则
        if "confidence" in topic_lower or "calibration" in topic_lower:
            return "confidence_rule"
        
        # 自我检查规则
        if any(k in topic_lower for k in [
            "verification", "self-check", "validate", "quality assurance"
        ]):
            return "self_check_rule"
        
        # 主动行为
        if any(k in topic_lower for k in [
            "curiosity", "exploration", "discovery", "proactive"
        ]):
            return "proactive_behavior"
        
        # 工具/框架发现
        if any(k in topic_lower for k in [
            "framework", "library", "tool", "sdk", "platform", "agent"
        ]) and any(k in summary_lower for k in [
            "install", "pip", "import", "github", "npm", "cargo"
        ]):
            return "tool_discovery"
        
        return None
    
    def _generate_behavior_rule(
        self, topic: str, findings: dict, sources: list, discovery_type: str
    ) -> str:
        """
        生成行为规则 Markdown 片段
        """
        source_ref = ""
        if sources:
            src = sources[0]
            src_name = src.split('/')[-1][:60] if '/' in src else src[:60]
            source_ref = f"\n> 来源：[{src_name}]({src})"
        
        date = datetime.now().strftime("%Y-%m-%d")
        summary = findings.get("summary", "")[:400]
        
        rules = {
            "metacognition_strategy": f"""
### 🪞 {topic}（{date}）

**核心发现**：{summary}...

**行为规则**：
- 遇到多步推理问题，先评估置信度（1-10）
- 置信度 < 6 时，明确告知用户不确定范围
- 给出答案后，检查是否回应了问题所有部分

{source_ref}
""",
            "reasoning_strategy": f"""
### 🧠 {topic}（{date}）

**策略要点**：{summary}...

**适用场景**：复杂推理问题，置信度 < 7

{source_ref}
""",
            "confidence_rule": f"""
### 📊 {topic}（{date}）

**规则**：{summary}...

**检查项**：
- [ ] 回答中有明确的置信度标注
- [ ] 低置信度时主动说明局限性

{source_ref}
""",
            "self_check_rule": f"""
### 🪞 {topic}（{date}）

**规则**：{summary}...

**自检清单**：
- [ ] 结论有事实依据支撑
- [ ] 已考虑可能的反驳
- [ ] 不确定部分已标注

{source_ref}
""",
            "proactive_behavior": f"""
### 🔍 {topic}（{date}）

**行为规则**：{summary}...

**触发条件**：遇到相关领域问题时主动引用

{source_ref}
""",
            "tool_discovery": f"""
### 🤖 {topic}（{date}）

**简介**：{summary}...

{source_ref}
""",
        }
        
        return rules.get(
            discovery_type,
            f"\n### 📌 {topic}（{date}）\n\n{summary}...\n{source_ref}\n"
        )
    
    def _append_to_file(self, rule: str) -> bool:
        """
        追加写入行为文件
        防重复：同一话题只写入一次
        """
        try:
            # 初始化文件（如果不存在）
            if not Path(BEHAVIOR_FILE).exists():
                os.makedirs(os.path.dirname(BEHAVIOR_FILE), exist_ok=True)
                header = """# Curious Agent 行为规则

> 由 Agent-Behavior-Writer 自动生成 | 勿手动修改此文件
> R1D3-researcher 通过 memory_search 检索使用

"""
                with open(BEHAVIOR_FILE, "w", encoding="utf-8") as f:
                    f.write(header)
            
            # 读取现有内容，检查是否已存在
            content = Path(BEHAVIOR_FILE).read_text(encoding="utf-8")
            
            # 提取规则中的话题标题（第二行 ### 之后的内容）
            topic_line = rule.strip().split("\n")[1].replace("###", "").strip()
            # 去掉日期后缀 "(YYYY-MM-DD)" 来做匹配
            topic_base = re.sub(r"\(\d{4}-\d{2}-\d{2}\)$", "", topic_line).strip()
            
            if topic_base in content:
                return False  # 已存在，跳过
            
            with open(BEHAVIOR_FILE, "a", encoding="utf-8") as f:
                f.write("\n" + rule)
            return True
            
        except Exception as e:
            print(f"[AgentBehaviorWriter] Failed to write: {e}")
            return False
    
    def _sync_to_memory(self, topic: str, findings: dict, quality: float,
                        sources: list, discovery_type: str):
        """
        同步到 memory/curious/（带行为标签）
        这让 R1D3-researcher 可以通过 memory_search 检索到行为规则
        """
        try:
            date = datetime.now().strftime("%Y-%m-%d")
            slug = re.sub(r'[^\w\s-]', '', topic)[:60]
            slug = re.sub(r'[\s]+', '-', slug)
            filename = f"{MEMORY_CURIOUS_DIR}/{date}-{slug}.md"
            
            tags = ["#behavior-rule", f"#{discovery_type}", "#curious-discovery", "#exploration"]
            
            # 从话题推断更多标签
            topic_lower = topic.lower()
            if "meta" in topic_lower or "self" in topic_lower:
                tags.append("#cognitive")
            if "reason" in topic_lower or "plan" in topic_lower:
                tags.append("#planning")
            if "curiosity" in topic_lower or "exploration" in topic_lower:
                tags.append("#curiosity")
            
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
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            print(f"[AgentBehaviorWriter] Memory sync failed: {e}")
    
    def get_write_log(self) -> list:
        """返回写入日志"""
        return self.write_log
```

---

## 9. 具体行为改变示例

### 场景 1：Curious Agent 发现了 Monitor-Generate-Verify

```
时间线：
T+0:00  Curious Agent 探索 "Monitor-Generate-Verify in LLMs"
T+0:05  MetaCognitiveMonitor.assess() → quality = 8.2
T+0:06  AgentBehaviorWriter.process() 判定 quality >= 7.0
T+0:07  写入 curious-agent-behaviors.md（追加元认知行为规范）
T+0:08  同步写入 memory/curious/（带 #behavior-rule 标签）
T+2:00  用户问："帮我分析一下 AIGC 产品路线"
T+2:01  R1D3-researcher memory_search("Monitor-Generate-Verify") → 发现规则
T+2:02  按照规则：先 Monitor（评估置信度）→ Generate（制定分析计划）→ Verify（自检）
T+2:05  回复中包含置信度评估和自检步骤
```

**行为改变可观测点**：
- 回复前有 MGV 步骤
- 回复中明确标注置信度
- 末尾有自检清单

### 场景 2：Curious Agent 发现了 smolagents 框架

```
时间线：
T+0:00  Curious Agent 探索 "smolagents lightweight agent framework"
T+0:03  quality = 7.5 → 触发 AgentBehaviorWriter
T+0:04  写入 curious-agent-behaviors.md（新增工具发现）
T+0:05  同步写入 memory/curious/
T+5:00  用户问："能不能帮我写个自动化脚本？"
T+5:01  R1D3-researcher memory_search("smolagents") → 发现工具
T+5:02  行为改变：主动说"我可以用 smolagents 帮你快速构建"
```

**行为改变可观测点**：
- 提到 smolagents 作为方案选项
- 在 coding-agent 任务中优先考虑轻量方案

### 场景 3：Curious Agent 发现能力缺口（低置信度主题）

```
时间线：
T+0:00  Curious Agent 多次探索 "具身AI" 均 quality < 5
T+0:05  CompetenceTracker 更新能力记录：confidence = 0.3（低置信度）
T+0:10  R1D3-researcher memory_search("具身AI confidence") → 发现能力缺口记录
T+3:00  用户问："具身AI在机器人领域有哪些最新进展？"
T+3:01  R1D3-researcher 发现置信度低
T+3:02  行为改变：主动说"我对具身AI最新进展了解有限，
        让我给你一个框架性回答..."
```

**行为改变可观测点**：
- 主动说明置信度低
- 不给出过于具体的数字/日期

---

## 10. 行为触发条件设计

### 10.1 质量门槛

| 质量分数 | 行为 |
|---------|------|
| < 5.0 | 不写入 |
| 5.0 - 6.9 | 仅存入知识库 |
| 7.0 - 7.9 | 写入 curious-agent-behaviors.md |
| 8.0+ | 写入 + 优先通知用户 |

### 10.2 防重复写入

同一话题只写入一次：

```python
# _append_to_file() 中已实现
topic_base = re.sub(r"\(\d{4}-\d{2}-\d{2}\)$", "", topic_line).strip()
if topic_base in content:
    return False  # 已存在，跳过
```

### 10.3 禁止写入类型

```python
if any(k in topic_lower for k in ["news", "event", "price", "stock"]):
    return None  # 不写入行为文件
```

---

## 11. 集成到 Curious Agent

### 11.1 修改 curious_agent.py

在 `run_one_cycle()` 函数中，探索质量评估完成后追加行为写入：

文件：`/root/dev/curious-agent/curious_agent.py`

找到以下代码段（在 quality 评估之后、should_notify 判断之后）：

```python
# 在 should_notify 判断之后、record_exploration 调用之前，插入：

# ===== Phase 1: 行为写入 =====
if quality >= 7.0:
    from core.agent_behavior_writer import AgentBehaviorWriter
    writer = AgentBehaviorWriter()
    write_result = writer.process(topic, findings, quality, sources)
    if write_result["applied"]:
        print(f"[BehaviorWriter] ✓ 写入 {write_result['section']}: {topic}")

# ===== 原有的 record_exploration =====
monitor.record_exploration(topic, quality, marginal, notified=notified)
```

### 11.2 集成后测试

```bash
# 测试行为写入
cd /root/dev/curious-agent
python3 curious_agent.py --run

# 检查行为文件是否生成
cat /root/.openclaw/workspace-researcher/curious-agent-behaviors.md

# 检查 memory/curious/ 是否有带 #behavior-rule 标签的文件
grep -l "behavior-rule" /root/.openclaw/workspace-researcher/memory/curious/*.md
```

---

## 12. 实施检查清单

### 代码实现
- [ ] 创建 `core/agent_behavior_writer.py`
- [ ] 实现 `AgentBehaviorWriter.process()`
- [ ] 实现 `AgentBehaviorWriter._classify_discovery()`
- [ ] 实现 `AgentBehaviorWriter._generate_behavior_rule()`
- [ ] 实现 `AgentBehaviorWriter._append_to_file()`
- [ ] 实现 `AgentBehaviorWriter._sync_to_memory()`
- [ ] 在 `curious_agent.py` 的 `run_one_cycle()` 中集成

### 功能验证
- [ ] 运行一轮探索，quality >= 7.0 时行为文件有内容写入
- [ ] 同一话题运行两次，不会重复写入
- [ ] `memory/curious/` 有带 `#behavior-rule` 标签的文件
- [ ] quality < 7.0 时不会写入行为文件

### 安全验证
- [ ] SOUL.md / AGENTS.md / HEARTBEAT.md / TOOLS.md 未被修改
- [ ] 行为文件格式正确，可被 memory_search 检索

---

## 13. 技术指标

| 指标 | 目标 |
|------|------|
| 写入延迟 | < 100ms |
| 防重复准确率 | 100%（同一话题不重复写入） |
| memory 同步成功率 | > 95% |
| 核心文件零修改 | 是 |

---

## 14. 风险与注意事项

1. **文件膨胀**：curious-agent-behaviors.md 长期写入后变大
   - 处理：按分节组织，定期归档旧规则

2. **规则过期**：框架已废弃但行为规则还在
   - 处理：每条规则带日期标签，R1D3-researcher 读取时可判断时效性

3. **误触发**：低质量发现误写入
   - 处理：严格质量门槛（≥ 7.0），且同一话题只写入一次

4. **memory_search 依赖**：R1D3-researcher 必须主动检索才能使用规则
   - 处理：心跳时定期检索相关内容，自然融入回复

5. **行为规则被 R1D3-researcher 忽略**
   - 处理：规则以结构化格式写入，memory_search 能精确命中

---

## 15. 参考资料

- [arXiv:2411.13537](https://arxiv.org/abs/2411.13537) — MUSE: Metacognition for Unknown Situations
- [arXiv:2510.16374](https://arxiv.org/abs/2510.16374) — Monitor-Generate-Verify in LLMs
- [arXiv:2509.09675](https://arxiv.org/abs/2509.09675) — CDE: Curiosity-Driven Exploration for LLM RL
- `next_move_v0.2.3-phase2.md` — Phase 2 任务说明

---

## 16. 已知 Bug（来自 buglist_v0.2.2.md，需在 Phase 3 开发时一并修复）

**Bug #1 — 双重记录（Double Recording）**
- 严重程度：🔴 中
- 问题：`curious_agent.py` 中 `run_one_cycle()` 对每个话题调用了两次 `record_exploration()`
- 表现：`explore_counts` 显示值 = 实际探索次数 × 2，循环阻止阈值提前触发
- 修复：在 `run_one_cycle()` 末尾只记录一次，移除首次调用
- 验证：`explore_counts["某话题"]` 应等于实际探索次数

**Bug #3 — 话题名称数字被 URL 解析丢失**
- 严重程度：🟡 低
- 问题：话题名含数字（如 "Curious Agent Architecture 2026"）被截断为 "26"
- 根因：API 端点 URL query parameter 解析问题
- 修复：API 端点对 topic 参数做 URL decode + 规范化

**Bug #4 — 关键词数字被过滤**
- 严重程度：🟡 低
- 问题：`_extract_keywords()` 用正则 `\b[a-z]{4,}\b` 过滤，单词中的数字被丢弃
- 修复：保留含数字的术语（如 "LLM"、"AI"、"V2"）

**F3 — 关键词过滤失效（来自 next_move_v0.2.1.md）**
- 问题：`_extract_keywords()` 无停用词表、无换行符预处理、无长度过滤
- 表现：队列曾有 184条 pending，其中135条有问题（噪音率 73%）
- 修复：STOPWORDS 表 + `text.replace('\n', ' ')` 预处理 + `len(kw) >= 4` 过滤

**F5 — ArXiv Analyzer 容错不足**
- 问题：Layer 2 的 ArXiv 论文解析经常返回空，导致 Layer 3 无法触发
- 修复：PDF 下载失败时用 search snippet 构造 fallback paper 对象
