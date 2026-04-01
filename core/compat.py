"""
Compatibility Layer - 兼容层

为旧接口提供向后兼容，内部调用新实现
"""

from typing import Optional, Dict, List

from core.feature_toggle import is_enabled
from core.queue_service import QueueService
from core.repositories import LineageInfo, QueueItem
from core.repositories.queue_repository import Actor, State


class CompatibilityLayer:
    """
    兼容层
    
    为旧代码提供兼容接口，内部根据 FeatureToggle 路由到新/旧实现
    """
    
    def __init__(
        self,
        queue_service: Optional[QueueService] = None,
        old_kg_module=None,
    ):
        self._queue_service = queue_service
        self._old_kg = old_kg_module
    
    def add_curiosity(
        self,
        topic: str,
        reason: str = "",
        relevance: float = 0.0,
        depth: float = 5.0,
        parent: Optional[str] = None,
        source: str = "system",
        **kwargs
    ) -> str:
        """
        旧接口：添加好奇心项
        
        兼容旧代码，内部路由到新的 QueueService
        """
        if is_enabled("v2_queue") and self._queue_service:
            # 使用新实现
            lineage = LineageInfo(
                parent_topic=parent,
                injected_by=source,
                original_reason=reason,
                exploration_path=[parent] if parent else [],
            )
            
            item = self._queue_service.enqueue(
                topic=topic,
                lineage=lineage,
                score=relevance,
                depth=depth,
                actor=Actor.SYSTEM,
                reason=reason,
            )
            
            return item.id
        else:
            # 使用旧实现
            if self._old_kg:
                return self._old_kg.add_curiosity(
                    topic=topic,
                    reason=reason,
                    relevance=relevance,
                    depth=depth,
                    **kwargs
                )
            raise RuntimeError("No implementation available")
    
    def claim_pending_item(self) -> Optional[Dict]:
        """
        旧接口：claim pending item
        
        返回兼容旧代码的字典格式
        """
        if is_enabled("v2_queue") and self._queue_service:
            item = self._queue_service.claim_next(agent_id="legacy_api")
            
            if item:
                return {
                    "id": item.id,
                    "topic": item.topic,
                    "status": item.status.value,
                    "score": item.score,
                    "depth": item.depth,
                    "lineage": item.lineage.to_dict(),
                    "parent": item.lineage.parent_topic,
                }
            return None
        else:
            if self._old_kg:
                return self._old_kg.claim_pending_item()
            raise RuntimeError("No implementation available")
    
    def update_curiosity_status(self, topic: str, status: str) -> bool:
        """
        旧接口：更新状态（已废弃）
        
        在新系统中状态由 StateMachine 自动管理
        """
        if is_enabled("v2_statemachine"):
            # 新系统中状态自动管理，此操作不再需要
            return True
        else:
            if self._old_kg:
                return self._old_kg.update_curiosity_status(topic, status)
            return False
    
    def list_pending(self) -> List[Dict]:
        """旧接口：列出待处理项"""
        if is_enabled("v2_queue") and self._queue_service:
            # 获取统计信息
            stats = self._queue_service.get_stats()
            
            # 返回兼容格式
            return [{
                "count": stats.get("pending", 0),
                "status": "pending",
            }]
        else:
            if self._old_kg:
                return self._old_kg.list_pending()
            return []
    
    def get_queue_stats(self) -> Dict[str, int]:
        """获取队列统计"""
        if is_enabled("v2_queue") and self._queue_service:
            return self._queue_service.get_stats()
        else:
            if self._old_kg:
                return self._old_kg.get_queue_stats()
            return {}


# 全局兼容层实例
_compat_layer: Optional[CompatibilityLayer] = None


def init_compat_layer(queue_service: QueueService, old_kg_module=None):
    """初始化兼容层"""
    global _compat_layer
    _compat_layer = CompatibilityLayer(queue_service, old_kg_module)


def get_compat_layer() -> CompatibilityLayer:
    """获取兼容层实例"""
    if _compat_layer is None:
        raise RuntimeError("Compatibility layer not initialized")
    return _compat_layer


# 便捷函数，直接暴露旧接口
def add_curiosity(*args, **kwargs):
    """添加好奇心项（兼容接口）"""
    return get_compat_layer().add_curiosity(*args, **kwargs)


def claim_pending_item():
    """Claim pending item（兼容接口）"""
    return get_compat_layer().claim_pending_item()


def update_curiosity_status(topic: str, status: str):
    """更新状态（兼容接口，已废弃）"""
    return get_compat_layer().update_curiosity_status(topic, status)


def list_pending():
    """列出待处理项（兼容接口）"""
    return get_compat_layer().list_pending()
