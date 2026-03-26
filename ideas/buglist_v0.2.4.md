# Bug List — v0.2.4 Spider 机制

> 发现时间: 2026-03-27 | 验证方式: 实际运行 SpiderEngine + 源码分析
> 发现工具: R1D3 主动验证

---

## Bug #1 — 致命：SpiderEngine(repo=None) 崩溃
- **文件**: `spider_engine.py`
- **位置**: `run_once()` 第 107 行
- **现象**: `AttributeError: 'NoneType' object has no attribute 'get_high_degree_unexplored'`
- **根因**: `run_once()` 调用 `self.repo.get_high_degree_unexplored()` 但没有检查 `self.repo is None`
- **复现**:
  ```python
  se = SpiderEngine(repo=None)
  asyncio.run(se.run_once())  # 崩溃
  ```
- **修复建议**: 在 `run_once()` 开头加 `if self.repo is None: raise RuntimeError("repo is required")`

---

## Bug #2 — 致命：Explorer Protocol 接口不匹配
- **文件**: `spider_engine.py` + `core/explorer.py`
- **位置**: `spider_engine.py` 第 114 行
- **现象**: `TypeError: Explorer.explore() takes 2 positional arguments but 3 were given`
- **根因**:
  - `SpiderEngine` 的 `TopicExplorer` Protocol 定义为:
    ```python
    async def explore(self, topic: str, depth: str = "medium") -> dict
    ```
  - 实际 `Explorer.explore()` 签名:
    ```python
    def explore(self, curiosity_item: dict) -> dict
    ```
  - `SpiderEngine.run_once()` 调用: `await self.explorer.explore(node, self.config.default_exploration_depth)`
  - 两个接口完全不兼容
- **复现**:
  ```python
  repo = JSONKnowledgeRepository('knowledge/state.json')
  explorer = Explorer()
  se = SpiderEngine(repo=repo, explorer=explorer)
  se.runtime_state.current_node = 'test'
  asyncio.run(se.run_once())  # TypeError
  ```
- **修复建议**: 修改 `Explorer.explore()` 适配 Protocol，或在 `SpiderEngine` 中添加 adapter wrapper

---

## Bug #3 — 严重：should_continue=True 但 decomposer=None 时错误累加 consecutive_low_gain
- **文件**: `spider_engine.py`
- **位置**: `run_once()` 第 117-125 行
- **现象**: `consecutive_low_gain` 被错误+1，实际上探索成功结束了
- **根因**: 代码逻辑:
  ```python
  if should_continue and self.decomposer:
      await self._expand_frontier(node, result)
      self.runtime_state.consecutive_low_gain = 0
  else:
      # ← 当 should_continue=True 但 decomposer=None 时，错误进入这里
      self.runtime_state.consecutive_low_gain += 1
  ```
  应该是: `if should_continue:`（不依赖 decomposer 是否存在）
- **复现**:
  ```python
  se = SpiderEngine(repo=repo, explorer=None, decomposer=None)
  se.runtime_state.current_node = 'some_node'
  se.runtime_state.consecutive_low_gain = 0
  asyncio.run(se.run_once())
  # consecutive_low_gain 变成 1，应该是 0
  ```
- **修复建议**: 改为:
  ```python
  if should_continue:
      if self.decomposer:
          await self._expand_frontier(node, result)
      self.runtime_state.consecutive_low_gain = 0
  else:
      topic.mark_fully_explored()
      self.repo.save_topic(topic)
      self.runtime_state.consecutive_low_gain += 1
  ```

---

## Bug #4 — 严重：SpiderEngine 使用内部简化版 MetaCognitive，而非 core/ 里的完整实现
- **文件**: `spider_engine.py` 第 37-52 行
- **现象**: `MetaCognitiveMonitor.get_marginal_returns()` 永远返回 `[]`，导致 `should_continue()` 永远返回 `True "First exploration"`
- **根因**: `SpiderEngine` 内部定义了简化版的 `MetaCognitiveMonitor` 和 `MetaCognitiveController`，而不是使用 `core/meta_cognitive_monitor.py` 和 `core/meta_cognitive_controller.py`
- **影响**: SpiderEngine 的元认知决策完全失效（无边际收益计算、无质量评估）
- **修复建议**: 删除内部简化类，从 `core` 导入并注入:
  ```python
  from core.meta_cognitive_controller import MetaCognitiveController
  from core.meta_cognitive_monitor import MetaCognitiveMonitor
  
  class SpiderEngine:
      def __init__(self, ..., monitor=None, controller=None, ...):
          self.controller = controller or MetaCognitiveController(
              monitor=monitor or MetaCognitiveMonitor(llm_client=...)
          )
  ```

