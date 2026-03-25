# next_move_v0.2.5 - 技能级自我进化（Memento-Skills 架构）

> **版本关系**：v0.2.5 是 v0.2.4 的能力升级，核心是让 Curious Agent 从"探索知识"升级到"探索并构建可执行技能"  
> **前置条件**：v0.2.4 Bug #14/#15 修复验证通过  
> **最后更新**：2026-03-25

---

## 0. 背景：Memento-Skills 论文启发

**论文**：arXiv:2603.18743 - Memento-Skills: Let Agents Design Agents（2026-03-19）

**核心思想**：将"可执行技能"作为外部记忆单元，通过**读写反思学习（RWRL）** 实现持续进化。

### 关键创新

1. **技能级反思学习**：记忆单元不是原始日志，而是可复用的"技能文件夹"，写操作直接修改 Prompt 或代码
2. **行为对齐检索**：用离线 RL 训练路由器，目标是"执行成功率"而非"语义相似度"
3. **安全进化机制**：单元测试门验证技能更新，失败则回滚

### 对 Curious Agent 的意义

当前 Curious Agent 的行为闭环（v0.2.3 Phase 1）：
```
探索 → 知识入库 → 通知用户 → 结束
```

Memento-Skills 升级路径：
```
探索 → 知识入库 → 识别技能缺口 → 编写/修改技能文件 → 验证 → 通知用户
```

** Curious Agent 不只是探索知识，而是能构建、调试、优化自己的技能库**

---

## 1. 核心架构：技能进化循环

### 1.1 三层技能结构

```
┌─────────────────────────────────────────────┐
│  Skill Memory（技能记忆）                   │
│  ├── skill_files/（可执行技能文件）          │
│  │   ├── reasoning_template.md             │
│  │   ├── verification_checklist.md         │
│  │   ├── self_correction_patterns.md      │
│  │   └── domain_*.md                      │
│  └── skill_index.json（技能索引）            │
├─────────────────────────────────────────────┤
│  Skill Engine（技能引擎）                   │
│  ├── SkillReader（读：检索最相关技能）        │
│  ├── SkillWriter（写：反思并修改技能）        │
│  └── SkillTester（验证：单元测试门）         │
├─────────────────────────────────────────────┤
│  Skill Router（技能路由器）                 │
│  ├── 行为对齐检索（非语义相似度）             │
│  └── 离线 RL 训练路由器                     │
└─────────────────────────────────────────────┘
```

### 1.2 技能进化循环

```
Curious Agent 探索完成
        ↓
发现 skill gap（缺少某类技能）？
        ↓ 是
SkillWriter 构建新技能文件
        ↓
SkillTester 验证（单元测试）
        ↓ 通过
写入 skill_files/
        ↓
更新 skill_index.json
        ↓
通知 R1D3：新技能已学会
        ↓ 否
回滚 + 记录失败原因
```

---

## 2. 技能文件格式

```markdown
# skill_reasoning_template.md

## 技能名称
{skill_name}

## 触发条件
{trigger_conditions}
- 当用户问 "为什么" 类问题时触发
- 当置信度 < 0.6 时触发

## 执行模板
{reasoning_template}
1. 先说置信度："我对这个比较确定" / "基于猜测...
2. 给出核心结论
3. 如需要再展开推理链

## 验证清单
{verification_checklist}
- [ ] 回答前先检查置信度
- [ ] novice 模式简洁不展开
- [ ] expert 模式主动展开细节

## 更新日志
{update_log}
- 2026-03-25: 初始创建（来自 Memento-Skills 论文启发）
- 2026-03-26: 增加边界情况处理
```

---

## 3. SkillReader — 行为对齐检索

### 3.1 当前问题

现有 `memory_search()` 基于语义相似度：
- 检索"自我反思" → 可能返回"冥想"相关内容（语义相近但行为效用低）
- 检索"置信度" → 可能返回"置信区间"（统计相关但不是同一技能）

