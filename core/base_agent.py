"""BaseAgent - Foundation class for all Curious Agent threads."""
import threading
import time


class BaseAgent(threading.Thread):
    """
    Base class for all agent threads.
    
    Features:
    - Daemon thread (exits when main process exits)
    - Running flag for graceful shutdown
    - yield_to_other() for cooperative multitasking
    """
    
    def __init__(self, name: str):
        """
        Initialize base agent.
        
        Args:
            name: Thread name for debugging
        """
        super().__init__(name=name, daemon=True)
        self.running = True
    
    def stop(self):
        """
        Signal agent to stop gracefully.
        
        Sets running flag to False. Subclasses should check
        this flag in their run() loop and exit cleanly.
        """
        self.running = False
    
    def yield_to_other(self):
        """
        Yield execution to other threads.
        
        Calls time.sleep(0) which releases the GIL,
        allowing other Python threads to run.
        """
        time.sleep(0)
