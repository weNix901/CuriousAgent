"""
Integration tests for Phase 1/2/3 module integration into main workflow

These tests ensure that modules are not just implemented, but actually integrated
into the main workflow to prevent "implemented but not integrated" issues.
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock, ANY

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPhase1BehaviorWriterIntegration:
    """Test Phase 1: AgentBehaviorWriter integration into curious_agent.py"""

    def test_behavior_writer_initialized_in_run_one_cycle(self):
        """Test that AgentBehaviorWriter is imported and used in run_one_cycle"""
        with patch('core.agent_behavior_writer.AgentBehaviorWriter') as MockWriter, \
             patch('curious_agent.kg'), \
             patch('curious_agent.CuriosityEngine') as MockEngine, \
             patch('curious_agent.Explorer') as MockExplorer, \
             patch('core.meta_cognitive_monitor.MetaCognitiveMonitor'), \
             patch('core.meta_cognitive_controller.MetaCognitiveController') as MockController, \
             patch('curious_agent.LLMManager'), \
             patch('curious_agent.get_config'):
            
            # Setup mocks
            mock_engine = Mock()
            mock_engine.select_next.return_value = {
                "topic": "test_topic",
                "score": 8.0,
                "reason": "test"
            }
            MockEngine.return_value = mock_engine
            
            mock_explorer = Mock()
            mock_explorer.explore.return_value = {
                "topic": "test_topic",
                "findings": "test findings",
                "sources": ["http://example.com"]
            }
            MockExplorer.return_value = mock_explorer
            
            mock_controller = Mock()
            mock_controller.should_explore.return_value = (True, "")
            MockController.return_value = mock_controller
            
            mock_writer = Mock()
            mock_writer.process.return_value = {
                "applied": True,
                "section": "## 🧠 推理策略",
                "rule_generated": "test rule"
            }
            MockWriter.return_value = mock_writer
            
            # Import and run
            from curious_agent import run_one_cycle
            result = run_one_cycle(depth="medium")
            
            # Verify AgentBehaviorWriter was instantiated
            MockWriter.assert_called_once()
            
            # Verify process was called with quality >= 7.0
            mock_writer.process.assert_called_once()
            call_args = mock_writer.process.call_args
            assert call_args[0][0] == "test_topic"  # topic
            assert call_args[0][2] >= 7.0  # quality threshold

    def test_behavior_writer_not_called_for_low_quality(self):
        """Test that AgentBehaviorWriter is NOT called when quality < 7.0"""
        with patch('core.agent_behavior_writer.AgentBehaviorWriter') as MockWriter, \
             patch('curious_agent.kg'), \
             patch('curious_agent.CuriosityEngine') as MockEngine, \
             patch('curious_agent.Explorer') as MockExplorer, \
             patch('core.meta_cognitive_monitor.MetaCognitiveMonitor') as MockMonitor, \
             patch('core.meta_cognitive_controller.MetaCognitiveController') as MockController, \
             patch('curious_agent.LLMManager'), \
             patch('curious_agent.get_config'):
            
            # Setup mocks with low quality
            mock_engine = Mock()
            mock_engine.select_next.return_value = {
                "topic": "test_topic",
                "score": 5.0,
                "reason": "test"
            }
            MockEngine.return_value = mock_engine
            
            mock_explorer = Mock()
            mock_explorer.explore.return_value = {
                "topic": "test_topic",
                "findings": "test findings",
                "sources": ["http://example.com"]
            }
            MockExplorer.return_value = mock_explorer
            
            mock_controller = Mock()
            mock_controller.should_explore.return_value = (True, "")
            MockController.return_value = mock_controller
            
            mock_monitor = Mock()
            mock_monitor.assess_exploration_quality.return_value = 5.0  # Low quality
            MockMonitor.return_value = mock_monitor
            
            mock_writer = Mock()
            MockWriter.return_value = mock_writer
            
            # Import and run
            from curious_agent import run_one_cycle
            result = run_one_cycle(depth="medium")
            
            # Verify AgentBehaviorWriter was instantiated but process NOT called
            MockWriter.assert_called_once()
            mock_writer.process.assert_not_called()


class TestPhase2CompetenceTrackerIntegration:
    """Test Phase 2: CompetenceTracker integration into CuriosityEngine"""

    def test_competence_tracker_initialized_in_curiosity_engine(self):
        """Test that CompetenceTracker is initialized in CuriosityEngine.__init__"""
        with patch('core.curiosity_engine.kg') as MockKG, \
             patch('core.curiosity_engine.IntrinsicScorer'), \
             patch('core.competence_tracker.CompetenceTracker') as MockCompetence:
            
            mock_competence = Mock()
            MockCompetence.return_value = mock_competence
            
            MockKG.get_state.return_value = {"knowledge": {}, "exploration_log": []}
            
            # Import and create CuriosityEngine
            from core.curiosity_engine import CuriosityEngine
            engine = CuriosityEngine()
            
            # Verify CompetenceTracker was initialized
            MockCompetence.assert_called_once()
            assert hasattr(engine, 'competence_tracker')

    def test_select_next_uses_competence_tracker(self):
        """Test that select_next uses competence_tracker for scoring"""
        with patch('core.curiosity_engine.kg') as MockKG, \
             patch('core.curiosity_engine.IntrinsicScorer'), \
             patch('core.competence_tracker.CompetenceTracker') as MockCompetence:
            
            mock_competence = Mock()
            mock_competence.assess_competence.return_value = {
                "score": 0.3,
                "level": "novice"
            }
            MockCompetence.return_value = mock_competence
            
            MockKG.get_state.return_value = {"knowledge": {}, "exploration_log": []}
            MockKG.get_top_curiosities.return_value = [
                {"topic": "topic1", "score": 8.0, "relevance": 8.0},
                {"topic": "topic2", "score": 7.0, "relevance": 7.0}
            ]
            
            # Import and create CuriosityEngine
            from core.curiosity_engine import CuriosityEngine
            engine = CuriosityEngine()
            
            # Call select_next
            result = engine.select_next()
            
            # Verify competence_tracker.assess_competence was called
            mock_competence.assess_competence.assert_called()


class TestPhase2QualityV2Integration:
    """Test Phase 2: QualityV2 integration into MetaCognitiveMonitor"""

    def test_quality_v2_initialized_in_monitor(self):
        """Test that QualityV2Assessor is initialized in MetaCognitiveMonitor"""
        with patch('core.meta_cognitive_monitor.kg'), \
             patch('core.quality_v2.QualityV2Assessor') as MockQualityV2:
            
            mock_quality = Mock()
            MockQualityV2.return_value = mock_quality
            
            # Import and create MetaCognitiveMonitor
            from core.meta_cognitive_monitor import MetaCognitiveMonitor
            monitor = MetaCognitiveMonitor(llm_client=Mock())
            
            # Verify QualityV2Assessor was initialized
            MockQualityV2.assert_called_once()
            assert hasattr(monitor, 'quality_v2')

    def test_assess_quality_uses_quality_v2_first(self):
        """Test that assess_exploration_quality tries QualityV2 first"""
        with patch('core.meta_cognitive_monitor.kg') as MockKG, \
             patch('core.quality_v2.QualityV2Assessor') as MockQualityV2:
            
            mock_quality_v2 = Mock()
            mock_quality_v2.assess_quality.return_value = 8.5
            MockQualityV2.return_value = mock_quality_v2
            
            MockKG.get_topic_keywords.return_value = []
            MockKG.get_topic_depth.return_value = 5
            
            # Import and create MetaCognitiveMonitor
            from core.meta_cognitive_monitor import MetaCognitiveMonitor
            monitor = MetaCognitiveMonitor(llm_client=Mock())
            
            # Call assess_exploration_quality
            findings = {"summary": "test summary"}
            quality = monitor.assess_exploration_quality("test_topic", findings)
            
            # Verify QualityV2.assess_quality was called
            mock_quality_v2.assess_quality.assert_called_once()
            assert quality == 8.5


class TestPhase2ThreePhaseExplorerIntegration:
    """Test Phase 2: ThreePhaseExplorer integration into curious_agent.py"""

    def test_three_phase_explorer_used_for_high_score_topics(self):
        """Test that ThreePhaseExplorer is used for score >= 5.0 topics"""
        with patch('curious_agent.kg'), \
             patch('curious_agent.CuriosityEngine') as MockEngine, \
             patch('curious_agent.Explorer') as MockExplorer, \
             patch('core.meta_cognitive_monitor.MetaCognitiveMonitor') as MockMonitor, \
             patch('core.meta_cognitive_controller.MetaCognitiveController') as MockController, \
             patch('curious_agent.LLMManager'), \
             patch('curious_agent.get_config'), \
             patch('core.three_phase_explorer.ThreePhaseExplorer') as MockThreePhase:
            
            # Setup mocks with high score
            mock_engine = Mock()
            mock_engine.select_next.return_value = {
                "topic": "test_topic",
                "score": 8.0,  # High score
                "reason": "test"
            }
            MockEngine.return_value = mock_engine
            
            mock_three_phase = Mock()
            mock_three_phase.explore.return_value = {
                "status": "success",
                "findings": {
                    "findings": "test findings",
                    "sources": ["http://example.com"],
                    "papers": []
                }
            }
            MockThreePhase.return_value = mock_three_phase
            
            mock_controller = Mock()
            mock_controller.should_explore.return_value = (True, "")
            MockController.return_value = mock_controller
            
            mock_monitor = Mock()
            mock_monitor.assess_exploration_quality.return_value = 8.0
            MockMonitor.return_value = mock_monitor
            
            # Import and run
            from curious_agent import run_one_cycle
            result = run_one_cycle(depth="medium")
            
            # Verify ThreePhaseExplorer was instantiated and used
            MockThreePhase.assert_called_once()
            mock_three_phase.explore.assert_called_once()

    def test_three_phase_explorer_not_used_for_low_score_topics(self):
        """Test that ThreePhaseExplorer is NOT used for score < 5.0 topics"""
        with patch('curious_agent.kg'), \
             patch('curious_agent.CuriosityEngine') as MockEngine, \
             patch('curious_agent.Explorer') as MockExplorer, \
             patch('core.meta_cognitive_monitor.MetaCognitiveMonitor') as MockMonitor, \
             patch('core.meta_cognitive_controller.MetaCognitiveController') as MockController, \
             patch('curious_agent.LLMManager'), \
             patch('curious_agent.get_config'), \
             patch('core.three_phase_explorer.ThreePhaseExplorer') as MockThreePhase:
            
            # Setup mocks with low score
            mock_engine = Mock()
            mock_engine.select_next.return_value = {
                "topic": "test_topic",
                "score": 3.0,  # Low score
                "reason": "test"
            }
            MockEngine.return_value = mock_engine
            
            mock_explorer = Mock()
            mock_explorer.explore.return_value = {
                "topic": "test_topic",
                "findings": "test findings",
                "sources": ["http://example.com"]
            }
            MockExplorer.return_value = mock_explorer
            
            mock_controller = Mock()
            mock_controller.should_explore.return_value = (True, "")
            MockController.return_value = mock_controller
            
            mock_monitor = Mock()
            mock_monitor.assess_exploration_quality.return_value = 6.0
            MockMonitor.return_value = mock_monitor
            
            # Import and run
            from curious_agent import run_one_cycle
            result = run_one_cycle(depth="medium")
            
            # Verify ThreePhaseExplorer was NOT used
            MockThreePhase.assert_not_called()
            # But regular Explorer was used
            mock_explorer.explore.assert_called_once()


class TestPhase3DecomposerIntegration:
    """Test Phase 3: CuriosityDecomposer integration into curious_agent.py"""

    def test_decomposer_initialized_in_run_one_cycle(self):
        """Test that CuriosityDecomposer is initialized in run_one_cycle"""
        with patch('curious_agent.kg'), \
             patch('curious_agent.CuriosityEngine') as MockEngine, \
             patch('curious_agent.Explorer'), \
             patch('core.meta_cognitive_monitor.MetaCognitiveMonitor'), \
             patch('core.meta_cognitive_controller.MetaCognitiveController') as MockController, \
             patch('curious_agent.LLMManager'), \
             patch('curious_agent.get_config'), \
             patch('curious_agent.init_default_providers'), \
             patch('core.curiosity_decomposer.CuriosityDecomposer') as MockDecomposer:
            
            # Setup mocks
            mock_engine = Mock()
            mock_engine.select_next.return_value = {
                "topic": "test_topic",
                "score": 8.0,
                "reason": "test"
            }
            MockEngine.return_value = mock_engine
            
            mock_decomposer = Mock()
            mock_decomposer.decompose.return_value = []
            MockDecomposer.return_value = mock_decomposer
            
            mock_controller = Mock()
            mock_controller.should_explore.return_value = (True, "")
            MockController.return_value = mock_controller
            
            # Import and run
            from curious_agent import run_one_cycle
            result = run_one_cycle(depth="medium")
            
            # Verify CuriosityDecomposer was instantiated
            MockDecomposer.assert_called_once()

    def test_decomposer_decompose_is_called(self):
        """Test that decomposer.decompose is called in run_one_cycle"""
        import asyncio
        
        with patch('curious_agent.kg'), \
             patch('curious_agent.CuriosityEngine') as MockEngine, \
             patch('curious_agent.Explorer'), \
             patch('core.meta_cognitive_monitor.MetaCognitiveMonitor'), \
             patch('core.meta_cognitive_controller.MetaCognitiveController') as MockController, \
             patch('curious_agent.LLMManager'), \
             patch('curious_agent.get_config'), \
             patch('curious_agent.init_default_providers'), \
             patch('core.curiosity_decomposer.CuriosityDecomposer') as MockDecomposer:
            
            # Setup mocks
            mock_engine = Mock()
            mock_engine.select_next.return_value = {
                "topic": "test_topic",
                "score": 8.0,
                "reason": "test"
            }
            MockEngine.return_value = mock_engine
            
            mock_decomposer = Mock()
            mock_decomposer.decompose = Mock(return_value=asyncio.Future())
            mock_decomposer.decompose.return_value.set_result([])
            MockDecomposer.return_value = mock_decomposer
            
            mock_controller = Mock()
            mock_controller.should_explore.return_value = (True, "")
            MockController.return_value = mock_controller
            
            # Import and run
            from curious_agent import run_one_cycle
            result = run_one_cycle(depth="medium")
            
            # Verify decompose was called
            mock_decomposer.decompose.assert_called_once()


class TestEndToEndIntegration:
    """End-to-end integration tests for complete workflow"""

    def test_full_workflow_with_all_phases(self):
        """Test complete workflow with all Phase 1/2/3 modules integrated"""
        import asyncio
        
        with patch('curious_agent.kg') as MockKG, \
             patch('curious_agent.CuriosityEngine') as MockEngine, \
             patch('curious_agent.Explorer') as MockExplorer, \
             patch('core.meta_cognitive_monitor.MetaCognitiveMonitor') as MockMonitor, \
             patch('core.meta_cognitive_controller.MetaCognitiveController') as MockController, \
             patch('curious_agent.LLMManager'), \
             patch('curious_agent.get_config'), \
             patch('curious_agent.init_default_providers'), \
             patch('core.curiosity_decomposer.CuriosityDecomposer') as MockDecomposer, \
             patch('core.three_phase_explorer.ThreePhaseExplorer') as MockThreePhase, \
             patch('core.agent_behavior_writer.AgentBehaviorWriter') as MockWriter:
            
            # Setup full workflow mocks
            mock_engine = Mock()
            mock_engine.select_next.return_value = {
                "topic": "AI reasoning",
                "score": 8.5,
                "relevance": 9.0,
                "reason": "High interest"
            }
            MockEngine.return_value = mock_engine
            
            # Phase 3: Decomposer
            mock_decomposer = Mock()
            mock_decomposer.decompose = Mock(return_value=asyncio.Future())
            mock_decomposer.decompose.return_value.set_result([
                {"sub_topic": "chain-of-thought", "total_count": 100}
            ])
            MockDecomposer.return_value = mock_decomposer
            
            # Phase 2: ThreePhaseExplorer
            mock_three_phase = Mock()
            mock_three_phase.explore.return_value = {
                "status": "success",
                "findings": {
                    "findings": "Chain-of-thought improves reasoning by 23%",
                    "sources": ["http://arxiv.org/abs/1234"],
                    "papers": []
                },
                "verification_score": 0.85
            }
            MockThreePhase.return_value = mock_three_phase
            
            mock_controller = Mock()
            mock_controller.should_explore.return_value = (True, "")
            mock_controller.should_continue.return_value = (False, "Max count reached")
            MockController.return_value = mock_controller
            
            mock_monitor = Mock()
            mock_monitor.assess_exploration_quality.return_value = 8.5  # High quality
            mock_monitor.compute_marginal_return.return_value = 0.75
            MockMonitor.return_value = mock_monitor
            
            # Phase 1: BehaviorWriter
            mock_writer = Mock()
            mock_writer.process.return_value = {
                "applied": True,
                "section": "## 🧠 推理策略",
                "rule_generated": "Use chain-of-thought for complex reasoning"
            }
            MockWriter.return_value = mock_writer
            
            MockKG.get_state.return_value = {
                "exploration_log": [],
                "knowledge": {"topics": {}}
            }
            
            # Run full workflow
            from curious_agent import run_one_cycle
            result = run_one_cycle(depth="deep")
            
            # Verify all phases were used
            assert result["status"] == "success"
            assert result["quality"] == 8.5
            
            # Phase 3: Decomposer was used
            MockDecomposer.assert_called_once()
            mock_decomposer.decompose.assert_called_once()
            
            # Phase 2: ThreePhaseExplorer was used (score >= 5.0)
            MockThreePhase.assert_called_once()
            mock_three_phase.explore.assert_called_once()
            
            # Phase 1: BehaviorWriter was used (quality >= 7.0)
            MockWriter.assert_called_once()
            mock_writer.process.assert_called_once()
            
            # Verify the topic was marked as done
            MockKG.mark_topic_done.assert_called()

    def test_integration_handles_all_status_types(self):
        """Test that integration handles all return status types correctly"""
        test_cases = [
            ("idle", {"status": "idle", "message": "No pending"}),
            ("blocked", {"status": "blocked", "topic": "test", "reason": "Blocked"}),
            ("clarification_needed", {"status": "clarification_needed", "topic": "test", "reason": "Need clarification"}),
            ("success", {"status": "success", "topic": "test", "quality": 8.0})
        ]
        
        for status_name, expected_result in test_cases:
            with patch('curious_agent.kg'), \
                 patch('curious_agent.CuriosityEngine') as MockEngine, \
                 patch('core.meta_cognitive_controller.MetaCognitiveController') as MockController:
                
                mock_engine = Mock()
                if status_name == "idle":
                    mock_engine.select_next.return_value = None
                else:
                    mock_engine.select_next.return_value = {
                        "topic": "test",
                        "score": 5.0,
                        "reason": "test"
                    }
                MockEngine.return_value = mock_engine
                
                mock_controller = Mock()
                if status_name == "blocked":
                    mock_controller.should_explore.return_value = (False, "Blocked")
                else:
                    mock_controller.should_explore.return_value = (True, "")
                MockController.return_value = mock_controller
                
                from curious_agent import run_one_cycle
                
                try:
                    result = run_one_cycle(depth="medium")
                    assert result["status"] == expected_result["status"], f"Failed for status: {status_name}"
                except Exception as e:
                    pytest.fail(f"Integration failed for status {status_name}: {e}")


class TestIntegrationRegressionPrevention:
    """Regression tests to prevent 'implemented but not integrated' issues"""

    def test_all_phase2_modules_are_imported_in_main(self):
        """Verify that Phase 2 modules are actually imported in main files"""
        # Check curious_agent.py imports
        with open('curious_agent.py', 'r') as f:
            content = f.read()
            assert 'from core.three_phase_explorer import' in content or 'import ThreePhaseExplorer' in content, \
                "ThreePhaseExplorer not imported in curious_agent.py"
        
        # Check meta_cognitive_monitor.py imports
        with open('core/meta_cognitive_monitor.py', 'r') as f:
            content = f.read()
            assert 'from .quality_v2 import' in content or 'import QualityV2' in content, \
                "QualityV2 not imported in meta_cognitive_monitor.py"
        
        # Check curiosity_engine.py imports
        with open('core/curiosity_engine.py', 'r') as f:
            content = f.read()
            assert 'from .competence_tracker import' in content or 'import CompetenceTracker' in content, \
                "CompetenceTracker not imported in curiosity_engine.py"

    def test_all_phase2_modules_are_used_in_methods(self):
        """Verify that Phase 2 modules are actually used (not just imported)"""
        # Check CuriosityEngine.select_next uses competence_tracker
        with open('core/curiosity_engine.py', 'r') as f:
            content = f.read()
            assert 'competence_tracker.assess_competence' in content, \
                "competence_tracker.assess_competence not used in select_next"
        
        # Check MetaCognitiveMonitor uses quality_v2
        with open('core/meta_cognitive_monitor.py', 'r') as f:
            content = f.read()
            assert 'quality_v2.assess_quality' in content, \
                "quality_v2.assess_quality not used in assess_exploration_quality"
        
        # Check curious_agent uses ThreePhaseExplorer
        with open('curious_agent.py', 'r') as f:
            content = f.read()
            assert 'ThreePhaseExplorer' in content and 'three_phase.explore' in content, \
                "ThreePhaseExplorer not used in run_one_cycle"

    def test_no_orphaned_phase_modules(self):
        """Test that no Phase modules are orphaned (imported but never instantiated/used)"""
        import ast
        import inspect
        
        # Parse curious_agent.py
        with open('curious_agent.py', 'r') as f:
            tree = ast.parse(f.read())
        
        # Find all class instantiations
        instantiations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    instantiations.append(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    instantiations.append(node.func.attr)
        
        # Verify ThreePhaseExplorer is instantiated
        assert 'ThreePhaseExplorer' in instantiations, \
            "ThreePhaseExplorer is imported but never instantiated in curious_agent.py"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
