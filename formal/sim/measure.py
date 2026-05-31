"""Python port of `Formal.Liveness.Measure` — byte-equivalent six-tuple.

Mirrors `formal/Formal/Liveness/Measure.lean`. Each slot computes the SAME
Nat-saturating subtraction the Lean version does, so the differential test
can assert lex-decrease using the production `WorldState`.

The xp curve is consulted via a callable injected at call time (not imported
globally) so the differential test can stub it deterministically. The Lean
axiom `xpToNextLevel` corresponds to this callable; both must satisfy
`xpToNextLevel(L) > 0` for `L in [1, 49]` (LIV-001).

ONE behavioural class per file: this module is pure data + functions, no
behavioural classes — exempt per CLAUDE.md.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.world_state import WorldState


# Mirrors `bankPressureThreshold` in Measure.lean: `inventoryMax * 4 / 5`.
def bank_pressure_threshold(inventory_max: int) -> int:
    """Floor of `inventory_max * 4 / 5` — matches Lean Nat division."""
    return (inventory_max * 4) // 5


def _sat_sub(a: int, b: int) -> int:
    """Saturating natural subtraction (Lean `Nat.sub`)."""
    return a - b if a > b else 0


@dataclass(frozen=True)
class Measure:
    """Lex measure tuple, ordered most-significant first (slot 1 → slot 6)."""

    level_deficit: int
    xp_deficit: int
    task_cycles: int
    skill_xp_deficit_projected: int
    bank_pressure: int
    hp_deficit: int

    def as_tuple(self) -> tuple[int, int, int, int, int, int]:
        return (self.level_deficit, self.xp_deficit, self.task_cycles,
                self.skill_xp_deficit_projected, self.bank_pressure,
                self.hp_deficit)


def measure(
    state: WorldState,
    xp_to_next_level: int,
    target_skill_xp: int,
    projected_skill_xp_delta: int,
) -> Measure:
    """Compute the Lean `Measure.measure` projection on a `WorldState`.

    `xp_to_next_level` is the value of the LIV-001 axiom at `state.level`.
    `target_skill_xp` / `projected_skill_xp_delta` are the single-skill
    scalars described in `Measure.lean` (the headline operates on one
    LevelSkillGoal at a time).
    """
    return Measure(
        level_deficit=_sat_sub(50, state.level),
        xp_deficit=_sat_sub(xp_to_next_level, state.xp),
        task_cycles=_sat_sub(state.task_total, state.task_progress),
        skill_xp_deficit_projected=_sat_sub(target_skill_xp,
                                            projected_skill_xp_delta),
        bank_pressure=_sat_sub(state.inventory_used,
                               bank_pressure_threshold(state.inventory_max)),
        hp_deficit=_sat_sub(state.max_hp, state.hp),
    )


def lex_lt(a: Measure, b: Measure) -> bool:
    """Strict lex order — mirrors `measureLt` in `Measure.lean`."""
    return a.as_tuple() < b.as_tuple()
