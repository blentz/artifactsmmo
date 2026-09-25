"""Phase 0 yardstick for the decision-architecture redesign.

`docs/PLAN_decision_architecture_redesign.md` removes about 35 compensating
mechanisms in five phases. Each phase must show that the bot behaves at least as
well afterwards. This census is the ruler every phase is measured with: the same
metrics, computed the same way, over any window of the durable `cycles` and
`sessions` history in the learning DB (never trace files, which are deleted
periodically).

No-plan cycles are ordinary `cycles` rows (`outcome="no_plan"`), so they count
against `ok_share` and appear as the `no_plan` error class. Compensating
mechanisms are counted from `decision_events` (Phase 0b): `mechanisms` is empty
for any window before that table existed, which means "not recorded", not "never
fired".
"""

import json
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from artifactsmmo_cli.ai.learning.models import Cycle, DecisionEvent, Session

ERROR_CLASSES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("grind_budget_exhausted", re.compile(r"grind sub-plan EXHAUSTED")),
    ("grind_dead_end", re.compile(r"grind produced no leg")),
    ("grind_other", re.compile(r"^LevelSkill\(|cyclic skill-grind")),
    ("fight_lost", re.compile(r"^fight_lost")),
    ("no_response", re.compile(r"no response data|Could not fetch character")),
    ("transport", re.compile(r"timed out|Errno|handshake")),
)
"""First match wins. An `error:HTTP_<code>` outcome is classed by its code
instead (`http_<code>`), since the code alone is what distinguishes those."""


@dataclass(frozen=True)
class CharacterCensus:
    """One character's decision quality over one window."""

    character: str
    window_hours: float
    cycles: int
    cycles_per_hour: float
    ok_share: float | None
    error_classes: dict[str, int]
    level_skill_share: float | None
    wait_cycles: int
    timed_out_share: float | None
    nodes_p50: int | None
    nodes_p95: int | None
    nodes_max: int | None
    goal_switch_share: float | None
    longest_failure_streak: int
    char_xp_per_hour: float
    skill_xp_per_hour: float
    cooldown_share: float
    session_exits: dict[str, int]
    mechanisms: dict[str, int]


def classify_error(outcome: str, error_text: str | None) -> str:
    """The error class of one failed cycle."""
    if outcome.startswith("error:HTTP_"):
        return "http_" + outcome.removeprefix("error:HTTP_")
    text = error_text or ""
    for name, pattern in ERROR_CLASSES:
        if pattern.search(text):
            return name
    return outcome.removeprefix("error:")


def _share(part: int, whole: int) -> float | None:
    """`part / whole`, or None when there is nothing to divide (not 0.0: "measured
    as nothing" and "could not tell" stay distinct)."""
    return None if whole == 0 else part / whole


def _percentile(sorted_values: Sequence[int], fraction: float) -> int | None:
    if not sorted_values:
        return None
    return sorted_values[min(len(sorted_values) - 1, int(fraction * len(sorted_values)))]


def _longest_failure_streak(cycles: Sequence[Cycle]) -> int:
    """Longest run of consecutive cycles that failed the SAME action the same
    way: the signature of a decision the bot keeps re-deriving."""
    longest = run = 0
    previous: tuple[str | None, str] | None = None
    for cycle in cycles:
        if cycle.outcome == "ok":
            previous, run = None, 0
            continue
        key = (cycle.action_repr, cycle.outcome)
        run = run + 1 if key == previous else 1
        previous = key
        longest = max(longest, run)
    return longest


def census(character: str, cycles: Sequence[Cycle], sessions: Sequence[Session],
           events: Sequence[DecisionEvent], window_hours: float) -> CharacterCensus:
    """Measure one character. `cycles` must be that character's rows inside the
    window in id order, `sessions` the sessions that ENDED inside it, and
    `events` its decision events inside it.
    `window_hours` is the wall-clock length of the window, so a character that
    was down for part of it shows the lost throughput instead of hiding it."""
    if window_hours <= 0:
        raise ValueError(f"window_hours must be positive, got {window_hours}")
    total = len(cycles)
    failed = [c for c in cycles if c.outcome != "ok"]
    nodes = sorted(c.planner_nodes for c in cycles if c.planner_nodes is not None)
    timed = [c for c in cycles if c.planner_timed_out is not None]
    goals = [c.selected_goal for c in cycles]
    switches = sum(1 for a, b in pairwise(goals) if a != b)
    skill_xp = sum(sum(json.loads(c.delta_skill_xp_json).values()) for c in cycles)
    cooldown = sum(c.actual_cooldown_seconds or 0.0 for c in cycles)
    return CharacterCensus(
        character=character,
        window_hours=window_hours,
        cycles=total,
        cycles_per_hour=total / window_hours,
        ok_share=_share(total - len(failed), total),
        error_classes=dict(Counter(classify_error(c.outcome, c.error_text) for c in failed)),
        level_skill_share=_share(sum(1 for c in cycles if c.action_class == "LevelSkill"), total),
        wait_cycles=sum(1 for c in cycles if c.action_class == "WaitAction"),
        timed_out_share=_share(sum(1 for c in timed if c.planner_timed_out), len(timed)),
        nodes_p50=_percentile(nodes, 0.5),
        nodes_p95=_percentile(nodes, 0.95),
        nodes_max=nodes[-1] if nodes else None,
        goal_switch_share=_share(switches, total - 1) if total > 1 else None,
        longest_failure_streak=_longest_failure_streak(cycles),
        char_xp_per_hour=sum(c.delta_xp or 0 for c in cycles) / window_hours,
        skill_xp_per_hour=skill_xp / window_hours,
        cooldown_share=cooldown / (window_hours * 3600.0),
        session_exits=dict(Counter(s.exit_reason or "running" for s in sessions)),
        mechanisms=dict(Counter(e.mechanism for e in events)),
    )
