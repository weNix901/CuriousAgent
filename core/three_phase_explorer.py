"""ThreePhaseExplorer - Monitor-Generate-Verify cycle"""
import json
from typing import Optional


class ThreePhaseExplorer:
    """
    Three-phase exploration cycle:
    1. Monitor: Assess current understanding, identify knowledge gaps
    2. Generate: Create exploration plan based on gaps
    3. Verify: Execute and validate gap closure
    """
    
    def __init__(self, explorer, monitor, llm_client):
        self.explorer = explorer
        self.monitor = monitor
        self.llm = llm_client
    
    def explore(self, curiosity_item: dict) -> dict:
        """Execute three-phase exploration"""
        topic = curiosity_item["topic"]
        depth = curiosity_item.get("depth", "medium")
        
        monitor_result = self._phase1_monitor(topic)
        if monitor_result.get("already_known"):
            return {
                "status": "already_known",
                "confidence": monitor_result["confidence"],
                "reason": monitor_result.get("reason", "")
            }
        
        knowledge_gaps = monitor_result.get("knowledge_gaps", [])
        
        exploration_plan = self._phase2_generate(topic, knowledge_gaps, depth)
        
        findings = self._phase3_execute(topic, exploration_plan)
        verification = self._verify_knowledge_gaps(knowledge_gaps, findings)
        
        return {
            "status": "success",
            "findings": findings,
            "verification_score": verification["score"],
            "gaps_filled": verification["gaps_filled"],
            "knowledge_gaps": knowledge_gaps
        }
    
    def _phase1_monitor(self, topic: str) -> dict:
        """Assess understanding and identify gaps"""
        confidence = self.monitor._compute_user_relevance(topic)
        
        if confidence > 0.8:
            return {
                "already_known": True,
                "confidence": confidence,
                "reason": f"High confidence ({confidence:.2f})"
            }
        
        gaps = self._identify_knowledge_gaps(topic)
        return {
            "already_known": False,
            "confidence": confidence,
            "knowledge_gaps": gaps
        }
    
    def _identify_knowledge_gaps(self, topic: str) -> list:
        """Use LLM to identify knowledge gaps with flexible typing and priority standards"""
        prompt = f"""Analyze "{topic}" and identify knowledge gaps in this exploration result.

Return a JSON array of gaps (if none found, return []):
[
  {{
    "gap_type": "practical_implementation" | "theoretical_foundation" |
                 "empirical_evidence" | "industry_applications" |
                 "comparison_analysis" | "limitations_ethics" | "general",
    "description": "specific description of what's missing",
    "priority": 0.0-1.0
  }}
]

gap_type definitions:
- practical_implementation: missing code, algorithm details, engineering practice guidelines
- theoretical_foundation: core principles, formal definitions, theoretical guarantees unclear
- empirical_evidence: missing experimental data, benchmarks, performance comparisons
- industry_applications: missing real-world application cases, production deployment experience
- comparison_analysis: missing comparison with other methods, pros/cons analysis
- limitations_ethics: missing limitations, safety, ethical considerations
- general: other types of gaps

priority reference:
- 0.7-1.0: critical gap - essential for understanding the topic but missing from exploration
- 0.5-0.7: minor gap - helpful but not core to understanding
- 0.3-0.5: nice-to-have gap - would be good to have but not essential

Return ONLY JSON, no other text."""

        try:
            response = self.llm.chat(prompt)
            result = json.loads(response)
            if isinstance(result, list):
                return result
            return result.get("gaps", [])
        except Exception:
            return [{"gap_type": "general", "description": "Need more information", "priority": 0.5}]

    def _phase2_generate(self, topic: str, gaps: list, depth: str) -> list:
        """Generate exploration plan based on gaps"""
        plans = []
        for gap in gaps:
            gap_type = gap.get("gap_type", "general")
            priority = gap.get("priority", 0.5)
            
            action_map = {
                "no_technical_definition": ("find_paper", "technical_implementation"),
                "no_empirical_results": ("find_benchmark", "quantitative_evaluation"),
                "no_applications": ("find_usecase", "practical_applications"),
                "no_limitations": ("find_critique", "limitations_and_drawbacks")
            }
            
            action, target = action_map.get(gap_type, ("general_explore", "overview"))
            
            plans.append({
                "action": action,
                "target": target,
                "priority": priority,
                "depth": "deep" if priority > 0.7 else depth
            })
        
        plans.sort(key=lambda x: x["priority"], reverse=True)
        return plans
    
    def _phase3_execute(self, topic: str, plan: list) -> dict:
        """Execute exploration plan"""
        if not plan:
            return {}
        
        # Convert depth string to int for Explorer.explore() which calls int(depth)
        depth_str = plan[0].get("depth", "medium")
        depth_map = {"shallow": 3, "medium": 5, "deep": 8}
        depth_int = depth_map.get(depth_str, 5)

        curiosity_item = {
            "topic": topic,
            "depth": depth_int,
            "score": 5.0
        }
        
        return self.explorer.explore(curiosity_item)
    
    def _verify_knowledge_gaps(self, gaps: list, findings: dict) -> dict:
        """Verify if gaps were filled"""
        summary = findings.get("findings", "")
        
        if not gaps or not summary:
            return {"score": 0.5, "gaps_filled": []}
        
        gaps_filled = []
        for gap in gaps:
            gap_type = gap.get("type", "").lower()
            if gap_type.replace("no_", "") in summary.lower():
                gaps_filled.append(gap_type)
        
        score = len(gaps_filled) / len(gaps) if gaps else 0.5
        return {"score": score, "gaps_filled": gaps_filled}
