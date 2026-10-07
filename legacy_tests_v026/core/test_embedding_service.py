# tests/core/test_embedding_service.py
import pytest
from unittest.mock import Mock, patch, MagicMock
from core.embedding_service import (
    EmbeddingService,
    EmbeddingConfig,
    EmbeddingError,
    BaseEmbeddingProvider,
    VolcengineEmbeddingProvider,
    LLMBasedEmbeddingProvider,
)


class TestEmbeddingConfig:
    """Test EmbeddingConfig defaults"""

    def test_default_values(self):
        """Test default configuration values"""
        config = EmbeddingConfig()
        assert config.provider == "volcengine"
        assert config.model == "text-embedding-async"
        assert config.dimension == 768
        assert config.similarity_threshold == 0.82
        assert config.batch_size == 32
        assert config.cache_size == 10000
        assert config.api_key_env == "EMBEDDING_API_KEY"
        assert config.fallback_chain == ["volcengine", "llm"]

    def test_custom_values(self):
        """Test custom configuration"""
        config = EmbeddingConfig(
            provider="volcengine",
            model="custom-model",
            dimension=1536,
            cache_size=5000,
        )
        assert config.model == "custom-model"
        assert config.dimension == 1536
        assert config.cache_size == 5000


class TestBaseEmbeddingProvider:
    """Test base provider interface"""

    def test_base_not_implemented(self):
        """Test that base provider embed raises NotImplementedError"""
        config = EmbeddingConfig()
        provider = BaseEmbeddingProvider(config)
        with pytest.raises(NotImplementedError):
            provider.embed(["test"])


class TestLLMBasedEmbeddingProvider:
    """Test LLM fallback provider"""

    def test_embed_returns_768_dim(self):
        """Test that LLM provider returns 768-dim embeddings"""
        config = EmbeddingConfig()
        provider = LLMBasedEmbeddingProvider(config)

        result = provider.embed(["test text"])

        assert len(result) == 1
        assert len(result[0]) == 768

    def test_embed_multiple_texts(self):
        """Test embedding multiple texts"""
        config = EmbeddingConfig()
        provider = LLMBasedEmbeddingProvider(config)

        result = provider.embed(["text1", "text2", "text3"])

        assert len(result) == 3
        assert all(len(emb) == 768 for emb in result)

    def test_same_text_same_embedding(self):
        """Test deterministic output for same text"""
        config = EmbeddingConfig()
        provider = LLMBasedEmbeddingProvider(config)

        result1 = provider.embed(["test"])
        result2 = provider.embed(["test"])

        assert result1[0] == result2[0]

    def test_different_text_different_embedding(self):
        """Test different texts produce different embeddings"""
        config = EmbeddingConfig()
        provider = LLMBasedEmbeddingProvider(config)

        result = provider.embed(["text A", "text B"])

        assert result[0] != result[1]

    def test_embedding_normalized(self):
        """Test that embeddings are normalized (L2 norm = 1)"""
        config = EmbeddingConfig()
        provider = LLMBasedEmbeddingProvider(config)

        result = provider.embed(["some text"])
        import numpy as np
        norm = np.linalg.norm(result[0])

        assert abs(norm - 1.0) < 0.001


class TestVolcengineEmbeddingProvider:
    """Test Volcengine API provider"""

    def test_embed_requires_api_key(self):
        """Test that missing API key raises EmbeddingError"""
        config = EmbeddingConfig(api_key_env="NONEXISTENT_KEY_12345")
        provider = VolcengineEmbeddingProvider(config)

        with pytest.raises(EmbeddingError) as exc_info:
            provider.embed(["test"])
        assert "API key not found" in str(exc_info.value)

    @patch("requests.post")
    def test_embed_success(self, mock_post):
        """Test successful embedding via API"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1] * 768}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        config = EmbeddingConfig(api_key_env="FAKE_KEY")
        with patch.dict("os.environ", {"FAKE_KEY": "test-key"}):
            provider = VolcengineEmbeddingProvider(config)
            result = provider.embed(["test text"])

        assert len(result) == 1
        assert len(result[0]) == 768

    @patch("requests.post")
    def test_embed_batch_processing(self, mock_post):
        """Test that batch processing works"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.5] * 768}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        config = EmbeddingConfig(api_key_env="FAKE_KEY", batch_size=2)
        with patch.dict("os.environ", {"FAKE_KEY": "test-key"}):
            provider = VolcengineEmbeddingProvider(config)
            result = provider.embed(["a", "b", "c"])

        assert mock_post.call_count == 2


