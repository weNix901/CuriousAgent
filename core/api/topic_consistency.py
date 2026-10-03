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
