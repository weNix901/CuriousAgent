"""
Complete API endpoint tests for Curious Agent
Tests all API endpoints with full parameter coverage
"""
import pytest
import sys
import os
import json
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from curious_api import app


@pytest.fixture
def client():
    """Create test client with isolated state"""
    app.config['TESTING'] = True
    
    # Create temporary state file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        initial_state = {
            "version": "1.0",
            "last_update": None,
            "knowledge": {"topics": {}},
            "curiosity_queue": [],
            "exploration_log": [],
            "config": {
                "curiosity_top_k": 3,
                "max_knowledge_nodes": 100,
                "notification_threshold": 7.0
            }
        }
        json.dump(initial_state, f)
        temp_state = f.name
    
    # Patch state file location
    from core import knowledge_graph as kg
    original_state_file = kg.STATE_FILE
    kg.STATE_FILE = temp_state
    
    with app.test_client() as client:
        yield client
    
    # Cleanup
    kg.STATE_FILE = original_state_file
    if os.path.exists(temp_state):
        os.unlink(temp_state)


class TestAPIState:
    """Test suite for /api/curious/state endpoint"""
    
    def test_state_returns_ok_status(self, client):
        """Test state endpoint returns ok status"""
        response = client.get('/api/curious/state')
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'ok'
    
    def test_state_returns_knowledge_structure(self, client):
        """Test state returns knowledge with topics"""
        response = client.get('/api/curious/state')
        data = response.get_json()
        
        assert 'knowledge' in data
        assert 'topics' in data['knowledge']
        assert isinstance(data['knowledge']['topics'], dict)
    
    def test_state_returns_curiosity_queue_array(self, client):
        """Test state returns curiosity_queue as array (not just count)"""
        response = client.get('/api/curious/state')
        data = response.get_json()
        
        assert 'curiosity_queue' in data
        assert isinstance(data['curiosity_queue'], list)
    
    def test_state_returns_exploration_log_array(self, client):
        """Test state returns exploration_log as array (not just count)"""
        response = client.get('/api/curious/state')
        data = response.get_json()
        
        assert 'exploration_log' in data
        assert isinstance(data['exploration_log'], list)
    
    def test_state_returns_last_update(self, client):
        """Test state returns last_update field"""
        response = client.get('/api/curious/state')
        data = response.get_json()
        
        assert 'last_update' in data
    
    def test_state_returns_complete_queue_items(self, client):
        """Test state returns complete queue item structure"""
        # First inject an item
        client.post('/api/curious/inject',
                   json={"topic": "test", "reason": "test"})
        
        response = client.get('/api/curious/state')
        data = response.get_json()
        
        queue = data.get('curiosity_queue', [])
        assert len(queue) > 0
        
        item = queue[0]
        required_fields = ['topic', 'score', 'reason', 'status', 'created_at']
        for field in required_fields:
            assert field in item, f"Missing field: {field}"
    
    def test_state_returns_complete_log_items(self, client):
        """Test state returns complete log item structure"""
        # Add a log entry directly
        from core import knowledge_graph as kg
        kg.log_exploration("test", "action", "findings", notified=True)
        
        response = client.get('/api/curious/state')
        data = response.get_json()
        
        logs = data.get('exploration_log', [])
        assert len(logs) > 0
        
        item = logs[0]
        required_fields = ['timestamp', 'topic', 'action', 'findings', 'notified_user']
        for field in required_fields:
            assert field in item, f"Missing field: {field}"
    
    def test_state_returns_knowledge_summary(self, client):
        """Test state returns knowledge summary stats"""
        response = client.get('/api/curious/state')
        data = response.get_json()
        
        knowledge = data.get('knowledge', {})
        summary_fields = ['total_topics', 'known_count', 'pending_curiosities', 'recent_explorations']
        for field in summary_fields:
            assert field in knowledge, f"Missing summary field: {field}"


