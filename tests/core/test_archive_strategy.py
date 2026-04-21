"""Tests for ArchiveStrategy (v0.3.3)."""
import gzip
import os
import pytest
from core.archive_strategy import ArchiveStrategy


class TestArchiveStrategy:
    def test_should_archive_cold_node(self):
        """Test archiving cold node deletes TXT and compresses PDF."""
        strategy = ArchiveStrategy()
        
        # Create test files
        os.makedirs("papers", exist_ok=True)
        txt_path = "papers/test_archive.txt"
        pdf_path = "papers/test_archive.pdf"
        
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
        
        assert not os.path.exists(txt_path)  # TXT deleted
        assert os.path.exists(pdf_path + ".gz")  # PDF compressed
        assert result["archive_status"] == "archived"
        assert result["txt_path"] is None
        
        # Cleanup
        os.remove(pdf_path + ".gz")
    
    def test_should_not_archive_warm_node(self):
        """Test warm node is not archived."""
        strategy = ArchiveStrategy()
        
        node = {
            "txt_path": "papers/test.txt",
            "pdf_path": "papers/test.pdf",
            "heat": 50,  # Warm
            "source_origin_type": "url"
        }
        
        result = strategy.archive_node(node)
        
        # Node unchanged
        assert result["txt_path"] == "papers/test.txt"
        assert "archive_status" not in result
    
    def test_skip_derived_nodes(self):
        """Test derived nodes are not archived."""
        strategy = ArchiveStrategy()
        
        node = {
            "txt_path": "papers/test.txt",
            "pdf_path": "papers/test.pdf",
            "heat": 10,  # Cold
            "source_origin_type": "derived"
        }
        
        result = strategy.archive_node(node)
        
        # Node unchanged
        assert result["txt_path"] == "papers/test.txt"
        assert "archive_status" not in result
    
    def test_restore_node_decompresses_pdf(self):
        """Test restoring node decompresses PDF."""
        strategy = ArchiveStrategy()
        
        # Create compressed file
        os.makedirs("papers", exist_ok=True)
        pdf_path = "papers/test_restore.pdf"
        gz_path = pdf_path + ".gz"
        
        with gzip.open(gz_path, "wb") as f:
            f.write(b"original pdf content")
        
        node = {
            "pdf_path": gz_path,
            "heat": 20,
        }
        
        result = strategy.restore_node(node)
        
        assert result["pdf_path"] == pdf_path
        assert result["archive_status"] == "restored"
        assert os.path.exists(pdf_path)
        
        # Cleanup
        os.remove(pdf_path)
    
    def test_should_archive_threshold(self):
        """Test archive threshold."""
        strategy = ArchiveStrategy(cold_threshold=30)
        
        assert strategy.should_archive(29) is True
        assert strategy.should_archive(30) is False
        assert strategy.should_archive(50) is False