# next_move_v0.2.5 - 自主闭环 + Hook 系统 + MUSE 框架

> **版本关系**：v0.2.5 是 v0.2.4 的能力升级，依赖 v0.2.4 mission 机制完成后的实战验证  
> **前置条件**：v0.2.4 mission 验证机制已上线并经过实战检验

> **核心理念**：v0.2.4 解决了"探索有终点"，v0.2.5 要解决"探索方向由 R1D3 主导"

---

## 0. 背景与前置验证

以下内容从 v0.2.4 移出，需要先完成的前置工作：

| 内容 | 前置验证任务 |
|------|------------|
| OpenClaw Hook 系统 | 确认 `before_prompt_build` hook 存在且接口已知 |
| MUSE 框架 | 阅读 arxiv:2411.13537，验证是否适合当前架构 |
| 完整状态机 | v0.2.4 mission 机制实战后的反馈 |

**v0.2.5 的开发策略**：先用 v0.2.4 的实战结果指导设计，不要在实战前过度设计。

---

## 1. OpenClaw Hook 系统验证（Section 6.4 移入）

> **优先级**：P0，在开始 v0.2.5 开发前必须完成验证

**待验证项**：
- [ ] OpenClaw 是否支持 `before_prompt_build` hook？
- [ ] hook 的接口格式（输入、输出、注册方式）是什么？
- [ ] hook 执行时机（每次 prompt 构建前？特定事件触发？）
- [ ] hook 的权限模型（哪些数据可以访问/修改）？

**验证方式**：
```bash
# 1. 查看 OpenClaw 文档
ls /root/.openclaw/workspace-researcher/docs/
cat /root/.openclaw/workspace-researcher/docs/hooks.md 2>/dev/null

# 2. 查看 OpenClaw 配置
cat /root/.openclaw/openclaw.json 2>/dev/null | grep -i hook

# 3. 搜索源码
grep -rn "before_prompt_build\|hook" /root/.nvm/versions/node/v24.13.1/lib/node_modules/openclaw/ 2>/dev/null | head -20
```

---

## 2. MUSE 框架研究（Section 6.6 移入）

> **优先级**：P0，在开始 v0.2.5 开发前必须完成阅读

**论文**：[arxiv:2411.13537](https://arxiv.org/abs/2411.13537) - MUSE: Metacognition for Unknown Situations and Environments

**阅读目标**：
- [ ] MUSE 核心机制是什么？
- [ ] 和当前 R1D3 的元认知监控有什么重叠？
- [ ] MUSE 的"能力边界识别"是否适合作为 Critic Agent 的核心？
- [ ] MUSE 的实现复杂度如何？能否在 v0.2.5 中简化集成？

**阅读输出**：在 `methodology/MUSE-research.md` 中记录结论。

---

## 3. R1D3 审视-反思-指令 自主闭环（Section 9 移入，简化版）

> **基于 v0.2.4 实战后的简化设计**

### 3.1 状态机（简化版）

```
IDLE → EXPLORING → REVIEWING → DIRECTING → (EXPLORING) → COMPLETED
```

**vs v0.2.4 设计的变化**：
- 不做完整状态持久化，用简单规则驱动
- REVIEWING 和 DIRECTING 合并为一个"评估决策"步骤
- 不需要复杂的状态机框架，用 if-else 规则替代

### 3.2 简化评估逻辑

```python
def r1d3_simple_review(findings, topic):
    """
    简化版 R1D3 审视
    核心：判断探索结果是否"足够完整"
    """
    gaps = identify_gaps(findings, topic)
    
    if not gaps:
        return {"action": "complete", "reason": "无缺口"}
    
    if len(gaps) <= 2:
        return {"action": "direct", "gaps": gaps}
    
    return {"action": "continue", "gaps": gaps}
```

### 3.3 缺口类型（保留，简化识别算法）

| 缺口类型 | 应对策略 |
|---------|---------|
| `surface` | 深入探索 |
| `depth` | 补充实践/代码 |
| `connection` | 补充对比/关联 |
| `correction` | 修改方向 |

---

## 4. 功能区接入标准范式（Section 8 移入）

> **基于 v0.2.4 实战后抽象**

v0.2.4 是第一个功能区接入案例，用完后的反思：

**验证点**：
- [ ] Curious Agent 可以独立运行/测试？
- [ ] 关闭 Curious Agent 不影响 R1D3 核心？
- [ ] 接口是否足够标准，其他功能区可复用？
- [ ] 全链路是否可观测？

**标准范式输出**：如果 v0.2.4 通过验证，将接口规范写入 `methodology/agent-integration-pattern.md`

---

## 5. OpenClaw Hook 实时注入设计（如果 hook 可用）

如果 Section 1 的验证通过，设计：

```
 Curious Agent 发现新知识
        ↓
 通过 hook 注册到 R1D3 prompt
        ↓
 实时注入到当前会话 context
        ↓
 R1D3 立即感知 ← 关键升级！
```

**Hook 接口设计**（待验证后补充）：

```python
# 注册 hook（示例，真实接口待确认）
def register_curious_agent_hook():
    openclaw.register_hook(
        name="curious_agent_context_inject",
        event="before_prompt_build",
        handler=inject_latest_findings
    )
```

---

## 6. R1D3 ↔ Curious Agent 指令协议（简化版）

基于 v0.2.4 实战结果，设计简化指令格式：

```python
class ExplorationDirective:
    mission_id: str
    directive: str          # 自然语言指令
    focus_areas: list[str]  # 重点方向
    success_criteria: str   # 这次探索的验收标准
```

**消息格式**（轻量版）：
```
R1D3 → Curious Agent:
  {"type": "directive", "directive": "继续探索 X，重点关注 Y"}

Curious Agent → R1D3:
  {"type": "findings", "findings": [...], "status": "completed"}
```

---

## 7. 不纳入 v0.2.5 的内容

- 多任务并探索
- 自动生成 `success_criteria`
- 跨 topic 技能迁移
- 完整 MUSE 框架（如果论文结论不适合，简化为"能力边界识别"即可）
- 复杂状态机（用简化规则替代）

---

## 8. 实现优先级

| 优先级 | 任务 | 前置条件 |
|-------|------|---------|
| P0 | 验证 OpenClaw Hook 系统 | 独立完成，不依赖 v0.2.4 |
| P0 | 阅读 MUSE 论文 | 独立完成，不依赖 v0.2.4 |
| P1 | 基于 v0.2.4 实战结果简化状态机 | v0.2.4 已上线 |
| P1 | 实现 R1D3 简化审视逻辑 | v0.2.4 findings 结构确认 |
| P2 | OpenClaw Hook 实时注入（如果 hook 可用） | Section 1 验证通过 |
| P3 | 功能区接入标准范式抽象 | v0.2.4 实战验证通过 |

---

## 9. 战略意义

v0.2.5 的目标是让 R1D3 从"探索结果的被动接收者"变成"探索方向的主动决策者"。

**但这个目标需要 v0.2.4 的实战验证后才能准确设计**——不要在不知道 v0.2.4 实战效果的情况下过度设计。

**开发节奏**：v0.2.4 上线 → 实战一段时间 → 基于反馈设计 v0.2.5
