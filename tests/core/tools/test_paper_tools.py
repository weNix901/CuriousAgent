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


import asyncio
import json
import os
from core.tools.paper_tools import SavePaperTextTool, PAPERS_DIR

def test_save_paper_text_tool_creates_file():
    """Test that SavePaperTextTool creates TXT file and returns path."""
    tool = SavePaperTextTool()
    
    result = asyncio.run(tool.execute(
        topic="TestPaper",
        text="This is test paper content for testing."
    ))
    
    data = json.loads(result)
    assert "txt_path" in data
    assert "pdf_path" in data
    assert "text_length" in data
    assert os.path.exists(data["txt_path"])
    
    # Cleanup
    os.remove(data["txt_path"])


from core.tools.paper_tools import ReadPaperTextTool

def test_read_paper_text_tool_reads_existing_file():
    """Test that ReadPaperTextTool reads TXT file content."""
    # Create test file
    test_path = "papers/test_read.txt"
    os.makedirs("papers", exist_ok=True)
    with open(test_path, "w", encoding="utf-8") as f:
        f.write("Test paper content for reading.")
    
    tool = ReadPaperTextTool()
    result = asyncio.run(tool.execute(txt_path=test_path))
    
    assert "Test paper content for reading." in result
    
    # Cleanup
    os.remove(test_path)

def test_read_paper_text_tool_file_not_found():
    """Test that ReadPaperTextTool returns error for missing file."""
    tool = ReadPaperTextTool()
    result = asyncio.run(tool.execute(txt_path="papers/nonexistent.txt"))
    
    assert "Error" in result
    assert "not found" in result.lower()


from core.tools.paper_tools import ExtractKnowledgePointsTool, ExtractFormulasTool

def test_extract_knowledge_points_tool_structure():
    """Test tool has correct name and parameters."""
    tool = ExtractKnowledgePointsTool()
    assert tool.name == "extract_knowledge_points"
    assert "paper_text" in tool.parameters
    assert "topic" in tool.parameters
    assert "parent_topic" in tool.parameters

def test_extract_knowledge_points_tool_returns_json():
    """Test tool returns valid JSON."""
    tool = ExtractKnowledgePointsTool()
    result = asyncio.run(tool.execute(
        paper_text="Test text",
        topic="Test",
        parent_topic="Parent"
    ))
    data = json.loads(result)
    assert "knowledge_points" in data
    assert "status" in data

def test_extract_formulas_tool_structure():
    """Test tool has correct name and parameters."""
    tool = ExtractFormulasTool()
    assert tool.name == "extract_formulas"
    assert "txt_path" in tool.parameters
    assert "sections" in tool.parameters

def test_extract_formulas_tool_returns_json():
    """Test tool returns valid JSON."""
    tool = ExtractFormulasTool()
    result = asyncio.run(tool.execute(txt_path="papers/test.txt"))
    data = json.loads(result)
    assert "formulas" in data
    assert "status" in data