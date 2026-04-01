"""
基础架构集成测试

测试 Week 1 实现的核心组件
"""

import os
import sys
import tempfile
import shutil
import threading
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.persistence import FileLockManager, create_lock_manager
from core.repositories import (
    StateRepository, QueueRepository, 
    StateInfo, QueueItem, LineageInfo,
    State, Actor, StateTransition, BackupManager
)
from core.state_machine import ExplorationStateMachine, SegmentedLock
from core.timeout_monitor import TimeoutMonitor
from core.queue_service import QueueService, ExplorationResult
from core.feature_toggle import FeatureToggle


class TestFileLockManager:
    """测试文件锁管理器"""
    
    def test_basic_lock(self):
        """测试基本锁功能"""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_file = os.path.join(tmpdir, "test.lock")
            lock_mgr = FileLockManager(lock_file)
            
            # 测试写锁
            with lock_mgr.write_lock():
                pass  # 锁应该成功获取
            
            # 测试读锁
            with lock_mgr.read_lock():
                pass  # 锁应该成功获取
            
            print("✓ FileLockManager basic lock test passed")
    
    def test_concurrent_access(self):
        """测试并发访问"""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_file = os.path.join(tmpdir, "test.lock")
            lock_mgr = FileLockManager(lock_file)
            data_file = os.path.join(tmpdir, "data.json")
            
            results = []
            
            def writer(value):
                with lock_mgr.write_lock():
                    with open(data_file, 'w') as f:
                        f.write(str(value))
                    results.append(f"wrote {value}")
            
            # 启动多个写线程
            threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            
            assert len(results) == 5, f"Expected 5 results, got {len(results)}"
            print("✓ FileLockManager concurrent access test passed")


class TestRepositories:
    """测试仓库"""
    
    def test_state_repository(self):
        """测试状态仓库"""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_mgr = create_lock_manager(os.path.join(tmpdir, "lock"))
            backup_mgr = BackupManager(os.path.join(tmpdir, "backup"))
            repo = StateRepository(tmpdir, lock_mgr, backup_mgr)
            
            # 测试保存状态
            state_info = StateInfo(
                topic="test_topic",
                state="pending",
                history=[],
            )
            repo.save_state(state_info)
            
            # 测试读取状态
            retrieved = repo.get_state("test_topic")
            assert retrieved is not None
            assert retrieved.topic == "test_topic"
            assert retrieved.state == "pending"
            
            print("✓ StateRepository test passed")
    
    def test_queue_repository(self):
        """测试队列仓库"""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_mgr = create_lock_manager(os.path.join(tmpdir, "lock"))
            backup_mgr = BackupManager(os.path.join(tmpdir, "backup"))
            repo = QueueRepository(tmpdir, lock_mgr, backup_mgr)
            
            # 测试保存队列项
            item = QueueItem(
                topic="test_topic",
                status=State.PENDING,
                score=8.5,
            )
            repo.save(item)
            
            # 测试读取
            retrieved = repo.get_by_id(item.id)
            assert retrieved is not None
            assert retrieved.topic == "test_topic"
            assert retrieved.score == 8.5
            
            # 测试按状态查找
            pending_items = repo.find_by_status(State.PENDING)
            assert len(pending_items) == 1
            
            print("✓ QueueRepository test passed")


