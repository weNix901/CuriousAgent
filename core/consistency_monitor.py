"""
Consistency Monitor - 数据一致性监控

实时监控数据一致性，自动修复问题
"""

import logging
import time
import threading
from datetime import datetime
from typing import List, Callable, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Severity(Enum):
    """问题严重程度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ConsistencyIssue:
    """一致性问题"""
    rule_name: str
    severity: str
    topic: str
    description: str
    suggestion: str
    auto_repairable: bool


class ConsistencyRule:
    """一致性检查规则"""
    
    def __init__(
        self,
        name: str,
        severity: str,
        check_fn: Callable[[], List[ConsistencyIssue]],
        auto_repair: bool = False,
        repair_fn: Optional[Callable[[ConsistencyIssue], bool]] = None,
    ):
        self.name = name
        self.severity = severity
        self.check_fn = check_fn
        self.auto_repair = auto_repair
        self.repair_fn = repair_fn


class ConsistencyMonitor:
    """
    数据一致性监控器
    
    实时检查 + 定期检查
    """
    
    def __init__(
        self,
        queue_repository,
        state_repository,
        check_interval: int = 300,  # 5分钟
    ):
        self._queue_repo = queue_repository
        self._state_repo = state_repository
        self._check_interval = check_interval
        self._rules: List[ConsistencyRule] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        self._init_rules()
    
    def _init_rules(self):
        """初始化检查规则"""
        self._rules = [
            ConsistencyRule(
                name="orphan_nodes",
                severity=Severity.ERROR.value,
                check_fn=self._check_orphan_nodes,
                auto_repair=False,
            ),
            ConsistencyRule(
                name="stale_exploring",
                severity=Severity.WARNING.value,
                check_fn=self._check_stale_exploring,
                auto_repair=True,
                repair_fn=self._repair_stale_exploring,
            ),
            ConsistencyRule(
                name="queue_state_mismatch",
                severity=Severity.ERROR.value,
                check_fn=self._check_queue_state_mismatch,
                auto_repair=False,
            ),
            ConsistencyRule(
                name="dangling_claimed",
                severity=Severity.WARNING.value,
                check_fn=self._check_dangling_claimed,
                auto_repair=True,
                repair_fn=self._repair_dangling_claimed,
            ),
        ]
    
    def start(self):
        """启动监控"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print(f"[ConsistencyMonitor] Started (interval: {self._check_interval}s)")
    
    def stop(self):
        """停止监控"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[ConsistencyMonitor] Stopped")
    
    def _monitor_loop(self):
        """监控循环"""
        while self._running:
            try:
                self.check_all()
            except Exception as e:
                print(f"[ConsistencyMonitor] Error: {e}")
            
            time.sleep(self._check_interval)
    
    def check_all(self) -> List[ConsistencyIssue]:
        """执行所有检查"""
        all_issues = []
        
        for rule in self._rules:
            try:
                issues = rule.check_fn()
                all_issues.extend(issues)
                
                for issue in issues:
                    self._report_issue(issue)
                    
                    if issue.auto_repairable and rule.repair_fn:
                        success = rule.repair_fn(issue)
                        if success:
                            print(f"[ConsistencyMonitor] Auto-repaired: {issue.topic}")
                        
            except Exception as e:
                print(f"[ConsistencyMonitor] Rule {rule.name} failed: {e}")
        
        return all_issues
    
    def _check_orphan_nodes(self) -> List[ConsistencyIssue]:
        """检查孤儿节点"""
        issues = []
        # 实现检查逻辑
        return issues
    
    def _check_stale_exploring(self) -> List[ConsistencyIssue]:
        """检查长时间 exploring"""
        issues = []
        from core.repositories.queue_repository import State
        
        items = self._queue_repo.find_by_status(State.EXPLORING)
        now = datetime.now()
        
        for item in items:
            # 获取进入 exploring 的时间
            exploring_time = None
            for transition in reversed(item.state_history):
                if transition.to_state == State.EXPLORING.value:
                    exploring_time = datetime.fromisoformat(transition.timestamp)
                    break
            
            if exploring_time:
                elapsed = (now - exploring_time).total_seconds()
                if elapsed > 1800:  # 30分钟
                    issues.append(ConsistencyIssue(
                        rule_name="stale_exploring",
                        severity=Severity.WARNING.value,
                        topic=item.topic,
                        description=f"Exploring for {elapsed//60} minutes",
                        suggestion="Check if exploration is stuck",
                        auto_repairable=True,
                    ))
        
        return issues
    
    def _repair_stale_exploring(self, issue: ConsistencyIssue) -> bool:
        """修复 stale exploring"""
        try:
            # 将状态改为 FAILED
            from core.repositories.queue_repository import State
            
            item = self._queue_repo.get_by_topic(issue.topic)
            if item:
                item.status = State.FAILED
                self._queue_repo.save(item)
                return True
        except Exception as e:
            logger.warning(f"Failed to repair stale exploring for '{issue.topic}': {e}", exc_info=True)
        return False
    
    def _check_queue_state_mismatch(self) -> List[ConsistencyIssue]:
        """检查队列和状态不一致"""
        issues = []
        # 实现检查逻辑
        return issues
    
    def _check_dangling_claimed(self) -> List[ConsistencyIssue]:
        """检查 dangling claimed"""
        issues = []
        from core.repositories.queue_repository import State
        
        items = self._queue_repo.find_by_status(State.CLAIMED)
        now = datetime.now()
        
        for item in items:
            claimed_time = None
            for transition in reversed(item.state_history):
                if transition.to_state == State.CLAIMED.value:
                    claimed_time = datetime.fromisoformat(transition.timestamp)
                    break
            
            if claimed_time:
                elapsed = (now - claimed_time).total_seconds()
                if elapsed > 300:  # 5分钟
                    issues.append(ConsistencyIssue(
                        rule_name="dangling_claimed",
                        severity=Severity.WARNING.value,
                        topic=item.topic,
                        description=f"Claimed for {elapsed//60} minutes",
                        suggestion="Release back to pending",
                        auto_repairable=True,
                    ))
        
        return issues
    
    def _repair_dangling_claimed(self, issue: ConsistencyIssue) -> bool:
        """修复 dangling claimed"""
        try:
            from core.repositories.queue_repository import State
            
            item = self._queue_repo.get_by_topic(issue.topic)
            if item:
                item.status = State.PENDING
                self._queue_repo.save(item)
                return True
        except Exception as e:
            logger.warning(f"Failed to repair dangling claimed for '{issue.topic}': {e}", exc_info=True)
        return False
    
    def _report_issue(self, issue: ConsistencyIssue):
        """报告问题"""
        print(f"[ConsistencyMonitor] [{issue.severity.upper()}] {issue.rule_name}: {issue.description}")
