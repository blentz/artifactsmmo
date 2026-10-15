"""Pure core: the win threshold a fight's measured loss cost implies (spec
2026-10-15 fight-gates-odds §2).

Expected seconds per kill at win probability p is t_win + (1 - p)/p × t_loss.
USER 2026-10-15: losses may cost at most one won fight per kill, so
(1 - p)/p × t_loss <= t_win, that is p >= t_loss / (t_win + t_loss).

A fight's cost is its own cooldown plus the Rest and Move cooldowns of the same
character after it, up to that character's next fight: the recovery a won close
fight needs and the rest and walk back a loss forces. Measured 2026-10-15 the
two are close (R2D2 v owlbear 94.7 s per win, 90.3 s per loss), so θ sits near
one half."""

from collections.abc import Sequence
from fractions import Fraction

from artifactsmmo_cli.ai.combat import MIN_WIN_SAMPLES

THRESHOLD_WINDOW_DAYS = 14
"""Days of `cycles` the threshold reads (spec §2 ruling: a cycle's refresh stays
cheap; older evidence is ignored)."""

FightCostRow = tuple[str, str, str, int]
"""`(action_class, action_repr, outcome, seconds)` of one cycle, one character,
in id order (`LearningStore.fight_cost_rows`)."""

_WIN = "ok"
_LOSS = "error:fight_lost"
_UPKEEP = frozenset({"RestAction", "MoveAction"})
_FIGHT = "FightAction"


def _monster(action_repr: str) -> str:
    """`Fight(cyclops)` -> `cyclops`."""
    return action_repr[len("Fight("):-1]


def win_thresholds_from_rows(rows: Sequence[FightCostRow]) -> dict[str, Fraction]:
    """Monster -> θ for every monster with at least MIN_WIN_SAMPLES won and
    MIN_WIN_SAMPLES lost fights whose window closed. A fight that is neither a
    win nor a loss (a cooldown or server error) opens no window; a monster whose
    fights all cost 0 s has no evidence."""
    totals: dict[tuple[str, bool], tuple[int, int]] = {}
    open_fight: tuple[str, bool] | None = None
    cost = 0
    for action_class, action_repr, outcome, seconds in rows:
        if action_class == _FIGHT:
            if open_fight is not None:
                total, count = totals.get(open_fight, (0, 0))
                totals[open_fight] = (total + cost, count + 1)
            open_fight = ((_monster(action_repr), outcome == _WIN)
                          if outcome in (_WIN, _LOSS) else None)
            cost = seconds
        elif action_class in _UPKEEP:
            cost += seconds
    thresholds: dict[str, Fraction] = {}
    for monster in sorted({m for m, _ in totals}):
        win_total, wins = totals.get((monster, True), (0, 0))
        loss_total, losses = totals.get((monster, False), (0, 0))
        if wins < MIN_WIN_SAMPLES or losses < MIN_WIN_SAMPLES:
            continue
        denominator = win_total * losses + loss_total * wins
        if denominator > 0:
            thresholds[monster] = Fraction(loss_total * wins, denominator)
    return thresholds