class TestStateMachine:
    """测试状态机"""
    
    def test_basic_transition(self):
        """测试基本状态转换"""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_mgr = create_lock_manager(os.path.join(tmpdir, "lock"))
            backup_mgr = BackupManager(os.path.join(tmpdir, "backup"))
            state_repo = StateRepository(tmpdir, lock_mgr, backup_mgr)
            sm = ExplorationStateMachine(state_repo)
            
            # PENDING -> CLAIMED
            result = sm.transition("topic1", State.PENDING, Actor.SYSTEM)
            assert result.success
            
            result = sm.transition("topic1", State.CLAIMED, Actor.SPIDER_AGENT)
            assert result.success
            
            # CLAIMED -> EXPLORING
            result = sm.transition("topic1", State.EXPLORING, Actor.SPIDER_AGENT)
            assert result.success
            
            # EXPLORING -> DONE
            result = sm.transition("topic1", State.DONE, Actor.SPIDER_AGENT)
            assert result.success
            
            print("✓ StateMachine basic transition test passed")
    
    def test_invalid_transition(self):
        """测试非法状态转换"""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_mgr = create_lock_manager(os.path.join(tmpdir, "lock"))
            backup_mgr = BackupManager(os.path.join(tmpdir, "backup"))
            state_repo = StateRepository(tmpdir, lock_mgr, backup_mgr)
            sm = ExplorationStateMachine(state_repo)
            
            sm.transition("topic1", State.PENDING, Actor.SYSTEM)
            sm.transition("topic1", State.CLAIMED, Actor.SPIDER_AGENT)
            
            # CLAIMED 不能直接到 DONE
            result = sm.transition("topic1", State.DONE, Actor.SPIDER_AGENT)
            assert not result.success
            
            print("✓ StateMachine invalid transition test passed")
    
    def test_concurrent_claim(self):
        """测试并发 claim"""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_mgr = create_lock_manager(os.path.join(tmpdir, "lock"))
            backup_mgr = BackupManager(os.path.join(tmpdir, "backup"))
            state_repo = StateRepository(tmpdir, lock_mgr, backup_mgr)
            queue_repo = QueueRepository(tmpdir, lock_mgr, backup_mgr)
            sm = ExplorationStateMachine(state_repo)
            qs = QueueService(queue_repo, sm)
            
            # 入队一个任务
            qs.enqueue("test_topic", score=8.0)
            
            results = []
            
            def claim_worker():
                item = qs.claim_next("worker")
                results.append(item is not None)
            
            # 10 个线程同时 claim
            threads = [threading.Thread(target=claim_worker) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            
            # 只有一个应该成功
            success_count = sum(results)
            assert success_count == 1, f"Expected 1 success, got {success_count}"
            
            print("✓ StateMachine concurrent claim test passed")


class TestQueueService:
    """测试队列服务"""
    
    def test_enqueue_and_claim(self):
        """测试入队和 claim"""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_mgr = create_lock_manager(os.path.join(tmpdir, "lock"))
            backup_mgr = BackupManager(os.path.join(tmpdir, "backup"))
            state_repo = StateRepository(tmpdir, lock_mgr, backup_mgr)
            queue_repo = QueueRepository(tmpdir, lock_mgr, backup_mgr)
            sm = ExplorationStateMachine(state_repo)
            qs = QueueService(queue_repo, sm)
            
            # 入队
            item = qs.enqueue("topic1", score=8.5)
            assert item.status == State.PENDING
            
            # claim
            claimed = qs.claim_next("agent1")
            assert claimed is not None
            assert claimed.status == State.CLAIMED
            
            print("✓ QueueService enqueue and claim test passed")
    
    def test_exploration_flow(self):
        """测试完整探索流程"""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_mgr = create_lock_manager(os.path.join(tmpdir, "lock"))
            backup_mgr = BackupManager(os.path.join(tmpdir, "backup"))
            state_repo = StateRepository(tmpdir, lock_mgr, backup_mgr)
            queue_repo = QueueRepository(tmpdir, lock_mgr, backup_mgr)
            sm = ExplorationStateMachine(state_repo)
            qs = QueueService(queue_repo, sm)
            
            # 入队
            item = qs.enqueue("topic1", score=8.0)
            
            # claim
            claimed = qs.claim_next("agent1")
            assert claimed is not None
            
            # 开始探索
            success = qs.start_exploration(claimed.id, "agent1")
            assert success
            
            # 完成探索
            result = ExplorationResult(
                topic="topic1",
                summary="Test summary",
                sources=["source1"],
                quality=8.5,
                findings={},
            )
            success = qs.complete_exploration(claimed.id, result)
            assert success
            
            # 验证状态
            final_item = qs.get_by_id(claimed.id)
            assert final_item.status == State.DONE
            
            print("✓ QueueService exploration flow test passed")


class TestFeatureToggle:
    """测试功能开关"""
    
    def test_basic_toggle(self):
        """测试基本开关功能"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "features.json")
            ft = FeatureToggle(config_file)
            
            # 默认应该禁用
            assert not ft.is_enabled("v2_queue")
            
            # 启用
            ft.enable("v2_queue")
            assert ft.is_enabled("v2_queue")
            
            # 禁用
            ft.disable("v2_queue")
            assert not ft.is_enabled("v2_queue")
            
            # 切换
            ft.toggle("v2_queue")
            assert ft.is_enabled("v2_queue")
            
            print("✓ FeatureToggle basic toggle test passed")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("Week 1 Integration Tests")
    print("=" * 60)
    
    tests = [
        ("FileLockManager", TestFileLockManager()),
        ("Repositories", TestRepositories()),
        ("StateMachine", TestStateMachine()),
        ("QueueService", TestQueueService()),
        ("FeatureToggle", TestFeatureToggle()),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_suite in tests:
        print(f"\n{'='*40}")
        print(f"Testing {name}")
        print('='*40)
        
        for method_name in dir(test_suite):
            if method_name.startswith('test_'):
                try:
                    getattr(test_suite, method_name)()
                    passed += 1
                except Exception as e:
                    failed += 1
                    print(f"✗ {method_name} failed: {e}")
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