---

## Bug #5 — 严重：_expand_frontier 静默吞掉所有异常
- **文件**: `spider_engine.py`
- **位置**: `_expand_frontier()` 第 149 行
- **现象**: 分解器返回格式不对时，探索静默失败，无法定位问题
- **根因**:
  ```python
  try:
      subtopics = await self.decomposer.decompose(node)
      for st in subtopics[:5]:
          child_name = st.get("topic", "")
          ...
  except Exception:
      pass  # ← 静默丢弃所有错误
  ```
- **修复建议**:
  ```python
  except Exception as e:
      logger.warning(f"[_expand_frontier] Decompose failed for {node}: {e}")
  ```

---

## Bug #6 — 中等：_run_async 无 try/catch，异常后死循环
- **文件**: `spider_engine.py`
- **位置**: `_run_async()`
- **现象**: `run_once()` 抛出异常时，async loop 崩溃，整个程序停止，无恢复机制
- **根因**: `_run_async` 没有包裹 `await self.run_once()` 的 try/except
- **修复建议**:
  ```python
  async def _run_async(self, max_steps=None):
      step = 0
      while True:
          if max_steps and step >= max_steps:
              break
          try:
              if not await self.run_once():
                  break
          except Exception as e:
              logger.error(f"[_run_async] run_once failed: {e}")
              await asyncio.sleep(self.config.loop_interval)
              continue
          step += 1
          await asyncio.sleep(self.config.loop_interval)
  ```

---

## Bug #7 — 中等：SpiderEngine 无日志系统
- **文件**: `spider_engine.py`
- **现象**: SpiderEngine 没有任何 `logger` 实例，所有状态变化无记录
- **影响**: 生产环境无法调试，无法追踪探索路径
- **修复建议**: 添加标准 logging:
  ```python
  import logging
  logger = logging.getLogger(__name__)
  
  class SpiderEngine:
      def __init__(self, ...):
          self.logger = logging.getLogger(f"{__name__}.{id(self)}")
  ```

---

## Bug #8 — 中等：get_high_degree_unexplored 返回 None 时未处理
- **文件**: `spider_engine.py` + `core/repository/json_repository.py`
- **位置**: `_select_next_node()` 第 135 行
- **现象**: 当知识图谱为空或所有节点都已完全探索时，`get_high_degree_unexplored()` 返回 `None`，导致 `current_node = None`，后续处理崩溃
- **复现**: 清空 `knowledge/state.json` 的 topics，重新运行
- **修复建议**: `_select_next_node()` 中:
  ```python
  def _select_next_node(self) -> None:
      if self.runtime_state.frontier:
          self.runtime_state.current_node = self.runtime_state.frontier.pop(0)
      else:
          self.runtime_state.current_node = self.repo.get_high_degree_unexplored()
          if not self.runtime_state.current_node:
              self.logger.warning("No unexplored nodes available, stopping")
              # raise StopIteration 或设置标志
  ```

---

## Bug #9 — 中等：SpiderCheckpoint.save 无线程安全
- **文件**: `core/spider/checkpoint.py`
- **现象**: `SpiderEngine._run_async` 是 async loop（单线程，安全），但如果 `trigger_async_exploration` 线程同时调用 checkpoint.save()，存在竞争条件
- **根因**: `save()` 方法无 `threading.Lock`
- **修复建议**:
  ```python
  import threading
  class SpiderCheckpoint:
      def __init__(self, path="state/spider_state.json"):
          self.path = path
          self._lock = threading.Lock()
      
      def save(self, state, kg_path):
          with self._lock:
              ...
  ```

---

## Bug #10 — 中等：SpiderEngine.__init__ 不接受 LLM client
- **文件**: `spider_engine.py`
- **现象**: 内部 `MetaCognitiveMonitor` 需要 `llm_client`，但 `SpiderEngine.__init__` 没有这个参数，导致即使传入 `monitor` 也需要自己初始化
- **根因**: `SpiderEngine` 内部类 `MetaCognitiveController` 和 `MetaCognitiveMonitor` 没有依赖注入
- **修复建议**: `SpiderEngine.__init__` 增加可选参数:
  ```python
  def __init__(self, repo, config=None, explorer=None, 
               decomposer=None, checkpoint=None,
               llm_client=None, monitor=None, controller=None):
      self.controller = controller or MetaCognitiveController(
          monitor=monitor or MetaCognitiveMonitor(llm_client=llm_client)
      )
  ```

