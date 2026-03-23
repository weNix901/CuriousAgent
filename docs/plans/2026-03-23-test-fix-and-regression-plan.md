# Curious Agent v0.2.3 测试修复与回归测试计划

> **日期**: 2026-03-23  
> **版本**: v0.2.3  
> **测试状态**: 287/320 通过 (89.7%), 33 失败  

---

## 一、当前测试状况分析

### 1.1 测试统计

| 类别 | 数量 | 占比 |
|------|------|------|
| **总测试数** | 320 | 100% |
| **通过** | 287 | 89.7% |
| **失败** | 33 | 10.3% |
| **跳过** | 0 | 0% |

### 1.2 测试文件分布

```
tests/
├── core/                          # 核心模块测试 (66 tests)
│   ├── providers/                 # Provider 测试 (4 tests)
│   │   ├── test_bocha_provider.py (2 tests) ✅
│   │   └── test_serper_provider.py (2 tests) ✅
│   ├── test_agent_behavior_writer.py (6 tests) ✅
│   ├── test_competence_tracker.py (4 tests) ✅
│   ├── test_curiosity_decomposer.py (5 tests) ⚠️
│   ├── test_exceptions.py (2 tests) ✅
│   ├── test_knowledge_graph_children.py (3 tests) ✅
│   ├── test_provider_heatmap.py (3 tests) ✅
│   ├── test_provider_registry.py (2 tests) ✅
│   ├── test_quality_gate.py (5 tests) ✅
│   ├── test_quality_v2.py (4 tests) ✅
│   └── test_three_phase_explorer.py (3 tests) ✅
├── test_api_complete.py (25 tests) ✅
├── test_api_trigger.py (3 tests) ✅
├── test_arxiv_analyzer.py (10 tests) ✅
├── test_auto_queue.py (17 tests) ⚠️ 7 failed
├── test_cli.py (5 tests) ⚠️ 4 failed
├── test_curiosity_engine.py (67 tests) ⚠️ 12 failed
├── test_e2e.py (20 tests) ⚠️ 5 failed
├── test_event_bus.py (8 tests) ✅
├── test_explorer_layers.py (7 tests) ✅
├── test_integration.py (15 tests) ✅
├── test_intrinsic_scorer.py (22 tests) ✅
├── test_knowledge_graph.py (45 tests) ✅
├── test_llm_client.py (13 tests) ⚠️ 8 failed
├── test_llm_manager.py (4 tests) ✅
├── test_meta_cognitive_controller.py (17 tests) ✅
├── test_meta_cognitive_monitor.py (23 tests) ✅
└── test_phase3_integration.py (3 tests) ✅
```

**图例**: ✅ 全部通过 | ⚠️ 部分失败

---

## 二、失败测试分类与根因分析

### 2.1 关键问题分类

#### 🔴 Category A: 代码缺陷导致的失败 (18 tests)

**问题 1: CuriosityDecomposer fallback 分支数据不一致**
- **失败测试**: 18 tests (所有调用 `run_one_cycle` 的测试)
- **错误信息**: `KeyError: 'sub_topic'`
- **位置**: `curious_agent.py:88`
- **根因**: 
  ```python
  # _verify_single 方法中，当没有启用 provider 时：
  if not enabled:
      return {
          "candidate": candidate,  # ❌ 缺少 sub_topic
          "provider_results": {},
          ...
      }
  
  # 而有 provider 时返回：
  return {
      "sub_topic": candidate,     # ✅ 有 sub_topic
      "candidate": candidate,
      ...
  }
  ```
- **修复方案**: 统一返回数据结构，确保 fallback 分支也有 `sub_topic`

**问题 2: 关键词提取逻辑变化**
- **失败测试**: `test_curiosity_engine.py::TestExtractKeywords::test_extract_keywords_finds_capitalized_phrases`
- **错误信息**: `AssertionError: assert 'Transformer' in ['Transformer Attention', 'Self', 'Reflection Mechanisms']`
- **根因**: `_extract_keywords` 方法现在返回完整短语而非单个单词
- **修复方案**: 更新测试期望或修改实现逻辑

