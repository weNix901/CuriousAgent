"""L4 契约测试：缺口订阅链路端到端护栏（2026-10-13）。

背景 / 为什么测副作用而不是测 HTTP 200
---------------------------------------
C2 死锁的真根因不是"端点 404"，而是"端点返回 200 但不写缺口"：
    hook → GET /api/kg/confidence/<topic>（200，无副作用）
    而写 gap 的副作用只挂在 POST /api/knowledge/check
    → 缺口表 8 天零新行（全程静默，无信号）
所以任何"只断言 status==200"的测试都抓不住这次事故。

本测试测的是**副作用**：
    调 hook 端点 → gaps 表新增/更新 real_seen=1 行
                → compute_from_store() 返回 value>0 的候选
这四步只要有一环接线断掉，测试就红。

同时锁死 L4 来源分类契约：
    hook 真名（knowledge-gate）计入 real_seen=1
    test/probe 打点不计入（real_seen 不增长）

设计纪律：用独立临时 DB，绝不污染 knowledge/ops.db。
"""
import os
import sys
import sqlite3
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from curious_api import app
from core.api import gap_store


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def temp_db(monkeypatch):
    """把 gap_store 的默认 DB 指向一个临时文件，测试后销毁。

    gap_store 内部所有函数都通过 `_get_conn(db_path=None)` → `_DEFAULT_DB`，
    故 patch 模块级 `_DEFAULT_DB` 即可全链路生效（record_gap / list_gaps /
    mark_consumed / reset_stale_consumed / compute_from_store）。
    """
    fd, path = tempfile.mkstemp(suffix=".db", prefix="gaps_contract_")
    os.close(fd)
    monkeypatch.setattr(gap_store, "_DEFAULT_DB", path)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def client(temp_db):
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _unknown_topic():
    """返回一个 KG 里无匹配的 topic（保证四态判为 unknown/void）。

    为什么必须无匹配：record_gap 只对 coverage∈{unknown,void} 落库。
    KG 存量大，几乎任何"看起来像话题"的字符串都会被 embedding 模糊匹配到某节点
    → coverage=partial → **正确地**不落库。测试若用这类 topic，会把"正确跳过"
    误判成"接线断掉"。故用随机 uuid 后缀，确保无匹配（unknown）。
    """
    import uuid
    return f"zz_gap_contract_{uuid.uuid4().hex}"


def _coverage_of(topic):
    """直接问 C1 该 topic 的覆盖态，用于前置断言测试前提成立。"""
    from core.api.host_agent_integration import KnowledgeConfidenceHandler
    return KnowledgeConfidenceHandler().check_confidence(topic).get("coverage")


def _row(db_path, topic):
    # 经 gap_store._get_conn 建连，确保 schema 已初始化（raw sqlite3.connect
    # 不会跑 _SCHEMA，空库首次访问会 no such table）。
    conn = gap_store._get_conn(db_path)
    try:
        r = conn.execute(
            "SELECT * FROM gaps WHERE topic = ?", (topic,)
        ).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 1. hook 端点 → 副作用落库（核心护栏）
