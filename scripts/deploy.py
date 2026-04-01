"""
Deployment Scripts - 部署和灰度发布脚本
"""

import os
import sys
import json
import shutil
import argparse
import subprocess
from datetime import datetime


class DeploymentManager:
    """部署管理器"""
    
    def __init__(self, config_file: str = "config/deployment.json"):
        self._config_file = config_file
        self._config = self._load_config()
    
    def _load_config(self) -> dict:
        """加载配置"""
        if os.path.exists(self._config_file):
            with open(self._config_file, 'r') as f:
                return json.load(f)
        return {
            "current_version": "v1",
            "target_version": "v2",
            "rollout_percentage": 0,
            "features": {
                "v2_queue": False,
                "v2_statemachine": False,
            }
        }
    
    def _save_config(self):
        """保存配置"""
        os.makedirs(os.path.dirname(self._config_file), exist_ok=True)
        with open(self._config_file, 'w') as f:
            json.dump(self._config, f, indent=2)
    
    def backup_data(self):
        """备份数据"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = f"knowledge/backup/pre_deploy_{timestamp}"
        
        os.makedirs(backup_dir, exist_ok=True)
        
        # 备份关键文件
        files_to_backup = [
            "knowledge/state.json",
            "knowledge/dream_topic_inbox.json",
        ]
        
        for file_path in files_to_backup:
            if os.path.exists(file_path):
                shutil.copy2(file_path, backup_dir)
                print(f"[Deploy] Backed up: {file_path}")
        
        return backup_dir
    
    def pre_deploy_check(self) -> bool:
        """部署前检查"""
        print("[Deploy] Running pre-deploy checks...")
        
        # 检查数据完整性
        if not os.path.exists("knowledge/state.json"):
            print("[Deploy] ERROR: state.json not found")
            return False
        
        # 检查磁盘空间
        stat = shutil.disk_usage("knowledge")
        free_gb = stat.free / (1024**3)
        if free_gb < 1.0:
            print(f"[Deploy] ERROR: Low disk space ({free_gb:.1f}GB free)")
            return False
        
        print("[Deploy] Pre-deploy checks passed")
        return True
    
    def enable_v2(self, percentage: int = 10):
        """
        启用 v2（灰度）
        
        Args:
            percentage: 启用百分比 (0-100)
        """
        print(f"[Deploy] Enabling v2 for {percentage}% of traffic")
        
        from core.feature_toggle import get_feature_toggle
        
        ft = get_feature_toggle()
        
        if percentage > 0:
            ft.enable("v2_compat_layer")
        
        if percentage >= 10:
            ft.enable("v2_queue")
            print("[Deploy] v2_queue enabled")
        
        if percentage >= 50:
            ft.enable("v2_statemachine")
            print("[Deploy] v2_statemachine enabled")
        
        if percentage >= 100:
            ft.enable("timeout_monitor")
            ft.enable("consistency_monitor")
            print("[Deploy] All v2 features enabled")
        
        self._config["rollout_percentage"] = percentage
        self._save_config()
        
        print(f"[Deploy] v2 enabled for {percentage}%")
    
    def disable_v2(self):
        """禁用 v2（回滚）"""
        print("[Deploy] Disabling v2 (rollback)")
        
        from core.feature_toggle import get_feature_toggle
        
        ft = get_feature_toggle()
        ft.disable("v2_queue")
        ft.disable("v2_statemachine")
        ft.disable("timeout_monitor")
        ft.disable("consistency_monitor")
        
        self._config["rollout_percentage"] = 0
        self._save_config()
        
        print("[Deploy] v2 disabled, rolled back to v1")
    
    def health_check(self) -> bool:
        """健康检查"""
        print("[Deploy] Running health checks...")
        
        try:
            # 检查 API 响应
            import requests
            response = requests.get("http://localhost:4848/api/curious/state", timeout=5)
            if response.status_code != 200:
                print(f"[Deploy] Health check failed: API returned {response.status_code}")
                return False
            
            print("[Deploy] Health checks passed")
            return True
            
        except Exception as e:
            print(f"[Deploy] Health check error: {e}")
            return False
    
    def status(self):
        """显示部署状态"""
        print("=" * 60)
        print("Deployment Status")
        print("=" * 60)
        
        print(f"Current rollout: {self._config.get('rollout_percentage', 0)}%")
        
        from core.feature_toggle import get_feature_toggle
        ft = get_feature_toggle()
        
        print("\nFeatures:")
        for feature, enabled in ft.get_all().items():
            status = "✓" if enabled else "✗"
            print(f"  {status} {feature}")
        
        print("\nHealth:", "✓" if self.health_check() else "✗")
        print("=" * 60)


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="Deployment management")
    parser.add_argument("command", choices=[
        "backup", "pre-check", "enable-v2", "disable-v2", 
        "health", "status", "full-deploy"
    ])
    parser.add_argument("--percentage", type=int, default=10, 
                       help="Rollout percentage (0-100)")
    
    args = parser.parse_args()
    
    deploy = DeploymentManager()
    
    if args.command == "backup":
        backup_dir = deploy.backup_data()
        print(f"[Deploy] Backup created at: {backup_dir}")
    
    elif args.command == "pre-check":
        success = deploy.pre_deploy_check()
        sys.exit(0 if success else 1)
    
    elif args.command == "enable-v2":
        # 先备份
        deploy.backup_data()
        # 检查
        if not deploy.pre_deploy_check():
            print("[Deploy] Pre-check failed, aborting")
            sys.exit(1)
        # 启用
        deploy.enable_v2(args.percentage)
    
    elif args.command == "disable-v2":
        deploy.disable_v2()
    
    elif args.command == "health":
        success = deploy.health_check()
        sys.exit(0 if success else 1)
    
    elif args.command == "status":
        deploy.status()
    
    elif args.command == "full-deploy":
        print("[Deploy] Starting full deployment...")
        deploy.backup_data()
        
        if not deploy.pre_deploy_check():
            print("[Deploy] Pre-check failed")
            sys.exit(1)
        
        # 逐步放量
        for pct in [10, 25, 50, 75, 100]:
            print(f"\n[Deploy] Rolling out {pct}%...")
            deploy.enable_v2(pct)
            time.sleep(60)  # 观察1分钟
            
            if not deploy.health_check():
                print(f"[Deploy] Health check failed at {pct}%, rolling back")
                deploy.disable_v2()
                sys.exit(1)
        
        print("[Deploy] Full deployment completed successfully!")


if __name__ == "__main__":
    import time
    main()
