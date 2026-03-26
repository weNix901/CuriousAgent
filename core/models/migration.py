def detect_schema_version(state: dict) -> str:
    return state.get("schema_version", "1.0")


def migrate_state_v1_to_v2(v1_state: dict) -> dict:
    v2_state = v1_state.copy()
    v2_state["schema_version"] = "2.0"
    
    if "knowledge" in v2_state and "topics" in v2_state["knowledge"]:
        topics = v2_state["knowledge"]["topics"]
        for name, topic_data in topics.items():
            topic_data.setdefault("parents", [])
            topic_data.setdefault("relations", [])
            topic_data.setdefault("explored_by", [])
            topic_data.setdefault("fully_explored", False)
            topic_data.setdefault("schema_version", "2.0")
            
            if "parent" in topic_data and topic_data["parent"]:
                parent = topic_data.pop("parent")
                if parent not in topic_data["parents"]:
                    topic_data["parents"].append(parent)
    
    return v2_state
