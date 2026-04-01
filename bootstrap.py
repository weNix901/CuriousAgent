"""
Application Bootstrap - 应用启动器

集成所有组件，启动 v0.2.7 服务
"""

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.persistence import create_lock_manager
from core.repositories import (
    StateRepository, QueueRepository, 
    BackupManager
)
from core.state_machine import ExplorationStateMachine
from core.queue_service import QueueService
from core.timeout_monitor import TimeoutMonitor
from core.feature_toggle import get_feature_toggle
from core.compat import init_compat_layer


def create_repositories(data_dir: str = "knowledge"):
    """创建所有仓库"""
    lock_mgr = create_lock_manager(os.path.join(data_dir, "lock"))
    backup_mgr = BackupManager(os.path.join(data_dir, "backup"))
    
    state_repo = StateRepository(data_dir, lock_mgr, backup_mgr)
    queue_repo = QueueRepository(data_dir, lock_mgr, backup_mgr)
    
    return {
        "state": state_repo,
        "queue": queue_repo,
        "lock": lock_mgr,
        "backup": backup_mgr,
    }


def create_services(repositories: dict):
    """创建所有服务"""
    state_machine = ExplorationStateMachine(repositories["state"])
    queue_service = QueueService(repositories["queue"], state_machine)
    timeout_monitor = TimeoutMonitor(
        state_machine,
        repositories["queue"],
    )
    
    return {
        "state_machine": state_machine,
        "queue_service": queue_service,
        "timeout_monitor": timeout_monitor,
    }


def bootstrap_v2():
    """启动 v2 系统"""
    print("=" * 60)
    print("Curious Agent v0.2.7 Bootstrap")
    print("=" * 60)
    
    # 1. 创建仓库
    print("[Bootstrap] Creating repositories...")
    repos = create_repositories()
    
    # 2. 创建服务
    print("[Bootstrap] Creating services...")
    services = create_services(repos)
    
    # 3. 初始化兼容层
    print("[Bootstrap] Initializing compatibility layer...")
    init_compat_layer(services["queue_service"])
    
    # 4. 检查 Feature Toggle
    ft = get_feature_toggle()
    print(f"[Bootstrap] Feature status: v2_queue={ft.is_enabled('v2_queue')}")
    
    # 5. 启动监控
    if ft.is_enabled("timeout_monitor"):
        print("[Bootstrap] Starting timeout monitor...")
        services["timeout_monitor"].start()
    
    print("[Bootstrap] System ready!")
    print("=" * 60)
    
    return {
        "repositories": repos,
        "services": services,
    }


def main():
    """主函数"""
    try:
        context = bootstrap_v2()
        
        # 这里可以启动 Flask 应用或其他服务
        print("\n[System] Running... Press Ctrl+C to stop")
        
        # 保持运行
        import time
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n[System] Shutting down...")
        
        # 停止监控
        if "services" in context:
            context["services"]["timeout_monitor"].stop()
        
        print("[System] Goodbye!")
    
    except Exception as e:
        print(f"[System] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
