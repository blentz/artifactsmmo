"""Differential: the LIVE gear rulers must agree EXACTLY with the proved HAND
Lean defs run by the oracle, over random nonneg inputs.

Two separate obligations live here:

* ``combat_raw`` (``gear_value_core.combat_raw``) vs ``Formal.GearValue.combatRaw``
  — the ECONOMICS layer's genuine-combat scalar, `strategic_value`'s input. NOT a
  gear ruler.
* ``gear_value(stats, Rank)`` (``ai/gear_value.py``) vs
  ``Formal.GearValue.rankValue`` — the ONE gear ruler on its monster-blind
  purpose. Because `rankValue` is DEFINITIONALLY `combatValue` at the canonical
  adversary, this differential also pins the adversary's own constants: changing
  `rank_adversary()`'s attack, its resistance, or its uniformity moves every armor
  value and diverges from the oracle immediately.

Exact-integer agreement is the soundness bridge: it pins the Python arithmetic to
the same defs `rawSum_decomp` / `rankValue_eq_combatValue_canonical` and the two
ordering theorems are proved about (the teeth behind the mutation gate).
NO `unique=True` — the strategies sample independently so summands can repeat.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.elements import ELEMENTS
from artifactsmmo_cli.ai.gear_value import gear_value
from artifactsmmo_cli.ai.gear_value_core import Rank, combat_raw
from artifactsmmo_cli.ai.item_catalog import ItemStats
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


_elem4 = st.lists(_stat, min_size=len(ELEMENTS), max_size=len(ELEMENTS))


def _item_block(stats: ItemStats, slot_fits: int) -> list[int]:
    """The 18-int Lean `Item` block Rank now reads — the SAME block the Combat
    purpose reads, which is the whole content of the unification."""
    return [
        0, stats.level, slot_fits,
        *[stats.attack.get(e, 0) for e in ELEMENTS],
        *[stats.resistance.get(e, 0) for e in ELEMENTS],
        stats.critical_strike,
        stats.hp_restore + stats.hp_bonus + stats.wisdom + stats.prospecting
        + stats.inventory_space + stats.haste + stats.lifesteal + stats.combat_buff,
        stats.dmg,
        *[stats.dmg_elements.get(e, 0) for e in ELEMENTS],
    ]


@settings(max_examples=400, deadline=None)
@given(
    attack=_elem4, resistance=_elem4, dmg_elements=_elem4,
    dmg=_stat, critical_strike=_stat, hp_restore=_stat, hp_bonus=_stat,
    wisdom=_stat, prospecting=_stat, inventory_space=_stat, haste=_stat,
    lifesteal=_stat, combat_buff=_stat,
    type_=st.sampled_from(["weapon", "body_armor", "amulet", "utility", "bag"]),
    subtype=st.sampled_from(["", "tool", "dagger", "potion"]),
)
def test_rank_matches_oracle(attack, resistance, dmg_elements, dmg, critical_strike,
                             hp_restore, hp_bonus, wisdom, prospecting,
                             inventory_space, haste, lifesteal, combat_buff,
                             type_, subtype):
    """`gear_value(stats, Rank)` ≡ `Formal.GearValue.rankValue`.

    Diverges on: a changed canonical-adversary attack or resistance, a
    non-uniform adversary, a dropped `flat_utility` summand (including the
    `hp_restore` that joined it), a dropped defense or offense term, the weapon
    branch's `2 *` scale, and the `nonToolBonus` (subtype == "tool" is the only
    branch that zeroes it)."""
    stats = ItemStats(
        code="x", level=1, type_=type_, subtype=subtype,
        attack=dict(zip(ELEMENTS, attack, strict=True)),
        resistance=dict(zip(ELEMENTS, resistance, strict=True)),
        dmg_elements=dict(zip(ELEMENTS, dmg_elements, strict=True)),
        dmg=dmg, critical_strike=critical_strike, hp_restore=hp_restore,
        hp_bonus=hp_bonus, wisdom=wisdom, prospecting=prospecting,
        inventory_space=inventory_space, haste=haste, lifesteal=lifesteal,
        combat_buff=combat_buff,
    )
    is_weapon = 1 if type_ == "weapon" else 0
    is_tool = 1 if subtype == "tool" else 0
    py = gear_value(stats, Rank)
    lean = run_oracle("rank_value",
                      [[is_weapon, is_tool, *_item_block(stats, 1)]])[0]["value"]
    assert py == lean
