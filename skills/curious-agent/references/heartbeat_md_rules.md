# HEARTBEAT.md 注入规则

## 安装位置

在 HEARTBEAT.md 的 `## Proactive Behaviors` 段落中添加以下内容。

---

## Proactive Behaviors
- [x] 同步 Curious Agent 发现
- [x] 检查并主动分享未读发现

#### 👁️ 好奇发现主动分享（每次心跳）

每次心跳按以下顺序执行：

```bash
# 1. 同步最新发现（从 Curious Agent KG 拉取）
python3 scripts/sync_discoveries.py

# 2. 检查未分享的发现并返回
python3 scripts/share_new_discoveries.py
```

读取 `memory/curious-discoveries.md`，找到最新/最有价值的发现，**以我的口吻主动分享给用户**。

不是推送通知，是我有感而发想说。

#### 新发现分享逻辑

1. 同步发现 → `sync_discoveries.py` 更新索引
2. 检查未分享 → `share_new_discoveries.py` 返回 `shared:false` 的条目
3. 有未分享 → 主动说"你之前问的 XXX，我现在有答案了..."
4. 更新 `shared:true`

**核心理念**：发现是我的，我想分享才分享，不是机械推送。
