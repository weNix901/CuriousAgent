"""
Exploration State Machine

统一的状态管理，替代碎片化的 update_curiosity_status
"""

import threading
import hashlib
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass

from core.repositories import StateRepository, StateInfo, StateTransition
from core.repositories.queue_repository import State, Actor


@dataclass
class TransitionResult:
    """状态转换结果"""
    success: bool
    from_state: Optional[State]
    to_state: State
    error: str = ""
    transition: Optional[StateTransition] = None


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    error: str = ""


@dataclass
class StateConfig:
    """状态配置"""
    allowed_transitions: List[State]
    valid_actors: List[Actor]
    timeout_seconds: Optional[int] = None
    max_retries: int = 0
    auto_retry: bool = False


class SegmentedLock:
    """
    分段锁 - 减少锁竞争
    
    将锁分成多个段，不同 topic 可能使用不同的锁
    """
    
    def __init__(self, segment_count: int = 16):
        self._segments = [threading.Lock() for _ in range(segment_count)]
        self._segment_count = segment_count
    
    def _get_segment_index(self, key: str) -> int:
        """根据 key 计算段索引"""
        hash_val = int(hashlib.md5(key.encode()).hexdigest(), 16)
        return hash_val % self._segment_count
    
    def acquire(self, key: str):
        """获取锁"""
        idx = self._get_segment_index(key)
        self._segments[idx].acquire()
        return idx
    
    def release(self, key: str):
        """释放锁"""
        idx = self._get_segment_index(key)
        self._segments[idx].release()
    
    def __enter__(self, key: str):
        self.acquire(key)
        return self
    
    def __exit__(self, *args):
        pass


