"""
Test utilities for Curious Agent

提供标准化的测试数据管理和隔离机制
"""
import json
import os
import tempfile
import shutil
from contextlib import contextmanager
from typing import Generator


# 测试数据前缀标记
TEST_DATA_PREFIX = "【test_data】"


def create_test_topic(name: str) -> str:
    """
    创建带有测试标识的 topic 名称
    
    Args:
        name: 原始 topic 名称
        
    Returns:
        带有 【test_data】 前缀的 topic 名称
    """
    return f"{TEST_DATA_PREFIX}{name}"


def is_test_topic(topic: str) -> bool:
    """
    检查 topic 是否为测试数据
    
    Args:
        topic: topic 名称
        
    Returns:
        是否以测试数据前缀开头
    """
    return topic.startswith(TEST_DATA_PREFIX)


@contextmanager
def isolated_knowledge_graph() -> Generator[str, None, None]:
    """
    上下文管理器，提供完全隔离的知识图谱状态文件
    
    Usage:
        with isolated_knowledge_graph() as kg_module:
            # 在隔离环境中操作
            kg_module.add_curiosity("test topic", "reason", 5.0, 5.0)
    
    Yields:
        临时的知识图谱模块
    """
    import sys
    from core import knowledge_graph as kg_module
    
    # 保存原始配置
    original_state_file = kg_module.STATE_FILE
    
    # 创建临时目录和状态文件
    temp_dir = tempfile.mkdtemp(prefix="curious_agent_test_")
    temp_state = os.path.join(temp_dir, "state.json")
    
    # 创建初始空状态
    initial_state = {
        "version": "1.0",
        "last_update": None,
        "knowledge": {"topics": {}},
        "curiosity_queue": [],
        "exploration_log": [],
        "config": {
            "curiosity_top_k": 3,
            "max_knowledge_nodes": 100,
            "notification_threshold": 7.0
        }
    }
    
    with open(temp_state, 'w', encoding='utf-8') as f:
        json.dump(initial_state, f, ensure_ascii=False, indent=2)
    
    # 替换状态文件路径
    kg_module.STATE_FILE = temp_state
    
    try:
        yield kg_module
    finally:
        # 恢复原始配置
        kg_module.STATE_FILE = original_state_file
        # 清理临时文件
        shutil.rmtree(temp_dir, ignore_errors=True)


@contextmanager
def temporary_state_file() -> Generator[str, None, None]:
    """
    创建临时状态文件用于测试
    
    Usage:
        with temporary_state_file() as state_file:
            # 使用 state_file 路径
            pass
    
    Yields:
        临时状态文件路径
    """
    temp_dir = tempfile.mkdtemp(prefix="curious_agent_test_")
    temp_state = os.path.join(temp_dir, "state.json")
    
    initial_state = {
        "version": "1.0",
        "last_update": None,
        "knowledge": {"topics": {}},
        "curiosity_queue": [],
        "exploration_log": [],
        "config": {
            "curiosity_top_k": 3,
            "max_knowledge_nodes": 100,
            "notification_threshold": 7.0
        }
    }
    
    with open(temp_state, 'w', encoding='utf-8') as f:
        json.dump(initial_state, f, ensure_ascii=False, indent=2)
    
    try:
        yield temp_state
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def cleanup_test_data_from_production():
    """
    从生产环境中清理测试数据
    在生产环境维护时使用，不应在测试代码中调用
    """
    from core import knowledge_graph as kg
    
    state = kg._load_state()
    original_counts = {
        'queue': len(state.get('curiosity_queue', [])),
        'completed': len(state.get('meta_cognitive', {}).get('completed_topics', [])),
        'topics': len(state.get('knowledge', {}).get('topics', {}))
    }
    
    # 清理队列中的测试数据
    state['curiosity_queue'] = [
        item for item in state.get('curiosity_queue', [])
        if not is_test_topic(item.get('topic', ''))
    ]
    
    # 清理 completed_topics 中的测试数据
    if 'meta_cognitive' in state:
        state['meta_cognitive']['completed_topics'] = [
            topic for topic in state['meta_cognitive'].get('completed_topics', [])
            if not is_test_topic(topic)
        ]
    
    # 清理 knowledge.topics 中的测试数据
    topics = state.get('knowledge', {}).get('topics', {})
    test_topics = [t for t in topics if is_test_topic(t)]
    for topic in test_topics:
        del topics[topic]
    
    kg._save_state(state)
    
    new_counts = {
        'queue': len(state.get('curiosity_queue', [])),
        'completed': len(state.get('meta_cognitive', {}).get('completed_topics', [])),
        'topics': len(state.get('knowledge', {}).get('topics', {}))
    }
    
    return {
        'removed': {
            'queue': original_counts['queue'] - new_counts['queue'],
            'completed': original_counts['completed'] - new_counts['completed'],
            'topics': original_counts['topics'] - new_counts['topics']
        },
        'test_topics': test_topics
    }
