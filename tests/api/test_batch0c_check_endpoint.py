"""批0c 第一步 (v0.3.6): /api/knowledge/check 委托 check_confidence + Y 扩展契约.

问题（2026-10-03，只读勘察）:
    旧实现用 kg_factory.get_node_sync(topic) 精确匹配，且读恒为 0 的
    `confidence` 字段（实测全库 confidence>0 的节点数 = 0）。→ Hook 对任何
    非逐字同名的话题都拿 0%，永远注入 "No KG knowledge"。

修法（第一步，Python 端点）:
    /api/knowledge/check 内部改调 KnowledgeConfidenceHandler.check_confidence()
    （语义检索 + E1 门 + quality 调制 + 四态），响应体 Y 扩展：
      · 旧字段保留（Hook 零改）
      · 新字段追加（coverage 等四态，供第二步 Hook 消费）

离线测试（mock handler），不需 Neo4j。实盘行为另行 live curl 验证。

对应设计：docs/plan/next_move_v0.3.6.md 七之三（批0c）
对应 CA2.0 条目：C1-C（Hook 端到端）
"""
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def client():
    from curious_api import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _fake_check_confidence(ret):
    """Return a patch context that makes KnowledgeConfidenceHandler.check_confidence return `ret`."""
    inst = Mock()
    inst.check_confidence = Mock(return_value=ret)
    return patch(
        "core.api.host_agent_integration.KnowledgeConfidenceHandler",
        return_value=inst,
    )


def test_known_coverage_maps_to_old_contract(client):
    ret = {
        "confidence": 0.70, "level": "intermediate", "gaps": [],
        "coverage": "known", "coverage_reason": "ok",
        "matched_topic": "Retrieval-Augmented Generation (RAG) | Pinecone",
        "similarity": 0.756, "quality": 8.5, "source_count": 5,
    }
    with _fake_check_confidence(ret):
        r = client.post("/api/knowledge/check", json={"topic": "RAG"})
    assert r.status_code == 200
    d = r.get_json()["result"]
    # old fields preserved
    assert d["confidence"] == 0.70
    assert d["level"] == "intermediate"
    assert d["should_search"] is False
    assert d["should_inject"] is False
    # new four-state fields
    assert d["coverage"] == "known"
    assert d["matched_topic"].startswith("Retrieval-Augmented")


def test_unknown_coverage_maps_to_search_and_inject(client):
    ret = {"confidence": 0.0, "level": "novice",
           "gaps": ["Matched node carries no content"],
           "coverage": "unknown", "coverage_reason": "ghost",
           "matched_topic": None, "similarity": 0.0, "quality": 0.0,
           "source_count": 0}
    with _fake_check_confidence(ret):
        r = client.post("/api/knowledge/check", json={"topic": "知识图谱"})
    d = r.get_json()["result"]
    assert d["coverage"] == "unknown"
    assert d["should_search"] is True
    assert d["should_inject"] is True
    assert d["confidence"] == 0.0


def test_partial_coverage(client):
    ret = {"confidence": 0.175, "level": "beginner", "gaps": [],
           "coverage": "partial", "coverage_reason": "below bar",
           "matched_topic": "agent上下文管理系统", "similarity": 0.874,
           "quality": 0.0, "source_count": 0}
    with _fake_check_confidence(ret):
        r = client.post("/api/knowledge/check", json={"topic": "agent 上下文管理"})
    d = r.get_json()["result"]
    assert d["coverage"] == "partial"
    assert d["should_search"] is True


def test_void_coverage(client):
    ret = {"confidence": 0.0, "level": "novice", "gaps": [],
           "coverage": "void", "coverage_reason": "no node and prior failed",
           "matched_topic": None, "similarity": 0.0, "quality": 0.0,
           "source_count": 0}
    with _fake_check_confidence(ret):
        r = client.post("/api/knowledge/check", json={"topic": "never-worked"})
    d = r.get_json()["result"]
    assert d["coverage"] == "void"
    assert d["should_search"] is True
    assert "void" in d["guidance"]


def test_empty_topic_returns_400(client):
    r = client.post("/api/knowledge/check", json={"topic": "   "})
    assert r.status_code == 400


def test_legacy_fields_all_present(client):
    ret = {"confidence": 0.5, "level": "intermediate", "gaps": [],
           "coverage": "known", "coverage_reason": "", "matched_topic": "x",
           "similarity": 0.8, "quality": 5.0, "source_count": 2}
    with _fake_check_confidence(ret):
        r = client.post("/api/knowledge/check", json={"topic": "x"})
    d = r.get_json()["result"]
    for legacy in ("topic", "confidence", "level", "gaps", "guidance",
                   "should_search", "should_inject"):
        assert legacy in d, f"legacy field {legacy} missing"
