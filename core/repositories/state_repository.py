"""
State Repository - 状态数据持久化
"""

import logging
import os
import json
import shutil
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass, field

from core.persistence.file_lock_manager import FileLockManager

logger = logging.getLogger(__name__)


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
class StateInfo:
    """状态信息"""
    topic: str
    state: str
    history: List[StateTransition] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "state": self.state,
            "history": [h.to_dict() for h in self.history],
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'StateInfo':
        return cls(
            topic=data["topic"],
            state=data["state"],
            history=[StateTransition.from_dict(h) for h in data.get("history", [])],
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )


class BackupManager:
    """
    备份管理器
    """
    
    def __init__(self, backup_dir: str):
        self._backup_dir = backup_dir
        os.makedirs(backup_dir, exist_ok=True)
    
    def create_backup(self, file_path: str) -> str:
        """
        创建文件备份
        
        Returns:
            备份文件路径
        """
        if not os.path.exists(file_path):
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = os.path.basename(file_path)
        backup_path = os.path.join(self._backup_dir, f"{filename}.{timestamp}.bak")
        
        shutil.copy2(file_path, backup_path)
        return backup_path
    
    def list_backups(self, file_path: str) -> List[str]:
        """列出文件的所有备份"""
        filename = os.path.basename(file_path)
        backups = []
        
        for f in os.listdir(self._backup_dir):
            if f.startswith(filename) and f.endswith(".bak"):
                backups.append(os.path.join(self._backup_dir, f))
        
        return sorted(backups, reverse=True)
    
    def restore_backup(self, backup_path: str, target_path: str) -> bool:
        """从备份恢复"""
        try:
            shutil.copy2(backup_path, target_path)
            return True
        except Exception as e:
            logger.warning(f"Failed to restore backup from '{backup_path}' to '{target_path}': {e}", exc_info=True)
            return False


class StateRepository:
    """
    状态仓库
    
    负责状态数据的持久化存储
    - 原子写操作
    - 自动备份
    - 内存缓存
    """
    
    VERSION = "2.0"
    
    def __init__(
        self,
        data_dir: str,
        file_lock_manager: FileLockManager,
        backup_manager: BackupManager,
    ):
        self._data_dir = data_dir
        self._state_file = os.path.join(data_dir, "state_v2.json")
        self._lock_mgr = file_lock_manager
        self._backup_mgr = backup_manager
        self._cache: Dict[str, StateInfo] = {}
        
        self._init_storage()
    
    def _init_storage(self):
        """初始化存储"""
        os.makedirs(self._data_dir, exist_ok=True)
        
        if not os.path.exists(self._state_file):
            self._write_initial_state()
    
    def _write_initial_state(self):
        """写入初始状态"""
        initial = {
            "version": self.VERSION,
            "created_at": datetime.now().isoformat(),
            "topics": {},
            "metadata": {},
        }
        self._atomic_write(initial)
    
    def _atomic_write(self, data: dict):
        """原子写入"""
        temp_file = f"{self._state_file}.tmp"
        
        with self._lock_mgr.write_lock():
            # 备份原文件
            if os.path.exists(self._state_file):
                self._backup_mgr.create_backup(self._state_file)
            
            # 写入临时文件
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            
            # 原子重命名
            os.rename(temp_file, self._state_file)
    
    def _read_state(self) -> dict:
        """读取状态"""
        with self._lock_mgr.read_lock():
            with open(self._state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    
    def get_state(self, topic: str) -> Optional[StateInfo]:
        """获取话题状态"""
        # 先查缓存
        if topic in self._cache:
            return self._cache[topic]
        
        # 查文件
        data = self._read_state()
        topic_data = data.get("topics", {}).get(topic)
        
        if topic_data:
            state_info = StateInfo.from_dict(topic_data)
            # 更新缓存
            self._cache[topic] = state_info
            return state_info
        
        return None
    
    def save_state(self, state_info: StateInfo):
        """保存状态"""
        # 更新时间戳
        state_info.updated_at = datetime.now().isoformat()
        
        # 更新缓存
        self._cache[state_info.topic] = state_info
        
        # 更新文件
        data = self._read_state()
        data["topics"][state_info.topic] = state_info.to_dict()
        self._atomic_write(data)
    
    def get_all_states(self) -> Dict[str, StateInfo]:
        """获取所有状态"""
        data = self._read_state()
        return {
            topic: StateInfo.from_dict(info)
            for topic, info in data.get("topics", {}).items()
        }
    
    def delete_state(self, topic: str) -> bool:
        """删除状态"""
        if topic in self._cache:
            del self._cache[topic]
        
        data = self._read_state()
        if topic in data.get("topics", {}):
            del data["topics"][topic]
            self._atomic_write(data)
            return True
        return False
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
    
    def restore_from_backup(self, backup_path: str) -> bool:
        """从备份恢复"""
        return self._backup_mgr.restore_backup(backup_path, self._state_file)
