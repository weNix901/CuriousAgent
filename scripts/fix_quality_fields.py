#!/usr/bin/env python3
"""
Fix missing quality fields in KG nodes
All nodes will be initialized with quality=0 if not present
"""

import sys
sys.path.insert(0, '/root/dev/curious-agent')

from core import knowledge_graph as kg

def fix_missing_quality():
    """Add quality field to all nodes that don't have it"""
    state = kg._load_state()
    topics = state.get("knowledge", {}).get("topics", {})
    
    fixed_count = 0
    already_has_quality = 0
    
    for topic_name, topic_data in topics.items():
        if "quality" not in topic_data:
            topic_data["quality"] = 0
            fixed_count += 1
        else:
            already_has_quality += 1
    
    kg._save_state(state)
    
    print(f"=== Quality Field Fix ===")
    print(f"Total nodes: {len(topics)}")
    print(f"Fixed (added quality=0): {fixed_count}")
    print(f"Already had quality: {already_has_quality}")
    
    return fixed_count

if __name__ == "__main__":
    fixed = fix_missing_quality()
    print(f"\n{fixed} nodes fixed. Refresh UI to see colored nodes.")
