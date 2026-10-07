"""Stress tests for NodeLockRegistry - high contention and deadlock prevention."""
import threading
import random
import pytest
from core.node_lock_registry import NodeLockRegistry


class TestNodeLockStress:
    """Stress test suite for NodeLockRegistry."""

    def test_high_contention_100_threads(self):
        """100 threads competing for 10 nodes with 10 operations each should complete without deadlock."""
        NodeLockRegistry.clear_all_locks()
        
        num_threads = 100
        num_nodes = 10
        ops_per_thread = 10
        
        results = []
        errors = []
        results_lock = threading.Lock()
        
        def worker(thread_id: int):
            try:
                for _ in range(ops_per_thread):
                    node_name = f"node_{thread_id % num_nodes}"
                    lock = NodeLockRegistry.get_lock(node_name)
                    with lock:
                        with results_lock:
                            results.append(thread_id)
            except Exception as e:
                with results_lock:
                    errors.append((thread_id, str(e)))
        
        threads = [
            threading.Thread(target=worker, args=(i,))
            for i in range(num_threads)
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join(timeout=30.0)
        
        alive_threads = [t for t in threads if t.is_alive()]
        assert len(alive_threads) == 0, f"Deadlock: {len(alive_threads)} threads still alive"
        
        assert len(errors) == 0, f"Errors: {errors}"
        
        expected_ops = num_threads * ops_per_thread
        assert len(results) == expected_ops

    def test_deadlock_prevention_with_random_order(self):
        """Random lock acquisition order should not cause deadlocks due to sorted lock pairs."""
        NodeLockRegistry.clear_all_locks()
        
        num_threads = 50
        num_iterations = 20
        
        results = []
        errors = []
        results_lock = threading.Lock()
        
        def random_acquirer(thread_id: int):
            try:
                for _ in range(num_iterations):
                    node_a = f"node_{random.randint(0, 9)}"
                    node_b = f"node_{random.randint(0, 9)}"
                    
                    if node_a != node_b:
                        lock_a, lock_b = NodeLockRegistry.get_lock_pair(node_a, node_b)
                        with lock_a:
                            with lock_b:
                                with results_lock:
                                    results.append(thread_id)
                    else:
                        lock = NodeLockRegistry.get_lock(node_a)
                        with lock:
                            with results_lock:
                                results.append(thread_id)
            except Exception as e:
                with results_lock:
                    errors.append((thread_id, str(e)))
        
        threads = [
            threading.Thread(target=random_acquirer, args=(i,))
            for i in range(num_threads)
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join(timeout=30.0)
        
        alive_threads = [t for t in threads if t.is_alive()]
        assert len(alive_threads) == 0, f"Deadlock: {len(alive_threads)} threads still alive"
        
        assert len(errors) == 0, f"Errors: {errors}"
        
        expected_ops = num_threads * num_iterations
        assert len(results) == expected_ops

    def test_global_write_lock_with_concurrent_reads(self):
        """Global write lock should serialize access while allowing concurrent reads."""
        NodeLockRegistry.clear_all_locks()
        
        read_count = 0
        write_count = 0
        count_lock = threading.Lock()
        
        def reader():
            nonlocal read_count
            for _ in range(10):
                lock = NodeLockRegistry.get_lock(f"node_{random.randint(0, 4)}")
                with lock:
                    with count_lock:
                        read_count += 1
        
        def writer():
            nonlocal write_count
            for _ in range(5):
                with NodeLockRegistry.global_write_lock():
                    with count_lock:
                        write_count += 1
        
        threads = []
        for _ in range(20):
            threads.append(threading.Thread(target=reader))
        for _ in range(5):
            threads.append(threading.Thread(target=writer))
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join(timeout=30.0)
        
        alive_threads = [t for t in threads if t.is_alive()]
        assert len(alive_threads) == 0, f"Deadlock: {len(alive_threads)} threads still alive"
        
        assert read_count == 200
        assert write_count == 25
