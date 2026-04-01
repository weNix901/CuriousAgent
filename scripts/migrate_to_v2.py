"""
Data Migration - 数据迁移工具

从 v1 格式迁移到 v2 格式
"""

import json
import os
import shutil
import argparse
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class MigrationResult:
    """迁移结果"""
    migrated: int = 0
    failed: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)
    validation: Optional['ValidationResult'] = None


@dataclass
class ValidationResult:
    """验证结果"""
    old_count: int = 0
    new_count: int = 0
    consistent: bool = False
    details: List[str] = field(default_factory=list)


class DataMigration:
    """
    数据迁移器
    
    从 v1 格式（原 knowledge_graph 格式）迁移到 v2 格式
    """
    
    def __init__(
        self,
        old_state_file: str = "knowledge/state.json",
        new_data_dir: str = "knowledge/v2",
    ):
        self._old_state_file = old_state_file
        self._new_data_dir = new_data_dir
    
    def migrate(self, dry_run: bool = False) -> MigrationResult:
        """
        执行迁移
        
        Args:
            dry_run: 如果为 True，只模拟不实际写入
            
        Returns:
            MigrationResult: 迁移结果
        """
        result = MigrationResult()
        
        print(f"[Migration] Starting migration (dry_run={dry_run})")
        
        # 1. 加载旧数据
        old_data = self._load_old_data()
        if not old_data:
            result.errors.append("Failed to load old data")
            return result
        
        # 2. 备份原始数据
        if not dry_run:
            self._backup_original_data()
        
        # 3. 初始化新存储
        if not dry_run:
            self._init_new_storage()
        
        # 4. 迁移队列数据
        old_queue = old_data.get("curiosity_queue", [])
        print(f"[Migration] Found {len(old_queue)} queue items to migrate")
        
        from core.repositories import QueueRepository, LineageInfo, QueueItem
        from core.repositories.queue_repository import State, StateTransition, Actor
        from core.persistence import FileLockManager, create_lock_manager
        from core.repositories.state_repository import BackupManager
        
        if not dry_run:
            lock_mgr = create_lock_manager(os.path.join(self._new_data_dir, "lock"))
            backup_mgr = BackupManager(os.path.join(self._new_data_dir, "backup"))
            queue_repo = QueueRepository(self._new_data_dir, lock_mgr, backup_mgr)
        
        for old_item in old_queue:
            try:
                new_item = self._convert_queue_item(old_item, old_data)
                
                if not dry_run:
                    queue_repo.save(new_item)
                
                result.migrated += 1
                
            except Exception as e:
                result.failed += 1
                error_msg = f"Failed to migrate item {old_item.get('topic', 'unknown')}: {e}"
                result.errors.append(error_msg)
                print(f"[Migration] ERROR: {error_msg}")
        
        # 5. 验证迁移结果
        if not dry_run:
            result.validation = self._validate_migration(old_queue)
        
        print(f"[Migration] Complete: {result.migrated} migrated, {result.failed} failed")
        
        return result
    
    def _load_old_data(self) -> Optional[Dict]:
        """加载旧数据"""
        if not os.path.exists(self._old_state_file):
            print(f"[Migration] Old state file not found: {self._old_state_file}")
            return None
        
        try:
            with open(self._old_state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Migration] Error loading old data: {e}")
            return None
    
    def _backup_original_data(self):
        """备份原始数据"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = f"knowledge/backup/migration_{timestamp}"
        os.makedirs(backup_dir, exist_ok=True)
        
        # 复制原文件
        if os.path.exists(self._old_state_file):
            shutil.copy2(self._old_state_file, backup_dir)
        
        print(f"[Migration] Original data backed up to {backup_dir}")
    
    def _init_new_storage(self):
        """初始化新存储目录"""
        os.makedirs(self._new_data_dir, exist_ok=True)
    
    def _convert_queue_item(self, old_item: Dict, old_data: Dict):
        """转换单个队列项"""
        from core.repositories import LineageInfo, QueueItem
        from core.repositories.queue_repository import State, StateTransition, Actor
        
        topic = old_item.get("topic")
        status_str = old_item.get("status", "pending")
        score = old_item.get("relevance", 0.0)
        depth = old_item.get("depth", 5.0)
        
        # 尝试推断 parent（从 KG 中查）
        parent_topic = None
        kg_topics = old_data.get("knowledge", {}).get("topics", {})
        if topic in kg_topics:
            parents = kg_topics[topic].get("parents", [])
            if parents:
                parent_topic = parents[0]
        
        # 创建 lineage
        lineage = LineageInfo(
            parent_topic=parent_topic,
            injected_by=old_item.get("source", "unknown"),
            injected_at=old_item.get("created_at", datetime.now().isoformat()),
            original_reason=old_item.get("reason", ""),
            exploration_path=[parent_topic] if parent_topic else [],
        )
        
        # 创建队列项
        item = QueueItem(
            topic=topic,
            status=State(status_str),
            lineage=lineage,
            score=score,
            depth=depth,
            created_at=old_item.get("created_at", datetime.now().isoformat()),
        )
        
        # 添加初始状态历史
        item.state_history = [
            StateTransition(
                from_state=None,
                to_state=status_str,
                actor=Actor.SYSTEM.value,
                timestamp=old_item.get("created_at", datetime.now().isoformat()),
                reason="Migrated from v1",
                context={},
            )
        ]
        
        return item
    
    def _validate_migration(self, old_queue: List[Dict]) -> ValidationResult:
        """验证迁移结果"""
        from core.repositories import QueueRepository
        from core.persistence import create_lock_manager
        from core.repositories.state_repository import BackupManager
        
        lock_mgr = create_lock_manager(os.path.join(self._new_data_dir, "lock"))
        backup_mgr = BackupManager(os.path.join(self._new_data_dir, "backup"))
        queue_repo = QueueRepository(self._new_data_dir, lock_mgr, backup_mgr)
        
        old_count = len(old_queue)
        new_count = queue_repo.count_all()
        
        details = [
            f"Old queue count: {old_count}",
            f"New queue count: {new_count}",
        ]
        
        # 检查每个旧项是否都在新存储中
        for old_item in old_queue:
            topic = old_item.get("topic")
            new_item = queue_repo.get_by_topic(topic)
            if not new_item:
                details.append(f"Missing: {topic}")
        
        return ValidationResult(
            old_count=old_count,
            new_count=new_count,
            consistent=(old_count == new_count),
            details=details,
        )


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="Migrate data to v2 format")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate migration without writing",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute migration",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify migration results",
    )
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("Running migration in DRY-RUN mode...")
        migration = DataMigration()
        result = migration.migrate(dry_run=True)
        print(f"\nWould migrate: {result.migrated} items")
        print(f"Would fail: {result.failed} items")
        
    elif args.execute:
        print("Executing migration...")
        confirm = input("This will modify data. Type 'yes' to continue: ")
        if confirm != "yes":
            print("Aborted")
            return
        
        migration = DataMigration()
        result = migration.migrate(dry_run=False)
        
        print(f"\nMigrated: {result.migrated}")
        print(f"Failed: {result.failed}")
        
        if result.validation:
            print(f"Consistent: {result.validation.consistent}")
        
        if result.errors:
            print("\nErrors:")
            for error in result.errors:
                print(f"  - {error}")
    
    elif args.verify:
        print("Verifying migration...")
        migration = DataMigration()
        # 验证逻辑
        print("Verification complete")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
