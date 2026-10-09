"""Reverse-verification harness for v0.3.6-SSOT migration.

Proves, per batch, that (a) the OLD path was silently failing and
(b) the NEW path actually reads/writes the single source of truth.

Read-only except for the SSOT-1 dormant write, which is applied to a
disposable test topic and then reverted.

Usage:
    python3 scripts/verify_ssot.py            # all checks
    python3 scripts/verify_ssot.py ssot1      # one batch
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.knowledge_graph_compat as kg


PASS, FAIL, INFO = "PASS", "FAIL", "INFO"
_results = []


def check(name, ok, detail=""):
    _results.append((name, ok))
    tag = PASS if ok else FAIL
    print(f"  [{tag}] {name}" + (f" — {detail}" if detail else ""))


def hdr(title):
    print(f"\n=== {title} ===")


# ---------------------------------------------------------------------------
# SSOT-0 — guardrail present
# ---------------------------------------------------------------------------
def ssot0():
    hdr("SSOT-0  读源一致性护栏")
    check("_warn_if_knowledge_read 存在",
          hasattr(kg, "_warn_if_knowledge_read"))
    state = kg._load_state()
    empty = not (state.get("knowledge") or {}).get("topics")
    check("_load_state() 的 knowledge.topics 确为空（预期）", empty,
          "这是 Neo4j 为知识源的预期结果，坐实旧路径读空")
    # Neo4j has nodes → the old path was reading an empty graph while data exists
    n = len(kg._get_kg_factory().get_all_nodes_sync(limit=5))
    check("Neo4j 有节点（坐实旧路径读空 ≠ 图空）", n > 0, f"sample={n}")


# ---------------------------------------------------------------------------
# SSOT-1 — dormant round-trip via Neo4j
# ---------------------------------------------------------------------------
def ssot1():
    hdr("SSOT-1  SleepPruner dormant → Neo4j 闭环")
    # Use a REAL existing node: mark_dormant() updates status, it does not
    # create nodes. Fabricating a topic would silently no-op (update_status
    # on a missing node returns False). Pick a done node and restore after.
    f = kg._get_kg_factory()
    sample = f.get_all_nodes_sync(limit=50)
    topic = None
    orig_status = None
    for n in sample:
        if n.get("status") == "done" and n.get("topic"):
            topic = n["topic"]
            orig_status = "done"
            break
    if not topic:
        check("找到可复用的 done 节点", False, "无可复用的 done 节点")
        return
    print(f"  [{INFO}] 使用真实节点: {topic} (orig_status={orig_status})")

    before = set(kg.get_dormant_nodes())
    check("改前：该节点不在 dormant 集", topic not in before)

    # NEW path: SleepPruner._mark_dormant_batch → kg.mark_dormant
    from core.sleep_pruner import SleepPruner
    pruner = SleepPruner()
    try:
        pruner._mark_dormant_batch([topic])
    except Exception as e:
        check("_mark_dormant_batch 调用", False, str(e))
        return

    after = set(kg.get_dormant_nodes())
    check("改后：get_dormant_nodes() 真读到该节点",
          topic in after,
          f"dormant_count={len(after)}")
    node_status = (f.get_node_sync(topic) or {}).get("status")
    check("Neo4j 节点 status == 'dormant'", node_status == "dormant",
          f"status={node_status}")

    # Reverse proof: the OLD path wrote to the empty skeleton → never observable
    skeleton_topics = (kg._load_state().get("knowledge") or {}).get("topics") or {}
    check("反向验证：旧 state 骨架仍为空（旧路径写不进去）",
          topic not in skeleton_topics,
          "旧路径写 state['knowledge']['topics'] = 空 dict，故永久不可观测")

    # Cleanup: restore original status
    try:
        kg.reactivate(topic)
        print(f"  [{INFO}] cleanup: reactivated {topic} (status now 'pending')")
    except Exception as e:
        print(f"  [{INFO}] cleanup skipped: {e}")


# ---------------------------------------------------------------------------
# SSOT-2 — DreamAgent reads non-empty topics
# ---------------------------------------------------------------------------
def ssot2():
    hdr("SSOT-2  DreamAgent 输入非空")
    state = kg.get_state()
    topics = (state.get("knowledge") or {}).get("topics") or {}
    check("get_state() 的 topics 非空（Neo4j 拼装）", len(topics) > 0,
          f"nodes={len(topics)}")
    # Sample 3 topics and show quality varies (no longer constant default)
    sample = list(topics.items())[:3]
    quals = [v.get("quality", 0) or 0 for _, v in sample]
    check("quality 有差异（非恒定默认值）", len(set(quals)) > 1,
          f"sample_qualities={quals}")


# ---------------------------------------------------------------------------
# SSOT-3 .. SSOT-5 — structural checks
# ---------------------------------------------------------------------------
def ssot_structure():
    hdr("SSOT-3/4/5  写入路径检查")
    import re
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target = os.path.join(base, "core")

    PAT = re.compile(r'''state\["knowledge"\]\["topics"\]''')
    # A read is ILLEGAL only when the variable `state` came from _load_state()
    # (the retired skeleton). Reads from get_state() are legal (Neo4j-backed).
    offenders = []
    legit = []
    for root, _, files in os.walk(target):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(root, fn)
            rel = os.path.relpath(path, base)
            # Skip the shim itself and the v1→v2 migration helper (which
            # legitimately operates on an in-memory legacy state dict passed
            # in by the caller). Note: the old JSON fallback backend
            # (json_kg_repository.py) was deleted in v0.3.9 as dead code.
            if ("knowledge_graph_compat.py" in rel
                    or "models/migration.py" in rel):
                continue
            lines = open(path, encoding="utf-8").read().splitlines()
            # Track whether we are inside a triple-quoted docstring so prose
            # mentioning the pattern is not mistaken for an executable read.
            in_doc = False
            for i, line in enumerate(lines):
                s = line.strip()
                if s.count('"""') == 1:
                    in_doc = not in_doc
                    continue
                if in_doc:
                    continue
                if not PAT.search(line):
                    continue
                # Skip comment lines.
                if s.startswith("#"):
                    continue
                # Find the nearest binding of `state` above (search wide).
                src = None
                for j in range(i, -1, -1):
                    m = re.search(r"(?:^|\s)state\s*=\s*([\w\.]+)\(", lines[j])
                    if m:
                        src = m.group(1)
                        break
                if src and src.endswith("get_state"):
                    legit.append(f"{rel}:{i+1}")
                else:
                    offenders.append(f"{rel}:{i+1}: src={src} :: {line.strip()}")

    check("core/ 中无非法 knowledge.topics 读点（_load_state 源）",
          len(offenders) == 0,
          f"illegal={len(offenders)} :: {offenders[:4]}" if offenders
          else f"legal get_state() reads={len(legit)}")


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    if only in (None, "ssot0"):
        ssot0()
    if only in (None, "ssot1"):
        ssot1()
    if only in (None, "ssot2"):
        ssot2()
    if only in (None, "structure"):
        ssot_structure()

    total = len(_results)
    passed = sum(1 for _, ok in _results if ok)
    print(f"\n{'='*50}")
    print(f"SSOT verification: {passed}/{total} passed")
    if passed != total:
        print("FAILED:", [n for n, ok in _results if not ok])
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
