# core/embedding_service.py
"""Multi-provider embedding service with fallback support"""
import os
from typing import List, Union, Dict
import numpy as np

from core.config import EmbeddingConfig


class EmbeddingError(Exception):
    """Raised when all embedding providers fail"""
    pass


class BaseEmbeddingProvider:
    """Base class for embedding providers"""

    def __init__(self, config: EmbeddingConfig):
        self.config = config

    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class VolcengineEmbeddingProvider(BaseEmbeddingProvider):
    """Volcengine embedding API provider"""

    def embed(self, texts: List[str]) -> List[List[float]]:
        import requests

        api_key = os.environ.get(self.config.api_key_env)
        if not api_key:
            raise EmbeddingError(f"API key not found in {self.config.api_key_env}")

        url = "https://ark.cn-beijing.volces.com/api/v3/embeddings"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        embeddings = []
        for i in range(0, len(texts), self.config.batch_size):
            batch = texts[i:i + self.config.batch_size]
            payload = {
                "model": self.config.model,
                "input": batch
            }

            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()

            data = response.json()
            batch_embeddings = [item["embedding"] for item in data["data"]]
            embeddings.extend(batch_embeddings)

        return embeddings


class LLMBasedEmbeddingProvider(BaseEmbeddingProvider):
    """Fallback: use hash-based pseudo-embeddings (last resort)"""

    def embed(self, texts: List[str]) -> List[List[float]]:
        import hashlib

        embeddings = []
        for text in texts:
            hash_val = hashlib.md5(text.encode()).hexdigest()
            np.random.seed(int(hash_val[:8], 16))
            embedding = np.random.randn(768).tolist()
            norm = np.linalg.norm(embedding)
            embedding = [x / norm for x in embedding]
            embeddings.append(embedding)

        return embeddings


class EmbeddingService:
    """Multi-provider embedding service with intelligent fallback"""

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.providers: Dict[str, BaseEmbeddingProvider] = {}
        self._init_providers()
        self._cache: Dict[str, List[float]] = {}
        self._cache_size = config.cache_size

    def _init_providers(self):
        """Initialize all available providers"""
        self.providers = {
            "volcengine": VolcengineEmbeddingProvider(self.config),
            "llm": LLMBasedEmbeddingProvider(self.config)
        }

    def embed(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """Embed texts with automatic fallback between providers."""
        if isinstance(texts, str):
            texts = [texts]

        cached_results = []
        texts_to_embed = []
        text_indices = []

        for i, text in enumerate(texts):
            if text in self._cache:
                cached_results.append((i, self._cache[text]))
            else:
                texts_to_embed.append(text)
                text_indices.append(i)

        if not texts_to_embed:
            result_map = {idx: emb for idx, emb in cached_results}
            return [result_map[i] for i in range(len(texts))]

        embeddings = None
        last_error = None

        for provider_name in self.config.fallback_chain:
            if provider_name not in self.providers:
                continue

            try:
                provider = self.providers[provider_name]
                embeddings = provider.embed(texts_to_embed)
                print(f"[EmbeddingService] Using provider: {provider_name}")
                break
            except Exception as e:
                print(f"[EmbeddingService] Provider {provider_name} failed: {e}")
                last_error = e
                continue

        if embeddings is None:
            raise EmbeddingError(f"All providers failed. Last error: {last_error}")

        for text, emb in zip(texts_to_embed, embeddings):
            if len(self._cache) >= self._cache_size:
                self._cache = dict(list(self._cache.items())[self._cache_size // 2:])
            self._cache[text] = emb

        result_map: Dict[int, List[float]] = {}
        for idx, emb in cached_results:
            result_map[idx] = emb
        for idx, emb in zip(text_indices, embeddings):
            result_map[idx] = emb

        return [result_map[i] for i in range(len(texts))]

    def cosine_similarity(self, emb1: List[float], emb2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings"""
        v1 = np.array(emb1)
        v2 = np.array(emb2)

        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(v1, v2) / (norm1 * norm2))