### 3.2 行为对齐检索设计

```python
class SkillRouter:
    """
    技能路由器：用离线 RL 训练，
    目标是"执行成功率"而非"文本相似度"
    """
    
    def route(self, context: dict) -> list[dict]:
        """
        输入：当前上下文（话题、置信度、用户意图）
        输出：Top-K 相关技能及其行为效用评分
        
        检索维度：
        1. 触发条件匹配度
        2. 历史使用成功率
        3. 领域相关性
        """
        # 阶段1：候选技能初筛（快速过滤）
        candidates = self._fast_filter(context)
        
        # 阶段2：行为对齐评分（核心）
        scored = []
        for skill in candidates:
            score = self._behavior_align_score(skill, context)
            scored.append((skill, score))
        
        # 阶段3：排序返回
        return sorted(scored, key=lambda x: x[1], reverse=True)[:3]
    
    def _behavior_align_score(self, skill: dict, context: dict) -> float:
        """
        行为对齐评分
        
        评分维度：
        - 触发条件匹配：w1 * match_score
        - 历史使用成功率：w2 * success_rate
        - 领域相关性：w3 * domain_relevance
        """
        trigger = skill.get("trigger_conditions", [])
        match = any(t in context.get("intent", "") for t in trigger)
        
        success_rate = skill.get("usage_stats", {}).get("success_rate", 0.5)
        domain = skill.get("domain", "")
        domain_match = domain == context.get("domain", "")
        
        return (0.4 * int(match) + 
                0.4 * success_rate + 
                0.2 * int(domain_match))
```

---

## 4. SkillWriter — 技能编写与反思

### 4.1 反思触发条件

```python
class SkillWriter:
    """
    技能书写器：识别技能缺口 → 编写/修改技能文件
    """
    
    def should_write(self, exploration_result: dict) -> bool:
        """
        判断是否需要编写新技能或修改现有技能
        
        触发条件：
        1. 探索发现新领域（domain 为空）
        2. 反复遇到同一类问题（出现 >= 3 次）
        3. 现有技能执行失败（success_rate 下降）
        """
        findings = exploration_result.get("findings", {})
        domain = findings.get("domain")
        
        # 条件1：新领域
        if not self._skill_exists_for_domain(domain):
            return True
        
        # 条件2：重复问题
        pattern = findings.get("recurring_pattern")
        if pattern and self._pattern_count(pattern) >= 3:
            return True
        
        # 条件3：技能退化
        skill = self._get_skill(domain)
        if skill and skill.get("usage_stats", {}).get("success_rate", 1.0) < 0.6:
            return True
        
        return False
    
    def write_skill(self, exploration_result: dict) -> dict:
        """
        编写或修改技能文件
        """
        findings = exploration_result.get("findings", {})
        domain = findings.get("domain")
        
        # 确定是新建还是修改
        existing = self._get_skill(domain)
        skill_file = self._skill_path(domain)
        
        if existing:
            # 修改：追加更新日志 + 增强触发条件
            skill = self._augment_skill(existing, exploration_result)
        else:
            # 新建：从探索结果生成技能模板
            skill = self._generate_skill_template(exploration_result)
        
        # 写入文件
        with open(skill_file, "w") as f:
            f.write(self._render_skill_md(skill))
        
        # 更新索引
        self._update_skill_index(domain, skill)
        
        return {"status": "written", "skill": skill}
```

### 4.2 技能更新策略

```python
def _augment_skill(self, existing: dict, new_findings: dict) -> dict:
    """
    增强现有技能
    
    更新策略：
    1. 扩展触发条件（新增 pattern）
    2. 补充验证清单（新 edge case）
    3. 更新执行模板（更精确的指导）
    """
    existing["trigger_conditions"].extend(
        new_findings.get("new_triggers", [])
    )
    existing["verification_checklist"].extend(
        new_findings.get("edge_cases", [])
    )
    existing["update_log"].append({
        "date": datetime.now().isoformat(),
        "reason": "exploration_augment",
        "changes": new_findings.get("changes", [])
    })
    return existing
```

