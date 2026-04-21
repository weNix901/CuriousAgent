"""Tests for TrustedSourceManager (v0.3.3)."""
import json
import os
import tempfile
import pytest
from core.trusted_sources import TrustedSourceManager


class TestTrustedSourceManager:
    def test_load_from_file(self):
        """Test manager loads trusted sources from JSON file."""
        manager = TrustedSourceManager(config_path="config/trusted_sources.json")
        manager.load()
        
        sources = manager.get_all_sources()
        assert len(sources) > 0
        
        # Check arxiv is present
        arxiv = manager.get_source("arxiv.org")
        assert arxiv is not None
        assert arxiv["trust_level"] == 5
        assert arxiv["enabled"] is True
    
    def test_check_url_trusted(self):
        """Test URL checking for trusted sources."""
        manager = TrustedSourceManager(config_path="config/trusted_sources.json")
        manager.load()
        
        result = manager.check_url("https://arxiv.org/pdf/2205.14135")
        assert result["is_trusted"] is True
        assert result["domain"] == "arxiv.org"
    
    def test_check_url_untrusted(self):
        """Test URL checking for untrusted sources."""
        manager = TrustedSourceManager(config_path="config/trusted_sources.json")
        manager.load()
        
        result = manager.check_url("https://random-blog.com/post")
        assert result["is_trusted"] is False
    
    def test_check_url_subdomain(self):
        """Test URL checking for subdomain matching."""
        manager = TrustedSourceManager(config_path="config/trusted_sources.json")
        manager.load()
        
        result = manager.check_url("https://link.springer.com/article/xxx")
        assert result["is_trusted"] is True
        assert result["domain"] == "link.springer.com"
    
    def test_add_and_remove_source(self):
        """Test adding and removing a source."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"version": 1, "updated_at": "2026-04-21", "sources": []}, f)
            temp_path = f.name
        
        try:
            manager = TrustedSourceManager(config_path=temp_path)
            manager.load()
            
            manager.add_source("test.com", "Test", "journal", 3, "Test source")
            assert manager.get_source("test.com") is not None
            assert manager.get_source("test.com")["trust_level"] == 3
            
            manager.remove_source("test.com")
            assert manager.get_source("test.com") is None
        finally:
            os.unlink(temp_path)
    
    def test_toggle_source(self):
        """Test enabling/disabling a source."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"version": 1, "updated_at": "2026-04-21", "sources": [
                {"domain": "test.com", "name": "Test", "type": "journal", "trust_level": 3, "enabled": True, "notes": ""}
            ]}, f)
            temp_path = f.name
        
        try:
            manager = TrustedSourceManager(config_path=temp_path)
            manager.load()
            
            assert manager.get_source("test.com")["enabled"] is True
            manager.toggle_source("test.com")
            assert manager.get_source("test.com")["enabled"] is False
        finally:
            os.unlink(temp_path)