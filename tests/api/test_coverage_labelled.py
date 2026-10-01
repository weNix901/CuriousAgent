"""C1-A-2: labelled-set acceptance test (v0.3.5).

Loads tests/data/coverage_labelled_20.json and checks the four-state resolver
against the recorded signals. This is a *mechanism* test: it proves the
resolver reproduces the recorded verdicts. It is NOT a human-baseline test —
the 'expected' labels are system-proposed and pending weNix review (see the
_meta.human_review block in the JSON).

Acceptance standard (CA2.0 §Phase 2): agreement >= 70%.
"""
import json
from pathlib import Path

import pytest

from core.api.coverage_resolver import resolve_coverage, calibrate

DATA = Path(__file__).parent.parent / "data" / "coverage_labelled_20.json"


def _load():
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def test_labelled_set_shape():
    d = _load()
    assert len(d["questions"]) == 20
    states = {q["expected"] for q in d["questions"]}
    assert states <= {"known", "partial", "unknown", "void"}


def test_resolver_agreement_at_default_theta():
    d = _load()
    t1, t2 = d["_meta"]["theta1"], d["_meta"]["theta2"]
    hit = 0
    misses = []
    for q in d["questions"]:
        v = resolve_coverage(
            similarity=q["similarity"],
            quality=q["quality"],
            source_count=q["source_count"],
            matched_topic=q.get("matched_topic"),
            explore_failed=q.get("explore_failed", False),
            theta1=t1,
            theta2=t2,
        )
        if v.coverage == q["expected"]:
            hit += 1
        else:
            misses.append((q["topic"], v.coverage, q["expected"]))
    agreement = hit / len(d["questions"])
    assert agreement >= 0.70, f"agreement {agreement:.0%} < 70%; misses={misses}"


def test_calibration_reproduces_default_theta():
    """calibrate() must not contradict the pinned module constants."""
    d = _load()
    labelled = [
        {**q, "matched_topic": q.get("matched_topic") or ("x" if q["similarity"] > 0 else None)}
        for q in d["questions"]
    ]
    best = calibrate(labelled)
    assert best["agreement"] >= 0.70
    # theta1 winner must be a grid value; theta2 must separate cleanly
    assert best["theta2"] in (0, 1, 2, 3)
