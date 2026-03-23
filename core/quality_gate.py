"""Quality Gate - Filter topics before queuing"""

# Blacklist of overly generic terms
BLACKLIST = {
    "agent", "agents",
    "system", "systems",
    "overview", "introduction",
    "what is", "how to",
}


def should_queue(topic: str, existing_topics: set = None) -> tuple[bool, str]:
    """
    Determine if a topic should be added to the curiosity queue
    
    Returns:
        (should_queue: bool, reason: str)
    """
    if not topic or not isinstance(topic, str):
        return False, "invalid_topic"
    
    topic = topic.strip()
    
    # 1. Too short
    words = topic.split()
    if len(words) < 2:
        return False, "too_short"
    
    topic_lower = topic.lower()
    if topic_lower in BLACKLIST:
        return False, f"blacklist: {topic_lower}"
    
    # 3. Duplicate check
    if existing_topics:
        topic_normalized = topic_lower.replace("_", " ")
        for existing in existing_topics:
            if _is_similar(topic_normalized, existing.lower().replace("_", " ")):
                return False, "similar_to_existing"
    
    return True, "ok"


def _is_similar(topic1: str, topic2: str, threshold: float = 0.6) -> bool:
    """Check if two topics are similar based on word overlap"""
    words1 = set(topic1.split())
    words2 = set(topic2.split())
    
    if not words1 or not words2:
        return False
    
    intersection = words1 & words2
    union = words1 | words2
    
    similarity = len(intersection) / len(union)
    return similarity >= threshold