#### 🟡 Category B: 测试环境配置问题 (10 tests)

**问题 3: LLM Client API 配置硬编码**
- **失败测试**: 8 tests in `test_llm_client.py`
- **错误信息**: 
  - `AssertionError: assert 'ark-code-latest' == 'minimax-m2.7'`
  - `AssertionError: assert 'Bearer 5f648...' == 'Bearer test-api-key'`
  - `TypeError: string indices must be integers`
- **根因**: 测试硬编码了模型名称和 API key，与实际环境变量配置不匹配
- **修复方案**: 
  - 使用 mocking 替代真实 API 调用
  - 或在测试中动态读取环境变量

**问题 4: 数据结构变化未同步到测试**
- **失败测试**: `test_curiosity_engine.py` 中的部分测试
- **错误信息**: `KeyError: 'knowledge'`
- **根因**: `curiosity_engine.py:168` 访问 `state["knowledge"]`，但 state 结构可能已变化
- **修复方案**: 检查 state 结构变化，更新测试数据

#### 🟠 Category C: 功能行为变化 (5 tests)

**问题 5: Auto Queue 行为变化**
- **失败测试**: 6 tests in `test_auto_queue.py`
- **错误信息**: `assert count == X` (期望添加 X 个，实际添加 0 个)
- **根因**: `auto_queue_topics` 方法的行为在 v0.2.3 中可能已改变
- **修复方案**: 检查实现逻辑，确认是 bug 还是预期行为变化

**问题 6: E2E 测试环境问题**
- **失败测试**: 5 tests in `test_e2e.py`
- **根因**: E2E 测试需要完整的系统状态和数据，测试环境缺少必要的 mock
- **修复方案**: 增强测试 isolation，添加必要的 fixtures

---

## 三、详细修复计划

### Phase 1: 修复关键代码缺陷 (优先级: 🔴 最高)

#### Task 1.1: 修复 CuriosityDecomposer 数据不一致
```python
# 文件: core/curiosity_decomposer.py
# 位置: _verify_single 方法 (第133-146行)

# 当前代码 (有bug):
if not enabled:
    return {
        "candidate": candidate,
        "provider_results": {},
        "total_count": 0,
        "provider_count": 0,
        "signal_strength": "unknown",
        "verified": True
    }

# 修复后:
if not enabled:
    return {
        "sub_topic": candidate,      # ✅ 添加缺失的字段
        "candidate": candidate,
        "provider_results": {},
        "total_count": 0,
        "provider_count": 0,
        "signal_strength": "unknown",
        "verified": True
    }
```

**影响**: 修复 18 个失败的测试  
**预计时间**: 5 分钟  
**验证**: `pytest tests/test_cli.py tests/test_auto_queue.py -v`

---

#### Task 1.2: 修复 curious_agent.py 中的 field access
```python
# 文件: curious_agent.py
# 位置: 第 88 行

# 当前代码 (有风险):
best = max(subtopics, key=lambda x: x.get("total_count", 0))
explore_topic = best["sub_topic"]  # 可能 KeyError

# 修复后 (使用 .get() 方法):
explore_topic = best.get("sub_topic", best.get("candidate", topic))
```

**影响**: 增强健壮性，防止 future bugs  
**预计时间**: 5 分钟

---

### Phase 2: 修复测试环境问题 (优先级: 🟡 高)

#### Task 2.1: 重构 LLM Client 测试
```python
# 文件: tests/test_llm_client.py

# 策略: 使用 unittest.mock 替代真实 API 调用
from unittest.mock import Mock, patch

@patch.dict(os.environ, {"ARK_API_KEY": "test-api-key"})
@patch("core.llm_client.requests.post")
def test_client_initialization_with_api_key(self, mock_post):
    # 测试逻辑...
    pass
```

