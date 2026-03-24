---
name: curious-agent
description: Curious Agent 接入工具。当需要检查 R1D3 对某个主题的置信度时，或需要主动触发 Curious Agent 定向探索时，使用此 skill。触发场景包括：(1) 用户提问但 R1D3 记忆中没有相关信息；(2) R1D3 需要检查自己对该主题的了解程度；(3) 需要让 Curious Agent 主动探索某个话题。Curious Agent API 地址：http://localhost:4848
---

# Curious Agent

接入 Curious Agent 的两个核心工具。

## Tool 1: check_confidence

检查 R1D3 对某个主题的置信度。

```bash
bash skills/curious-agent/scripts/check_confidence.sh "主题关键词"
```

**返回字段解读**：
- `should_explore: true` → 置信度低，需要探索
- `should_explore: false` → 置信度足够，可以直接回答
- `should_notify: true` → 有高质量发现可分享
- `explore_count` → 已探索次数（超过 3 次停止）

**使用时机**：用户提问后，R1D3 可以先用此工具判断是否需要触发探索。

## Tool 2: trigger_explore

主动触发 Curious Agent 定向探索。

```bash
bash skills/curious-agent/scripts/trigger_explore.sh "主题" "上下文"
```

**参数**：
- `$1`: topic（必填）- 探索主题
- `$2`: context（可选）- 背景上下文

**返回**：
- `status: ok` → 任务已加入队列
- `score` → 好奇心分数（越高越值得探索）

**使用时机**：
- R1D3 检查置信度后发现 `should_explore: true`
- 用户提问但 R1D3 没有相关记忆
- R1D3 想主动延伸当前话题

## 典型工作流

```
用户提问 → memory_search → 找到答案 → 直接回答
                              ↓ 没找到
                       check_confidence.sh
                              ↓
                   should_explore: true?
                              ↓ 是
                    trigger_explore.sh
                              ↓
                    先回答（哪怕不完整）
                    探索结果后续同步
```

## API 端点参考

| 功能 | 端点 | 方法 |
|------|------|------|
| 置信度检查 | `/api/metacognitive/check?topic=` | GET |
| 触发探索 | `/api/curious/inject` | POST |
| 查看状态 | `/api/curious/state` | GET |

 Curious Agent Web UI: http://10.1.0.13:4848