# ---------------------------------------------------------------------------
class TestHookEndpointWritesGap:
    """调 hook 端点 = 缺口订阅必须真的发生（测副作用）。"""

    def test_hook_call_creates_gap_row_with_real_seen(self, client, temp_db):
        """GET /api/kg/confidence/<topic> 带 hook 头 → gaps 表新增 real_seen=1 行。"""
        topic = _unknown_topic()
        # 前置：确认该 topic 确实判为 unknown（否则断言前提不成立）
        assert _coverage_of(topic) in ("unknown", "void"), \
            "测试前提失效：随机 topic 竟被判为已知，松开前置会误报"
        assert _row(temp_db, topic) is None

        resp = client.get(
            f"/api/kg/confidence/{topic}",
            headers={"X-OpenClaw-Hook-Name": "knowledge-gate"},
        )
        assert resp.status_code == 200  # 不足以证明接线 — 只是前置

        row = _row(temp_db, topic)
        # ↓ 这才是真正抓住"接线断掉"的断言
        assert row is not None, "hook 端点未写 gaps 表 → 缺口订阅断线"
        assert row["real_seen"] == 1, (
            f"hook 真名应计入 real_seen=1，实际 {row['real_seen']} "
            f"(observed_by={row['observed_by']!r})"
        )
        assert row["observed_by"] == "knowledge-gate"
        assert row["consumed_at"] is None, "新缺口应为未消费(consumed_at IS NULL)"

    def test_hook_call_feeds_compute_from_store(self, client, temp_db):
        """hook 落库后 → compute_from_store 产出该 topic 的候选（满足闸门）。

        这是整条 C2 链路的终点断言：hook 观测 → 队列有燃料。

        ⚠️ 语义（2026-10-13 weNix 定）：**首次观测即应有燃料**。
        一次真实会话触发（real_seen>=1）即视相关性饱和（rel=1.0），
        故单次 hook 调用 → value = coverage_gap(0.80) × 1.0 = 0.80，
        过任何动态闸门（最高 0.70）。见 RELEVANCE_BOOTSTRAP_FLOOR。
        """
        from core.api.gap_calculator import compute_from_store, GapConfig

        cfg = GapConfig.resolve()
        topic = _unknown_topic()
        # 仅一次真实观测
        client.get(
            f"/api/kg/confidence/{topic}",
            headers={"X-OpenClaw-Hook-Name": "knowledge-gate"},
        )

        candidates = compute_from_store(only_unconsumed=True)
        hit = [c for c in candidates if getattr(c, "topic", None) == topic]
        assert hit, (
            "单次真实观测未产出候选 → 首次观测无燃料（违反 2026-10-13 需求）"
        )
        assert hit[0].value > 0, (
            f"候选 value={hit[0].value} 应 >0（首次观测 real_seen=1 → rel=1.0）"
        )

    def test_first_observation_passes_gate(self, client, temp_db):
        """首次观测即过闸门（weNix 2026-10-13）：一次触发 = 燃料。

        bootstrap 语义：real_seen>=1 → rel=1.0。
        对比：real_seen=0（无真实触发）→ rel=0 → 不入队（防无源噪声）。
        """
        from core.api.gap_calculator import compute_gap_value, GapConfig
        cfg = GapConfig.resolve()
        v1 = compute_gap_value(
            topic="t", status="unknown", quality=0.0, seen_count=1,
            relevance_saturation=cfg.relevance_saturation,
        ).value
        assert v1 >= cfg.gap_threshold, (
            f"首次观测 value={v1:.3f} 应 >= 闸门 {cfg.gap_threshold}（首次即有燃料）"
        )
        v0 = compute_gap_value(
            topic="t", status="unknown", quality=0.0, seen_count=0,
            relevance_saturation=cfg.relevance_saturation,
        ).value
        assert v0 == 0.0, "无真实触发(real_seen=0) → rel=0 → 不入队"


# ---------------------------------------------------------------------------
# 2. 来源分类契约（L4）
# ---------------------------------------------------------------------------
class TestRealSourceClassification:
    """非 test/probe/unknown 的观测来源计入 real_seen；test/probe 不计入。"""

    def test_test_source_excluded_from_real_seen(self, client, temp_db):
        topic = _unknown_topic()
        client.get(
            f"/api/kg/confidence/{topic}",
            headers={"X-OpenClaw-Hook-Name": "knowledge-gate"},
        )
        before = _row(temp_db, topic)
        assert before is not None and before["real_seen"] == 1

        # 再打一次 test 来源 → real_seen 不应增长
        client.get(f"/api/kg/confidence/{topic}?observed_by=test")
        after = _row(temp_db, topic)
        assert after["real_seen"] == 1, (
            f"test 打点不应计入 real_seen，仍应为 1，实际 {after['real_seen']}"
        )

    def test_unit_is_real_source_helper(self):
        """_is_real_source 排除法单元契约。"""
        f = gap_store._is_real_source
        assert f("knowledge-gate") == 1
        assert f("user") == 1
        assert f("hook") == 1
        assert f("anything-real") == 1
        assert f("test") == 0
        assert f("TEST") == 0
        assert f("probe") == 0
        assert f("unknown") == 0
        assert f("") == 0
        assert f(None) == 0


