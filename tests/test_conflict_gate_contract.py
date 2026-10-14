"""L4 契约测试：冲突降权不得否决候选（v0.3.7-D1e）。

背景 / 为什么测这个
-------------------
rank_gaps 先用 conflict 降权（weak ×0.8 / strong ×0.5），再用 `>= thr` 过闸门。
这产生一个死区：单次真实观测 (real_seen=1) 的 value=0.80，遇 weak ×0.8=0.64
< thr(0.7) → 被静默丢弃 → 该话题永不探索。

语义上 weak = "有的 provider 找到、有的没找到"（source split），是证据不是否决
（CA2.0 公理B）。降权应是排序手段，不是闸门。

修复：闸门用降权前的 value，降权后的 value 只参与排序。

设计纪律：纯函数测试，无副作用。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.api.gap_calculator import rank_gaps, GapConfig


def _gap(topic, real_seen=1, status="unknown", quality=0.0):
    return {
        "topic": topic,
        "status": status,
        "quality": quality,
        "real_seen": real_seen,
        "explore_failed": False,
    }


class TestConflictDoesNotVeto:
    def test_weak_conflict_candidate_survives_gate(self):
        """单次真实观测 + weak 冲突 → 仍应过闸门（只降权排序）。"""
        gaps = [_gap("FlashAttention", real_seen=1)]
        cfg = GapConfig.resolve()
        out = rank_gaps(gaps, conflict_lookup={"FlashAttention": "weak"}, config=cfg)
        assert [s.topic for s in out] == ["FlashAttention"], (
            "weak conflict must not veto a real gap below the gate"
        )

    def test_strong_conflict_candidate_survives_gate(self):
        gaps = [_gap("SomeTopic", real_seen=1)]
        cfg = GapConfig.resolve()
        out = rank_gaps(gaps, conflict_lookup={"SomeTopic": "strong"}, config=cfg)
        assert [s.topic for s in out] == ["SomeTopic"]

    def test_conflict_still_affects_ordering(self):
        """无冲突的候选应排在有冲突的候选之前（降权=排序手段）。"""
        gaps = [_gap("Clean", real_seen=1), _gap("Conflicted", real_seen=1)]
        cfg = GapConfig.resolve()
        out = rank_gaps(gaps, conflict_lookup={"Conflicted": "weak"}, config=cfg)
        assert [s.topic for s in out] == ["Clean", "Conflicted"]

    def test_zero_relevance_still_filtered(self):
        """real_seen=0（无真实观测）的缺口仍需被闸门挡掉。"""
        gaps = [_gap("TestOnly", real_seen=0)]
        cfg = GapConfig.resolve()
        out = rank_gaps(gaps, conflict_lookup={"TestOnly": "none"}, config=cfg)
        assert out == []