class TestAPIInject:
    """Test suite for /api/curious/inject endpoint"""
    
    def test_inject_basic(self, client):
        """Test basic inject with topic"""
        response = client.post('/api/curious/inject',
                              json={"topic": "test topic", "reason": "test"})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'ok'
        assert data['topic'] == 'test topic'
    
    def test_inject_requires_topic(self, client):
        """Test inject requires topic"""
        response = client.post('/api/curious/inject',
                              json={"reason": "test"})
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
    
    def test_inject_rejects_empty_topic(self, client):
        """Test inject rejects empty topic"""
        response = client.post('/api/curious/inject',
                              json={"topic": "", "reason": "test"})
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
    
    def test_inject_with_alpha_parameter(self, client):
        """Test inject with alpha parameter (v0.2.1 feature)"""
        response = client.post('/api/curious/inject',
                              json={
                                  "topic": "test alpha",
                                  "reason": "test",
                                  "alpha": 0.7
                              })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['alpha'] == 0.7
    
    def test_inject_with_mode_fusion(self, client):
        """Test inject with mode=fusion"""
        response = client.post('/api/curious/inject',
                              json={
                                  "topic": "test fusion",
                                  "mode": "fusion",
                                  "alpha": 0.5
                              })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['mode'] == 'fusion'
        assert 'score' in data
    
    def test_inject_with_mode_intrinsic(self, client):
        """Test inject with mode=intrinsic"""
        response = client.post('/api/curious/inject',
                              json={
                                  "topic": "test intrinsic",
                                  "mode": "intrinsic"
                              })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['mode'] == 'intrinsic'
        assert 'score' in data
    
    def test_inject_default_alpha_is_0_5(self, client):
        """Test inject default alpha is 0.5"""
        response = client.post('/api/curious/inject',
                              json={"topic": "test default"})
        
        data = response.get_json()
        assert data['alpha'] == 0.5
    
    def test_inject_default_mode_is_fusion(self, client):
        """Test inject default mode is fusion"""
        response = client.post('/api/curious/inject',
                              json={"topic": "test default mode"})
        
        data = response.get_json()
        assert data['mode'] == 'fusion'
    
    def test_inject_with_relevance_and_depth(self, client):
        """Test inject with relevance and depth parameters"""
        response = client.post('/api/curious/inject',
                              json={
                                  "topic": "test params",
                                  "relevance": 8.5,
                                  "depth": 7.0
                              })
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'score' in data
    
    def test_inject_trims_whitespace_topic(self, client):
        """Test inject trims whitespace from topic"""
        response = client.post('/api/curious/inject',
                              json={"topic": "  test trim  ", "reason": "test"})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['topic'] == "test trim"


class TestAPIQueueDelete:
    """Test suite for /api/curious/queue DELETE endpoint"""
    
    def test_delete_queue_item_success(self, client):
        """Test deleting a queue item"""
        # First inject an item
        client.post('/api/curious/inject',
                   json={"topic": "to-delete", "reason": "test"})
        
        # Then delete it
        response = client.delete('/api/curious/queue?topic=to-delete')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert data['deleted'] is True
    
    def test_delete_requires_topic(self, client):
        """Test delete requires topic parameter"""
        response = client.delete('/api/curious/queue')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
    
    def test_delete_not_found_topic(self, client):
        """Test deleting non-existent topic"""
        response = client.delete('/api/curious/queue?topic=non-existent')
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'
    
    def test_delete_with_force(self, client):
        """Test force delete (ignore status)"""
        # Inject and mark as done
        client.post('/api/curious/inject',
                   json={"topic": "force-delete", "reason": "test"})
        
        from core import knowledge_graph as kg
        kg.update_curiosity_status("force-delete", "done")
        
        # Try delete without force (should fail)
        response = client.delete('/api/curious/queue?topic=force-delete')
        assert response.status_code == 400  # Cannot delete done item
        
        # Try delete with force (should succeed)
        response = client.delete('/api/curious/queue?topic=force-delete&force=true')
        assert response.status_code == 200
        data = response.get_json()
        assert data['deleted'] is True


class TestAPIQueuePending:
    """Test suite for /api/curious/queue/pending endpoint"""
    
    def test_list_pending_empty(self, client):
        """Test listing pending when queue is empty"""
        response = client.get('/api/curious/queue/pending')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert data['count'] == 0
        assert data['items'] == []
    
    def test_list_pending_with_items(self, client):
        """Test listing pending with items"""
        # Inject some items
        client.post('/api/curious/inject',
                   json={"topic": "pending-1", "reason": "test"})
        client.post('/api/curious/inject',
                   json={"topic": "pending-2", "reason": "test"})
        
        response = client.get('/api/curious/queue/pending')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['count'] == 2
        assert len(data['items']) == 2
    
    def test_list_pending_excludes_done_items(self, client):
        """Test listing pending excludes done items"""
        # Inject item
        client.post('/api/curious/inject',
                   json={"topic": "pending-vs-done", "reason": "test"})
        
        # Mark as done
        from core import knowledge_graph as kg
        kg.update_curiosity_status("pending-vs-done", "done")
        
        response = client.get('/api/curious/queue/pending')
        data = response.get_json()
        
        assert data['count'] == 0
        done_items = [i for i in data['items'] if i.get('status') == 'done']
        assert len(done_items) == 0
    
    def test_list_pending_item_structure(self, client):
        """Test pending items have complete structure"""
        client.post('/api/curious/inject',
                   json={"topic": "structure-test", "reason": "test reason"})
        
        response = client.get('/api/curious/queue/pending')
        data = response.get_json()
        
        assert data['count'] > 0
        item = data['items'][0]
        
        required_fields = ['topic', 'score', 'reason', 'status', 'created_at']
        for field in required_fields:
            assert field in item, f"Missing field: {field}"


