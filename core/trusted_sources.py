"""Trusted source management for Curious Agent v0.3.3."""
import json
import logging
import os
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

TRUSTED_SOURCES_PATH = "config/trusted_sources.json"


class TrustedSourceManager:
    """Manage trusted source configuration."""
    
    def __init__(self, config_path: str = TRUSTED_SOURCES_PATH):
        self.config_path = config_path
        self.sources: dict[str, dict] = {}
    
    def load(self):
        """Load trusted sources from JSON file."""
        if not os.path.exists(self.config_path):
            logger.warning(f"Trusted sources file not found: {self.config_path}")
            return
        
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        for source in data.get("sources", []):
            domain = source["domain"]
            self.sources[domain] = source
        
        logger.info(f"Loaded {len(self.sources)} trusted sources")
    
    def get_all_sources(self) -> list[dict]:
        """Get all trusted sources."""
        return list(self.sources.values())
    
    def get_source(self, domain: str) -> dict | None:
        """Get a specific trusted source by domain."""
        return self.sources.get(domain)
    
    def check_url(self, url: str) -> dict[str, Any]:
        """Check if a URL comes from a trusted source."""
        parsed = urlparse(url)
        domain = parsed.hostname or ""
        
        # Check exact match first
        if domain in self.sources:
            source = self.sources[domain]
            return {
                "is_trusted": source.get("enabled", False),
                "domain": domain,
                "source": source
            }
        
        # Check parent domain
        for trusted_domain in self.sources:
            if domain.endswith(f".{trusted_domain}"):
                source = self.sources[trusted_domain]
                return {
                    "is_trusted": source.get("enabled", False),
                    "domain": trusted_domain,
                    "source": source
                }
        
        return {
            "is_trusted": False,
            "domain": domain,
            "source": None
        }
    
    def add_source(self, domain: str, name: str, source_type: str, trust_level: int, notes: str = ""):
        """Add a new trusted source."""
        self.sources[domain] = {
            "domain": domain,
            "name": name,
            "type": source_type,
            "trust_level": trust_level,
            "enabled": True,
            "notes": notes
        }
        self.save()
    
    def remove_source(self, domain: str):
        """Remove a trusted source."""
        if domain in self.sources:
            del self.sources[domain]
            self.save()
    
    def toggle_source(self, domain: str):
        """Enable/disable a trusted source."""
        if domain in self.sources:
            self.sources[domain]["enabled"] = not self.sources[domain].get("enabled", False)
            self.save()
    
    def save(self):
        """Save trusted sources to JSON file."""
        data = {
            "version": 1,
            "updated_at": "2026-04-21T00:00:00Z",
            "sources": list(self.sources.values())
        }
        
        os.makedirs(os.path.dirname(self.config_path) if os.path.dirname(self.config_path) else ".", exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(self.sources)} trusted sources")