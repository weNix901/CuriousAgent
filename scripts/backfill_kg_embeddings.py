"""Backfill embeddings for existing KG nodes."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.kg.neo4j_client import Neo4jClient
from core.kg.kg_repository import KGRepository
from core.embedding_service import EmbeddingService
from core.config import load_config
from core.concept_normalizer import ConceptNormalizer
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def backfill_embeddings():
    """Backfill embeddings for all existing KG nodes without embeddings."""
    config = load_config()
    
    kg_config = config.knowledge["kg"]
    neo4j_uri = kg_config.uri
    neo4j_username = kg_config.username
    neo4j_password_env = kg_config.password_env
    neo4j_password = None
    
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists() and not neo4j_password:
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    if key.strip() == "NEO4J_PASSWORD":
                        neo4j_password = value.strip().strip('"').strip("'")
                        break
    
    if not neo4j_password:
        neo4j_password = "R1D3researcher2026"
    
    logger.info(f"Connecting to Neo4j at {neo4j_uri}")
    
    neo4j_client = Neo4jClient(
        uri=neo4j_uri,
        username=neo4j_username,
        password=neo4j_password
    )
    await neo4j_client.connect()
    
    embedding_config = config.knowledge["embedding"]
    embedding_service = EmbeddingService(embedding_config)
    repo = KGRepository(neo4j_client, embedding_service)
    normalizer = ConceptNormalizer()
    
    query = """
    MATCH (n:Knowledge)
    WHERE n.status = 'done' AND (n.embedding IS NULL OR n.embedding = [])
    RETURN n.topic as topic, n.content as content
    """
    nodes = await neo4j_client.execute_query(query)
    
    logger.info(f"Found {len(nodes)} nodes to backfill")
    
    if not nodes:
        logger.info("No nodes need backfill. Exiting.")
        await neo4j_client.disconnect()
        return
    
    processed = 0
    skipped = 0
    failed = 0
    
    for node in nodes:
        topic = node["topic"]
        content = node.get("content", "")
        
        if not content:
            logger.warning(f"Skipping '{topic}' - no content")
            skipped += 1
            continue
        
        logger.info(f"Processing: {topic}")
        
        keywords = normalizer.extract_core_concepts(topic + " " + content)[:10]
        key_points = [s.strip()[:100] for s in content.split("\n")[:5] if s.strip()]
        combined_text = repo._build_combined_text(topic, content, key_points, keywords)
        
        try:
            embedding = embedding_service.embed([combined_text])[0]
        except Exception as e:
            logger.error(f"Failed to embed '{topic}': {e}")
            failed += 1
            continue
        
        update_query = """
        MATCH (n:Knowledge {topic: $topic})
        SET n.embedding = $embedding,
            n.key_points = $key_points,
            n.keywords = $keywords,
            n.updated_at = timestamp()
        """
        await neo4j_client.execute_write(
            update_query,
            topic=topic,
            embedding=embedding,
            key_points=key_points,
            keywords=keywords
        )
        
        logger.info(f"Updated: {topic} (embedding dim: {len(embedding)})")
        processed += 1
    
    await neo4j_client.disconnect()
    
    logger.info("=" * 50)
    logger.info("Backfill complete!")
    logger.info(f"  Processed: {processed}")
    logger.info(f"  Skipped: {skipped}")
    logger.info(f"  Failed: {failed}")
    logger.info(f"  Total: {len(nodes)}")
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(backfill_embeddings())
