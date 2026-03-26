import pytest
from unittest.mock import Mock
from core.kg_graph import KGGraph


def test_should_explore_first_visit():
    mock_repo = Mock()
    mock_repo.get_topic.return_value = None
    
    kg = KGGraph(mock_repo)
    should_explore, reason = kg.should_explore("new_node")
    
    assert should_explore is True
    assert reason == "first_visit"


def test_should_explore_not_yet_explored():
    mock_topic = Mock()
    mock_topic.explored = False
    
    mock_repo = Mock()
    mock_repo.get_topic.return_value = mock_topic
    
    kg = KGGraph(mock_repo)
    should_explore, reason = kg.should_explore("existing_node")
    
    assert should_explore is True
    assert reason == "not_yet_explored"


def test_should_explore_already_explored():
    mock_topic = Mock()
    mock_topic.explored = True
    mock_topic.parents = ["parent1"]
    
    mock_repo = Mock()
    mock_repo.get_topic.return_value = mock_topic
    
    kg = KGGraph(mock_repo)
    should_explore, reason = kg.should_explore("explored_node", from_parent="parent1")
    
    assert should_explore is False
    assert reason == "already_explored"


def test_should_explore_linked_only():
    mock_topic = Mock()
    mock_topic.explored = True
    mock_topic.parents = ["parent1"]
    
    mock_repo = Mock()
    mock_repo.get_topic.return_value = mock_topic
    
    kg = KGGraph(mock_repo)
    should_explore, reason = kg.should_explore("explored_node", from_parent="new_parent")
    
    assert should_explore is False
    assert reason == "linked_only"
