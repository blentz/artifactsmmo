"""Pure cores extracted from `scalarizer.py` for formal verification.

These functions contain NO I/O, store, or game_data dependencies — they are
total functions of their numeric/collection arguments, mirroring exactly the
arithmetic of `scalar_yield` and the `coins_spent` derivation in
`expected_coin_value_with_prices`. The impure inputs (which skills are active,
the observed coin value) are lifted to plain parameters so the cores can be
proved in Lean and differentially tested.

Spec: docs/superpowers/specs/2026-05-18-strategic-reasoning-design.md §3.
"""

from collections.abc import Collection, Mapping


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
    """Collapse the numeric components of a Yield into a single scalar.

    Mirrors `scalar_yield` EXACTLY:

        char_xp * char_scalar * (level + 1)
      + Σ_skill skill_xp[s] * (relevant_w if s in active_skills else baseline_w)
      + gold / gold_per_xp
      + tasks_coins * coin_value / gold_per_xp

    `active_skills` is the lifted impure input (the caller computes it from
    `game_data.active_gathering_skills(...)`); `coin_value` is likewise the
    lifted observed/default coin valuation.
    """
    char_xp_component = char_xp * char_scalar * (level + 1)

    # Start the accumulator at integer 0 (not 0.0) so the core stays type-generic:
    # with float inputs the sum is float (production, unchanged); with exact
    # `fractions.Fraction` inputs/weights every term stays an exact Fraction, which
    # the differential test relies on to compare against the Lean `Rat` oracle.
    skill_xp_component = 0
    for skill_name, delta in skill_xp.items():
        weight = relevant_w if skill_name in active_skills else baseline_w
        skill_xp_component += delta * weight

    gold_component = gold / gold_per_xp
    coin_component = tasks_coins * coin_value / gold_per_xp

    return char_xp_component + skill_xp_component + gold_component + coin_component


def coins_spent_from_delta(received: int, delta_inv_used: int) -> int:
    """Coins spent on a TaskExchange, derived from the inventory delta.

    A TaskExchange adds `received` items and removes the coins spent, so
    `delta_inv_used = received - coins_spent`, hence
    `coins_spent = received - delta_inv_used`. This is the exact inverse of how
    the delta was recorded (no sign error)."""
    return received - delta_inv_used
