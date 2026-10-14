"""L4 契约测试：URL/标题变体去重（v0.3.7-B1）。

背景 / 为什么测这个
-------------------
同一论文常以多个变体入队（arXiv id 前缀 / 站点后缀 / HTML 实体差异）：
    '[1910.03771] Transformers: State-of-the-Art NL Processing'
    'Transformers: State-of-the-Art NL Processing - ACL Anthology'
    'Transformers: State-of-the-Art NL Processing'
concept_normalizer 对英文标题返回 different_concept（提取不到中文概念词）
→ 去重漏过 → 同一内容反复探索，浪费队列轮次（实测 165 条真话题冗余）。

修复：add_curiosity 去重前加 URL/标题变体归一化层（确定同源的变换）。
本测试锁死"确定同源必须收敛" + "不确定同源不得误合并"。

设计纪律：纯函数测试，无副作用。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.knowledge_graph_compat import _normalize_topic_for_dedup


class TestVariantNormalization:
    def test_arxiv_prefix_stripped(self):
        a = "[1910.03771] Transformers: State-of-the-Art Natural Language Processing"
        b = "Transformers: State-of-the-Art Natural Language Processing"
        assert _normalize_topic_for_dedup(a) == _normalize_topic_for_dedup(b)

    def test_site_suffix_stripped(self):
        a = "Transformers: State-of-the-Art Natural Language Processing - ACL Anthology"
        b = "Transformers: State-of-the-Art Natural Language Processing"
        assert _normalize_topic_for_dedup(a) == _normalize_topic_for_dedup(b)

    def test_pipe_suffix_stripped(self):
        a = "Semantic Scholar | About Us"
        b = "Semantic Scholar | Frequently Asked Questions"
        assert _normalize_topic_for_dedup(a) == _normalize_topic_for_dedup(b)

    def test_html_entities_decoded(self):
        assert (
            _normalize_topic_for_dedup("A&#39;s B")
            == _normalize_topic_for_dedup("A's B")
        )

    def test_full_group_converges(self):
        grp = [
            "[1910.03771] Transformers: State-of-the-Art NL Processing",
            "Transformers: State-of-the-Art NL Processing - ACL Anthology",
            "Transformers: State-of-the-Art NL Processing",
        ]
        assert len({_normalize_topic_for_dedup(t) for t in grp}) == 1


class TestNoFalseMerge:
    def test_different_titles_not_merged(self):
        a = "Attention Is All You Need"
        b = "BERT: Pre-training of Deep Bidirectional Transformers"
        assert _normalize_topic_for_dedup(a) != _normalize_topic_for_dedup(b)

    def test_empty_safe(self):
        assert _normalize_topic_for_dedup("") == ""
        assert _normalize_topic_for_dedup(None) == ""