class TestAPIRun:
    """Test suite for /api/curious/run endpoint"""
    
    @patch('core.explorer.Explorer')
    @patch('core.curiosity_engine.CuriosityEngine')
    def test_run_exploration_success(self, MockEngine, MockExplorer, client):
        """Test running exploration successfully"""
        # Mock engine
        mock_engine = Mock()
        mock_engine.select_next.return_value = {
            "topic": "test",
            "score": 8.0,
            "reason": "test"
        }
        MockEngine.return_value = mock_engine
        
        # Mock explorer
        mock_explorer = Mock()
        mock_explorer.explore.return_value = {
            "topic": "test",
            "action": "test_action",
            "findings": "test findings",
            "sources": ["source1"],
            "notified": True,
            "score": 8.0
        }
        MockExplorer.return_value = mock_explorer
        
        response = client.post('/api/curious/run')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert data['topic'] == 'test'
    
    @patch('core.curiosity_engine.CuriosityEngine')
    def test_run_idle_when_queue_empty(self, MockEngine, client):
        """Test run returns idle when queue is empty"""
        mock_engine = Mock()
        mock_engine.select_next.return_value = None
        MockEngine.return_value = mock_engine
        
        response = client.post('/api/curious/run')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'idle'


class TestAPIContract:
    """Test API contract - data format compatibility"""
    
    def test_state_contract_matches_frontend_expectations(self, client):
        """Critical test: state endpoint returns what frontend expects"""
        # This test ensures the bug we fixed doesn't regress
        response = client.get('/api/curious/state')
        data = response.get_json()
        
        # Frontend expects these exact keys
        required_keys = [
            'status',
            'knowledge',
            'curiosity_queue',
            'exploration_log',
            'last_update'
        ]
        
        for key in required_keys:
            assert key in data, f"Frontend expects '{key}' in state response"
        
        # Verify types
        assert isinstance(data['curiosity_queue'], list), \
            "curiosity_queue must be an array (not just count)"
        assert isinstance(data['exploration_log'], list), \
            "exploration_log must be an array (not just count)"
    
    def test_inject_response_includes_score_and_alpha(self, client):
        """Test inject response includes all expected fields"""
        response = client.post('/api/curious/inject',
                              json={"topic": "contract-test", "alpha": 0.7})
        data = response.get_json()
        
        assert 'status' in data
        assert 'topic' in data
        assert 'score' in data
        assert 'alpha' in data
        assert 'mode' in data
    
    def test_error_response_format(self, client):
        """Test error responses have consistent format"""
        response = client.post('/api/curious/inject',
                               json={})  # Missing topic
        data = response.get_json()

        assert 'error' in data
        assert isinstance(data['error'], str)


