"""L4 契约测试：概念去重不得跨域误合并（v0.3.7-D1d）。

背景 / 为什么测这个
-------------------
concept_normalizer 的翻译映射含单字概念（'图'/'边'/'系统' 等）。反向映射
按英文 token 匹配，导致：
    'graph neural network' → 核心概念 ['图']
    '知识图谱'             → 核心概念 ['图']
    overlap=1.0 → translated_concept → 去重跳过 → 永不探索（认知不诚实）。

实测误判：graph neural network ≈ 知识图谱；edge computing ≈ 边；
system prompt ≈ 系统；Graph RAG ≈ 图数据库。

修复：移除单字/超通用概念词。本测试锁死"跨域不得误合并"，同时保留
合法的语义模糊匹配（attention mechanism ≈ 注意力）。

设计纪律：纯函数测试，无副作用。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.concept_normalizer import get_default_normalizer

_MERGE_TYPES = ("naming_variant", "translated_concept")


class TestNoCrossDomainMerge:
    @pytest.mark.parametrize("a,b", [
        ("graph neural network", "知识图谱"),
        ("knowledge graph", "知识图谱"),
        ("Graph RAG", "图数据库"),
        ("edge computing", "边"),
        ("system prompt", "系统"),
        ("diffusion model", "注意力"),
        ("vision transformer", "注意力"),
        ("chain of thought reasoning", "思维链推理"),
    ])
    def test_cross_domain_not_merged(self, a, b):
        n = get_default_normalizer()
        sim, mt = n.compute_concept_similarity(a, b)
        assert mt not in _MERGE_TYPES, (
            f"cross-domain false merge: {a!r} vs {b!r} -> {mt} (sim={sim})"
        )


class TestLegitFuzzyMatchPreserved:
    @pytest.mark.parametrize("a,b", [
        ("attention mechanism", "注意力"),
        ("self-attention", "注意力"),
    ])
    def test_legit_match_kept(self, a, b):
        n = get_default_normalizer()
        sim, mt = n.compute_concept_similarity(a, b)
        assert mt in _MERGE_TYPES, (
            f"legit fuzzy match lost: {a!r} vs {b!r} -> {mt}"
        )


class TestNoSingleCharConcepts:
    def test_no_single_char_in_translation_map(self):
        from core.concept_normalizer import CONCEPT_TRANSLATION_MAP
        singles = [k for k in CONCEPT_TRANSLATION_MAP if len(k) == 1]
        assert singles == [], f"single-char concepts cause cross-domain merges: {singles}"
