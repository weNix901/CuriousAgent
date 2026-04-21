"""Tests for KnowledgeNode Pydantic models (v0.3.3)."""
import pytest
from pydantic import ValidationError
from core.kg.knowledge_node import (
    KnowledgeContent, KnowledgeSource, KnowledgeRelations,
    KnowledgeCitation, KnowledgeNode
)


def test_knowledge_content_required_fields():
    """Test that definition is required."""
    content = KnowledgeContent(definition="Test definition")
    assert content.definition == "Test definition"
    
    # Missing definition should fail
    with pytest.raises(ValidationError):
        KnowledgeContent()


def test_knowledge_content_completeness_score_bounds():
    """Test completeness_score is between 1 and 6."""
    content = KnowledgeContent(definition="test", completeness_score=3)
    assert content.completeness_score == 3
    
    # Out of bounds should fail
    with pytest.raises(ValidationError):
        KnowledgeContent(definition="test", completeness_score=0)
    
    with pytest.raises(ValidationError):
        KnowledgeContent(definition="test", completeness_score=7)


def test_knowledge_source_trusted_flag():
    """Test source trusted flag defaults."""
    source = KnowledgeSource(source_type="paper")
    assert source.source_type == "paper"
    assert source.source_trusted is False
    assert source.source_missing is False


def test_knowledge_node_composite_structure():
    """Test KnowledgeNode with all sub-structures."""
    node = KnowledgeNode(
        topic="FlashAttention",
        content=KnowledgeContent(
            definition="I/O-aware attention mechanism",
            formula="softmax(QK^T/√d_k)V"
        ),
        source=KnowledgeSource(
            source_url="https://arxiv.org/pdf/2205.14135",
            source_type="paper",
            source_trusted=True
        ),
        relations=KnowledgeRelations(),
        citation=KnowledgeCitation()
    )
    
    assert node.topic == "FlashAttention"
    assert node.content.formula == "softmax(QK^T/√d_k)V"
    assert node.source.source_trusted is True
    assert node.status == "pending"
    assert node.deep_read_status == "pending"


def test_knowledge_node_serialization():
    """Test KnowledgeNode can be serialized to dict."""
    node = KnowledgeNode(
        topic="Test",
        content=KnowledgeContent(definition="Test def"),
        source=KnowledgeSource(source_type="web"),
        relations=KnowledgeRelations(),
        citation=KnowledgeCitation()
    )
    
    data = node.model_dump()
    assert data["topic"] == "Test"
    assert data["content"]["definition"] == "Test def"
    assert data["source"]["source_type"] == "web"