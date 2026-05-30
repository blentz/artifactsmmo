"""Phase-17 — wire the proved `scalar_yield` projection into discretionary goal
priorities via the survival-safe `clamp_into_band`.

Both ``PursueTaskGoal`` and ``GatherMaterialsGoal`` are discretionary goals
(no survival role). Their learned-yield bonus is routed through
``clamp_into_band`` so the Phase-1 invariant holds: a discretionary goal's
priority can NEVER reach the survival floor (70). The per-goal band ceilings
defined here all sit strictly below 70.

The bonus formula matches the Phase-1 pattern in ``grind_character_xp.py``:

    bonus = max(0, scalar_yield - BASELINE) * BAND_GAIN

Subtracting ``BASELINE`` is a "lift above baseline" so a goal yielding the
default scalar adds 0 priority; the ``max(0, ...)`` floors negative scalars
(an unlucky observed-negative run can't subtract priority below the floor —
``clamp_into_band`` would handle that too, but the explicit floor keeps the
formula's intent obvious at the callsite).
"""
from fractions import Fraction

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.projections import Yield, expected_yield_per_cycle
from artifactsmmo_cli.ai.learning.scalarizer import scalar_yield
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

BASELINE_SCALAR = 1.0
"""Scalar baseline subtracted before scaling. A goal whose observed scalar is
~1 (one character-XP-equivalent per cycle) earns 0 bonus; only above-baseline
yields lift the priority."""

BAND_GAIN = 1.0
"""Priority points per unit of scalar above baseline. Tuned so a modestly
above-baseline goal (scalar=2-15) lands inside the band without saturating
the ceiling in the typical case."""


def yield_bonus(
    yield_: Yield,
    state: WorldState,
    game_data: GameData,
    history: LearningStore | None,
) -> Fraction:
    """Compute the band-clamp bonus (in priority units) for a learned ``Yield``.

    Returns Fraction(0) when the yield has insufficient samples. Otherwise
    returns ``max(0, scalar - BASELINE_SCALAR) * BAND_GAIN`` as a Fraction so
    downstream arithmetic with ``clamp_into_band`` stays exact (bit-equivalent
    to the Lean ``Rat`` model)."""
    if yield_.sample_count == 0:
        return Fraction(0)
    scalar = scalar_yield(yield_, state, game_data, history)
    lifted = scalar - BASELINE_SCALAR
    if lifted <= 0.0:
        return Fraction(0)
    return Fraction(lifted) * Fraction(BAND_GAIN)


def yield_bonus_for_goal(
    goal_repr: str,
    state: WorldState,
    game_data: GameData,
    history: LearningStore | None,
) -> Fraction:
    """Fetch the per-cycle yield for ``goal_repr`` from history and convert
    it to a band-clamp bonus. ``Fraction(0)`` when history is None or there
    are no observed cycles for the goal."""
    if history is None:
        return Fraction(0)
    yield_ = expected_yield_per_cycle(goal_repr, history)
    return yield_bonus(yield_, state, game_data, history)