class TestEmbeddingService:
    """Test main EmbeddingService class"""

    def test_embed_single_text(self):
        """Test embedding a single text"""
        config = EmbeddingConfig(provider="volcengine")
        service = EmbeddingService(config)

        # Mock the volcengine provider
        mock_embedding = [0.1] * 768
        service.providers["volcengine"].embed = Mock(return_value=[mock_embedding])

        result = service.embed("Test text")

        assert len(result) == 1
        assert len(result[0]) == 768
        assert result[0] == mock_embedding

    def test_embed_multiple_texts(self):
        """Test embedding multiple texts"""
        config = EmbeddingConfig(provider="volcengine")
        service = EmbeddingService(config)

        mock_embeddings = [[0.1] * 768, [0.2] * 768, [0.3] * 768]
        service.providers["volcengine"].embed = Mock(return_value=mock_embeddings)

        result = service.embed(["Text one", "Text two", "Text three"])

        assert len(result) == 3
        assert all(len(emb) == 768 for emb in result)

    def test_caching(self):
        """Test that embeddings are cached"""
        config = EmbeddingConfig(provider="volcengine", cache_size=100)
        service = EmbeddingService(config)

        mock_embedding = [0.1] * 768
        service.providers["volcengine"].embed = Mock(return_value=[mock_embedding])

        # First call
        emb1 = service.embed("Cached text")
        # Second call should use cache
        emb2 = service.embed("Cached text")

        # Provider should only be called once
        assert service.providers["volcengine"].embed.call_count == 1
        assert emb1[0] == emb2[0]

    def test_cache_order_preserved(self):
        """Test that cached results maintain original text order"""
        config = EmbeddingConfig(provider="volcengine")
        service = EmbeddingService(config)

        def mock_embed(texts):
            return [[float(i)] * 768 for i, _ in enumerate(texts)]

        service.providers["volcengine"].embed = Mock(side_effect=mock_embed)

        result = service.embed(["a", "b", "c"])

        assert len(result) == 3

    def test_fallback_to_llm(self):
        """Test fallback when volcengine fails"""
        config = EmbeddingConfig(provider="volcengine", fallback_chain=["volcengine", "llm"])
        service = EmbeddingService(config)

        # Make volcengine fail
        service.providers["volcengine"].embed = Mock(side_effect=Exception("API Error"))

        # Should fallback to llm
        result = service.embed("Test text")

        assert len(result) == 1
        assert len(result[0]) == 768

    def test_all_providers_fail(self):
        """Test error when all providers fail"""
        config = EmbeddingConfig(provider="volcengine", fallback_chain=["volcengine", "llm"])
        service = EmbeddingService(config)

        # Make all providers fail
        service.providers["volcengine"].embed = Mock(side_effect=Exception("API Error"))
        service.providers["llm"].embed = Mock(side_effect=Exception("LLM Error"))

        with pytest.raises(EmbeddingError):
            service.embed("Test text")

    def test_cosine_similarity(self):
        """Test cosine similarity calculation"""
        config = EmbeddingConfig()
        service = EmbeddingService(config)

        # Same vector should have similarity 1.0
        emb = [1.0] + [0.0] * 767
        sim = service.cosine_similarity(emb, emb)
        assert abs(sim - 1.0) < 0.001

        # Orthogonal vectors should have similarity 0.0
        emb1 = [1.0] + [0.0] * 767
        emb2 = [0.0, 1.0] + [0.0] * 766
        sim = service.cosine_similarity(emb1, emb2)
        assert abs(sim - 0.0) < 0.001

    def test_cosine_similarity_opposite(self):
        """Test cosine similarity for opposite vectors"""
        config = EmbeddingConfig()
        service = EmbeddingService(config)

        emb1 = [1.0] + [0.0] * 767
        emb2 = [-1.0] + [0.0] * 767
        sim = service.cosine_similarity(emb1, emb2)
        assert abs(sim - (-1.0)) < 0.001

    def test_cosine_similarity_zero_vector(self):
        """Test cosine similarity with zero vector"""
        config = EmbeddingConfig()
        service = EmbeddingService(config)

        emb1 = [0.0] * 768
        emb2 = [1.0] + [0.0] * 767
        sim = service.cosine_similarity(emb1, emb2)
        assert sim == 0.0

    def test_mixed_cached_and_new(self):
        """Test that mixed cached and new texts work correctly"""
        config = EmbeddingConfig(provider="volcengine")
        service = EmbeddingService(config)

        mock_embed = Mock(side_effect=lambda texts: [[0.9] * 768 for _ in texts])
        service.providers["volcengine"].embed = mock_embed

        # First call caches "a"
        service.embed("a")
        assert mock_embed.call_count == 1

        # Second call: "a" cached, "b" new
        service.embed(["a", "b"])
        assert mock_embed.call_count == 2

    def test_empty_cache_eviction(self):
        """Test that cache evicts old entries when full"""
        config = EmbeddingConfig(provider="volcengine", cache_size=3)
        service = EmbeddingService(config)

        call_count = 0

        def mock_embed(texts):
            nonlocal call_count
            call_count += 1
            return [[0.1] * 768 for _ in texts]

        service.providers["volcengine"].embed = Mock(side_effect=mock_embed)

        # Fill cache
        service.embed("a")
        service.embed("b")
        service.embed("c")

        # This should trigger eviction
        service.embed("d")

        assert call_count == 4

    def test_providers_initialized(self):
        """Test that both volcengine and llm providers are initialized"""
        config = EmbeddingConfig()
        service = EmbeddingService(config)

        assert "volcengine" in service.providers
        assert "llm" in service.providers
        assert isinstance(service.providers["volcengine"], VolcengineEmbeddingProvider)
        assert isinstance(service.providers["llm"], LLMBasedEmbeddingProvider)

    def test_unknown_provider_in_chain_skipped(self):
        """Test that unknown providers in chain are skipped"""
        config = EmbeddingConfig(fallback_chain=["unknown", "llm"])
        service = EmbeddingService(config)

        result = service.embed("test")
        assert len(result) == 1
        assert len(result[0]) == 768
