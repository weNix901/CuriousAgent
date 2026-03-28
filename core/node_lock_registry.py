"""Node-level locking system for Knowledge Graph thread safety."""
import threading


class NodeLockRegistry:
    """Registry for managing node-level locks with deadlock prevention."""
    
    _locks: dict = {}
    _global_write_lock: threading.RLock = threading.RLock()
    _registry_lock: threading.Lock = threading.Lock()
    
    @classmethod
    def get_lock(cls, node_name: str) -> threading.Lock:
        """Get or create a lock for the specified node."""
        with cls._registry_lock:
            if node_name not in cls._locks:
                cls._locks[node_name] = threading.Lock()
            return cls._locks[node_name]
    
    @classmethod
    def get_lock_pair(cls, name_a: str, name_b: str) -> tuple:
        """Get a sorted pair of locks to prevent deadlocks."""
        lock_a = cls.get_lock(name_a)
        lock_b = cls.get_lock(name_b)
        return tuple(sorted([lock_a, lock_b], key=lambda l: id(l)))
    
    @classmethod
    def global_write_lock(cls) -> threading.RLock:
        """Get the global write lock for cross-node operations."""
        return cls._global_write_lock
    
    @classmethod
    def clear_all_locks(cls):
        """Clear all node locks (for testing)."""
        with cls._registry_lock:
            cls._locks.clear()
