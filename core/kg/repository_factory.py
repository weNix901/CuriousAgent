"""Repository factory for creating the appropriate KG repository."""
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config import Config
    from core.kg.kg_repository import KGRepository
    from core.kg.json_kg_repository import JSONKGRepository


class KGRepositoryFactory:
    """Factory for creating Knowledge Graph repositories."""

    @staticmethod
    def create(config: "Config") -> "KGRepository | JSONKGRepository":
        """
        Create the appropriate KG repository based on config.
        
        Returns:
            - Neo4jKGRepository if config.knowledge.kg.enabled is True and Neo4j is available
            - JSONKGRepository otherwise (fallback)
        """
        kg_cfg = config.knowledge.get("kg")
        
        if kg_cfg and getattr(kg_cfg, "enabled", False):
            # Try to create Neo4j repository
            try:
                from core.kg.neo4j_client import Neo4jClient
                from core.kg.kg_repository import KGRepository
                
                password = os.environ.get(kg_cfg.password_env, "")
                if not password:
                    raise ValueError(f"Environment variable {kg_cfg.password_env} not set")
                
                client = Neo4jClient(
                    uri=kg_cfg.uri,
                    username=kg_cfg.username,
                    password=password
                )
                
                return KGRepository(client)
            except Exception as e:
                print(f"[KGRepositoryFactory] Neo4j unavailable ({e}), falling back to JSON")
        
        # Fallback to JSON repository
        from core.kg.json_kg_repository import JSONKGRepository
        return JSONKGRepository()

    @staticmethod
    def create_json() -> "JSONKGRepository":
        """Create a JSON-backed repository (always available)."""
        from core.kg.json_kg_repository import JSONKGRepository
        return JSONKGRepository()
