"""Custom exceptions for Curious Agent"""


class ClarificationNeeded(Exception):
    """
    Raised when the decomposer cannot determine the domain/context of a topic
    and needs user clarification.
    """
    
    def __init__(self, topic: str, alternatives: list[str] = None, reason: str = ""):
        self.topic = topic
        self.alternatives = alternatives or ["AI/Agent", "软件开发", "通用概念"]
        self.reason = reason
        message = f"无法确定 '{topic}' 的领域，请选择或输入具体领域"
        if reason:
            message += f" ({reason})"
        super().__init__(message)
