            subtopics = decomposer.decompose_and_write(topic)
            print(f"[SpiderAgent] Decomposed '{topic}' into {len(subtopics)} subtopics")
            for st in subtopics:
                print(f"  + {st['sub_topic']} ({st.get('signal_strength', 'unknown')})")
        except Exception as e:
            print(f"[SpiderAgent] Decompose failed for '{topic}': {e}")

    def is_healthy(self, max_idle_seconds: float = 300) -> bool:
        """
        Check if SpiderAgent is healthy based on heartbeat.
        
        Args:
            max_idle_seconds: Maximum allowed idle time before considered stuck (default 5 minutes)
        
        Returns:
            True if healthy, False if stuck
        """
        idle_time = time.time() - self._last_explored_timestamp
        return idle_time < max_idle_seconds
    
    def get_idle_time(self) -> float:
        """Get seconds since last successful exploration."""
        return time.time() - self._last_explored_timestamp
    
    def get_explored_count(self) -> int:
        """Get total number of explored topics."""
        return len(self._explored_topics)
