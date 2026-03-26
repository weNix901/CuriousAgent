import json
import os
from pathlib import Path


class R1D3Sync:
    DEFAULT_DISCOVERIES_DIR = "shared_knowledge/ca/discoveries"

    def __init__(self, discoveries_dir: str = None):
        self.discoveries_dir = Path(discoveries_dir or self.DEFAULT_DISCOVERIES_DIR)
        self.discoveries_dir.mkdir(parents=True, exist_ok=True)

    def mark_discovery_shared(self, discovery_filename: str) -> bool:
        file_path = self.discoveries_dir / discovery_filename

        if not file_path.exists():
            return False

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            data['shared'] = True
            data['shared_at'] = self._get_timestamp()

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return True
        except Exception as e:
            print(f"[R1D3Sync] Error marking discovery: {e}")
            return False

    def get_unshared_discoveries(self) -> list:
        unshared = []

        try:
            for filename in os.listdir(self.discoveries_dir):
                if not filename.endswith('.json'):
                    continue

                file_path = self.discoveries_dir / filename

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    if not data.get('shared', False):
                        data['_filename'] = filename
                        unshared.append(data)

                except (json.JSONDecodeError, Exception):
                    continue

        except FileNotFoundError:
            pass

        return unshared

    def _get_timestamp(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
