"""Leverage scoring for the gap backlog: score = journey_impact * live_bottleneck
* stall_risk, except IGNORE gaps (deliberately not actioned) score 0. Pure."""

from dataclasses import dataclass

_VALID_KINDS = frozenset({"MISSING", "THIN", "UNPROVEN", "WRONG-POLICY", "IGNORE"})


@dataclass(frozen=True)
class GapItem:
    concept: str
    kind: str
    journey_impact: int   # 0-3: how much closing it unblocks tier progression
    live_bottleneck: int  # 0-3: is it the current binding constraint (from play data)
    stall_risk: int       # 0-3: does the gap cause stuck/incoherent behavior

    def __post_init__(self) -> None:
        if self.kind not in _VALID_KINDS:
            raise ValueError(f"unknown gap kind: {self.kind!r}")


def leverage_score(g: GapItem) -> int:
    if g.kind == "IGNORE":
        return 0
    return g.journey_impact * g.live_bottleneck * g.stall_risk


def rank_backlog(gaps: list[GapItem]) -> list[GapItem]:
    """Highest leverage first; ties keep input order (stable)."""
    return sorted(gaps, key=leverage_score, reverse=True)
