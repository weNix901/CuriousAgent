"""
Curious Agent Core Package

Exports key components for V1 architecture.
"""

__version__ = "0.3.1"
__version_name__ = "Observability Layer"

from core.knowledge_graph_compat import (
    get_state,
    add_knowledge,
    add_curiosity,
    claim_pending_item,
    mark_topic_done,
)

from core.curiosity_engine import CuriosityEngine
from core.quality_v2 import QualityV2Assessor

__all__ = [
    'get_state',
    'add_knowledge',
    'add_curiosity',
    'claim_pending_item',
    'mark_topic_done',
    'CuriosityEngine',
    'QualityV2Assessor',
]