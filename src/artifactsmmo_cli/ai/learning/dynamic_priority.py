"""Phase G-F dynamic priority: convert observed yield into a priority bonus.

Goals call `learned_priority_bonus` from their `priority()` to add a
projection-driven term on top of their hardcoded base. The base keeps the
survival floor (RestoreHP=80, UnlockBank=70 must always dominate); the bonus
is the scalarized expected yield, scaled by sample confidence.

Cold start: zero bonus, original priority preserved.
Warm: bonus proportional to confidence (0→1 over WARMUP_MIN_SAMPLES * 3 cycles).
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.projections import WARMUP_MIN_SAMPLES, expected_yield_per_cycle
from artifactsmmo_cli.ai.learning.scalarizer import scalar_yield
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


CONFIDENCE_CAP_SAMPLES = WARMUP_MIN_SAMPLES * 3
"""Number of observed cycles where confidence reaches 1.0. Below this, the
bonus is scaled linearly."""

DEFAULT_BONUS_WEIGHT = 5.0
"""Multiplier on scalar_yield to convert it into a priority bonus. Tuned so
a goal yielding ~3 char-XP/cycle at level 1 adds about 30 priority — enough
to outrank a fixed base of 30 if observed throughput is twice the baseline.
"""


def learned_priority_bonus(
    goal_repr: str,
    state: WorldState,
    game_data: GameData,
    history: LearningStore | None,
    weight: float = DEFAULT_BONUS_WEIGHT,
) -> float:
    """Return a non-negative bonus to add to a goal's hardcoded base priority.

    Returns 0.0 when:
      - history is None (no store wired)
      - the goal has no observed cycles
      - the goal's observed scalar yield is non-positive

    Bonus = scalar_yield(observed) * weight * confidence
    where confidence ramps linearly from 0 at zero samples to 1.0 at
    CONFIDENCE_CAP_SAMPLES.
    """
    if history is None:
        return 0.0
    observed = expected_yield_per_cycle(goal_repr, history)
    if observed.sample_count == 0:
        return 0.0
    scalar = scalar_yield(observed, state, game_data, history)
    if scalar <= 0:
        return 0.0
    confidence = min(1.0, observed.sample_count / CONFIDENCE_CAP_SAMPLES)
    return scalar * weight * confidence
