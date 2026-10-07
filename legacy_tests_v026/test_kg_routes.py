"""KG meta-cognition + dream-insight API routes (v0.3.6 baseline).

设计依据 : docs/plan/next_move_v0.3.6.md  批0d（路由与 CA2.0 目标对齐）
CA2.0 对位: C3 发现回流 / C2 缺口生成 / C1 自省质量 / C1-C 外部置信度注入

版本沿革
--------
v0.2.6 (e09fcbe)      本文件首次落地，覆盖当时全部端点。
v0.2.x                 /api/kg/overview 重构中，6 条路由被 09d6b37 删除，
                      测试成为"陈旧测试"（7 failed）。
v0.3.5 (fd56b6b)      恢复 /api/kg/confidence/<topic>（C1-C 单一化重构）。
                      → 该路由不再属于"缺失"，对应测试转为 passed。
v0.3.6 (本版)         按 CA2.0 高阶设计重新取舍：
  · 保留并转绿: dream_insights×2 (C3), frontier (C2), calibration (C1)
  · 删除不对位: TestDormantNodesAPI / TestReactivateAPI
    —— CA2.0 §4.1-4.3 无 dormant 列表需求；reactivate 宜并入 C2-D。
  · 新增校准空数据断言: calibration 在无预测样本时不得报 well_calibrated。
  · confidence: 路由已存在（勿重复注册，否则 Flask 双注册崩溃）。

注意：本文件中每个 class 的首行注释标注其 CA2.0 对位条目。
"""
import pytest
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from curious_api import app


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestDreamInsightsAPI:
    """Dream insights endpoints（v0.3.6 保留）。

    CA2.0 对位: C3 发现回流 + §2.3.4 F8-c（散落 JSON 归并）。
    DreamAgent 洞察是待回流的发现原料；本期恢复路由，归并 Neo4j 留待后续。
    """

    def test_api_dream_insights_returns_list(self, client):
        """Should return list of dream insights."""
        response = client.get('/api/kg/dream_insights')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'insights' in data
        assert isinstance(data['insights'], list)

    def test_api_dream_insights_topic_filters(self, client):
        """Should filter insights by topic."""
        response = client.get('/api/kg/dream_insights/test_topic')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'insights' in data


# ---------------------------------------------------------------------------
# TestDormantNodesAPI / TestReactivateAPI — 已于 v0.3.6 删除。
#
# 原因（docs/plan/next_move_v0.3.6.md §1.3.1）:
#   · /api/kg/dormant 对位缺失：CA2.0 §4.1-4.3 无"dormant 节点列表"需求；
#     底层 knowledge_graph_compat 仅有 mark_dormant（写），无查询能力。
#     属 v0.2.6 遗留端点。
#   · /api/kg/reactivate 与 C2-D（缺口去重闭环）弱相关，但本期无消费方，
#     宜并入 C2-D 一并设计，而非作为独立历史债恢复。
# 若将来 C2-D 落地需要，请在新版测试中重建（标注对应版本）。
# ---------------------------------------------------------------------------


class TestFrontierAPI:
    """Knowledge frontier endpoint（v0.3.6 保留）。

    CA2.0 对位: C2-A 缺口计算器上游数据源。
    detect_frontier() 返回 leaf nodes（已知但无子节点）+ uncertainty + quality，
    即"可探索边界"，是缺口价值公式 1 - quality/10 的天然输入。
    """

    def test_api_frontier_returns_frontiers(self, client):
        """Should return knowledge frontier."""
        response = client.get('/api/kg/frontier')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'frontiers' in data
        assert isinstance(data['frontiers'], list)


class TestCalibrationAPI:
    """Calibration endpoint（v0.3.6 保留 + 新增空数据断言）。

    CA2.0 对位: C1 自省质量 / 公理B（外部可验证判断）。
    实现修复: get_calibration_error() 在无预测样本时曾静默返回 0.0，
    而 Brier=0.0 本义是"完美校准" → 空数据被读成满分。恢复路由时
    必须区分 "no_data" 与 "well_calibrated"（R8 / 设计原则6 失败必须可见）。
    """

    def test_api_calibration_returns_error_and_verdict(self, client):
        """Should return calibration error and verdict."""
        response = client.get('/api/kg/calibration')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'calibration_error' in data
        assert 'verdict' in data
        assert data['verdict'] in [
            'well_calibrated', 'overconfident', 'moderate', 'no_data',
        ]

    def test_api_calibration_empty_history_is_not_well_calibrated(self, client):
        """空历史必须报 no_data，不得伪装成完美校准（v0.3.6 新增）。"""
        response = client.get('/api/kg/calibration')
        assert response.status_code == 200
        data = json.loads(response.data)
        # 无预测样本时 Brier=0.0，绝不能解读为 well_calibrated。
        if data.get('calibration_error') == 0.0:
            assert data['verdict'] == 'no_data'


class TestConfidenceAPI:
    """Confidence endpoint（v0.3.6 保留）。

    CA2.0 对位: C1-C 外部置信度注入 —— knowledge-gate hook 的调用目标。
    路由已于 v0.3.5 (fd56b6b) 恢复；本测试在 v0.3.5 起即为绿。
    警告: 该路由当前必须只注册一次；重复注册会致 Flask 启动 AssertionError，
    进而使 CA 无法启动、hook 全线 404（R6）。
    """

    def test_api_confidence_returns_interval(self, client):
        """Should return confidence interval for topic."""
        response = client.get('/api/kg/confidence/test_topic')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'topic' in data
        assert 'confidence_low' in data
        assert 'confidence_high' in data
        assert isinstance(data['confidence_low'], float)
        assert isinstance(data['confidence_high'], float)
