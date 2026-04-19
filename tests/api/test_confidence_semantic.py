import pytest
from unittest.mock import Mock


def test_confidence_returns_nonzero_for_similar_query():
    from core.api.host_agent_integration import KnowledgeConfidenceHandler
    
    kg_repo = Mock()
    kg_repo.query_knowledge_semantic_sync = Mock(return_value=[
        {"topic": "agent 上下文 管理系统", "score": 0.89, "quality": 8.0}
    ])
    
    handler = KnowledgeConfidenceHandler()
    handler._kg_repository = kg_repo
    
    result = handler.check_confidence("agent 上下文 管理系统是干嘛的？")
    
    assert result["confidence"] > 0.0
    assert result.get("matched_topic") == "agent 上下文 管理系统"


def test_confidence_zero_when_no_match():
    from core.api.host_agent_integration import KnowledgeConfidenceHandler
    
    kg_repo = Mock()
    kg_repo.query_knowledge_semantic_sync = Mock(return_value=[])
    
    handler = KnowledgeConfidenceHandler()
    handler._kg_repository = kg_repo
    
    result = handler.check_confidence("unknown topic xyz")
    
    assert result["confidence"] == 0.0
    assert "gaps" in result
