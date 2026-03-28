"""Tests for NodeLockRegistry - node-level locking system for Knowledge Graph thread safety."""
import threading
import pytest
from core.node_lock_registry import NodeLockRegistry


class TestNodeLockRegistry:
    """Test suite for NodeLockRegistry class."""

    def test_global_write_lock_is_rlock(self):
        """Global write lock should be an RLock for reentrant locking."""
        lock = NodeLockRegistry.global_write_lock()
        assert isinstance(lock, type(threading.RLock()))

    def test_node_lock_created_on_demand(self):
        """Node locks should be created when first requested."""
        # Clear any existing locks first
        NodeLockRegistry.clear_all_locks()
        
        lock = NodeLockRegistry.get_lock("test_node")
        assert lock is not None
        assert isinstance(lock, type(threading.Lock()))

    def test_different_nodes_different_locks(self):
        """Different node names should return different lock instances."""
        NodeLockRegistry.clear_all_locks()
        
        lock_a = NodeLockRegistry.get_lock("node_a")
        lock_b = NodeLockRegistry.get_lock("node_b")
        
        assert lock_a is not lock_b

    def test_same_node_same_lock(self):
        """Same node name should return the same lock instance."""
        NodeLockRegistry.clear_all_locks()
        
        lock1 = NodeLockRegistry.get_lock("same_node")
        lock2 = NodeLockRegistry.get_lock("same_node")
        
        assert lock1 is lock2

    def test_lock_pair_sorted_by_id(self):
        """Lock pairs should be sorted by id to prevent deadlocks."""
        NodeLockRegistry.clear_all_locks()
        
        # Get locks in different orders
        pair1 = NodeLockRegistry.get_lock_pair("node_a", "node_b")
        pair2 = NodeLockRegistry.get_lock_pair("node_b", "node_a")
        
        # Both pairs should have locks in same order
        assert pair1[0] is pair2[0]
        assert pair1[1] is pair2[1]

    def test_concurrent_reads_no_deadlock(self):
        """Multiple threads reading different nodes should not deadlock."""
        NodeLockRegistry.clear_all_locks()
        
        results = []
        errors = []
        
        def read_node(node_name: str, iterations: int):
            try:
                for _ in range(iterations):
                    lock = NodeLockRegistry.get_lock(node_name)
                    with lock:
                        results.append(f"{node_name}_read")
            except Exception as e:
                errors.append(str(e))
        
        # Create 5 threads reading different nodes
        threads = []
        for i in range(5):
            thread = threading.Thread(
                target=read_node,
                args=(f"node_{i}", 10)
            )
            threads.append(thread)
        
        # Start all threads
        for t in threads:
            t.start()
        
        # Wait for all threads with timeout (deadlock detection)
        for t in threads:
            t.join(timeout=5.0)
        
        # Check no threads are still alive (deadlock indicator)
        alive_threads = [t for t in threads if t.is_alive()]
        assert len(alive_threads) == 0, f"Deadlock detected: {len(alive_threads)} threads still alive"
        
        # Check no errors occurred
        assert len(errors) == 0, f"Errors during concurrent reads: {errors}"
        
        # Check all operations completed
        assert len(results) == 50  # 5 threads * 10 iterations

    def test_lock_ordering_prevents_deadlock(self):
        """Lock ordering in pairs should prevent deadlocks with 3 threads."""
        NodeLockRegistry.clear_all_locks()
        
        results = []
        errors = []
        
        def acquire_pair(node_a: str, node_b: str, iterations: int):
            try:
                for _ in range(iterations):
                    lock_a, lock_b = NodeLockRegistry.get_lock_pair(node_a, node_b)
                    with lock_a:
                        with lock_b:
                            results.append(f"{node_a}_{node_b}")
            except Exception as e:
                errors.append(str(e))
        
        # Create 3 threads acquiring locks in different orders
        threads = [
            threading.Thread(target=acquire_pair, args=("node_1", "node_2", 10)),
            threading.Thread(target=acquire_pair, args=("node_2", "node_3", 10)),
            threading.Thread(target=acquire_pair, args=("node_3", "node_1", 10)),
        ]
        
        # Start all threads
        for t in threads:
            t.start()
        
        # Wait for all threads with timeout (deadlock detection)
        for t in threads:
            t.join(timeout=5.0)
        
        # Check no threads are still alive (deadlock indicator)
        alive_threads = [t for t in threads if t.is_alive()]
        assert len(alive_threads) == 0, f"Deadlock detected: {len(alive_threads)} threads still alive"
        
        # Check no errors occurred
        assert len(errors) == 0, f"Errors during lock acquisition: {errors}"
        
        # Check all operations completed
        assert len(results) == 30  # 3 threads * 10 iterations

    def test_clear_all_locks(self):
        """clear_all_locks should remove all node locks."""
        # Create some locks
        NodeLockRegistry.get_lock("node_1")
        NodeLockRegistry.get_lock("node_2")
        
        # Clear them
        NodeLockRegistry.clear_all_locks()
        
        # Getting locks again should create new instances
        # (WeakValueDictionary will have cleared them)
        # This test verifies the method exists and runs without error
        NodeLockRegistry.clear_all_locks()