class ExplorationStateMachine:
    """
    探索状态机
    
    统一的状态管理，确保状态转换合法性和可追溯性
    """
    
    # 状态配置表
    STATE_CONFIG: Dict[State, StateConfig] = {
        State.PENDING: StateConfig(
            allowed_transitions=[State.CLAIMED, State.CANCELLED],
            valid_actors=[Actor.SYSTEM, Actor.USER],
            timeout_seconds=None,
        ),
        State.CLAIMED: StateConfig(
            allowed_transitions=[State.EXPLORING, State.PENDING],
            valid_actors=[Actor.SPIDER_AGENT, Actor.ASYNC_TRIGGER],
            timeout_seconds=300,  # 5分钟超时
        ),
        State.EXPLORING: StateConfig(
            allowed_transitions=[State.DONE, State.PAUSED, State.FAILED],
            valid_actors=[Actor.SPIDER_AGENT, Actor.ASYNC_TRIGGER],
            timeout_seconds=1800,  # 30分钟超时
        ),
        State.DONE: StateConfig(
            allowed_transitions=[],
            valid_actors=[Actor.SYSTEM],
        ),
        State.PAUSED: StateConfig(
            allowed_transitions=[State.PENDING],
            valid_actors=[Actor.SYSTEM],
            auto_retry=True,
        ),
        State.FAILED: StateConfig(
            allowed_transitions=[State.PENDING],
            valid_actors=[Actor.SYSTEM],
            max_retries=3,
        ),
        State.CANCELLED: StateConfig(
            allowed_transitions=[],
            valid_actors=[Actor.SYSTEM, Actor.USER],
        ),
    }
    
    def __init__(self, repository: StateRepository):
        self._repo = repository
        self._segmented_lock = SegmentedLock(segment_count=16)
        self._timeout_handlers: Dict[State, Callable] = {}
        
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """注册默认的超时处理器"""
        self._timeout_handlers[State.CLAIMED] = self._handle_claimed_timeout
        self._timeout_handlers[State.EXPLORING] = self._handle_exploring_timeout
    
    def transition(
        self,
        topic: str,
        to_state: State,
        actor: Actor,
        reason: str = "",
        context: Optional[Dict] = None,
    ) -> TransitionResult:
        """
        执行状态转换
        
        线程安全，使用分段锁
        """
        # 获取分段锁
        segment_idx = self._segmented_lock.acquire(topic)
        
        try:
            # 获取当前状态
            current = self._repo.get_state(topic)
            current_state = State(current.state) if current else None
            
            # 验证转换
            validation = self._validate_transition(
                topic, current_state, to_state, actor
            )
            
            if not validation.is_valid:
                return TransitionResult(
                    success=False,
                    from_state=current_state,
                    to_state=to_state,
                    error=validation.error,
                )
            
            # 创建转换记录
            from datetime import datetime
            transition = StateTransition(
                from_state=current_state.value if current_state else None,
                to_state=to_state.value,
                actor=actor.value,
                timestamp=datetime.now().isoformat(),
                reason=reason,
                context=context or {},
            )
            
            # 准备新的状态信息
            if current:
                history = current.history + [transition]
            else:
                history = [transition]
            
            new_state_info = StateInfo(
                topic=topic,
                state=to_state.value,
                history=history,
                metadata=context.get("metadata", {}) if context else {},
            )
            
            # 保存
            self._repo.save_state(new_state_info)
            
            return TransitionResult(
                success=True,
                from_state=current_state,
                to_state=to_state,
                transition=transition,
            )
            
        finally:
            self._segmented_lock.release(topic)
    
    def _validate_transition(
        self,
        topic: str,
        from_state: Optional[State],
        to_state: State,
        actor: Actor,
    ) -> ValidationResult:
        """验证状态转换的合法性"""
        
        # 检查目标状态是否存在
        if to_state not in self.STATE_CONFIG:
            return ValidationResult(
                is_valid=False,
                error=f"Invalid target state: {to_state.value}"
            )
        
        config = self.STATE_CONFIG[to_state]
        
        # 初始状态只能到 PENDING
        if from_state is None:
            if to_state != State.PENDING:
                return ValidationResult(
                    is_valid=False,
                    error=f"Initial state must be PENDING, got {to_state.value}"
                )
            return ValidationResult(is_valid=True)
        
        # 检查是否允许该转换
        if to_state not in config.allowed_transitions:
            allowed = [s.value for s in config.allowed_transitions]
            return ValidationResult(
                is_valid=False,
                error=f"Cannot transition from {from_state.value} to {to_state.value}. "
                      f"Allowed: {allowed}"
            )
        
        # 检查执行者权限
        if actor not in config.valid_actors:
            return ValidationResult(
                is_valid=False,
                error=f"Actor {actor.value} not allowed for {to_state.value}"
            )
        
        return ValidationResult(is_valid=True)
    
    def get_state(self, topic: str) -> Optional[StateInfo]:
        """获取话题当前状态"""
        return self._repo.get_state(topic)
    
    def get_history(self, topic: str) -> List[StateTransition]:
        """获取话题状态历史"""
        state = self._repo.get_state(topic)
        return state.history if state else []
    
    def can_transition(
        self,
        topic: str,
        to_state: State,
        actor: Actor,
    ) -> bool:
        """检查是否可以执行状态转换（不实际执行）"""
        current = self._repo.get_state(topic)
        current_state = State(current.state) if current else None
        
        validation = self._validate_transition(
            topic, current_state, to_state, actor
        )
        return validation.is_valid
    
    def _handle_claimed_timeout(self, topic: str):
        """处理 CLAIMED 超时 - 自动释放回 PENDING"""
        self.transition(
            topic=topic,
            to_state=State.PENDING,
            actor=Actor.SYSTEM,
            reason="CLAIMED timeout - auto release",
        )
    
    def _handle_exploring_timeout(self, topic: str):
        """处理 EXPLORING 超时 - 标记为 FAILED"""
        self.transition(
            topic=topic,
            to_state=State.FAILED,
            actor=Actor.SYSTEM,
            reason="EXPLORING timeout - marked as failed",
        )
    
    def get_config(self, state: State) -> Optional[StateConfig]:
        """获取状态配置"""
        return self.STATE_CONFIG.get(state)
