#!/usr/bin/env python3
"""
一次性迁移: knowledge/state.json → Neo4j

用法:
    python scripts/migrate_state_to_neo4j.py --dry-run  # 预览
    python scripts/migrate_state_to_neo4j.py --execute  # 执行
"""

import argparse
import json
import os
import sys
from pathlib import Path
from neo4j import GraphDatabase


class StateToNeo4jMigrator:
    def __init__(self, uri: str, user: str, password: str, state_file: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.state_file = Path(state_file)
        
    def load_state(self) -> dict:
        """加载state.json"""
        if not self.state_file.exists():
            raise FileNotFoundError(f"State file not found: {self.state_file}")
        with open(self.state_file) as f:
            return json.load(f)
    
    def migrate_topics(self, topics: dict) -> int:
        """迁移知识节点"""
        count = 0
        with self.driver.session() as session:
            for topic_name, node_data in topics.items():
                session.execute_write(self._create_node, topic_name, node_data)
                count += 1
                if count % 50 == 0:
                    print(f"  Migrated {count} nodes...")
        return count
    
    def _create_node(self, tx, topic: str, data: dict):
        """创建单个Knowledge节点"""
        query = """
        MERGE (k:Knowledge {topic: $topic})
        SET k.summary = $summary,
            k.status = $status,
            k.quality = $quality,
            k.depth = $depth,
            k.sources = $sources,
            k.explore_count = $explore_count,
            k.created_at = datetime(),
            k.updated_at = datetime()
        """
        tx.run(query, {
            "topic": topic,
            "summary": data.get("summary", ""),
            "status": data.get("status", "unexplored"),
            "quality": data.get("quality", 0) or 0,
            "depth": data.get("depth", 0) or 0,
            "sources": data.get("sources", []),
            "explore_count": data.get("explore_count", 0) or 0
        })
    
    def migrate_relations(self, topics: dict) -> int:
        """迁移关系"""
        count = 0
        with self.driver.session() as session:
            for parent, data in topics.items():
                # 父子关系
                for child in data.get("children", []):
                    if child in topics:
                        session.execute_write(self._create_relation, parent, child, "IS_CHILD_OF")
                        count += 1
                # 引用关系
                for cited in data.get("cites", []):
                    if cited in topics:
                        session.execute_write(self._create_relation, parent, cited, "CITES")
                        count += 1
        return count
    
    def _create_relation(self, tx, source: str, target: str, rel_type: str):
        """创建关系"""
        query = f"""
        MATCH (a:Knowledge {{topic: $source}})
        MATCH (b:Knowledge {{topic: $target}})
        MERGE (a)-[:{rel_type}]->(b)
        """
        tx.run(query, {"source": source, "target": target})
    
    def migrate_queue(self, queue: list) -> int:
        """迁移队列到SQLite"""
        try:
            from core.tools.queue_tools import QueueStorage
            storage = QueueStorage()
            storage.initialize()
            
            count = 0
            for item in queue:
                if item.get("status") != "done":
                    storage.add_item(
                        topic=item["topic"],
                        priority=item.get("score", 5.0),
                        metadata={"reason": item.get("reason", "")}
                    )
                    count += 1
            return count
        except Exception as e:
            print(f"  Warning: Queue migration failed: {e}")
            return 0
    
    def verify(self, expected_topics: int) -> dict:
        """验证迁移"""
        with self.driver.session() as session:
            result = session.execute_read(lambda tx: 
                tx.run("MATCH (k:Knowledge) RETURN count(k) as count").single())
            neo4j_count = result["count"] if result else 0
        
        return {
            "expected": expected_topics,
            "actual": neo4j_count,
            "success": neo4j_count >= expected_topics * 0.95  # 允许5%差异
        }
    
    def close(self):
        self.driver.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate state.json to Neo4j")
    parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    parser.add_argument("--execute", action="store_true", help="Execute migration")
    parser.add_argument("--neo4j-uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", default=os.environ.get("NEO4J_USERNAME", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.environ.get("NEO4J_PASSWORD", ""))
    parser.add_argument("--state-file", default="knowledge/state.json")
    args = parser.parse_args()
    
    if not args.neo4j_password:
        print("Error: NEO4J_PASSWORD not set (use --neo4j-password or env var)")
        sys.exit(1)
    
    migrator = StateToNeo4jMigrator(
        uri=args.neo4j_uri,
        user=args.neo4j_user,
        password=args.neo4j_password,
        state_file=args.state_file
    )
    
    try:
        state = migrator.load_state()
        topics = state.get("knowledge", {}).get("topics", {})
        queue = state.get("curiosity_queue", [])
        
        print(f"📊 Topics to migrate: {len(topics)}")
        print(f"📊 Queue items to migrate: {len(queue)}")
        
        if args.dry_run:
            print("✅ Dry run complete - no changes made")
            return
        
        if not args.execute:
            print("❌ Must specify --execute or --dry-run")
            sys.exit(1)
        
        # 执行迁移
        print("🔄 Migrating topics...")
        topic_count = migrator.migrate_topics(topics)
        print(f"✅ Migrated {topic_count} topics")
        
        print("🔄 Migrating relations...")
        rel_count = migrator.migrate_relations(topics)
        print(f"✅ Migrated {rel_count} relations")
        
        print("🔄 Migrating queue...")
        queue_count = migrator.migrate_queue(queue)
        print(f"✅ Migrated {queue_count} queue items")
        
        # 验证
        print("🔍 Verifying...")
        verification = migrator.verify(len(topics))
        if verification["success"]:
            print(f"✅ Verification passed: {verification['actual']} nodes in Neo4j")
        else:
            print(f"⚠️ Verification: expected {verification['expected']}, got {verification['actual']}")
        
        print("✅ Migration complete")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        migrator.close()


if __name__ == "__main__":
    main()