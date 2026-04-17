# Git 工作流指南

## 分支结构

本项目使用 **双分支策略**，分离公开代码和内部文档：

| 分支 | 用途 | 推送到 |
|------|------|--------|
| `main` | 公开代码 + 用户文档 | `origin` (GitHub) |
| `internal` | 完整代码 + 内部文档 | `internal` (本地 bare repo) |

## Remote 配置

```bash
origin    → git@github.com:weNix901/CuriousAgent.git  (公开)
internal  → .internal-git                              (本地)
```

## 分支内容

### main 分支（公开）

```
curious-agent/
├── core/                    # 核心代码
├── ui/                      # WebUI
├── openclaw-hooks/          # OpenClaw Hooks
├── skills/                  # OpenClaw Skills
├── tests/                   # 测试
├── README.md                # 项目介绍
├── ARCHITECTURE.md          # 架构文档
├── RELEASE_NOTE_v0.3.1.md   # 最新版本说明
├── docs/                    # 用户文档
│   ├── curious-agent-installation-guide.md
│   └── integration-guide.md
├── config.example.json      # 配置示例
├── start.sh                 # 启动脚本
└── .gitignore
```

### internal 分支（完整）

在 main 基础上，额外包含：

```
├── ideas/                   # 头脑风暴、next_move、buglist
├── docs/plans/              # 历史实现计划、设计文档
├── .sisyphus/               # Sisyphus 工作计划
├── RELEASE_NOTE_v0.2.*.md   # 旧版本说明
└── docs/{01-05,10,参考}*.md  # 内部调研、设计文档
```

## 日常工作流

### 1. 开发代码（main 分支）

```bash
git checkout main
git add core/ ui/ ...
git commit -m "feat: xxx"
git push origin main
```

### 2. 编写内部文档（internal 分支）

```bash
git checkout internal
git add ideas/ docs/plans/ ...
git commit -m "internal: v0.3.2 计划"
git push internal internal
```

### 3. 同步 main 到 internal

```bash
git checkout internal
git merge main --no-edit
git push internal internal
git checkout main
```

## 注意事项

- ❌ 不要将 `internal` 分支推送到 `origin`
- ❌ 不要在 `main` 分支添加内部文档
- ❌ 不要删除 `.internal-git/` 目录
- 恢复内部文档：`git checkout internal -- ideas/ docs/plans/ .sisyphus/`

---
_最后更新：2026-04-17 | v0.3.1_
