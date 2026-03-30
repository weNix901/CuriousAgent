#!/usr/bin/env python3
"""
G4 Data Cleanup Script
Fixes stuck items and cleans up stub files from v0.2.6
"""

import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, '/root/dev/curious-agent')

from core import knowledge_graph as kg

def fix_stuck_items():
    """Fix 93 stuck curiosity items"""
    state = kg._load_state()
    queue = state.get("curiosity_queue", [])
    topics = state.get("knowledge", {}).get("topics", {})
    
    fixed_partial = 0
    fixed_missing = 0
    deleted_test = 0
    
    for item in queue[:]:  # Copy list to avoid modification during iteration
        topic = item.get("topic", "")
        status = item.get("status", "")
        
        # Skip non-stuck items
        if status != "exploring":
            continue
        
        # Delete "test connectivity" items
        if "test connectivity" in topic.lower():
            queue.remove(item)
            deleted_test += 1
            print(f"Deleted test item: {topic}")
            continue
        
        # Check if topic has content in KG
        kg_topic = topics.get(topic, {})
        has_content = bool(
            kg_topic.get("summary") or 
            kg_topic.get("sources") or 
            kg_topic.get("children")
        )
        
        if has_content:
            # Partial but has content -> mark as done
            item["status"] = "done"
            fixed_partial += 1
            print(f"Fixed partial (done): {topic}")
        else:
            # Missing -> mark as pending for retry
            item["status"] = "pending"
            fixed_missing += 1
            print(f"Fixed missing (pending): {topic}")
    
    kg._save_state(state)
    
    print(f"\n=== Stuck Items Fixed ===")
    print(f"Partial → done: {fixed_partial}")
    print(f"Missing → pending: {fixed_missing}")
    print(f"Test items deleted: {deleted_test}")
    print(f"Total fixed: {fixed_partial + fixed_missing + deleted_test}")
    
    return fixed_partial, fixed_missing, deleted_test

def clear_dream_inbox():
    """Clear DreamInbox counter"""
    inbox_path = Path('/root/dev/curious-agent/knowledge/dream_topic_inbox.json')
    if inbox_path.exists():
        with open(inbox_path, 'r') as f:
            inbox = json.load(f)
        
        count = len(inbox.get("items", []))
        # Keep items but log count
        print(f"\n=== DreamInbox Status ===")
        print(f"Current items: {count}")
        print(f"Inbox will be consumed by SpiderAgent normally")
    
    return count if inbox_path.exists() else 0

def cleanup_stub_files():
    """Clean up stub discovery files"""
    discoveries_dir = Path('/root/dev/curious-agent/knowledge/discoveries')
    if not discoveries_dir.exists():
        print("\n=== No Discoveries Directory ===")
        return 0
    
    stub_count = 0
    
    for file_path in discoveries_dir.glob("*.md"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if it's a stub file (starts with "推理分析：" or has stub markers)
            is_stub = (
                content.startswith("推理分析：") or
                "stub" in content.lower() or
                len(content) < 200  # Very short files are likely stubs
            )
            
            if is_stub:
                # Backup before delete
                backup_dir = Path('/root/dev/curious-agent/knowledge/discoveries_backup')
                backup_dir.mkdir(exist_ok=True)
                backup_path = backup_dir / file_path.name
                
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                file_path.unlink()
                stub_count += 1
                print(f"Cleaned stub: {file_path.name}")
        
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
    
    print(f"\n=== Stub Files Cleaned ===")
    print(f"Total stubs removed: {stub_count}")
    print(f"Backups saved to: {discoveries_dir}_backup")
    
    return stub_count

def main():
    """Run all cleanup tasks"""
    print("="*60)
    print("G4 Data Cleanup - v0.2.6 Bug Fixes")
    print("="*60)
    
    # Fix stuck items
    fixed_partial, fixed_missing, deleted_test = fix_stuck_items()
    
    # Clear/check DreamInbox
    inbox_count = clear_dream_inbox()
    
    # Cleanup stub files
    stub_count = cleanup_stub_files()
    
    # Summary
    print("\n" + "="*60)
    print("Cleanup Summary")
    print("="*60)
    print(f"Stuck items fixed: {fixed_partial + fixed_missing + deleted_test}")
    print(f"  - Partial → done: {fixed_partial}")
    print(f"  - Missing → pending: {fixed_missing}")
    print(f"  - Test items deleted: {deleted_test}")
    print(f"DreamInbox items: {inbox_count}")
    print(f"Stub files cleaned: {stub_count}")
    print("\nNext steps:")
    print("1. Restart Daemon: python3 curious_agent.py --daemon")
    print("2. Monitor: curl http://localhost:4848/api/curious/state")
    print("="*60)

if __name__ == "__main__":
    main()
