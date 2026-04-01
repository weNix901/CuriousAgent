"""
Curious Agent v0.2.7 - Foundation Refactor

Complete implementation of the v0.2.7 architecture.
"""

__version__ = "0.2.7"
__version_name__ = "Foundation Refactor"

# Export key components
from core.persistence import FileLockManager
from core.repositories import (
    StateRepository, QueueRepository,
    StateInfo, QueueItem, LineageInfo,
    State, Actor, BackupManager
)
from core.state_machine import ExplorationStateMachine
from core.queue_service import QueueService
from core.timeout_monitor import TimeoutMonitor
from core.consistency_monitor import ConsistencyMonitor
from core.feature_toggle import FeatureToggle, get_feature_toggle
from core.compat import CompatibilityLayer, init_compat_layer

__all__ = [
    'FileLockManager',
    'StateRepository', 'QueueRepository',
    'StateInfo', 'QueueItem', 'LineageInfo',
    'State', 'Actor', 'BackupManager',
    'ExplorationStateMachine',
    'QueueService',
    'TimeoutMonitor',
    'ConsistencyMonitor',
    'FeatureToggle', 'get_feature_toggle',
    'CompatibilityLayer', 'init_compat_layer',
]
