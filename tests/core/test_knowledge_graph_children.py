import pytest
from core import knowledge_graph as kg


def test_add_child_and_get_children():
    kg.add_child("agent", "agent_memory")
    kg.add_child("agent", "agent_planning")
    
    children = kg.get_children("agent")
    assert "agent_memory" in children
    assert "agent_planning" in children


def test_mark_child_explored():
    kg.add_child("test_parent", "test_child")
    kg.mark_child_explored("test_parent", "test_child")
    
    status = kg.get_exploration_status("test_parent")
    assert status == "complete"


def test_partial_status():
    kg.add_child("partial_test", "child1")
    kg.add_child("partial_test", "child2")
    kg.mark_child_explored("partial_test", "child1")
    
    status = kg.get_exploration_status("partial_test")
    assert status == "partial"
