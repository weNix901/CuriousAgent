import json
import os
from datetime import datetime
from core.spider.state import SpiderRuntimeState


class SpiderCheckpoint:
    def __init__(self, path="state/spider_state.json"):
        self.path = path
    
    def save(self, state, kg_path):
        data = {
            "runtime_state": state.to_dict(),
            "kg_path": kg_path,
            "timestamp": datetime.now().isoformat(),
        }
        
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load(self):
        if not os.path.exists(self.path):
            return None
        
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        state = SpiderRuntimeState.from_dict(data["runtime_state"])
        kg_path = data["kg_path"]
        
        return state, kg_path
    
    def exists(self):
        return os.path.exists(self.path)
    
    def clear(self):
        if os.path.exists(self.path):
            os.remove(self.path)
