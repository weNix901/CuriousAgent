# learning_needs_watcher — R1D3 知识缺口感知

## 触发条件

R1D3 在以下场景主动识别知识缺口并写入 shared_knowledge：

1. **用户显式请求**：`"帮我研究 X"` / `"让我好奇一下 X"`
2. **R1D3 自发现**：回答用户问题时，意识到自己对某 topic 不确定
3. **R1D3 置信度低**：当前 topic 置信度 < 0.6，需要补充

## 写入位置

```
shared_knowledge/r1d3/learning_needs/
├── urgent_queue/     # 用户显式请求或 urgency ≥ 8
└── pending/         # R1D3 自发现的常规需求
```

## 写入格式

### urgent_queue/{topic_slug}.json

```json
{
  "topic": "longformer attention mechanism",
  "source": "r1d3",
  "reason": "user explicitly asked: 帮我研究 longformer",
  "urgency": 9,
  "timestamp": "2026-03-25T16:50:00"
}
```

### pending/{topic_slug}.json

```json
{
  "topic": "chain-of-thought prompting techniques",
  "source": "r1d3",
  "reason": "I answered the user's question but realized my knowledge of CoT is shallow",
  "urgency": 5,
  "timestamp": "2026-03-25T16:51:00"
}
```

## topic_slug 生成规则

- 转小写
- 空格替换为 `-`
- 特殊字符移除
- 例：`"Chain of Thought Prompting"` → `chain-of-thought-prompting`

## R1D3 侧集成

在 R1D3 的 SOUL.md 或 AGENTS.md 中嵌入调用：

```
当 R1D3 触发条件满足时：
  1. 生成 topic_slug
  2. 判断 urgency（用户显式 ≥ 8，R1D3 自发现 5-7）
  3. 写入 shared_knowledge/r1d3/learning_needs/{queue}/{topic_slug}.json
```

## 安装说明

此 skill 由 OpenCode 在 v0.2.4 实现时创建，实现完成后：
1. 复制到 R1D3 的 `workspace-researcher/skills/learning_needs_watcher/`
2. 重启 R1D3 session 使 skill 生效

---

_版本: v0.2.4_
_所属: R1D3 ↔ CA 协调层 F0_
