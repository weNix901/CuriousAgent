import json
import os


class R1D3Watcher:
    def __init__(self, propositions_dir: str = "shared_knowledge/r1d3/propositions"):
        self.propositions_dir = propositions_dir
        self._processed = set()
        os.makedirs(propositions_dir, exist_ok=True)
    
    def scan_new_propositions(self) -> list[dict]:
        if not os.path.exists(self.propositions_dir):
            return []
        
        propositions = []
        for filename in sorted(os.listdir(self.propositions_dir)):
            if not filename.endswith(".json"):
                continue
            if filename in self._processed:
                continue
            
            filepath = os.path.join(self.propositions_dir, filename)
            try:
                with open(filepath, encoding="utf-8") as f:
                    prop = json.load(f)
                    propositions.append(prop)
                    self._processed.add(filename)
            except Exception as e:
                print(f"[R1D3Watcher] Failed to read {filename}: {e}")
        
        return propositions
    
    def get_seed_topics(self, proposition: dict) -> list[str]:
        return proposition.get("seed_topics", [])
