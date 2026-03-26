import json
import os
import re
import time
from datetime import datetime


class DiscoveryWriter:
    def __init__(self, discoveries_dir: str = "shared_knowledge/ca/discoveries"):
        self.discoveries_dir = discoveries_dir
        os.makedirs(discoveries_dir, exist_ok=True)
    
    def write_discovery(
        self,
        topic: str,
        findings: str,
        quality: float,
        surprise: dict = None,
    ) -> str:
        os.makedirs(self.discoveries_dir, exist_ok=True)
        
        filename = f"{int(time.time())}_{self._slugify(topic)}.json"
        filepath = os.path.join(self.discoveries_dir, filename)
        
        data = {
            "topic": topic,
            "findings_summary": findings[:500],
            "quality_score": quality,
            "is_surprise": surprise.get("is_surprise", False) if surprise else False,
            "surprise_level": surprise.get("surprise_level", 0.0) if surprise else 0.0,
            "timestamp": datetime.now().isoformat(),
            "shared": False,
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    def _slugify(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text[:50]
