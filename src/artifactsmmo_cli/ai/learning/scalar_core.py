"""Pure cores extracted from `scalarizer.py` for formal verification.

These functions contain NO I/O, store, or game_data dependencies — they are
total functions of their numeric/collection arguments, mirroring exactly the
arithmetic of `scalar_yield` and the `coins_spent` derivation in
`expected_coin_value_with_prices`. The impure inputs (which skills are active,
the observed coin value) are lifted to plain parameters so the cores can be
proved in Lean and differentially tested.

EXACT CORE + FLOAT BOUNDARY (mechanical-extraction P3c):
========================================================

The decision arithmetic lives in `scalar_yield_exact`, a `Fraction`-only core
mechanically extracted to `formal/Formal/Extracted/ScalarCore.lean` and
bridged against the proved `Formal.Scalarizer.scalarYield` (over `Rat`, where
every operation is exact).

`scalar_yield_pure` is the preserved public float boundary (production passes
the float constants 0.2 / 2.0 / 100.0 / 1.0 from `scalarizer.py`): it converts
EVERY input to `Fraction` exactly (`Fraction(float)` is the exact binary
expansion — e.g. 0.2 becomes the precise double it always was), runs the exact
core, and converts the single result back to `float` at the end. The scalar is
therefore the correctly-rounded double of the EXACT rational value — ONE
rounding at the boundary instead of one per operation (results can differ from
the former per-op float arithmetic in the last ULPs; every caller compares /
thresholds scalars, none pins bit patterns). That final `float(...)` is the
trusted seam OUTSIDE the proved core; the differential suite samples it.

Division caveat (mirrors the extracted `Rat` image): `gold_per_xp` must be
non-zero — production passes 100.0; Lean's total `Rat` division reads `x / 0`
as 0 where Python raises `ZeroDivisionError`, so divisors stay non-zero by
construction on every reachable input.

Spec: docs/superpowers/specs/2026-05-18-strategic-reasoning-design.md §3.
"""

from collections.abc import Collection, Mapping
from fractions import Fraction


def scalar_yield_exact(
    char_xp: Fraction,
    level: int,
    skill_xp: Mapping[str, Fraction],
    active_skills: frozenset[str],
    gold: Fraction,
    tasks_coins: Fraction,
    coin_value: Fraction,
    baseline_w: Fraction,
    relevant_w: Fraction,
    gold_per_xp: Fraction,
    char_scalar: Fraction,
) -> Fraction:
    """Collapse the numeric components of a Yield into a single EXACT scalar.

    Mirrors `scalar_yield` EXACTLY, over the rationals:

        char_xp * char_scalar * (level + 1)
      + Σ_skill skill_xp[s] * (relevant_w if s in active_skills else baseline_w)
      + gold / gold_per_xp
      + tasks_coins * coin_value / gold_per_xp

    `active_skills` is the lifted impure input (the caller computes it from
    `game_data.active_gathering_skills(...)`); `coin_value` is likewise the
    lifted observed/default coin valuation. Membership in `active_skills` is
    order-independent, so the unordered set is safe for the extracted image."""
    char_xp_component = char_xp * char_scalar * Fraction(level + 1)
    skill_xp_component = Fraction(0)
    for skill_name, delta in skill_xp.items():
        skill_xp_component = skill_xp_component + delta * (
            relevant_w if skill_name in active_skills else baseline_w)
    gold_component = gold / gold_per_xp
    coin_component = tasks_coins * coin_value / gold_per_xp
    return char_xp_component + skill_xp_component + gold_component + coin_component


def scalar_yield_pure(
    char_xp: float,
    level: int,
    skill_xp: Mapping[str, float],
    active_skills: Collection[str],
    gold: float,
    tasks_coins: float,
    coin_value: float,
    *,
    baseline_w: float,
    relevant_w: float,
    gold_per_xp: float,
    char_scalar: float,
) -> float:
    """Public float boundary of the scalar yield (callers untouched).

    Every input is lifted to an exact `Fraction` (exact for float, int and
    Fraction arguments alike), the proved exact core computes the rational
    scalar, and the single `float(...)` below rounds once at the boundary —
    see the module header for the exactness argument."""
    total = scalar_yield_exact(
        Fraction(char_xp),
        level,
        {name: Fraction(xp) for name, xp in skill_xp.items()},
        frozenset(active_skills),
        Fraction(gold),
        Fraction(tasks_coins),
        Fraction(coin_value),
        Fraction(baseline_w),
        Fraction(relevant_w),
        Fraction(gold_per_xp),
        Fraction(char_scalar),
    )
    return float(total)


def coins_spent_from_delta(received: int, delta_inv_used: int) -> int:
    """Coins spent on a TaskExchange, derived from the inventory delta.

    A TaskExchange adds `received` items and removes the coins spent, so
    `delta_inv_used = received - coins_spent`, hence
    `coins_spent = received - delta_inv_used`. This is the exact inverse of how
    the delta was recorded (no sign error)."""
    return received - delta_inv_used
