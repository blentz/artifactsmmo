"""Differential: the LIVE unified gear-value core (`gear_value_core.combat_raw` /
`rank_value`) must agree EXACTLY with the proved HAND Lean defs
(`Formal.GearValue.combatRaw` / `rankValue`) run by the oracle, over random
nonneg inputs.

Exact-integer agreement is the soundness bridge: it pins the Python arithmetic to
the same defs the `rawSum_decomp` / `rank_eq_equipValue` theorems are proved about,
so a dropped `combat_raw` summand, a dropped `nonToolBonus`, or a changed `2 *`
scale diverges from the oracle and is caught (the teeth behind the mutation gate).
NO `unique=True` — the strategies sample independently so summands can repeat.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.gear_value_core import combat_raw, rank_value
from formal.diff.oracle_client import run_oracle

_stat = st.integers(min_value=0, max_value=500)


@settings(max_examples=400)
@given(
    attack=_stat, resistance=_stat, hp_restore=_stat, hp_bonus=_stat, dmg=_stat,
    critical_strike=_stat, lifesteal=_stat, combat_buff=_stat,
)
def test_combat_raw_matches_oracle(attack, resistance, hp_restore, hp_bonus, dmg,
                                   critical_strike, lifesteal, combat_buff):
    """`combat_raw` (8-summand genuine-combat signal) ≡ `Formal.GearValue.combatRaw`.
    Dropping ANY of the 8 summands diverges here."""
    args = [attack, resistance, hp_restore, hp_bonus, dmg, critical_strike,
            lifesteal, combat_buff]
    py = combat_raw(*args)
    lean = run_oracle("combat_raw", [args])[0]["value"]
    assert py == lean


@settings(max_examples=400)
@given(
    combat_raw_value=_stat, wisdom=_stat, prospecting=_stat, inventory_space=_stat,
    haste=_stat, subtype=st.sampled_from(["weapon", "tool", "body_armor", "ring"]),
)
def test_rank_value_matches_oracle(combat_raw_value, wisdom, prospecting,
                                   inventory_space, haste, subtype):
    """`rank_value` (the unified Rank ruler) ≡ `Formal.GearValue.rankValue`.
    Catches a dropped `2 *` scale and the `nonToolBonus` term (subtype == "tool"
    is the only branch that zeroes the bonus)."""
    py = rank_value(combat_raw_value, wisdom, prospecting, inventory_space, haste,
                    subtype)
    is_tool = 1 if subtype == "tool" else 0
    lean = run_oracle("rank_value",
                      [[combat_raw_value, wisdom, prospecting, inventory_space,
                        haste, is_tool]])[0]["value"]
    assert py == lean
