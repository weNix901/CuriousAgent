"""C1-B: Conflict resolver (v0.3.6, 批2).

Answers "do the sources agree?" as an EXTERNAL measurement over provider
agreement signals — same axiom as C1-A (decision authority belongs to external
measurement, not to introspection). Never asks the LLM.

Input: provider agreement for a topic.
[deprecated 2026-10-07] upstream生产者 CuriosityDecomposer 已废弃，
当前无活跃数据源，resolve_conflict_for_topic() 恒返回 none。

Verdict (per CA2.0 plan §批2):

    none    all providers agree (all found, or all found nothing)
    weak    partial disagreement (some found, some did not)
    strong  result-count spread across providers exceeds `threshold`

IMPORTANT DESIGN NOTE: `conflict` is an ADDITIONAL dimension, not a change to
the four-state main verdict. A `known` topic stays `known` — it is merely
annotated "sources disagree". The four-state machine in coverage_resolver.py is
untouched.

`threshold` is a ratio in [0, 1]: the relative spread of result counts among the
providers that DID return results. It is a calibration target (批3) and lives
here so a single edit retunes the whole system.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Default spread threshold. A topic whose provider result counts differ by more
# than this fraction of their max is flagged strong_conflict. Provisional value;
# pending 批3 human-baseline calibration (see R2 in v0.3.6 risk register).
DEFAULT_THRESHOLD = 0.5


@dataclass
class ConflictVerdict:
    conflict: str            # none | weak | strong
    reason: str
    provider_count: int = 0  # providers that were queried
    agreed_count: int = 0    # providers that returned > 0 results
    spread: float = 0.0      # normalized result-count spread among agreeing providers

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict": self.conflict,
            "conflict_reason": self.reason,
            "conflict_provider_count": self.provider_count,
            "conflict_agreed_count": self.agreed_count,
            "conflict_spread": self.spread,
        }


def resolve_conflict(
    provider_results: Dict[str, int],
    provider_count: Optional[int] = None,
    threshold: float = DEFAULT_THRESHOLD,
) -> ConflictVerdict:
    """Pure function: provider agreement → conflict verdict. No I/O, easy to test.

    Args:
        provider_results: {provider_name: result_count} for ALL queried providers
                          (providers that found nothing are present with 0).
        provider_count: total providers queried. If None, inferred from
                        len(provider_results).
        threshold: relative spread above which agreement is flagged `strong`.

    Rules:
        - < 2 providers            → none (can't compare; insufficient signal)
        - all agree (all 0 or all >0 with low spread) → none
        - some 0 / some >0         → weak  (finding vs not-finding is a real split)
        - all >0 but counts spread > threshold → strong
    """
    # Normalize: keep zero-count providers in the picture.
    counts = {p: int(c) for p, c in (provider_results or {}).items()}
    total = provider_count if provider_count is not None else len(counts)

    if total < 2 or len(counts) < 2:
        return ConflictVerdict(
            conflict="none",
            reason="fewer than 2 providers — no cross-check possible",
            provider_count=total,
            agreed_count=sum(1 for c in counts.values() if c > 0),
        )

    agreed = {p: c for p, c in counts.items() if c > 0}
    agreed_count = len(agreed)
    found_none = total - agreed_count  # providers that returned nothing

    # All found nothing, or all found something → check the "all found" case for spread.
    if agreed_count == 0:
        return ConflictVerdict(
            conflict="none",
            reason="all providers returned no results (unanimous negative)",
            provider_count=total,
            agreed_count=0,
        )

    if found_none == 0:
        # All providers found something. Conflict only if counts diverge widely.
        spread = _spread(agreed)
        if spread > threshold:
            return ConflictVerdict(
                conflict="strong",
                reason=(f"all {agreed_count} providers agree topic exists, but "
                        f"result counts diverge (spread={spread:.2f} > {threshold})"),
                provider_count=total,
                agreed_count=agreed_count,
                spread=spread,
            )
        return ConflictVerdict(
            conflict="none",
            reason=f"{agreed_count} providers agree (spread={spread:.2f} ≤ {threshold})",
            provider_count=total,
            agreed_count=agreed_count,
            spread=spread,
        )

    # Some found, some did not → weak (a genuine split, but not an extreme spread).
    return ConflictVerdict(
        conflict="weak",
        reason=(f"{agreed_count}/{total} providers found results; "
                f"{found_none} returned none — sources split"),
        provider_count=total,
        agreed_count=agreed_count,
        spread=_spread(agreed),
    )


def _spread(counts: Dict[str, int]) -> float:
    """Normalized spread = (max - min) / max, in [0, 1]. 0 if degenerate."""
    if not counts:
        return 0.0
    vals = list(counts.values())
    hi, lo = max(vals), min(vals)
    if hi <= 0:
        return 0.0
    return (hi - lo) / hi


def resolve_conflict_for_topic(topic: str, threshold: float = DEFAULT_THRESHOLD) -> ConflictVerdict:
    """Convenience: pull agreement and resolve. Not pure (reads db).

    [deprecated 2026-10-07] Provider-agreement 数据源（CuriosityDecomposer ->
    provider_agreement_store）已废弃：语义拆解链路被 ExploreAgent(ReAct) 取代，
    provider_agreement 表不再有新写入，无生产数据源。

    本函数保留纯 resolve_conflict() 的调用形态，但恒返回 `none` 判定，
    以免消费者（gap_calculator 批2 conflict 负项）拿到陈旧的 4 条历史数据
    当作有效信号。冲突信号是注解，绝不打断调用方。

    TODO: 若将来 ExploreAgent 链路重新产出 provider 一致性信号，
          在此恢复真实查询。
    """
    return ConflictVerdict(
        conflict="none",
        reason="provider-agreement source deprecated (2026-10-07): no active producer",
    )
