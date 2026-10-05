"""批4b (v0.3.6): Gap calculator — C2 缺口价值计算。

CA2.0 §4.2 公式：
    缺口价值 = 覆盖度缺口 × 相关性 × 可解性
      覆盖度缺口 = 1 - KG_quality(topic)/10
      相关性     = 【第一版只用"会话触发" = 观测频次 seen_count，见 4a】
      可解性     = 【纯排序，不参与价值计算 —— CA2.0 §4.2 明确】

设计约束（逐条对应 CA2.0 原文）：
  * 乘法（非加法）：任一项低 → 价值为 0 → 不入队。这是防"无差别抓取"的核心闸门。
  * 可解性不进价值：难探索的领域常是最重要的未知；若进价值，系统会压制它们，
    退化为"搜索引擎复读机"。难探索 ≠ 不值得记录（CA2.0 §4.2 记录原则）。
  * 相关性用外部可查信号（seen_count），不读心、不造数据。

纯函数核心（compute_gap_value / rank_gaps），便于测试；db 仅用于便捷入口。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# =============================================================================
# 参数配置层（4b 地基；4b-2 动态化在此接入）
# =============================================================================
#
# 设计原则：阈值是"可配置参数"，不是散落的魔法常量。
#   * GapConfig 是唯一真源；默认值 = 当前定稿行为（不改变任何现有输出）。
#   * 4b-2（动态化）只替换 resolve() 的来源：从"固定默认"改为"外部统计驱动"，
#     调用方签名不变。这就是"地基"的意义 —— 动态化不改调用点。

# 缺口的 status 权重：void 比 unknown 更"缺"（连历史探索都失败了）。
STATUS_WEIGHT = {"void": 1.0, "unknown": 0.8}

# 相关性：seen_count 的归一化饱和点。达到该次数视为相关性=1.0。
RELEVANCE_SATURATION = 3

# 入队闸门：价值 >= 此阈值才产生任务候选。
DEFAULT_GAP_THRESHOLD = 0.35

# 阈值合法区间（4b-2 动态化时的硬上下限 —— 防止"阈值自我强化"失控）。
THRESHOLD_FLOOR = 0.15
THRESHOLD_CEIL = 0.80
SATURATION_FLOOR = 1
SATURATION_CEIL = 10


class GapConfig:
    """缺口计算参数（唯一真源）。

    默认值 = 当前定稿行为。4b-2 动态化时，只需在 resolve() 中用外部可观测
    统计（队列积压/消费率/seen 分位数）替换硬编码默认，调用方零改动。

    ⚠️ 动态化的驱动力必须是【外部可观测统计】，绝不能让 LLM 自判
    （违反 C1 公理：决策权归属外部测量，不归属被测对象）。
    """

    def __init__(
        self,
        relevance_saturation: int = RELEVANCE_SATURATION,
        gap_threshold: float = DEFAULT_GAP_THRESHOLD,
    ):
        # 上下限钳制：无论来源（默认/配置/动态），都不允许越界。
        self.relevance_saturation = max(
            SATURATION_FLOOR, min(int(relevance_saturation), SATURATION_CEIL)
        )
        self.gap_threshold = max(
            THRESHOLD_FLOOR, min(float(gap_threshold), THRESHOLD_CEIL)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relevance_saturation": self.relevance_saturation,
            "gap_threshold": self.gap_threshold,
            "source": "static-default",
        }

    @classmethod
    def resolve(cls, overrides: Optional[Dict[str, Any]] = None) -> "GapConfig":
        """解析配置。4b-2 的接入点。

        第一版：返回默认（可被 overrides 覆盖）。
        4b-2：在此处接入 dynamic_threshold() / 外部统计，调用方不变。
        """
        o = overrides or {}
        return cls(
            relevance_saturation=o.get("relevance_saturation", RELEVANCE_SATURATION),
            gap_threshold=o.get("gap_threshold", DEFAULT_GAP_THRESHOLD),
        )


def dynamic_threshold() -> Dict[str, Any]:
    """4b-2 占位：动态阈值骨架。

    第一版【固定返回默认，行为零变化】。骨架存在是为了锁定接口契约：
    4b-2 将填入"外部可观测统计驱动"的实现，并带滞回 + 硬上下限。

    预期实现（见对话定稿）：
        pending = queue.pending_count()
        recent_done = queue.done_in_last(hours=1)
        if pending > 100 and recent_done < 10:  → 收紧 (0.7)
        elif pending < 20:                       → 放松 (0.25)
        else:                                    → 常态 (0.35)
    驱动力 = 队列健康度（外部信号），绝不让 LLM 拍。
    """
    return {
        "relevance_saturation": RELEVANCE_SATURATION,
        "gap_threshold": DEFAULT_GAP_THRESHOLD,
        "source": "static-default (4b-2 will enable adaptive)",
    }


@dataclass
class GapScore:
    topic: str
    value: float            # 缺口价值（三因子乘积）
    coverage_gap: float     # 覆盖度缺口因子
    relevance: float        # 相关性因子（会话触发）
    solvability: float      # 可解性（仅排序，不参与 value）
    status: str
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "value": round(self.value, 4),
            "coverage_gap": round(self.coverage_gap, 4),
            "relevance": round(self.relevance, 4),
            "solvability": round(self.solvability, 4),
            "status": self.status,
            "reason": self.reason,
        }


def _coverage_gap(quality: float, status: str) -> float:
    """1 - quality/10，再乘 status 权重（void 更缺）。"""
    q = max(0.0, min(float(quality or 0.0), 10.0))
    base = 1.0 - q / 10.0
    return base * STATUS_WEIGHT.get(status, 0.8)


def _relevance(seen_count: int, saturation: int = None) -> float:
    """会话触发相关性：观测频次归一化到 [0,1]（饱和于 saturation）。

    seen_count 来自 4a —— topic 被判 unknown/void 的次数，即"用户问了几次我却没有"。
    这是外部可查信号，无需读心。

    saturation 可注入（4b-2 动态化）；None → 用模块默认。
    """
    sat = int(saturation) if saturation is not None else RELEVANCE_SATURATION
    if sat <= 0:
        return 0.0
    n = max(0, int(seen_count or 0))
    return min(1.0, n / sat)


def _solvability(has_failed: bool) -> float:
    """可解性：历史探索是否失败过（failed → 低可解）。仅用于排序。"""
    return 0.2 if has_failed else 1.0


def compute_gap_value(
    topic: str,
    status: str,
    quality: float = 0.0,
    seen_count: int = 1,
    explore_failed: bool = False,
    relevance_saturation: int = None,
) -> GapScore:
    """纯函数：缺口记录 → 价值评分。

    价值 = 覆盖度缺口 × 相关性   （可解性不进价值，仅随附用于排序）
    relevance_saturation 可注入（4b-2 动态化）；None → 模块默认。
    """
    cg = _coverage_gap(quality, status)
    rel = _relevance(seen_count, saturation=relevance_saturation)
    sol = _solvability(explore_failed)
    value = cg * rel  # 可解性不进乘积（CA2.0 §4.2）
    return GapScore(
        topic=topic,
        value=value,
        coverage_gap=cg,
        relevance=rel,
        solvability=sol,
        status=status,
        reason=(f"coverage_gap={cg:.2f} × relevance={rel:.2f} "
                f"(seen={seen_count}); solvability={sol:.2f} (sort-only)"),
    )


def rank_gaps(
    gaps: List[Dict[str, Any]],
    threshold: float = None,
    conflict_lookup: Optional[Dict[str, str]] = None,
    config: "GapConfig" = None,
) -> List[GapScore]:
    """对缺口列表评分排序。

    Args:
        gaps: 4a 的 list_gaps() 输出（dict 列表）。
        threshold: 入队闸门（value >= threshold）。None → 用 config/默认。
        conflict_lookup: {topic: conflict}（批2 信号），"strong" 作负项降权。
        config: GapConfig；None → resolve() 默认。

    Returns:
        按 (value desc, solvability desc) 排序的 GapScore 列表（已过闸门）。

    Note: 批2 conflict 作负项 —— 来源分歧高 → 即使缺，优先级也降（不可信）。
    """
    cfg = config or GapConfig.resolve()
    thr = cfg.gap_threshold if threshold is None else threshold
    scored: List[GapScore] = []
    for g in gaps or []:
        topic = g.get("topic")
        if not topic:
            continue
        s = compute_gap_value(
            topic=topic,
            status=g.get("status", "unknown"),
            quality=g.get("quality", 0.0),
            seen_count=g.get("seen_count", 1),
            explore_failed=bool(g.get("explore_failed", False)),
            relevance_saturation=cfg.relevance_saturation,
        )
        # 批4d：conflict 负项
        if conflict_lookup:
            c = (conflict_lookup.get(topic) or "none").lower()
            if c == "strong":
                s.value *= 0.5
                s.reason += "; conflict=strong (×0.5)"
            elif c == "weak":
                s.value *= 0.8
                s.reason += "; conflict=weak (×0.8)"
        if s.value >= thr:
            scored.append(s)

    scored.sort(key=lambda x: (-x.value, -x.solvability))
    return scored


def compute_from_store(
    only_unconsumed: bool = True,
    threshold: float = None,
    with_conflict: bool = True,
    config: "GapConfig" = None,
) -> List[GapScore]:
    """便捷入口：从 ops.db.gaps 拉缺口 → 评分排序（含批2 conflict 负项）。

    threshold/config 为 None 时用 GapConfig.resolve()（4b-2 动态化接入点）。
    任何异常 → 返回空列表（绝不打断调用方，同批1/4a 纪律）。
    """
    try:
        cfg = config or GapConfig.resolve()
        from core.api.gap_store import list_gaps
        gaps = list_gaps(only_unconsumed=only_unconsumed)
        conflict_lookup = None
        if with_conflict:
            try:
                from core.provider_agreement_store import get_agreement
                conflict_lookup = {}
                from core.api.conflict_resolver import resolve_conflict
                for g in gaps:
                    a = get_agreement(g["topic"])
                    v = resolve_conflict(
                        provider_results=a.get("providers", {}),
                        provider_count=a.get("provider_count", 0),
                    )
                    conflict_lookup[g["topic"]] = v.conflict
            except Exception:
                conflict_lookup = None
        return rank_gaps(gaps, threshold=threshold, conflict_lookup=conflict_lookup, config=cfg)
    except Exception:
        return []
