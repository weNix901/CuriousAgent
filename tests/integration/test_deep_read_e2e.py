"""End-to-end integration tests for v0.3.3 deep read pipeline."""
import asyncio
import json
import os
import pytest


@pytest.mark.integration
class TestDeepReadE2E:
    """Integration tests for the full deep read pipeline."""
    
    def test_paper_storage_paths_consistency(self):
        """Test that paper_storage_paths generates consistent paths."""
        from core.tools.paper_tools import paper_storage_paths
        
        pdf1, txt1 = paper_storage_paths("FlashAttention")
        pdf2, txt2 = paper_storage_paths("FlashAttention")
        
        assert pdf1 == pdf2
        assert txt1 == txt2
        assert pdf1.endswith(".pdf")
        assert txt1.endswith(".txt")
    
    def test_save_and_read_paper_text_roundtrip(self):
        """Test saving and reading paper text roundtrip."""
        from core.tools.paper_tools import SavePaperTextTool, ReadPaperTextTool
        
        test_content = "This is test paper content for roundtrip testing."
        
        # Save
        save_tool = SavePaperTextTool()
        save_result = asyncio.run(save_tool.execute(
            topic="RoundtripTest",
            text=test_content
        ))
        save_data = json.loads(save_result)
        txt_path = save_data["txt_path"]
        
        try:
            # Read
            read_tool = ReadPaperTextTool()
            read_result = asyncio.run(read_tool.execute(txt_path=txt_path))
            
            assert test_content in read_result
        finally:
            # Cleanup
            if os.path.exists(txt_path):
                os.remove(txt_path)
    
    def test_temperature_system_integration(self):
        """Test temperature system with realistic scenarios."""
        from core.temperature_system import TemperatureSystem
        
        system = TemperatureSystem()
        
        # Hot node stays hot with hits
        heat = 100
        for _ in range(5):
            heat = system.update_heat(heat, retrieved=True, child_count=3)
        assert heat >= 80, f"Expected hot (>=80), got {heat}"
        
        # Cold node without hits decays
        heat = 50
        for _ in range(20):
            heat = system.update_heat(heat, retrieved=False, age_days=10)
        assert heat < 30, f"Expected cold (<30), got {heat}"
    
    def test_archive_strategy_integration(self):
        """Test archive strategy with real files."""
        from core.archive_strategy import ArchiveStrategy
        
        strategy = ArchiveStrategy()
        
        # Create test files
        os.makedirs("papers", exist_ok=True)
        txt_path = "papers/test_e2e_archive.txt"
        pdf_path = "papers/test_e2e_archive.pdf"
        
        with open(txt_path, "w") as f:
            f.write("test content")
        with open(pdf_path, "wb") as f:
            f.write(b"pdf content")
        
        node = {
            "txt_path": txt_path,
            "pdf_path": pdf_path,
            "heat": 20,  # Cold
            "source_origin_type": "url"
        }
        
        result = strategy.archive_node(node)
        
        assert not os.path.exists(txt_path)
        assert os.path.exists(pdf_path + ".gz")
        assert result["archive_status"] == "archived"
        
        # Cleanup
        os.remove(pdf_path + ".gz")
    
    def test_trusted_source_manager_integration(self):
        """Test trusted source manager with real config."""
        from core.trusted_sources import TrustedSourceManager
        
        manager = TrustedSourceManager(config_path="config/trusted_sources.json")
        manager.load()
        
        sources = manager.get_all_sources()
        assert len(sources) >= 10
        
        # Check specific domains
        arxiv = manager.get_source("arxiv.org")
        assert arxiv is not None
        assert arxiv["trust_level"] == 5
        
        # URL checking
        result = manager.check_url("https://arxiv.org/pdf/2205.14135")
        assert result["is_trusted"] is True
        
        result = manager.check_url("https://random-blog.com/post")
        assert result["is_trusted"] is False
    
    def test_knowledge_node_model_serialization(self):
        """Test KnowledgeNode model serialization."""
        from core.kg.knowledge_node import (
            KnowledgeNode, KnowledgeContent, KnowledgeSource,
            KnowledgeRelations, KnowledgeCitation
        )
        
        node = KnowledgeNode(
            topic="Test Node",
            content=KnowledgeContent(
                definition="Test definition",
                formula="E=mc^2",
                completeness_score=3
            ),
            source=KnowledgeSource(
                source_url="https://example.com",
                source_type="paper",
                source_trusted=True
            ),
            relations=KnowledgeRelations(parent="Parent Topic"),
            citation=KnowledgeCitation()
        )
        
        data = node.model_dump()
        assert data["topic"] == "Test Node"
        assert data["content"]["definition"] == "Test definition"
        assert data["content"]["formula"] == "E=mc^2"
        assert data["source"]["source_trusted"] is True
        assert data["relations"]["parent"] == "Parent Topic"
    
    def test_add_to_kg_completeness_scoring(self):
        """Test AddToKGTool completeness score calculation."""
        from unittest.mock import AsyncMock, patch
        from core.tools.kg_tools import AddToKGTool
        
        mock_repo = AsyncMock()
        mock_repo.add_to_knowledge_graph = AsyncMock(return_value="test")
        
        tool = AddToKGTool(repository=mock_repo)
        
        # Test with all 5 elements
        result = asyncio.run(tool.execute(
            topic="Test",
            definition="def",
            core="core",
            context="ctx",
            examples=["ex1"],
            formula="E=mc^2"
        ))
        assert "completeness: 5/5" in result
        
        # Test with partial elements
        result = asyncio.run(tool.execute(
            topic="Test2",
            definition="def",
            core="core"
        ))
        assert "completeness: 2/5" in result