**修复内容**:
1. Mock 所有外部 API 调用
2. 不要硬编码模型名称，使用环境变量或 mock
3. 修复 `TypeError: string indices must be integers` (返回类型错误)

**影响**: 修复 8 个失败的测试  
**预计时间**: 30 分钟

---

#### Task 2.2: 修复 Curiosity Engine 测试数据
```python
# 文件: tests/test_curiosity_engine.py

# 检查点:
# 1. state 数据结构是否匹配最新实现
# 2. _extract_keywords 的期望输出是否需要更新
# 3. add_curiosity 的返回值检查
```

**影响**: 修复 12 个失败的测试  
**预计时间**: 45 分钟

---

### Phase 3: 修复行为变化相关的测试 (优先级: 🟠 中)

#### Task 3.1: 分析 Auto Queue 行为
```python
# 需要检查:
# 1. auto_queue_topics 方法的当前实现
# 2. 测试期望的行为是否仍然有效
# 3. 决定: 修复代码 或 更新测试期望
```

**影响**: 修复 6 个失败的测试  
**预计时间**: 30 分钟

---

#### Task 3.2: 增强 E2E 测试的稳定性
```python
# 策略:
# 1. 使用 pytest fixtures 提供隔离的测试数据
# 2. Mock 外部依赖 (搜索 API, LLM API)
# 3. 添加 setUp/tearDown 清理状态
```

**影响**: 修复 5 个失败的测试  
**预计时间**: 60 分钟

---

### Phase 4: 补充缺失的测试 (优先级: 🟢 低)

#### Task 4.1: 为核心模块添加边界测试

| 模块 | 当前覆盖率 | 目标 | 需补充的测试 |
|------|-----------|------|-------------|
| `curiosity_decomposer.py` | 85% | 95% | 异常处理、空输入、边界条件 |
| `agent_behavior_writer.py` | 75% | 90% | 文件写入失败、格式错误 |
| `competence_tracker.py` | 80% | 95% | 并发更新、数据损坏恢复 |
| `quality_v2.py` | 70% | 90% | LLM 调用失败 fallback |

**预计时间**: 2 小时

---

#### Task 4.2: 添加集成测试
```python
# 建议添加:
# 1. 完整的 Phase 1/2/3 流程集成测试
# 2. ProviderRegistry 动态注册测试
# 3. EventBus 事件链测试
# 4. 错误恢复和重试机制测试
```

**预计时间**: 1.5 小时

---

## 四、回归测试方案

### 4.1 回归测试策略

```
Level 1: 单元测试 (Unit Tests)
├── 每个函数/方法的独立测试
├── Mock 所有外部依赖
└── 目标: 100% 代码覆盖率

Level 2: 集成测试 (Integration Tests)
├── 模块间的交互测试
├── 使用测试数据库/隔离环境
└── 目标: 核心流程 100% 覆盖

Level 3: 端到端测试 (E2E Tests)
├── 完整用户场景测试
├── 接近生产环境的配置
└── 目标: 主流程通过

Level 4: 性能测试 (Performance Tests)
├── 大规模数据下的性能
├── 内存泄漏检测
└── 目标: 响应时间 < 5s
```

### 4.2 回归测试执行计划

#### 日常开发 (每次 commit 前)
```bash
# 快速反馈 (30s)
pytest tests/core/ -x -q

# 完整单元测试 (2min)
pytest tests/ --ignore=tests/test_e2e.py -x
```

#### 版本发布前 (Release Checklist)
```bash
# 1. 全量测试
pytest tests/ -v --tb=short

# 2. 覆盖率检查
pytest tests/ --cov=core --cov-report=html

# 3. 代码质量检查
flake8 core/ tests/
black --check core/ tests/

# 4. 文档检查
python3 -c "import curious_agent"  # 确保无导入错误
```

### 4.3 回归测试通过标准