class TestAPIAgentBehaviorWriterIntegration:
    """Regression tests for Bug #15: API AgentBehaviorWriter integration"""

    @patch('core.agent_behavior_writer.AgentBehaviorWriter')
    @patch('core.meta_cognitive_monitor.MetaCognitiveMonitor')
    @patch('core.explorer.Explorer')
    @patch('core.curiosity_engine.CuriosityEngine')
    def test_api_run_triggers_behavior_writer_on_high_quality(
        self, mock_engine_class, mock_explorer_class, mock_monitor_class, mock_writer_class, client
    ):
        """Regression test: API /run should trigger AgentBehaviorWriter when quality >= 7.0"""
        mock_engine = Mock()
        mock_engine.score_topic.return_value = {'final_score': 8.5}
        mock_engine_class.return_value = mock_engine

        mock_explorer = Mock()
        mock_explorer.explore.return_value = {
            'topic': 'test-topic',
            'action': 'exploration',
            'score': 8.5,
            'findings': 'Test findings',
            'notified': False,
            'sources': ['http://example.com']
        }
        mock_explorer_class.return_value = mock_explorer

        mock_monitor = Mock()
        mock_monitor.assess_exploration_quality.return_value = 8.5
        mock_monitor_class.return_value = mock_monitor

        mock_writer = Mock()
        mock_writer.process.return_value = {'applied': True}
        mock_writer_class.return_value = mock_writer

        response = client.post('/api/curious/run',
                               json={'topic': 'test-topic', 'depth': 'medium'})

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        mock_writer_class.assert_called_once()
        mock_writer.process.assert_called_once()
        call_args = mock_writer.process.call_args
        assert call_args[0][0] == 'test-topic'
        assert call_args[0][2] == 8.5

    @patch('core.agent_behavior_writer.AgentBehaviorWriter')
    @patch('core.meta_cognitive_monitor.MetaCognitiveMonitor')
    @patch('core.explorer.Explorer')
    @patch('core.curiosity_engine.CuriosityEngine')
    def test_api_run_skips_behavior_writer_on_low_quality(
        self, mock_engine_class, mock_explorer_class, mock_monitor_class, mock_writer_class, client
    ):
        """Regression test: API /run should NOT trigger AgentBehaviorWriter when quality < 7.0"""
        mock_engine = Mock()
        mock_engine.score_topic.return_value = {'final_score': 5.0}
        mock_engine_class.return_value = mock_engine

        mock_explorer = Mock()
        mock_explorer.explore.return_value = {
            'topic': 'test-topic',
            'action': 'exploration',
            'score': 5.0,
            'findings': 'Test findings',
            'notified': False,
            'sources': []
        }
        mock_explorer_class.return_value = mock_explorer

        mock_monitor = Mock()
        mock_monitor.assess_exploration_quality.return_value = 5.5
        mock_monitor_class.return_value = mock_monitor

        mock_writer = Mock()
        mock_writer_class.return_value = mock_writer

        response = client.post('/api/curious/run',
                               json={'topic': 'test-topic', 'depth': 'medium'})

        assert response.status_code == 200
        mock_writer.process.assert_not_called()

    @patch('core.meta_cognitive_monitor.MetaCognitiveMonitor')
    @patch('core.explorer.Explorer')
    @patch('core.curiosity_engine.CuriosityEngine')
    def test_api_run_records_exploration_quality(
        self, mock_engine_class, mock_explorer_class, mock_monitor_class, client
    ):
        """Regression test: API /run should record exploration quality via monitor.record_exploration"""
        mock_engine = Mock()
        mock_engine.score_topic.return_value = {'final_score': 8.0}
        mock_engine_class.return_value = mock_engine

        mock_explorer = Mock()
        mock_explorer.explore.return_value = {
            'topic': 'test-topic',
            'action': 'exploration',
            'score': 8.0,
            'findings': 'Test findings',
            'notified': False,
            'sources': []
        }
        mock_explorer_class.return_value = mock_explorer

        mock_monitor = Mock()
        mock_monitor.assess_exploration_quality.return_value = 7.5
        mock_monitor_class.return_value = mock_monitor

        response = client.post('/api/curious/run',
                               json={'topic': 'test-topic', 'depth': 'medium'})

        mock_monitor.record_exploration.assert_called_once()
        call_args = mock_monitor.record_exploration.call_args
        assert call_args[0][0] == 'test-topic'
        assert call_args[0][1] == 7.5

    @patch('core.agent_behavior_writer.AgentBehaviorWriter')
    @patch('core.meta_cognitive_monitor.MetaCognitiveMonitor')
    @patch('core.explorer.Explorer')
    @patch('core.curiosity_engine.CuriosityEngine')
    def test_api_run_quality_assessment_called_with_correct_findings(
        self, mock_engine_class, mock_explorer_class, mock_monitor_class, mock_writer_class, client
    ):
        """Regression test: API /run should assess quality with proper findings structure"""
        mock_engine = Mock()
        mock_engine.score_topic.return_value = {'final_score': 8.0}
        mock_engine_class.return_value = mock_engine

        mock_explorer = Mock()
        mock_explorer.explore.return_value = {
            'topic': 'test-topic',
            'action': 'exploration',
            'score': 8.0,
            'findings': 'Detailed findings text',
            'notified': False,
            'sources': ['http://source1.com', 'http://source2.com'],
            'papers': [{'title': 'Paper 1'}]
        }
        mock_explorer_class.return_value = mock_explorer

        mock_monitor = Mock()
        mock_monitor.assess_exploration_quality.return_value = 7.8
        mock_monitor_class.return_value = mock_monitor

        mock_writer = Mock()
        mock_writer_class.return_value = mock_writer

        response = client.post('/api/curious/run',
                               json={'topic': 'test-topic', 'depth': 'medium'})

        mock_monitor.assess_exploration_quality.assert_called_once()
        call_args = mock_monitor.assess_exploration_quality.call_args
        assert call_args[0][0] == 'test-topic'
        findings = call_args[0][1]
        assert 'summary' in findings
        assert 'sources' in findings
        assert 'papers' in findings
        assert findings['summary'] == 'Detailed findings text'
        assert len(findings['sources']) == 2
