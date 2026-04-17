#!/usr/bin/env python3
"""回滚迁移: 从Neo4j恢复到state.json"""

import json
import os
import sys
from pathlib import Path
from neo4j import GraphDatabase


def rollback():
    """从Neo4j导出数据恢复到state.json"""
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USERNAME", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "")
    
    if not password:
        print("Error: NEO4J_PASSWORD not set")
        sys.exit(1)
    
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    try:
        with driver.session() as session:
            # 导出所有节点
            print("🔄 Exporting nodes from Neo4j...")
            nodes_result = session.execute_read(lambda tx:
                tx.run("MATCH (k:Knowledge) RETURN k").values())
            
            topics = {}
            for row in nodes_result:
                node = row[0]
                topics[node["topic"]] = {
                    "summary": node.get("summary", ""),
                    "status": node.get("status", "unexplored"),
                    "quality": node.get("quality", 0),
                    "depth": node.get("depth", 0),
                    "sources": node.get("sources", []),
                    "explore_count": node.get("explore_count", 0),
                    "children": [],
                    "cites": [],
                    "cited_by": [],
                    "parents": []
                }
            
            print(f"✅ Exported {len(topics)} topics")
            
            # 导出关系
            print("🔄 Exporting relations...")
            rels_result = session.execute_read(lambda tx:
                tx.run("""
                MATCH (a:Knowledge)-[r]->(b:Knowledge)
                RETURN a.topic as source, b.topic as target, type(r) as rel_type
                """))
            
            rel_count = 0
            for record in rels_result:
                source = record["source"]
                target = record["target"]
                rel_type = record["rel_type"]
                
                if source in topics:
                    if rel_type == "IS_CHILD_OF":
                        topics[source]["children"].append(target)
                        if target in topics:
                            topics[target]["parents"].append(source)
                    elif rel_type == "CITES":
                        topics[source]["cites"].append(target)
                        if target in topics:
                            topics[target]["cited_by"].append(source)
                    rel_count += 1
            
            print(f"✅ Exported {rel_count} relations")
            
            # 写入state.json
            state = {
                "version": "1.0",
                "last_update": None,
                "knowledge": {"topics": topics},
                "curiosity_queue": [],
                "exploration_log": [],
                "config": {
                    "curiosity_top_k": 3,
                    "max_knowledge_nodes": 5000,
                    "notification_threshold": 7.0
                },
                "root_technology_pool": {"candidates": []},
                "meta_cognitive": {
                    "last_quality": {},
                    "marginal_returns": {},
                    "explore_count": {},
                    "completed_topics": {}
                }
            }
            
            backup_path = Path("knowledge/state.json.rollback")
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            with open(backup_path, "w") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Rollback complete: {backup_path}")
            print(f"📊 Restored {len(topics)} topics, {rel_count} relations")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        driver.close()


if __name__ == "__main__":
    rollback()