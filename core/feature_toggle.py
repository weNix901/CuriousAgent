"""
Feature Toggle - 功能开关

支持渐进式发布和快速回滚
"""

import json
import os
from typing import Dict, Optional


class FeatureToggle:
    """
    功能开关
    
    控制新功能的启用/禁用，支持：
    - 渐进式发布
    - 快速回滚
    - A/B测试
    """
    
    DEFAULT_FEATURES = {
        "v2_queue": False,              # 新队列系统
        "v2_statemachine": False,       # 新状态机
        "v2_compat_layer": True,        # 兼容层（始终启用）
        "consistency_monitor": False,   # 一致性监控
        "timeout_monitor": False,       # 超时监控
    }
    
    def __init__(self, config_file: str = "knowledge/config/features.json"):
        self._config_file = config_file
        self._config: Dict[str, bool] = {}
        self._load_config()
    
    def _load_config(self):
        """加载配置"""
        if os.path.exists(self._config_file):
            try:
                with open(self._config_file, 'r') as f:
                    self._config = json.load(f)
            except Exception:
                self._config = self.DEFAULT_FEATURES.copy()
        else:
            self._config = self.DEFAULT_FEATURES.copy()
            self._save_config()
    
    def _save_config(self):
        """保存配置"""
        os.makedirs(os.path.dirname(self._config_file), exist_ok=True)
        with open(self._config_file, 'w') as f:
            json.dump(self._config, f, indent=2)
    
    def is_enabled(self, feature: str) -> bool:
        """检查功能是否启用"""
        return self._config.get(feature, False)
    
    def enable(self, feature: str):
        """启用功能"""
        self._config[feature] = True
        self._save_config()
        print(f"[FeatureToggle] {feature} enabled")
    
    def disable(self, feature: str):
        """禁用功能"""
        self._config[feature] = False
        self._save_config()
        print(f"[FeatureToggle] {feature} disabled")
    
    def toggle(self, feature: str) -> bool:
        """切换功能状态"""
        current = self.is_enabled(feature)
        if current:
            self.disable(feature)
        else:
            self.enable(feature)
        return not current
    
    def get_all(self) -> Dict[str, bool]:
        """获取所有功能状态"""
        return self._config.copy()
    
    def reset_to_defaults(self):
        """重置为默认值"""
        self._config = self.DEFAULT_FEATURES.copy()
        self._save_config()


# 全局实例
_features: Optional[FeatureToggle] = None


def get_feature_toggle() -> FeatureToggle:
    """获取全局功能开关实例"""
    global _features
    if _features is None:
        _features = FeatureToggle()
    return _features


def is_enabled(feature: str) -> bool:
    """便捷函数：检查功能是否启用"""
    return get_feature_toggle().is_enabled(feature)
