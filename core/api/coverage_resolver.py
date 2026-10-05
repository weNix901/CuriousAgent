"""C1-A: Coverage state resolver (v0.3.5).

Answers "does the system know this topic?" WITHOUT asking the LLM to
introspect. The verdict is an external measurement over KG signals, per the
C1 design principle: decision authority belongs to external measurement, not
to the thing being measured.

Four states (state machine from CA2.0 plan §4.1):

    known    KG node & quality ≥ θ₁ & sources ≥ θ₂   → answer directly
    partial  KG node, but quality or sources thin     → answer + flag uncertainty
    unknown  no node, no failed history               → answer (search) + explore
    void     no node AND prior exploration failed     → declare "no basis"

Thresholds θ₁/θ₂ are NOT hard-coded guesses; they default to values
calibrated against a 20-question labelled set (see calibrate()) and live in
this module so a single edit retunes the whole system.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Calibrated against the 20-question annotation set (2026-10-01).
#
# BUG FIX (2026-10-01): these defaults previously read 6.0, contradicting the
# batch-4 report which declared θ₁=4.0. Root cause: calibrate() searched a grid
# of 8 θ₁ values and settled on 4.0, but that winner was never written back to
# the module constant — the "calibrated" value existed only in a report table.
# The label set has no known-node with quality in [4.0, 6.0), so θ₁=4.0 and
# θ₁=6.0 agree on all 20 labels (agreement plateau); either is defensible, but
# the constant must MATCH what the calibration actually produced, otherwise
# "θ is calibrated, not preset" is self-contradictory. Set to the grid winner.
#
# - θ₁=4.0: lowest grid value that still excludes quality=0 partials (LTKD).
#   The known/partial split here is driven mostly by θ₂, not θ₁.
# - θ₂=1: known min sources = 2; partial all 0 → clean separation.
DEFAULT_THETA1 = 4.0   # quality threshold (grid-calibrated, was incorrectly 6.0)
DEFAULT_THETA2 = 1     # minimum source count


@dataclass
class CoverageVerdict:
    coverage: str            # known | partial | unknown | void
    reason: str
    similarity: float = 0.0
    quality: float = 0.0
    source_count: int = 0
    matched_topic: Optional[str] = None
    explore_failed: bool = False
    # 批2 (v0.3.6): ADDITIONAL dimension — do NOT let this change `coverage`.
    # A `known` topic stays `known`; conflict merely annotates source disagreement.
    conflict: str = "none"   # none | weak | strong
    conflict_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "coverage": self.coverage,
            "coverage_reason": self.reason,
            "similarity": self.similarity,
            "quality": self.quality,
            "source_count": self.source_count,
            "matched_topic": self.matched_topic,
            "explore_failed": self.explore_failed,
            "conflict": self.conflict,
            "conflict_reason": self.conflict_reason,
        }


def resolve_coverage(
    similarity: float,
    quality: float,
    source_count: int,
    matched_topic: Optional[str] = None,
    explore_failed: bool = False,
    theta1: float = DEFAULT_THETA1,
    theta2: int = DEFAULT_THETA2,
    conflict: str = "none",
    conflict_reason: str = "",
) -> CoverageVerdict:
    """Pure function: KG signals → four-state verdict. No I/O, easy to test.

    `conflict`/`conflict_reason` (批2, v0.3.6) are an ADDITIONAL dimension: they
    are attached to the verdict verbatim and never influence `coverage`.
    """
    # No hit at all → unknown or void.
    if similarity <= 0.0 or matched_topic is None:
        return CoverageVerdict(
            coverage="void" if explore_failed else "unknown",
            reason=("no node and prior exploration failed" if explore_failed
                    else "no matching node"),
            similarity=similarity,
            quality=quality,
            source_count=source_count,
            explore_failed=explore_failed,
            conflict=conflict,
            conflict_reason=conflict_reason,
        )

    # Hit exists → known or partial.
    if quality >= theta1 and source_count >= theta2:
        return CoverageVerdict(
            coverage="known",
            reason=f"quality={quality} ≥ θ₁={theta1} and {source_count} ≥ θ₂={theta2} source(s)",
            similarity=similarity,
            quality=quality,
            source_count=source_count,
            matched_topic=matched_topic,
            conflict=conflict,
            conflict_reason=conflict_reason,
        )

    return CoverageVerdict(
        coverage="partial",
        reason=(f"quality={quality} (θ₁={theta1}), sources={source_count} "
                f"(θ₂={theta2}) — below bar"),
        similarity=similarity,
        quality=quality,
        source_count=source_count,
        matched_topic=matched_topic,
        conflict=conflict,
        conflict_reason=conflict_reason,
    )


def calibrate(
    labelled: List[Dict[str, Any]],
    theta1_grid: Optional[List[float]] = None,
    theta2_grid: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Grid-search θ₁/θ₂ maximising agreement with a labelled set.

    `labelled` entries: {"similarity", "quality", "source_count", "expected"}
    where expected ∈ {known, partial, unknown, void}.

    Returns {"theta1", "theta2", "agreement", "total", "grid_best"}.
    """
    # Match the calibration that produced DEFAULT_THETA1/2: the grid must
    # include the pinned default, or calibrate() and the module constant can
    # silently drift apart again (the exact bug fixed on 2026-10-01).
    if theta1_grid is None:
        theta1_grid = [DEFAULT_THETA1, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0]
    if theta2_grid is None:
        theta2_grid = [0, 1, 2, 3]

    best = {"agreement": -1.0, "theta1": DEFAULT_THETA1, "theta2": DEFAULT_THETA2}
    for t1 in theta1_grid:
        for t2 in theta2_grid:
            hit = 0
            for item in labelled:
                v = resolve_coverage(
                    similarity=item.get("similarity", 0.0),
                    quality=item.get("quality", 0.0),
                    source_count=item.get("source_count", 0),
                    matched_topic=item.get("matched_topic", "x") if item.get("similarity", 0) > 0 else None,
                    explore_failed=item.get("explore_failed", False),
                    theta1=t1,
                    theta2=t2,
                )
                if v.coverage == item.get("expected"):
                    hit += 1
            acc = hit / len(labelled) if labelled else 0.0
            if acc > best["agreement"]:
                best = {"agreement": acc, "theta1": t1, "theta2": t2,
                        "hit": hit, "total": len(labelled)}
    return best
