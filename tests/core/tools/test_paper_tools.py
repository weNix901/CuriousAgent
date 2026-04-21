# tests/core/tools/test_paper_tools.py
import pytest
from core.tools.paper_tools import paper_storage_paths

def test_paper_storage_paths_generates_consistent_paths():
    """Test that same topic always generates same paths."""
    pdf_path, txt_path = paper_storage_paths("FlashAttention")
    assert pdf_path.startswith("papers/")
    assert txt_path.startswith("papers/")
    assert pdf_path.endswith(".pdf")
    assert txt_path.endswith(".txt")
    
    # Same topic → same paths
    pdf_path2, txt_path2 = paper_storage_paths("FlashAttention")
    assert pdf_path == pdf_path2
    assert txt_path == txt_path2

def test_paper_storage_paths_different_topics():
    """Test that different topics generate different paths."""
    pdf1, txt1 = paper_storage_paths("FlashAttention")
    pdf2, txt2 = paper_storage_paths("Transformer Architecture")
    assert pdf1 != pdf2
    assert txt1 != txt2