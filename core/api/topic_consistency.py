"""批0 (v0.3.6): Match trustworthiness check — pure automatic (E1: substance gate).

Problem (reproduced 2026-10-03):
    query "知识图谱"       → vector top-1 'Knowledge Distillation' (sim=0.7855)
    query "Knowledge Graph" → vector top-1 'Knowledge Distillation' (sim=0.7893)
Neither "知识图谱" nor "Knowledge Graph" has a KG node, so the true four-state
verdict is `unknown`. But `check_confidence` fed the WRONG node's quality (8.0)
into the coverage resolver and would report `partial`.

The decisive finding (measured, not assumed):
    'Knowledge Distillation' is a GHOST NODE:
        content = ""        definition = ""        source_urls = []
        ...yet quality = 8.0
    'Simulating User Watch-Time to Investigate Bias ...' is a REAL node:
        content  = "A simulation-based auditing approach ..."  (full text)
        source_urls = ['arxiv.org/abs/2507.04605', ...]

Design history (why the earlier ideas were rejected — all measured):
    * B1 lexical overlap: failed 3/3 — cross-lingual ("知识图谱"↔"Knowledge
      Graph"), acronyms ("RAG"↔"Retrieval-Augmented Generation"), and long
      crawled titles share no usable tokens.
    * A vector loopback: the reverse query returned the matched node itself in
      all three cases (原 query 从不出现) → zero discriminating power.
    * B score gap: video-bias had a NARROWER gap (0.005) than the bad match
      (0.026) → would invert the decision.
    Conclusion: retrieval-layer signals cannot express "I have no node for
    this". The discriminator lives in the KNOWLEDGE layer: does the matched
    node actually contain substance?

E1 (this module): a matched node is only trustworthy if it carries substance.
    Hard gate: at least one of {content, definition, core} is non-empty.
    Empty node + non-empty source_urls is NOT enough on its own — sources
    without content still give the four-state judge nothing to read.
    When the gate fails, the caller downgrades the verdict to `unknown`
    (no node / no usable knowledge), regardless of similarity or quality.

    Note the ghost node had quality=8.0 — which is exactly why quality cannot
    be trusted as a substance proxy. We look at content, not at quality.

Pure automatic: reads node fields only. No alias table, no LLM, no network.
Conservative: an empty node is treated as "no usable knowledge"; a false
downgrade only costs a search + exploration trigger, while trusting a ghost
node corrupts the four-state verdict and everything downstream (C2/C1).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


TRUSTWORTHY = "trustworthy"
EMPTY = "empty"
CONSISTENT = "consistent"
INCONSISTENT = "inconsistent"


@dataclass
class SubstanceVerdict:
    dependable: bool
    verdict: str
    score: float
    reason: str
    signals: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "match_verdict": self.verdict,
            "match_dependable": self.dependable,
            "match_confidence": round(self.score, 4),
            "match_reason": self.reason,
            "match_signals": self.signals,
        }


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def check_match_substance(
    matched: Optional[Dict[str, Any]],
    query: str = "",
    matched_topic: str = "",
) -> SubstanceVerdict:
    """E1: does the matched node carry substance the four-state judge can read?

    `matched` is the retrieval row (keys: topic, content, quality,
    source_urls, score, ...). Returns a verdict with `dependable=False` when
    the node is a ghost (content/definition/core all empty) so the caller can
    downgrade to `unknown`.

    Missing vs empty (important):
        * A field the row DOES NOT carry is "unknown to us" → we cannot claim
          the node is empty. Such rows fall back to the previous behaviour
          (dependable=True) so we never regress callers/fixtures that omit
          these fields. Every real retrieval channel returns `content`, so the
          live ghost-node case still sees the key present-and-empty.
        * A field the row DOES carry but which is blank IS evidence of
          emptiness. Only this counts toward the ghost verdict.
    """
    if not matched:
        return SubstanceVerdict(
            False, EMPTY, 0.0, "no matched node",
            {"has_content": False, "has_sources": False},
        )

    topic = matched_topic or matched.get("topic") or ""
    srcs = matched.get("source_urls")
    src_count = len(srcs) if isinstance(srcs, (list, tuple)) else 0
    quality = matched.get("quality") or 0.0

    # Which of the three text fields does the row actually carry?
    text_keys = [k for k in ("content", "definition", "core") if k in matched]
    has_text = any(_nonempty(matched.get(k)) for k in text_keys)

    signals = {
        "text_keys_present": text_keys,
        "has_content": _nonempty(matched.get("content")),
        "has_definition": _nonempty(matched.get("definition")),
        "has_core": _nonempty(matched.get("core")),
        "has_sources": src_count > 0,
        "source_count": src_count,
        "node_quality": quality,
    }

    if has_text:
        # Substance present. Faithful to C1: we do NOT re-judge similarity
        # here — that is the retrieval layer's job. We only answer "can this
        # node be trusted as knowledge at all?".
        return SubstanceVerdict(
            True, TRUSTWORTHY, 1.0,
            f"node has substance (content/definition/core non-empty, "
            f"{src_count} source(s))",
            signals,
        )

    if not text_keys:
        # Row carries no text fields at all → nothing to judge. Do not claim
        # ghost; preserve legacy behaviour. Real channels always include
        # `content`, so this branch is for thin fixtures / future callers.
        return SubstanceVerdict(
            True, TRUSTWORTHY, 1.0,
            "row carries no text fields — substance not assessable, "
            "passing through",
            signals,
        )

    # Ghost node: at least one text field is present, and all present text
    # fields are blank. quality may be high (observed 8.0) but there is
    # nothing to read. This is the 知识图谱 → Knowledge Distillation case.
    return SubstanceVerdict(
        False, EMPTY, 0.0,
        f"ghost node: content/definition/core present but all empty "
        f"(quality={quality}, sources={src_count}) — not usable knowledge",
        signals,
    )


# =============================================================================
# E2 (批0 residuals, v0.3.6): topic consistency — token-substring absorption.
# =============================================================================
#
# Distinct failure class from E1. E1 catches GHOST nodes (content empty).
# E2 catches SUBSTANTIVE nodes that are matched to the WRONG topic because the
# query token got absorbed into a longer unrelated token.
#
# Reproduced 2026-10-05:
#     query "LLM"   → top-1 'TypeLLM/TypeLLM' (sim=0.7514, quality=4.5)
#     query "知识图谱" → 'Knowledge Distillation' (E1 already handles this)
#
# Why E1 misses it: 'TypeLLM/TypeLLM' HAS content — it is not a ghost. The
# problem is purely lexical/semantic: "LLM" is a proper substring of the
# LONGER token "TypeLLM". A token-substring absorption is a strong signal that
# the node is a DIFFERENT topic that merely happens to contain the query
# string. Feeding its quality/sources into the four-state judge corrupts the
# verdict (LLM judged `known`, truth is `partial`/`unknown`).
#
# Decisive discriminator (measured on the labelled set, 2026-10-05):
#     absoption rules out  "LLM"→"TypeLLM"   (: absorbed, no shared token)
#     preserves legitimate  "RAG"→"... (RAG) ..." (exact shared token)
#                           "MCP"→"MCP (Model Context Protocol)"
#                           "embedding"→"embedding"
#
# Design notes (why this rule, not a similarity threshold):
#   * Raising the similarity threshold does NOT help: the bad match (0.7514)
#     scores HIGHER than some legitimate legs (transformer→transformers).
#   * Alias tables are language-specific and high-maintenance.
#   * The substring test is PURE, symmetric, and needs no per-topic config.
#
# Conservative (same philosophy as E1): we only flag when the query's ENTIRE
# token set is "explained" by absorption — i.e. no query token appears as an
# independent token in the match AND at least one query token is a genuine
# substring-extension of a longer matched token. A lone shared token, or any
# exact token match, keeps the node legitimate.

_CH_ALNUM = __import__("re").compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+")


def _tokens(text: str) -> set:
    return set(_CH_ALNUM.findall((text or "").lower()))


@dataclass
class ConsistencyVerdict:
    consistent: bool
    verdict: str
    reason: str
    signals: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "consistency": self.verdict,
            "consistency_ok": self.consistent,
            "consistency_reason": self.reason,
            "consistency_signals": self.signals,
        }


def check_topic_consistency(
    query: str,
    matched_topic: str,
    min_absorb_len: int = 2,
) -> ConsistencyVerdict:
    """E2: does the matched topic actually CONTAIN the query as a token?

    Flags token-substring absorption ("LLM" absorbed into "TypeLLM").

    Rules (all must hold to flag INCONSISTENT):
        1. No exact shared token between query and matched topic.
        2. At least one query token is a PROPER substring of a matched token,
           with length difference >= min_absorb_len (default 2). This avoids
           flagging benign truncations (singular/plural: "transformer" vs
           "transformers" differ by 1).
        3. Every query token is accounted for by absorption (the query is
           fully "eaten", not merely partially overlapping).

    Never raises. Empty inputs → consistent (cannot judge → pass through).
    """
    q = (query or "").strip()
    m = (matched_topic or "").strip()
    if not q or not m:
        return ConsistencyVerdict(
            True, CONSISTENT, "empty query or match — consistency not assessable")

    qt = _tokens(q)
    mt = _tokens(m)
    if not qt or not mt:
        return ConsistencyVerdict(
            True, CONSISTENT, "no comparable tokens",
            {"query_tokens": sorted(qt), "matched_tokens": sorted(mt)})

    shared = qt & mt
    if shared:
        return ConsistencyVerdict(
            True, CONSISTENT,
            f"query token(s) present verbatim in match: {sorted(shared)}",
            {"query_tokens": sorted(qt), "matched_tokens": sorted(mt),
             "shared": sorted(shared)})

    # No exact overlap — look for absorption: query token ⊂ longer matched token.
    absorbed = []
    for a in qt:
        for b in mt:
            if a in b and len(b) - len(a) >= min_absorb_len:
                absorbed.append((a, b))
                break

    if absorbed and len(absorbed) == len(qt):
        # Every query token was swallowed by a longer unrelated token.
        return ConsistencyVerdict(
            False, INCONSISTENT,
            f"token-substring absorption: {absorbed} — query {q!r} looks "
            f"contained in {m!r} but shares no independent token",
            {"query_tokens": sorted(qt), "matched_tokens": sorted(mt),
             "absorbed": absorbed})

    # Partial overlap / no absorption: not confident enough to reject.
    return ConsistencyVerdict(
        True, CONSISTENT,
        "no decisive inconsistency signal",
        {"query_tokens": sorted(qt), "matched_tokens": sorted(mt),
         "absorbed": absorbed})
