"""
文件锁管理器

提供进程级的文件锁，解决多进程并发读写 JSON 文件的问题
"""

import logging
import os
import threading
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# 尝试导入 portalocker，如果不存在则使用 fcntl（Unix only）
try:
    import portalocker
    PORTALOCKER_AVAILABLE = True
except ImportError:
    PORTALOCKER_AVAILABLE = False
    try:
        import fcntl
        FCNTL_AVAILABLE = True
    except ImportError:
        FCNTL_AVAILABLE = False


class FileLockManager:
    """
    进程级文件锁管理器
    
    支持读锁（共享锁）和写锁（排他锁）
    使用场景：多进程同时读写 JSON 文件
    
    Example:
        lock_mgr = FileLockManager("knowledge/state.lock")
        
        # 读操作
        with lock_mgr.read_lock():
            data = read_json_file()
        
        # 写操作
        with lock_mgr.write_lock():
            write_json_file(data)
    """
    
    def __init__(self, lock_file: str):
        """
        初始化文件锁管理器
        
        Args:
            lock_file: 锁文件路径，用于进程间同步
        """
        self._lock_file = lock_file
        self._local_lock = threading.Lock()  # 线程级锁
        self._fd: Optional[int] = None
        
        # 确保锁文件存在
        self._ensure_lock_file()
    
    def _ensure_lock_file(self):
        """确保锁文件存在"""
        lock_dir = os.path.dirname(self._lock_file)
        if lock_dir and not os.path.exists(lock_dir):
            os.makedirs(lock_dir, exist_ok=True)
        
        if not os.path.exists(self._lock_file):
            open(self._lock_file, 'a').close()
    
    @contextmanager
    def read_lock(self):
        """
        获取读锁（共享锁）
        
        允许多个进程同时读取
        """
        self._acquire_lock(lock_type='read')
        try:
            yield self
        finally:
            self._release_lock()
    
    @contextmanager
    def write_lock(self):
        """
        获取写锁（排他锁）
        
        同一时间只有一个进程可以写入
        """
        self._acquire_lock(lock_type='write')
        try:
            yield self
        finally:
            self._release_lock()
    
    def _acquire_lock(self, lock_type: str = 'read'):
        """
        获取文件锁
        
        Args:
            lock_type: 'read' 或 'write'
        """
        # 先获取线程级锁（防止同一线程内多个上下文嵌套）
        self._local_lock.acquire()
        
        try:
            # 打开锁文件
            self._fd = open(self._lock_file, 'r+' if lock_type == 'write' else 'r')
            
            if PORTALOCKER_AVAILABLE:
                # 使用 portalocker（跨平台）
                if lock_type == 'write':
                    portalocker.lock(self._fd, portalocker.LOCK_EX)
                else:
                    portalocker.lock(self._fd, portalocker.LOCK_SH)
            
            elif FCNTL_AVAILABLE:
                # 使用 fcntl（Unix only）
                if lock_type == 'write':
                    fcntl.flock(self._fd.fileno(), fcntl.LOCK_EX)
                else:
                    fcntl.flock(self._fd.fileno(), fcntl.LOCK_SH)
            
            else:
                # 降级：无锁模式（仅单进程使用）
                import warnings
                warnings.warn("No file locking mechanism available. "
                            "Running in single-process mode only.")
        
        except Exception as e:
            logger.warning(f"Failed to acquire file lock '{self._lock_file}': {e}", exc_info=True)
            # 获取锁失败，释放线程锁
            self._local_lock.release()
            if self._fd:
                self._fd.close()
                self._fd = None
            raise
    
    def _release_lock(self):
        """释放文件锁"""
        try:
            if self._fd:
                if PORTALOCKER_AVAILABLE:
                    portalocker.unlock(self._fd)
                elif FCNTL_AVAILABLE:
                    fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
                
                self._fd.close()
                self._fd = None
        finally:
            # 释放线程锁
            self._local_lock.release()
    
    def __enter__(self):
        """支持 with 语句（默认读锁）"""
        self._acquire_lock('read')
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出 with 语句时释放锁"""
        self._release_lock()


class NoOpLockManager:
    """
    空锁管理器（用于测试或单进程环境）
    """
    
    @contextmanager
    def read_lock(self):
        yield self
    
    @contextmanager
    def write_lock(self):
        yield self
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass


# 便捷函数
def create_lock_manager(lock_file: str, enabled: bool = True) -> FileLockManager:
    """
    创建锁管理器
    
    Args:
        lock_file: 锁文件路径
        enabled: 是否启用锁（False 则返回 NoOpLockManager）
    
    Returns:
        FileLockManager 实例
    """
    if enabled:
        return FileLockManager(lock_file)
    else:
        return NoOpLockManager()