| 指标 | 当前 | 目标 | 通过标准 |
|------|------|------|----------|
| **测试通过率** | 89.7% | ≥98% | 所有核心模块测试通过 |
| **代码覆盖率** | ~75% | ≥90% | 核心逻辑全覆盖 |
| **测试执行时间** | ~95s | ≤120s | 不显著增加 CI 时间 |
| **失败测试数** | 33 | 0 | 零容忍 |

---

## 五、实施时间表

| 阶段 | 任务 | 预计时间 | 交付物 |
|------|------|----------|--------|
| **Day 1** | 修复 Category A (代码缺陷) | 2h | 18 个测试通过 |
| **Day 1** | 修复 Category B (环境问题) | 2h | 10 个测试通过 |
| **Day 2** | 修复 Category C (行为变化) | 2h | 5 个测试通过 |
| **Day 2** | 补充缺失测试 | 4h | 新增 20+ 测试 |
| **Day 3** | 完整回归测试 | 2h | 测试报告 |
| **Day 3** | 文档更新 | 1h | 更新测试文档 |

**总计**: 约 13 小时工作量

---

## 六、修复验证 Checklist

### 修复前检查
- [ ] 确认失败测试的错误日志
- [ ] 定位问题代码位置
- [ ] 分析问题根因 (代码 bug / 测试问题 / 环境配置)

### 修复中检查
- [ ] 编写最小复现案例
- [ ] 实施修复
- [ ] 运行相关测试验证
- [ ] 检查是否有副作用

### 修复后检查
- [ ] 运行完整测试套件
- [ ] 更新测试文档 (如需要)
- [ ] 代码审查
- [ ] 合并到主分支

---

## 七、附录: 失败测试完整清单

### Category A: 代码缺陷 (18 tests)
```
tests/test_cli.py (4 tests)
├── TestDepthParameter::test_depth_parameter_accepts_shallow
├── TestDepthParameter::test_depth_parameter_accepts_medium
├── TestDepthParameter::test_depth_parameter_accepts_deep
└── TestDepthParameter::test_depth_parameter_default_is_medium

tests/test_auto_queue.py (2 tests)
├── TestAutoQueueIntegration::test_auto_queue_called_for_medium_depth
└── TestAutoQueueIntegration::test_auto_queue_called_for_deep_depth

tests/test_e2e.py (5 tests)
├── TestE2EFullWorkflow::test_full_workflow_deep_exploration
├── TestE2EFullWorkflow::test_medium_exploration_layer1_and_layer2
├── TestE2EAutoQueue::test_auto_queue_adds_new_topics
├── TestE2EStateUpdates::test_exploration_log_contains_required_fields
└── TestE2ECLI::test_cli_depth_parameter_validation

... (其他 7 个测试)
```

### Category B: 环境配置 (10 tests)
```
tests/test_llm_client.py (8 tests)
├── test_client_initialization_with_api_key
├── test_generate_insights_returns_error_without_api_key
├── test_generate_insights_skips_single_paper
├── test_generate_insights_success
├── test_generate_insights_handles_api_error
├── test_call_api_makes_correct_request
└── ...

tests/test_curiosity_engine.py (2 tests)
└── ...
```

### Category C: 行为变化 (5 tests)
```
tests/test_auto_queue.py (6 tests)
├── TestAutoQueueTopics::test_auto_queue_topics_adds_new_curiosities
├── TestAutoQueueTopics::test_auto_queue_topics_avoids_duplicates_in_queue
├── TestAutoQueueTopics::test_auto_queue_topics_avoids_duplicates_case_insensitive
├── TestAutoQueueTopics::test_auto_queue_topics_avoids_done_items
└── TestAutoQueueTopics::test_auto_queue_topics_filters_empty_strings

tests/test_curiosity_engine.py (1 test)
└── TestExtractKeywords::test_extract_keywords_finds_capitalized_phrases
```

---

**制定人**: AI Assistant  
**日期**: 2026-03-23  
**版本**: v1.0