# ---------------------------------------------------------------------------
# 3. 消费真源契约（L2）：consumed_at 唯一真源
# ---------------------------------------------------------------------------
class TestConsumedAtSoleSourceOfTruth:
    def test_mark_consumed_sets_consumed_at_only(self, temp_db):
        t = _unknown_topic()
        gap_store.record_gap(
            topic=t, coverage="unknown", quality=0.0,
            source_count=0, observed_by="knowledge-gate",
        )
        gap_store.mark_consumed(t)
        row = _row(temp_db, t)
        assert row["consumed_at"] is not None

        # 未消费查询必须排除它
        unconsumed = [g["topic"] for g in gap_store.list_gaps(only_unconsumed=True)]
        assert t not in unconsumed

    def test_reobservation_resets_consumed_at(self, temp_db):
        """重新观测 = 出现新证据 → 回到未消费（consumed_at 清空）。"""
        t = _unknown_topic()
        gap_store.record_gap(
            topic=t, coverage="unknown", quality=0.0,
            source_count=0, observed_by="knowledge-gate",
        )
        gap_store.mark_consumed(t)
        assert _row(temp_db, t)["consumed_at"] is not None

        gap_store.record_gap(
            topic=t, coverage="unknown", quality=0.0,
            source_count=0, observed_by="knowledge-gate",
        )
        assert _row(temp_db, t)["consumed_at"] is None, (
            "重新观测后应回到未消费"
        )

    def test_self_heal_dirty_consumed_row(self, temp_db):
        """自愈：consumed=1 且 consumed_at IS NULL 的脏行，_get_conn 打开时归零。

        这是 C2 死锁的直接病灶：旧冗余列时代产生的 `consumed=1, consumed_at=NULL`
        行会被 reset_stale_consumed 永久跳过。自愈后它们重新进入候选。
        （旧库才有 consumed 列；此处模拟旧库结构。）
        """
        # 手工建一个带旧冗余列的库
        conn = sqlite3.connect(temp_db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gaps (
                topic TEXT PRIMARY KEY, status TEXT NOT NULL,
                quality REAL NOT NULL DEFAULT 0.0,
                source_count INTEGER NOT NULL DEFAULT 0,
                seen_count INTEGER NOT NULL DEFAULT 1,
                first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
                consumed INTEGER NOT NULL DEFAULT 0,
                observed_by TEXT NOT NULL DEFAULT 'unknown',
                real_seen INTEGER NOT NULL DEFAULT 0,
                consumed_at TEXT
            )
        """)
        conn.execute(
            "INSERT INTO gaps (topic,status,quality,source_count,seen_count,"
            "first_seen,last_seen,consumed,observed_by,real_seen,consumed_at) "
            "VALUES ('dirty_row','unknown',0,0,1,'t','t',1,'knowledge-gate',1,NULL)"
        )
        conn.commit()
        conn.close()

        # 打开连接触发自愈
        c = gap_store._get_conn()
        try:
            row = c.execute(
                "SELECT consumed FROM gaps WHERE topic='dirty_row'"
            ).fetchone()
            assert row[0] == 0, "脏行 consumed=1+consumed_at=NULL 应被自愈归零"
        finally:
            c.close()

        # 归零后应出现在未消费列表（即以 consumed_at 为准）
        unconsumed = [g["topic"] for g in gap_store.list_gaps(only_unconsumed=True)]
        assert "dirty_row" in unconsumed
