#!/usr/bin/env python3
"""
fix_stuck_exploring.py — Hotfix for CA v0.2.7 deadlock

Problem: SpiderAgent uses kg.claim_pending_item() which sets status=exploring
WITHOUT setting claimed_at. These items get stuck forever.

Fix: Reset stuck "exploring" items (no claimed_at or too old) back to "pending".

Usage: python3 fix_stuck_exploring.py [--dry-run] [--max-age-minutes 30]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

# Add curious-agent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge/state.json")
DEFAULT_STATE = {
    "curiosity_queue": [],
    "knowledge": {"topics": {}},
    "last_update": None,
}


def load_state():
    if not os.path.exists(STATE_FILE):
        return DEFAULT_STATE.copy()
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return DEFAULT_STATE.copy()


def save_state(state):
    state["last_update"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def fix_stuck_items(max_age_minutes: int = 30, dry_run: bool = True):
    state = load_state()
    queue = state.get("curiosity_queue", [])
    
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=max_age_minutes)
    
    stuck_items = []
    for item in queue:
        if item.get("status") != "exploring":
            continue
        
        claimed_at_str = item.get("metadata", {}).get("claimed_at") or item.get("claimed_at")
        
        if not claimed_at_str:
            # No claimed_at → definitely stuck (v0.2.7 bug)
            stuck_items.append(item)
        else:
            # Has claimed_at but check if it's old
            try:
                claimed_at = datetime.fromisoformat(claimed_at_str.replace("Z", "+00:00"))
                if claimed_at < cutoff:
                    stuck_items.append(item)
            except (ValueError, TypeError):
                stuck_items.append(item)
    
    if not stuck_items:
        print(f"✅ No stuck items found (checked {len(queue)} queue items)")
        return
    
    print(f"🔧 Found {len(stuck_items)} stuck 'exploring' items:")
    for item in stuck_items:
        topic = item.get("topic", "?")
        claimed_at = item.get("metadata", {}).get("claimed_at") or item.get("claimed_at") or "NONE"
        created = item.get("created_at", "?")
        print(f"  - {topic}")
        print(f"    created: {created}, claimed_at: {claimed_at}")
    
    if dry_run:
        print(f"\n🟡 DRY RUN — {len(stuck_items)} items would be reset to 'pending'")
        print("   Run with --no-dry-run to apply")
    else:
        for item in stuck_items:
            item["status"] = "pending"
            # Clear claimed_at so SpiderAgent can re-claim cleanly
            if "metadata" in item and "claimed_at" in item["metadata"]:
                del item["metadata"]["claimed_at"]
            elif "claimed_at" in item:
                del item["claimed_at"]
        save_state(state)
        print(f"\n✅ Fixed {len(stuck_items)} stuck items — reset to 'pending'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix stuck exploring items in CA queue")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", 
                        help="Show what would be fixed without making changes")
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false",
                        help="Actually apply the fix")
    parser.add_argument("--max-age-minutes", type=int, default=30,
                        help="Consider items stuck if exploring > N minutes (default: 30)")
    parser.set_defaults(dry_run=True)
    args = parser.parse_args()
    
    fix_stuck_items(max_age_minutes=args.max_age_minutes, dry_run=args.dry_run)
