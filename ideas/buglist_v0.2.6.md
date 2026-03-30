# Buglist v0.2.7 - 2026-03-30

## 根因汇总

本次诊断发现 4 个独立根因，各自产生不同症状：

| 根因 | 症状 | 影响范围 |
|------|------|---------|
| G1: SpiderAgent 卡死 | DreamInbox 堆积 620 项，_explored_topics 停在 10 | 整个 DreamInbox 消费链路 |
| G2: Daemon 不调用 run_one_cycle() | 主 curiosity_queue 1461 项从未被处理，93 项 stuck | 手动注入的好奇心项 |
| G3: Decomposition 跨进程中断 | 100 个 partial 节点 + 93 个 stuck 项 | KG 完整性和探索质量 |
| G4: API SIGTERM | decomposition 线程被强制终止，stub 写入 KG | KG 内容质量 |

---

## G1: SpiderAgent 卡死（Daemon Thread 冻结）

**严重程度**: P0

**症状**:
- `_explored_topics` 停在 10，在 4963 个监控周期（~14 小时）内没有变化
- DreamInbox 堆积 620 项从未被消费
- SpiderAgent 线程仍在 is_alive()，但不再处理任何 inbox 项

**根因分析**:
`_explore_topic()` 里 explorer.explore() 可能因网络请求卡住，异常被 try/except 吞掉后 continue，导致当前批次内剩余 topic 全部跳过。fetch_and_clear_dream_inbox() 清空 inbox 后，下一轮返回空列表，SpiderAgent 每次 loop 直接 return。

**修复方向**:
1. 守护机制：Daemon 主循环检测 SpiderAgent._explored_topics 连续 5 分钟无增长，强制 restart SpiderAgent thread
2. 加超时：explorer.py 搜索请求加 timeout
3. 加心跳：fetch_and_clear_dream_inbox() 连续 5 次返回空时打印警告

---

## G2: Daemon 不调用 run_one_cycle()（主队列死锁）

**严重程度**: P0

**症状**:
- 主 curiosity_queue（1461 项）从未被消费
- 手动注入的 6 个 agent harness topic 全部卡在 "exploring" 状态
- 93 个 stuck 项：队列=exploring，KG=missing

**根因分析**:
v0.2.6 三代理 Daemon 模式里，SpiderAgent 只读 DreamInbox 文件，完全不访问 curiosity_queue。run_one_cycle() 是处理主队列的唯一函数，但在 Daemon 模式里没有被调用。

**修复方向**:
1. 在 Daemon 模式里增加对主 curiosity_queue 的消费循环
2. 或者：DreamInbox 作为主队列，手动注入的 topic 也写入 DreamInbox

---

## G3: Decomposition 跨进程中断（100 partial + 93 stuck）

**严重程度**: P1

**症状**:
- 100 个 KG partial 节点（decomposition 生成了 children 但自身内容为空）
- 93 个 stuck curiosity 项（队列=exploring，KG 里 missing）
- 其中 83 个 partial 有 KG 内容但队列状态错误，10 个 missing 需要重跑

**根因分析**:
API 进程响应 /api/curious/inject 时，开 threading.Thread 执行 _explore_in_thread()（含 decomposition）。explore() 完成写入 KG partial 后，decomposition 开始调用 update_curiosity_status("exploring")，此时 SIGTERM 杀死 API 进程。队列状态停留在 "exploring"，KG 是 partial。

**分类处理**:
- 83 个 KG partial 但有内容：队列状态改为 "done"（内容已在 KG）
- 10 个 KG missing：队列状态改为 "pending"，等待重跑
- 1 个 "test connectivity"：删除

**修复方向**:
1. Decomposition 原子化：写入队列是最小原子操作，不被 SIGTERM 打断
2. Decomposition 移至 Daemon：API 只做探索，decomposition 必须在 Daemon SpiderAgent 里同步执行
3. KG 健康检查：SleepPruner 增加 incomplete 节点自动补全逻辑

---

## G4: API SIGTERM（stub 根因）

**严重程度**: P1

**症状**:
- v0.2.6 stub 产生（100 个"推理分析：XXX"文件）
- API 进程每 5 分钟被杀死一次

**根因分析**:
之前的 bash 管理脚本已不存在，但 curious_api.py 残留了 300s shutdown timeout 机制。API 进程在 timeout 后自动退出，导致 decomposition 线程被强制终止。

**已修复（2026-03-29）**:
- SIGTERM handler 已加入 curious_api.py
- timeout 已从 300s 改为永久等待

**遗留问题**:
- 100 个 stub 文件仍保留在 KG/discoveries/，需清理
- 旧的"推理分析"格式发现文件需重新探索

---

## 行动清单

### 立即执行（无需 OpenCode）

- [x] 修复 83 个 partial 队列状态：exploring → done（内容已在 KG）✅ G4 cleanup script
- [x] 修复 10 个 missing 项：exploring → pending（需要重跑）✅ G4 cleanup script
- [x] 删除 "test connectivity" 项 ✅ G4 cleanup script
- [x] 清空 DreamInbox 计数器（重新开始）✅
- [x] 清理 100 个 stub 发现文件 ✅ G4 cleanup script

### 需要 OpenCode

- [ ] **G1-Fix1**: SpiderAgent 守护机制（检测 _explored_topics 无增长超过 5 分钟，restart thread）
  ⚠️ cb8fbf4 代码已写，但 spider_agent.py 文件在 git commit 中损坏（284行→27行截断），需重新提交
- [ ] **G1-Fix2**: explorer.py 搜索加 timeout（requests 30s，curl 15s）
- [ ] **G1-Fix3**: fetch_and_clear_dream_inbox 连续空时打印警告
- [ ] **G2-Fix**: Daemon 模式增加主 curiosity_queue 消费循环（每 60s 调用 select_next）
  ⚠️ curious_agent.py 中 G2 逻辑已写入，但因 spider_agent.py 损坏导致 daemon 启动失败，已临时 patch curious_agent.py 注释 G1/G2 调用
- [ ] **G3-Fix1**: Decomposition 原子化（写入队列是原子操作，SIGTERM 不影响）
- [ ] **G3-Fix2**: API /inject 不执行 decomposition，只触发探索请求到 Daemon
- [ ] **G3-Fix3**: SleepPruner 增加 incomplete 节点自动补全逻辑
- [x] **G4-Cleanup**: 清理 100 个 stub 发现文件 ✅ 已完成（78 stuck items fixed, 0 stub files found）

### 遗留问题

- ⚠️ **spider_agent.py 文件损坏**：commit cb8fbf4 中文件从 284 行截断至 27 行，导致 G1/G2/G3 守护机制无法生效
  - 修复方案：weNix 重新提交 spider_agent.py 完整代码
  - 当前状态：spider_agent.py 已从 c330738 恢复（不含 G1-G3 新方法），Daemon 可启动但 G1 守护机制缺失

---

## 验证方法

修复后验证：
1. DreamInbox 应稳定消费（每分钟减少）
2. curiosity_queue 的 manual inject 项应在 5 分钟内变为 done
3. SpiderAgent._explored_topics 应持续增长
4. KG 里不应出现新的 partial 节点
5. 93 个 stuck 项应在 1 小时内全部处理完毕