---

## Bug #11 — 中等：curious_api.py 的 inject endpoint 导入顺序问题
- **文件**: `curious_api.py`
- **位置**: `api_inject()` 第 160 行
- **现象**: `from core.config import get_config` 放在函数内部，在高频调用时每次都重新 import
- **根因**: 函数内部 import（应在模块顶部）
- **修复建议**: 将 `from core.config import get_config` 移到 `curious_api.py` 顶部

---

## Bug #12 — 低：_restore_from_checkpoint 忽略 kg_path
- **文件**: `spider_engine.py`
- **位置**: `_restore_from_checkpoint()` 第 69-72 行
- **现象**: `checkpoint.load()` 返回 `(state, kg_path)`，但代码只用 `state`，`kg_path` 被丢弃
- **修复建议**: 如果 `kg_path` 与当前 repo.path 不同，应发出警告或重新加载正确的 repo

---

## Bug #13 — 低：SpiderEngine 无 __repr__，调试不友好
- **文件**: `spider_engine.py`
- **现象**: `print(se)` 输出无意义
- **修复建议**:
  ```python
  def __repr__(self):
      return (f"SpiderEngine(current_node={self.runtime_state.current_node}, "
              f"frontier={len(self.runtime_state.frontier)}, "
              f"visited={len(self.runtime_state.visited)}, "
              f"step={self.runtime_state.step_count})")
  ```

---

## Bug #14 — 低：_run_async 无优雅超时保护
- **文件**: `spider_engine.py`
- **现象**: `run(max_steps=None)` 永久运行，无最大运行时间限制
- **修复建议**: 增加 `max_runtime_seconds` 参数:
  ```python
  def run(self, max_steps=None, max_runtime_seconds=None):
      asyncio.run(self._run_async(max_steps, max_runtime_seconds))
  
  async def _run_async(self, max_steps=None, max_runtime_seconds=None):
      start = asyncio.get_event_loop().time()
      while True:
          if max_steps and step >= max_steps:
              break
          if max_runtime_seconds and (loop.time() - start) >= max_runtime_seconds:
              break
          ...
  ```

---

## Bug #15 — 低：SpiderEngine 无法从外部注入初始探索主题
- **文件**: `spider_engine.py`
- **现象**: 只能从 repo 的已有节点开始探索，无法直接指定起始主题
- **修复建议**: 增加 `seed_topics: list[str]` 参数，在初始化时预填充 frontier

---

## Bug 汇总

| # | 严重度 | 类型 | 文件 | 状态 |
|---|--------|------|------|------|
| 1 | 🔴 致命 | 运行时崩溃 | spider_engine.py | 待修复 |
| 2 | 🔴 致命 | 接口不匹配 | spider_engine.py | 待修复 |
| 3 | 🔴 严重 | 逻辑错误 | spider_engine.py | 待修复 |
| 4 | 🔴 严重 | 架构问题 | spider_engine.py | 待修复 |
| 5 | 🔴 严重 | 静默失败 | spider_engine.py | 待修复 |
| 6 | 🟡 中等 | 异常处理 | spider_engine.py | 待修复 |
| 7 | 🟡 中等 | 观测性 | spider_engine.py | 待修复 |
| 8 | 🟡 中等 | 边界处理 | spider_engine.py | 待修复 |
| 9 | 🟡 中等 | 线程安全 | checkpoint.py | 待修复 |
| 10 | 🟡 中等 | 依赖注入 | spider_engine.py | 待修复 |
| 11 | 🟡 中等 | 代码质量 | curious_api.py | 待修复 |
| 12 | 🟢 低 | 逻辑遗漏 | spider_engine.py | 待修复 |
| 13 | 🟢 低 | 开发者体验 | spider_engine.py | 待修复 |
| 14 | 🟢 低 | 功能缺失 | spider_engine.py | 待修复 |
| 15 | 🟢 低 | 功能缺失 | spider_engine.py | 待修复 |

**关键问题**：Bug #1/#2/#3/#4/#5 是 v0.2.4 Spider 机制的核心阻塞问题，必须优先修复才能让蜘蛛引擎正常工作。
