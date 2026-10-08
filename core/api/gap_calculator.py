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

# =============================================================================
# 批4b-2 动态阈值参数（队列健康度驱动）
# =============================================================================
#
# 驱动力 = 队列健康度（外部可观测统计：pending 积压 + 近窗消费速率）。
# 三条规则 + 滞回（hysteresis），防止阈值在边界上抖动（颤振）。
#
# 收紧（backlog 高 & 消费慢）→ 阈值升 → 只放行最高价值缺口（防止灌爆）
# 放松（backlog 低）      → 阈值降 → 欢迎更多缺口
# 常态                    → 保持默认

# 队列健康度阈值（规则触发点）
BACKLOG_HIGH = 100          # pending > 此值 视为积压
CONSUME_LOW = 10            # 近1h done < 此值 视为消费滞缓
BACKLOG_LOW = 20            # pending < 此值 视为空闲

# 三档目标阈值
THRESHOLD_TIGHT = 0.70      # 收紧档（积压+滞缓）
THRESHOLD_NORMAL = DEFAULT_GAP_THRESHOLD   # 常态档 0.35
THRESHOLD_LOOSE = 0.25      # 放松档（空闲）

# 滞回带宽：状态切换需越过触发点 ± 此带宽，防止在边界反复横跳。
HYSTERESIS_BAND = 0.05


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
        source: str = "static-default",
    ):
        # 上下限钳制：无论来源（默认/配置/动态），都不允许越界。
        self.relevance_saturation = max(
            SATURATION_FLOOR, min(int(relevance_saturation), SATURATION_CEIL)
        )
        self.gap_threshold = max(
            THRESHOLD_FLOOR, min(float(gap_threshold), THRESHOLD_CEIL)
        )
        # 来源标注（排查用）：static-default / adaptive-driven / overrides
        self.source = source

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relevance_saturation": self.relevance_saturation,
            "gap_threshold": self.gap_threshold,
            "source": self.source,
        }

    @classmethod
    def resolve(
        cls,
        overrides: Optional[Dict[str, Any]] = None,
        dynamic: bool = True,
        queue_stats: Optional[Dict[str, Any]] = None,
        prev_threshold: Optional[float] = None,
    ) -> "GapConfig":
        """解析配置（4b-2 接入点）。

        优先级：显式 overrides > 动态阈值 > 静态默认。

        Args:
            overrides: 显式参数（最高优先级，不被动态覆盖）。
            dynamic: True（默认）→ 尝试队列健康度驱动的动态阈值；
                     False → 强制静态默认（向后兼容 / 测试可重现）。
            queue_stats: 注入队列信号（测试用）；None → 实时拉取。
            prev_threshold: 上一轮阈值（滞回用）。
        """
        o = overrides or {}
        cfg: Dict[str, Any] = {}
        if dynamic and "gap_threshold" not in o:
            try:
                cfg = dynamic_threshold(queue_stats=queue_stats, prev_threshold=prev_threshold)
            except Exception:
                cfg = {}
        if "gap_threshold" in o:
            source = "overrides"
        else:
            source = cfg.get("source", "static-default")
        return cls(
            relevance_saturation=o.get(
                "relevance_saturation",
                cfg.get("relevance_saturation", RELEVANCE_SATURATION),
            ),
            gap_threshold=o.get(
                "gap_threshold",
                cfg.get("gap_threshold", DEFAULT_GAP_THRESHOLD),
            ),
            source=source,
        )


