"""
Queue Service

队列服务，统一管理层级
"""

from typing import Optional, List, Callable, Dict
from datetime import datetime

from core.repositories import QueueRepository, QueueItem, LineageInfo
from core.state_machine import ExplorationStateMachine
from core.repositories.queue_repository import State, Actor


class ExplorationResult:
    """探索结果"""
    
    def __init__(
        self,
        topic: str,
        summary: str,
        sources: List[str],
        quality: float,
        findings: Dict,
    ):
        self.topic = topic
        self.summary = summary
        self.sources = sources
        self.quality = quality
        self.findings = findings
    
    def to_dict(self) -> Dict:
        return {
            "topic": self.topic,
            "summary": self.summary,
            "sources": self.sources,
            "quality": self.quality,
            "findings": self.findings,
        }


class QueueService:
    """
    队列服务
    
    统一管理层级：
    - 入队/出队
    - 状态管理（委托给 StateMachine）
    - 持久化
    """
    
    def __init__(
        self,
        repository: QueueRepository,
        state_machine: ExplorationStateMachine,
    ):
        self._repo = repository
        self._sm = state_machine
    
    def enqueue(
        self,
        topic: str,
        lineage: Optional[LineageInfo] = None,
        score: float = 0.0,
        depth: float = 5.0,
        actor: Actor = Actor.SYSTEM,
        reason: str = "",
    ) -> QueueItem:
        """
        入队
        
        自动设置状态为 PENDING
        """
        # 创建队列项
        item = QueueItem(
            topic=topic,
            status=State.PENDING,
            lineage=lineage or LineageInfo(),
            score=score,
            depth=depth,
        )
        
        # 使用状态机设置初始状态
        result = self._sm.transition(
            topic=topic,
            to_state=State.PENDING,
            actor=actor,
            reason=reason,
            context={"item_id": item.id},
        )
        
        if not result.success:
            raise QueueOperationError(f"Failed to enqueue: {result.error}")
        
        # 更新历史
        item.state_history = [result.transition] if result.transition else []
        
        # 保存到仓库
        self._repo.save(item)
        
        return item
    
    def claim_next(
        self,
        agent_id: str,
        filter_fn: Optional[Callable[[QueueItem], bool]] = None,
    ) -> Optional[QueueItem]:
        """
        原子claim下一个待处理项
        
        自动更新状态: PENDING -> CLAIMED
        """
        # 获取所有pending项，按分数排序
        pending_items = self._repo.find_by_status(State.PENDING)
        pending_items.sort(key=lambda x: x.score, reverse=True)
        
        # 应用自定义过滤
        if filter_fn:
            pending_items = [i for i in pending_items if filter_fn(i)]
        
        for item in pending_items:
            # 尝试状态转换
            result = self._sm.transition(
                topic=item.topic,
                to_state=State.CLAIMED,
                actor=Actor.SPIDER_AGENT,
                reason=f"Claimed by {agent_id}",
                context={"agent_id": agent_id},
            )
            
            if result.success:
                # 更新项
                item.status = State.CLAIMED
                item.state_history.append(result.transition)
                item.metadata["claimed_by"] = agent_id
                item.metadata["claimed_at"] = datetime.now().isoformat()
                
                self._repo.save(item)
                return item
        
        return None
    
    def start_exploration(self, item_id: str, agent_id: str) -> bool:
        """
        标记开始探索
        
        状态: CLAIMED -> EXPLORING
        """
        item = self._repo.get_by_id(item_id)
        if not item:
            return False
        
        result = self._sm.transition(
            topic=item.topic,
            to_state=State.EXPLORING,
            actor=Actor.SPIDER_AGENT,
            reason=f"Start exploration by {agent_id}",
        )
        
        if result.success:
            item.status = State.EXPLORING
            item.state_history.append(result.transition)
            self._repo.save(item)
            return True
        
        return False
    
    def complete_exploration(
        self,
        item_id: str,
        result: ExplorationResult,
    ) -> bool:
        """
        标记探索完成
        
        状态: EXPLORING -> DONE
        """
        item = self._repo.get_by_id(item_id)
        if not item:
            return False
        
        transition_result = self._sm.transition(
            topic=item.topic,
            to_state=State.DONE,
            actor=Actor.SPIDER_AGENT,
            reason="Exploration completed",
            context={"result": result.to_dict()},
        )
        
        if transition_result.success:
            item.status = State.DONE
            item.state_history.append(transition_result.transition)
            item.metadata["exploration_result"] = result.to_dict()
            self._repo.save(item)
            return True
        
        return False
    
    def fail_exploration(
        self,
        item_id: str,
        error: str,
        retryable: bool = True,
    ) -> bool:
        """
        标记探索失败
        
        根据重试策略决定状态：FAILED 或 PENDING
        """
        item = self._repo.get_by_id(item_id)
        if not item:
            return False
        
        # 检查重试次数
        retry_count = item.metadata.get("retry_count", 0)
        max_retries = 3
        
        if retryable and retry_count < max_retries:
            new_state = State.PENDING
            item.metadata["retry_count"] = retry_count + 1
        else:
            new_state = State.FAILED
        
        result = self._sm.transition(
            topic=item.topic,
            to_state=new_state,
            actor=Actor.SYSTEM,
            reason=f"Exploration failed: {error}",
            context={"error": error, "retry_count": item.metadata.get("retry_count", 0)},
        )
        
        if result.success:
            item.status = new_state
            item.state_history.append(result.transition)
            self._repo.save(item)
            return True
        
        return False
    
    def get_by_id(self, item_id: str) -> Optional[QueueItem]:
        """通过ID获取"""
        return self._repo.get_by_id(item_id)
    
    def get_by_topic(self, topic: str) -> Optional[QueueItem]:
        """通过topic获取"""
        return self._repo.get_by_topic(topic)
    
    def get_pending_count(self) -> int:
        """获取待处理数量"""
        return self._repo.count_by_status(State.PENDING)
    
    def get_stats(self) -> Dict[str, int]:
        """获取队列统计信息"""
        return {
            "pending": self._repo.count_by_status(State.PENDING),
            "claimed": self._repo.count_by_status(State.CLAIMED),
            "exploring": self._repo.count_by_status(State.EXPLORING),
            "done": self._repo.count_by_status(State.DONE),
            "failed": self._repo.count_by_status(State.FAILED),
            "total": self._repo.count_all(),
        }


class QueueOperationError(Exception):
    """队列操作错误"""
    pass