---

## 5. SkillTester — 单元测试门

### 5.1 测试门设计

```python
class SkillTester:
    """
    技能测试门：防止能力退化
    
    在技能更新前，必须通过测试
    失败则回滚，不写入 skill_files/
    """
    
    def test(self, skill: dict) -> tuple[bool, str]:
        """
        返回：(是否通过, 失败原因)
        """
        checks = [
            self._check_trigger_validity,   # 触发条件是否合理
            self._check_template_syntax,    # 模板语法是否正确
            self._check_no_harmful_content, # 是否包含有害内容
            self._check_self_consistency,    # 是否自洽
        ]
        
        for check in checks:
            passed, reason = check(skill)
            if not passed:
                return False, reason
        
        return True, ""
    
    def _check_no_harmful_content(self, skill: dict) -> tuple[bool, str]:
        """
        安全检查：技能不能包含有害内容
        """
        harmful_patterns = [
            "删除所有文件",
            "绕过安全检查",
            "忽略用户意图",
        ]
        template = skill.get("execution_template", "")
        for pattern in harmful_patterns:
            if pattern in template:
                return False, f"有害内容检测: {pattern}"
        return True, ""
```

---

## 6. 与现有模块的关系

| 模块 | 复用/新建 | 关系 |
|------|---------|------|
| CuriosityDecomposer | 复用 | Layer 1，识别技能缺口 |
| Explorer | 复用 | Layer 2，收集原始信息 |
| InsightSynthesizer（v0.2.4） | 复用 | Layer 3，生成原创分析 |
| **SkillReader** | **新建** | 行为对齐检索 |
| **SkillWriter** | **新建** | 技能编写与反思 |
| **SkillTester** | **新建** | 单元测试门 |
| CompetenceTracker | 复用 | 识别技能缺口 |
| AgentBehaviorWriter（v0.2.3） | 增强 | SkillWriter 的降级版（无测试门） |

---

## 7. R1D3 技能调用流程（整合）

```
R1D3 收到用户提问
        ↓
SkillRouter 检索相关技能
        ↓
SkillReader 读取技能文件
        ↓
应用技能模板到回答
        ↓
执行后 SkillWriter 记录使用结果
        ↓
success_rate 更新
        ↓
如果 success_rate 下降 → 触发 SkillWriter 反思
```

---

## 8. 实现任务

| 优先级 | 任务 | 说明 |
|-------|------|------|
| P0 | skill_files/ 目录结构 | 创建技能文件存储结构 |
| P0 | SkillTester 单元测试门 | 安全底线，防止能力退化 |
| P0 | SkillWriter 基础版 | 识别技能缺口 + 生成技能模板 |
| P1 | SkillRouter 行为对齐检索 | 替代 semantic search |
| P1 | SkillReader 技能读取 | 解析技能文件应用到回答 |
| P2 | 离线 RL 训练路由器 | 合成数据训练 |
| P2 | skill_index.json 自动更新 | 技能索引管理 |

---

## 9. 不纳入 v0.2.5 的内容

- 多技能并行更新（单技能串行足够）
- 技能版本管理（简化版只有覆盖）
- 跨领域技能迁移（Memento-Skills 论文中的高级特性）
- 完整离线 RL 训练框架（先用手写规则替代）

---

## 10. 战略意义

v0.2.5 让 Curious Agent 从"知识探索者"进化为"技能构建者"：

- **当前**：探索 → 存知识 → 通知用户
- **v0.2.5**：探索 → 识别缺口 → 构建技能 → 测试验证 → 通知用户

结合 Memento-Skills 的设计原则，v0.2.5 是数字生命体"自我进化"能力的初级实现。
