import json
from typing import Any, Dict, List
from core.kg.neo4j_client import Neo4jClient


def read_json_state(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def convert_to_neo4j_nodes(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    nodes = []
    topics = state.get("knowledge", {}).get("topics", {})
    
    for topic_name, topic_data in topics.items():
        node = {
            "topic": topic_name,
            "content": topic_data.get("summary", ""),
            "metadata": {
                "status": topic_data.get("status", "pending"),
                "quality": topic_data.get("quality", 0.0),
                "confidence": topic_data.get("confidence", 0.0),
                "known": topic_data.get("known", False),
                "depth": topic_data.get("depth", 0),
            }
        }
        nodes.append(node)
    
    return nodes


def validate_migration(source_count: int, target_count: int) -> bool:
    return source_count > 0 and source_count == target_count


async def run_migration(
    json_path: str,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str
) -> Dict[str, Any]:
    result = {
        "success": False,
        "nodes_migrated": 0,
        "validation_passed": False,
        "error": None
    }
    
    try:
        client = Neo4jClient(neo4j_uri, neo4j_user, neo4j_password)
        
        try:
            await client.connect()
        except Exception as e:
            result["error"] = f"Neo4j connection failed: {e}"
            return result
        
        try:
            state = read_json_state(json_path)
            nodes = convert_to_neo4j_nodes(state)
            source_count = len(nodes)
            
            if source_count == 0:
                result["error"] = "No topics found in JSON state"
                return result
            
            migrated_count = 0
            for node in nodes:
                await client.execute_write(
                    """
                    MERGE (n:Knowledge {topic: $topic})
                    SET n.content = $content,
                        n.status = $status,
                        n.quality = $quality,
                        n.confidence = $confidence,
                        n.known = $known,
                        n.depth = $depth,
                        n.updated_at = timestamp()
                    """,
                    topic=node["topic"],
                    content=node["content"],
                    status=node["metadata"]["status"],
                    quality=node["metadata"]["quality"],
                    confidence=node["metadata"]["confidence"],
                    known=node["metadata"]["known"],
                    depth=node["metadata"]["depth"]
                )
                migrated_count += 1
            
            result["nodes_migrated"] = migrated_count
            result["validation_passed"] = validate_migration(source_count, migrated_count)
            result["success"] = result["validation_passed"]
            
        finally:
            await client.disconnect()
            
    except Exception as e:
        result["error"] = str(e)
        result["success"] = False
    
    return result