def dynamic_threshold(
    queue_stats: Optional[Dict[str, Any]] = None,
    prev_threshold: Optional[float] = None,
) -> Dict[str, Any]:
    """4b-2：动态阈值 —— 队列健康度驱动的自适应入队闸门。

    驱动力 = 队列健康度（外部可观测统计），绝不让 LLM 拍（C1 公理：
    决策权归属外部测量，不归属被测对象）。

    三档规则（带滞回，防颤振）：
        pending > BACKLOG_HIGH 且 recent_done < CONSUME_LOW
                              → 收紧 THRESHOLD_TIGHT (0.70)
        pending < BACKLOG_LOW → 放松 THRESHOLD_LOOSE (0.25)
        其余                  → 常态 THRESHOLD_NORMAL (0.35)

    滞回：给定 prev_threshold 时，仅在越过触发点 ± HYSTERESIS_BAND 才切换，
    避免 pending 在 100 附近抖动导致阈值反复跳变。

    Args:
        queue_stats: {"pending": int, "recent_done": int}；None → 从 QueueStorage
                     实时拉取（失败则回退静态默认，行为与 4b 一致）。
        prev_threshold: 上一轮阈值（用于滞回）；None → 不做滞回（首轮/无状态）。

    Returns:
        {"relevance_saturation": int, "gap_threshold": float, "source": str}
    """
    # 获取外部信号
    pending: Optional[int] = None
    recent_done: Optional[int] = None
    if queue_stats is not None:
        pending = queue_stats.get("pending")
        recent_done = queue_stats.get("recent_done")
    else:
        try:
            from core.tools.queue_tools import QueueStorage
            qs = QueueStorage()
            qs.initialize()
            try:
                pending = qs.pending_count()
                recent_done = qs.done_in_last(hours=1.0)
            finally:
                qs.close()
        except Exception:
            pending = None
            recent_done = None

    # 信号不可得 → 回退静态默认（绝不因动态化故障改变既有行为）
    if pending is None or recent_done is None:
        return {
            "relevance_saturation": RELEVANCE_SATURATION,
            "gap_threshold": DEFAULT_GAP_THRESHOLD,
            "source": "static-default (queue signal unavailable)",
        }

    pending = int(pending)
    recent_done = int(recent_done)

    # 滞回：用上一轮阈值判断当前处于哪个档，再决定是否切换
    # prev=None 时直接按原始触发点判档
    if prev_threshold is None:
        if pending > BACKLOG_HIGH and recent_done < CONSUME_LOW:
            target = THRESHOLD_TIGHT
        elif pending < BACKLOG_LOW:
            target = THRESHOLD_LOOSE
        else:
            target = THRESHOLD_NORMAL
    else:
        prev = float(prev_threshold)
        # 判断是否已处于某档（含滞回带宽）
        is_tight = prev >= THRESHOLD_TIGHT - HYSTERESIS_BAND
        is_loose = prev <= THRESHOLD_LOOSE + HYSTERESIS_BAND

        if is_tight:
            # 解除收紧需 pending 回落到 BACKLOG_HIGH*(1-band) 以下
            if pending < BACKLOG_HIGH * (1 - HYSTERESIS_BAND):
                target = THRESHOLD_NORMAL
            else:
                target = THRESHOLD_TIGHT
        elif is_loose:
            # 解除放松需 pending 回升到 BACKLOG_LOW*(1+band) 以上
            if pending > BACKLOG_LOW * (1 + HYSTERESIS_BAND):
                target = THRESHOLD_NORMAL
            else:
                target = THRESHOLD_LOOSE
        else:
            # 常态：按原始触发点判档
            if pending > BACKLOG_HIGH and recent_done < CONSUME_LOW:
                target = THRESHOLD_TIGHT
            elif pending < BACKLOG_LOW:
                target = THRESHOLD_LOOSE
            else:
                target = THRESHOLD_NORMAL

    # 硬上下限钳制（无论来源）
    target = max(THRESHOLD_FLOOR, min(float(target), THRESHOLD_CEIL))

    return {
        "relevance_saturation": RELEVANCE_SATURATION,
        "gap_threshold": round(target, 4),
        "source": (f"adaptive-driven (pending={pending}, "
                   f"recent_done={recent_done})"),
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

    v0.3.6-C2 (2026-10-08)：传入的 seen_count 应为 **real_seen**（只计
    observed_by ∈ {user,hook} 的观测），而非原始 seen_count。后者混入
    test/probe 打点，会使 UnknownTopic123 这类测试词相关性虚高。若调用方
    传的是原始 seen_count，相关性会失真（退化为旧的混噪声行为）。

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

    NOTE (v0.3.6-C2): 调用方应传 real_seen（仅真实会话触发）。rank_gaps()
    已自动优先取 real_seen；本纯函数保留 seen_count 语义供单测直调。
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
    Note: C3D-R (2026-10-08) —— 已移除 feedback 提权。原批6 用"被检索"驱动
          缺口提权，因果方向接反（被动→主动），违反 CA2.0 §1.3 公理：
          会让系统系统性遗忘自己主动探过的方向。现缺口优先级仅由 C2 三因子
          （覆盖度 × 相关性[real_seen]）决定；C3-D 改为"发现→消费提示"（见
        　feedback_store.related_discoveries）。
    """
    cfg = config or GapConfig.resolve()
    thr = cfg.gap_threshold if threshold is None else threshold
    scored: List[GapScore] = []
    for g in gaps or []:
        topic = g.get("topic")
        if not topic:
            continue
        # v0.3.6-C2: 相关性只认"真实会话触发"(real_seen)。
        # 唯一通路原则：不再回退到 seen_count（seen_count 混入 test/probe 打点，
        # 回退=保留旧通路，会让测试词虚高）。real_seen 由 record_gap 统一维护，
        # 缺失即视为 0（缺值 = 无真实观测，而非"用旧值"）。
        rel_source = int(g.get("real_seen") or 0)
        s = compute_gap_value(
            topic=topic,
            status=g.get("status", "unknown"),
            quality=g.get("quality", 0.0),
            seen_count=rel_source,
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
    """便捷入口：从 ops.db.gaps 拉缺口 → 评分排序。

    C3D-R (2026-10-08)：已移除 with_feedback / feedback 提权通路。
    缺口优先级仅由 C2 三因子决定（不掺检索反馈）。

    threshold/config 为 None 时用 GapConfig.resolve()（4b-2 动态化接入点）。
    任何异常 → 返回空列表（绝不打断调用方，同批1/4a 纪律）。
    """
    try:
        cfg = config or GapConfig.resolve()
        from core.api.gap_store import list_gaps
        gaps = list_gaps(only_unconsumed=only_unconsumed)
        # 批2/批8 (v0.3.6, 2026-10-08 重接通): provider-agreement 数据源已恢复
        # （批8 把一致性信号接入 ExploreAgent 真实搜索链路）。遍历缺口批量取冲突。
        conflict_lookup = None
        if with_conflict:
            try:
                from core.api.conflict_resolver import resolve_conflict_for_topic
                conflict_lookup = {}
                for g in gaps:
                    t = g.get("topic")
                    if not t:
                        continue
                    v = resolve_conflict_for_topic(t)
                    if v.conflict != "none":
                        conflict_lookup[t] = v.conflict
                conflict_lookup = conflict_lookup or None
            except Exception:
                conflict_lookup = None
        return rank_gaps(
            gaps,
            threshold=threshold,
            conflict_lookup=conflict_lookup,
            config=cfg,
        )
    except Exception:
        return []
