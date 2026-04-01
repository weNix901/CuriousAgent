"""
Queue Repository - 队列数据持久化
"""

import os
import json
from datetime import datetime
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from enum import Enum

from core.persistence.file_lock_manager import FileLockManager
from core.repositories.state_repository import BackupManager


class State(Enum):
    """队列项状态"""
    PENDING = "pending"
    CLAIMED = "claimed"
    EXPLORING = "exploring"
    DONE = "done"
    PAUSED = "paused"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Actor(Enum):
    """执行者"""
    SYSTEM = "system"
    SPIDER_AGENT = "spider_agent"
    DREAM_AGENT = "dream_agent"
    ASYNC_TRIGGER = "async_trigger"
    USER = "user"


@dataclass
class LineageInfo:
    """话题血缘信息"""
    parent_topic: Optional[str] = None
    injected_by: str = "system"
    injected_at: str = field(default_factory=lambda: datetime.now().isoformat())
    decomposition_depth: int = 0
    exploration_path: List[str] = field(default_factory=list)
    original_reason: str = ""
    
    def to_dict(self) -> dict:
        return {
            "parent_topic": self.parent_topic,
            "injected_by": self.injected_by,
            "injected_at": self.injected_at,
            "decomposition_depth": self.decomposition_depth,
            "exploration_path": self.exploration_path,
            "original_reason": self.original_reason,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'LineageInfo':
        return cls(
            parent_topic=data.get("parent_topic"),
            injected_by=data.get("injected_by", "system"),
            injected_at=data.get("injected_at", datetime.now().isoformat()),
            decomposition_depth=data.get("decomposition_depth", 0),
            exploration_path=data.get("exploration_path", []),
            original_reason=data.get("original_reason", ""),
        )


@dataclass
class StateTransition:
    """状态转换记录"""
    from_state: Optional[str]
    to_state: str
    actor: str
    timestamp: str
    reason: str
    context: Dict
    
    def to_dict(self) -> dict:
        return {
            "from": self.from_state,
            "to": self.to_state,
            "actor": self.actor,
            "timestamp": self.timestamp,
            "reason": self.reason,
            "context": self.context,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'StateTransition':
        return cls(
            from_state=data.get("from"),
            to_state=data["to"],
            actor=data["actor"],
            timestamp=data["timestamp"],
            reason=data.get("reason", ""),
            context=data.get("context", {}),
        )


@dataclass
class QueueItem:
    """队列项"""
    id: str
    topic: str
    status: State
    state_history: List[StateTransition] = field(default_factory=list)
    lineage: LineageInfo = field(default_factory=LineageInfo)
    score: float = 0.0
    depth: float = 5.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.id:
            self.id = self._generate_id()
    
    def _generate_id(self) -> str:
        """生成唯一ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_topic = "".join(c if c.isalnum() else "_" for c in self.topic[:20])
        return f"cq_{timestamp}_{safe_topic}"
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "topic": self.topic,
            "status": self.status.value,
            "state_history": [h.to_dict() for h in self.state_history],
            "lineage": self.lineage.to_dict(),
            "score": self.score,
            "depth": self.depth,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'QueueItem':
        return cls(
            id=data["id"],
            topic=data["topic"],
            status=State(data["status"]),
            state_history=[StateTransition.from_dict(h) for h in data.get("state_history", [])],
            lineage=LineageInfo.from_dict(data.get("lineage", {})),
            score=data.get("score", 0.0),
            depth=data.get("depth", 5.0),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )


class QueueRepository:
    """
    队列仓库
    
    负责队列数据的持久化存储
    """
    
    VERSION = "2.0"
    
    def __init__(
        self,
        data_dir: str,
        file_lock_manager: FileLockManager,
        backup_manager: BackupManager,
    ):
        self._data_dir = data_dir
        self._queue_file = os.path.join(data_dir, "curiosity_queue_v2.json")
        self._lock_mgr = file_lock_manager
        self._backup_mgr = backup_manager
        
        self._init_storage()
    
    def _init_storage(self):
        """初始化存储"""
        os.makedirs(self._data_dir, exist_ok=True)
        
        if not os.path.exists(self._queue_file):
            self._write_initial_queue()
    
    def _write_initial_queue(self):
        """写入初始队列"""
        initial = {
            "version": self.VERSION,
            "created_at": datetime.now().isoformat(),
            "items": [],
            "sequence": 0,
            "metadata": {},
        }
        self._atomic_write(initial)
    
    def _atomic_write(self, data: dict):
        """原子写入"""
        temp_file = f"{self._queue_file}.tmp"
        
        with self._lock_mgr.write_lock():
            # 备份
            if os.path.exists(self._queue_file):
                self._backup_mgr.create_backup(self._queue_file)
            
            # 写入临时文件
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            
            # 原子重命名
            os.rename(temp_file, self._queue_file)
    
    def _read_queue(self) -> dict:
        """读取队列"""
        with self._lock_mgr.read_lock():
            with open(self._queue_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    
    def save(self, item: QueueItem):
        """保存队列项"""
        item.updated_at = datetime.now().isoformat()
        
        data = self._read_queue()
        items = data.get("items", [])
        
        # 查找并更新，或新增
        for i, existing in enumerate(items):
            if existing["id"] == item.id:
                items[i] = item.to_dict()
                break
        else:
            items.append(item.to_dict())
        
        data["items"] = items
        self._atomic_write(data)
    
    def get_by_id(self, item_id: str) -> Optional[QueueItem]:
        """通过ID获取"""
        data = self._read_queue()
        for item_data in data.get("items", []):
            if item_data["id"] == item_id:
                return QueueItem.from_dict(item_data)
        return None
    
    def get_by_topic(self, topic: str) -> Optional[QueueItem]:
        """通过topic获取"""
        data = self._read_queue()
        for item_data in data.get("items", []):
            if item_data["topic"] == topic:
                return QueueItem.from_dict(item_data)
        return None
    
    def find_by_status(self, status: State) -> List[QueueItem]:
        """按状态查找"""
        data = self._read_queue()
        return [
            QueueItem.from_dict(item_data)
            for item_data in data.get("items", [])
            if item_data.get("status") == status.value
        ]
    
    def find_all(self) -> List[QueueItem]:
        """获取所有"""
        data = self._read_queue()
        return [QueueItem.from_dict(item_data) for item_data in data.get("items", [])]
    
    def count_by_status(self, status: State) -> int:
        """按状态计数"""
        return len(self.find_by_status(status))
    
    def count_all(self) -> int:
        """总数"""
        data = self._read_queue()
        return len(data.get("items", []))
    
    def delete(self, item_id: str) -> bool:
        """删除队列项"""
        data = self._read_queue()
        items = data.get("items", [])
        
        for i, item_data in enumerate(items):
            if item_data["id"] == item_id:
                del items[i]
                data["items"] = items
                self._atomic_write(data)
                return True
        
        return False
    
    def get_next_sequence(self) -> int:
        """获取下一个序列号（原子操作）"""
        with self._lock_mgr.write_lock():
            data = self._read_queue()
            seq = data.get("sequence", 0) + 1
            data["sequence"] = seq
            self._atomic_write(data)
            return seq
