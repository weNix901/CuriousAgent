#!/usr/bin/env python3
"""Backfill quality scores for KG nodes that have quality=null, using the async explorer pipeline."""

import json
import time
from core.knowledge_graph import get_state, _save_state, _ensure_meta_cognitive
from core.explorer import Explorer
from core.quality_v2 import QualityV2Assessor
from core.llm_manager import LLMManager

def main():
    state = get_state()
    topics = state["knowledge"]["topics"]
    
    # Find topics with null quality that have a summary (already explored)
    to_backfill = []
    for name, v in topics.items():
        if v.get("quality") is None and v.get("summary"):
            to_backfill.append(name)
    
    print(f"Topics needing quality backfill: {len(to_backfill)}")
    
    llm_manager = LLMManager()
    llm_client = llm_manager.get_client()
    quality_assessor = QualityV2Assessor(llm_client)
    
    for i, topic in enumerate(to_backfill):
        v = topics[topic]
        findings = {
            "summary": v.get("summary", ""),
            "sources": v.get("sources", [])
        }
        try:
            from core import knowledge_graph as kg_module
            quality = quality_assessor.assess_quality(
                topic=topic,
                findings=findings,
                knowledge_graph=kg_module
            )
        except Exception as e:
            print(f"  [{i+1}/{len(to_backfill)}] {topic}: ERROR - {e}")
            quality = 0.0
        
        # Write quality to topics[topic]
        topics[topic]["quality"] = quality
        
        # Write to meta_cognitive.last_quality
        state = _ensure_meta_cognitive(state)
        mc = state["meta_cognitive"]
        if "last_quality" not in mc:
            mc["last_quality"] = {}
        mc["last_quality"][topic] = quality
        
        print(f"  [{i+1}/{len(to_backfill)}] {topic}: quality={quality}")
        time.sleep(0.5)  # Rate limit
    
    _save_state(state)
    print(f"\nDone. Backfilled {len(to_backfill)} topics.")

if __name__ == "__main__":
    main()
