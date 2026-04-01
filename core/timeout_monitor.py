"""
Timeout Monitor

监控状态超时，自动处理超时状态
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Callable

from core.state_machine import ExplorationStateMachine, State, Actor
from core.repositories import StateRepository, QueueRepository
from core.repositories.queue_repository import QueueItem


class TimeoutMonitor:
    """
    超时监控器
    
    定期检查各状态是否超时，触发相应处理
    在独立线程中运行
    """
    
    CHECK_INTERVAL = 30  # 检查间隔（秒）
    
    def __init__(
        self,
        state_machine: ExplorationStateMachine,
        queue_repository: QueueRepository,
        check_interval: int = None,
    ):
        self._sm = state_machine
        self._queue_repo = queue_repository
        self._check_interval = check_interval or self.CHECK_INTERVAL
        self._running = False
        self._thread: threading.Thread = None
        self._handlers: Dict[State, Callable[[str], None]] = {}
        
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """注册默认超时处理器"""
        self._handlers[State.CLAIMED] = self._handle_claimed_timeout
        self._handlers[State.EXPLORING] = self._handle_exploring_timeout
    
    def start(self):
        """启动监控线程"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print(f"[TimeoutMonitor] Started (interval: {self._check_interval}s)")
    
    def stop(self):
        """停止监控线程"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[TimeoutMonitor] Stopped")
    
    def _monitor_loop(self):
        """监控循环"""
        while self._running:
            try:
                self._check_timeouts()
            except Exception as e:
                print(f"[TimeoutMonitor] Error: {e}")
            
            time.sleep(self._check_interval)
    
    def _check_timeouts(self):
        """检查所有超时"""
        now = datetime.now()
        
        # 检查 CLAIMED 和 EXPLORING 状态
        for state in [State.CLAIMED, State.EXPLORING]:
            items = self._queue_repo.find_by_status(state)
            
            for item in items:
                if self._is_timeout(item, now):
                    handler = self._handlers.get(state)
                    if handler:
                        print(f"[TimeoutMonitor] {state.value} timeout for {item.topic}")
                        handler(item.topic)
    
    def _is_timeout(self, item: QueueItem, now: datetime) -> bool:
        """检查是否超时"""
        # 获取进入当前状态的时间
        current_state_time = None
        for transition in reversed(item.state_history):
            if transition.to_state == item.status.value:
                current_state_time = datetime.fromisoformat(transition.timestamp)
                break
        
        if not current_state_time:
            return False
        
        elapsed = (now - current_state_time).total_seconds()
        
        # 根据状态获取超时时间
        config = self._sm.get_config(item.status)
        if config and config.timeout_seconds:
            return elapsed > config.timeout_seconds
        
        return False
    
    def _handle_claimed_timeout(self, topic: str):
        """处理 CLAIMED 超时 - 释放回 PENDING"""
        result = self._sm.transition(
            topic=topic,
            to_state=State.PENDING,
            actor=Actor.SYSTEM,
            reason="CLAIMED timeout - auto release",
        )
        
        if result.success:
            # 更新队列项
            item = self._queue_repo.get_by_topic(topic)
            if item:
                item.status = State.PENDING
                item.metadata["timeout_released_at"] = datetime.now().isoformat()
                self._queue_repo.save(item)
    
    def _handle_exploring_timeout(self, topic: str):
        """处理 EXPLORING 超时 - 标记为 FAILED"""
        result = self._sm.transition(
            topic=topic,
            to_state=State.FAILED,
            actor=Actor.SYSTEM,
            reason="EXPLORING timeout - marked as failed",
        )
        
        if result.success:
            # 更新队列项
            item = self._queue_repo.get_by_topic(topic)
            if item:
                item.status = State.FAILED
                item.metadata["timeout_failed_at"] = datetime.now().isoformat()
                self._queue_repo.save(item)
    
    def check_now(self):
        """立即执行一次检查（用于测试）"""
        self._check_timeouts()
