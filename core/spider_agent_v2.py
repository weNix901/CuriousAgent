"""
SpiderAgent - 重构版

使用新的 QueueService 消费队列
"""

import time
import threading

from core.queue_service import QueueService, ExplorationResult


class SpiderAgent(threading.Thread):
    """
    SpiderAgent - 重构版
    
    使用新的 QueueService 消费队列
    """
    
    def __init__(
        self,
        queue_service: QueueService,
        explorer,
        name: str = "SpiderAgent",
    ):
        super().__init__(name=name, daemon=True)
        self._queue = queue_service
        self._explorer = explorer
        self._running = False
        self._consecutive_empty = 0
        self._max_empty = 5
        self._sleep_interval = 30
    
    def run(self):
        """主循环"""
        self._running = True
        print(f"[{self.name}] Started")
        
        while self._running:
            try:
                item = self._queue.claim_next(agent_id=self.name)
                
                if item:
                    self._consecutive_empty = 0
                    self._process_item(item)
                else:
                    self._consecutive_empty += 1
                    
                    if self._consecutive_empty >= self._max_empty:
                        time.sleep(self._sleep_interval)
                    else:
                        time.sleep(1)
                        
            except Exception as e:
                print(f"[{self.name}] Error: {e}")
                time.sleep(5)
        
        print(f"[{self.name}] Stopped")
    
    def stop(self):
        """停止 Agent"""
        self._running = False
    
    def _process_item(self, item):
        """处理队列项"""
        topic = item.topic
        print(f"[{self.name}] Processing: {topic}")
        
        try:
            # 开始探索
            if not self._queue.start_exploration(item.id, self.name):
                print(f"[{self.name}] Failed to start: {topic}")
                return
            
            # 执行探索
            result = self._explorer.explore(topic=topic, depth=item.depth)
            
            # 评估质量
            quality = self._assess_quality(topic, result)
            
            # 完成探索
            exploration_result = ExplorationResult(
                topic=topic,
                summary=result.get("summary", ""),
                sources=result.get("sources", []),
                quality=quality,
                findings=result,
            )
            
            self._queue.complete_exploration(item.id, exploration_result)
            print(f"[{self.name}] Completed {topic} (Q={quality})")
            
            # 高质量则分解
            if quality >= 7.0:
                self._decompose(item, result)
                
        except Exception as e:
            print(f"[{self.name}] Error processing {topic}: {e}")
            self._queue.fail_exploration(item.id, str(e), retryable=True)
    
    def _assess_quality(self, topic: str, result: dict) -> float:
        """评估质量"""
        from core.quality_v2_fixed import QualityV2Assessor
        
        assessor = QualityV2Assessor(self._explorer.llm_client)
        findings = {
            "summary": result.get("summary", ""),
            "sources": result.get("sources", []),
        }
        return assessor.assess_quality(topic, findings)
    
    def _decompose(self, item, result: dict):
        """分解话题"""
        try:
            from core.curiosity_decomposer import decompose_and_write
            
            subtopics = decompose_and_write(
                topic=item.topic,
                content=result.get("summary", ""),
                parent=item.topic,
            )
            
            print(f"[{self.name}] Decomposed into {len(subtopics)} subtopics")
            
        except Exception as e:
            print(f"[{self.name}] Decompose error: {e}")
