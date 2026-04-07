# core/assertion_index.py
"""FAISS-powered assertion index for efficient similarity search"""
import sqlite3
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional


class AssertionIndex:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            root = Path(__file__).parent.parent
            db_path = str(root / "shared_knowledge" / "assertion_index" / "assertions.db")
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._faiss_index = None
        self._id_to_text = {}
        self._next_id = 0
        self._faiss_idx_to_row_id = []
        
        self._init_db()
        self._load_faiss_index()
    
    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS assertions (
                id INTEGER PRIMARY KEY,
                text TEXT UNIQUE NOT NULL,
                topic TEXT,
                source_topic TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_topic ON assertions(topic)
        """)
        
        conn.commit()
        conn.close()
    
    def _load_faiss_index(self):
        try:
            import faiss  # type: ignore[attr-defined, import-not-found]
        except ImportError:
            print("[AssertionIndex] Warning: faiss not installed, using linear scan fallback")
            return
        
        conn = sqlite3.connect(str(self.db_path))
        rows = conn.execute("SELECT id, text FROM assertions").fetchall()
        conn.close()
        
        dimension = 768
        self._faiss_index = faiss.IndexFlatIP(dimension)
        
        if rows:
            for row_id, text in rows:
                self._id_to_text[row_id] = text
                self._next_id = max(self._next_id, row_id + 1)
    
    def insert(self, text: str, embedding: List[float], 
               topic: Optional[str] = None, source_topic: Optional[str] = None) -> int:
        conn = sqlite3.connect(str(self.db_path))
        
        cursor = conn.execute("SELECT id FROM assertions WHERE text = ?", (text,))
        existing = cursor.fetchone()
        
        if existing:
            conn.close()
            return existing[0]
        
        cursor = conn.execute(
            """INSERT INTO assertions (text, topic, source_topic) 
               VALUES (?, ?, ?)""",
            (text, topic, source_topic)
        )
        row_id: int = cursor.lastrowid  # type: ignore[assignment]
        
        conn.commit()
        conn.close()
        
        if self._faiss_index is not None:
            import faiss  # type: ignore[attr-defined, import-not-found]
            emb_array = np.array([embedding], dtype=np.float32)
            faiss.normalize_L2(emb_array)
            self._faiss_index.add(emb_array)
            self._faiss_idx_to_row_id.append(row_id)
        
        self._id_to_text[row_id] = text
        self._next_id = max(self._next_id, row_id + 1)
        
        return row_id
    
    def search_similar(self, query_embedding: List[float], 
                       k: int = 5,
                       threshold: float = 0.82) -> List[Tuple[str, float]]:
        if self._faiss_index is None or self._faiss_index.ntotal == 0:
            return []
        
        import faiss  # type: ignore[attr-defined, import-not-found]
        query = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query)
        
        similarities, indices = self._faiss_index.search(query, k)
        
        results = []
        for sim, faiss_idx in zip(similarities[0], indices[0]):
            if faiss_idx < 0:
                continue
            row_id = self._faiss_idx_to_row_id[faiss_idx]
            if sim >= threshold and row_id in self._id_to_text:
                results.append((self._id_to_text[row_id], float(sim)))
        
        return results
    
    def max_similarity(self, query_embedding: List[float]) -> float:
        results = self.search_similar(query_embedding, k=1, threshold=0.0)
        return results[0][1] if results else 0.0
    
    def get_stats(self) -> dict:
        conn = sqlite3.connect(str(self.db_path))
        count = conn.execute("SELECT COUNT(*) FROM assertions").fetchone()[0]
        conn.close()
        
        return {
            "total_assertions": count,
            "faiss_index_size": self._faiss_index.ntotal if self._faiss_index else 0
        }
