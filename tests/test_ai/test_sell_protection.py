"""Sell protection semantics: the keep authority licenses the sale, nothing else.

A sale takes copies OUT OF THE BAG *and* out of OWNERSHIP, and it is
IRREVERSIBLE — so, exactly like RECYCLE (item-protection-authority epic, Task 7),
the licensed quantity is `min(bankable, destroyable)`:

  * `destroyable` (bag+bank beyond `keep_owned`) LICENSES the destruction. Bank
    copies count toward satisfying it — they are still owned.
  * `bankable` (bag beyond `keep_in_bag`) bounds it to the copies that may leave
    the BAG at all. `KeepReason.WORKING_KIT` / `COMBAT_WEAPON` live in the in-bag
    ladder: the ONE tool the gather re-arm is about to equip must not be sold out
    from under it, and `bankable` is what stops that.

Before this migration the sell path sourced its surplus from
`inventory_caps.useful_quantity_cap`, which in profiles-aware mode gives an
un-profiled equippable a cap of ZERO — so a bag of 18 `copper_axe` (the live
2026-07-12 hoard) sold ALL EIGHTEEN, the working tool included.
"""

from artifactsmmo_cli.ai.accumulation_sell import (
    sellable_accumulation,
    sellable_surplus,
    worst_accumulation_steps,
)
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE
from tests.test_ai.fixtures import make_state


def _ctx(**kw: object) -> SelectionContext:
    base: dict[str, object] = dict(
        bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=1, combat_monster=None,
        gear_review_active=False)
    base.update(kw)
    return SelectionContext(**base)  # type: ignore[arg-type]


def _gd() -> GameData:
    """One vendor who buys everything the tests hold. A PERMANENT NPC (no event
    code) — every gold merchant in the live catalog is an EVENT merchant, and a
    dormant one is not a route at all (`NpcSellAction.is_applicable`)."""
    gd = GameData()
    gd._item_stats = {
        "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon",
                                attack={"earth": 3}, skill_effects={"woodcutting": -10},
                                crafting_skill="weaponcrafting", crafting_level=1,
                                tradeable=True),
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   attack={"fire": 6},
                                   crafting_skill="weaponcrafting", crafting_level=1,
                                   tradeable=True),
        "copper_helmet": ItemStats(code="copper_helmet", level=1, type_="helmet",
                                   crafting_skill="gearcrafting", crafting_level=1,
                                   tradeable=True),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                tradeable=True),
        "golden_egg": ItemStats(code="golden_egg", level=1, type_="resource",
                                tradeable=True),
        "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_="consumable",
                                    hp_restore=60, tradeable=True),
        TASKS_COIN_CODE: ItemStats(code=TASKS_COIN_CODE, level=1, type_="currency",
                                   tradeable=True),
    }
    gd._crafting_recipes = {"copper_helmet": {"copper_bar": 6},
                            "copper_axe": {"copper_bar": 6}}
    gd._npc_sell_prices = {"vendor": {code: 3 for code in gd._item_stats}}
    gd._npc_locations = {"vendor": (1, 1)}
    return gd


# --- the migration itself ---------------------------------------------------


def test_unprofiled_tool_hoard_keeps_ONE_and_sells_the_REST() -> None:
    """THE BUG. Profiles-aware, `copper_axe` in no active profile: the old
    `useful_quantity_cap` cap was ZERO, so all 18 copies — the WORKING axe
    included — were sold. The authority keeps the one the re-arm wears."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 18})
    ctx = _ctx(gear_keep={"copper_helmet": 1})
    assert sellable_surplus(state, gd, ctx) == {"copper_axe": 17}
    assert sellable_accumulation(state, gd, ctx) == {"copper_axe": 17}


def test_working_tool_survives_when_the_bank_holds_the_spares() -> None:
    """`destroyable` ALONE sells the working tool: 6 axes in the bag + 12 in the
    bank is `keep_owned` 1 → 17 destroyable, and 6 of those are the only copies
    the seller can reach — including the ONE the bag must keep. `bankable`
    (bag 6 − `keep_in_bag` 1 = 5) is what stops it."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 6},
                       bank_items={"copper_axe": 12})
    ctx = _ctx(gear_keep={"copper_helmet": 1})
    assert sellable_surplus(state, gd, ctx) == {"copper_axe": 5}


def test_ferried_working_tool_is_never_sold() -> None:
    """One axe in the bag (ferried by WithdrawTools, equipped next cycle), 17 in
    the bank: nothing is sellable — the only reachable copy is the working one."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 1},
                       bank_items={"copper_axe": 17})
    assert sellable_surplus(state, gd, _ctx(gear_keep={"copper_helmet": 1})) == {}


def test_equipped_copy_is_never_sold() -> None:
    """EQUIPPED is worth 1 on the OWNED ladder; the worn copy is not in the
    inventory count at all, so its bag spares are scrap like any other."""
    gd = _gd()
    state = make_state(level=10, inventory={"copper_helmet": 1},
                       equipment={"helmet_slot": "copper_helmet"})
    assert sellable_surplus(state, gd, _ctx()) == {}
    spares = make_state(level=10, inventory={"copper_helmet": 9},
                        equipment={"helmet_slot": "copper_helmet"})
    assert sellable_surplus(spares, gd, _ctx()) == {"copper_helmet": 8}


def test_last_combat_weapon_is_never_sold() -> None:
    """COMBAT_WEAPON: never sell the weapon you are swinging (and never the last
    one you own) — 1 copy on BOTH ladders."""
    gd = _gd()
    state = make_state(level=10, inventory={"copper_dagger": 1})
    assert sellable_surplus(state, gd, _ctx(gear_keep={"copper_helmet": 1})) == {}


def test_profile_gear_demand_is_a_cap_not_a_blanket() -> None:
    """GEAR_DEMAND keeps the demanded COUNT, not every copy of the code."""
    gd = _gd()
    state = make_state(level=10, inventory={"copper_helmet": 12})
    ctx = _ctx(gear_keep={"copper_helmet": 2})
    assert sellable_surplus(state, gd, ctx) == {"copper_helmet": 10}


def test_recipe_demand_is_never_sold() -> None:
    """RECIPE_DEMAND: material a known recipe consumes is not sold below its
    demand — selling the copper_bar the axe needs would be self-defeating."""
    gd = _gd()
    state = make_state(level=10, inventory={"copper_bar": 6})
    assert sellable_surplus(state, gd, _ctx()) == {}


def test_active_task_item_is_never_sold() -> None:
    """ACTIVE_TASK: the copies the task still owes stay; the surplus above them
    is sellable."""
    gd = _gd()
    state = make_state(level=10, inventory={"golden_egg": 11},
                       task_code="golden_egg", task_type="items",
                       task_progress=0, task_total=5)
    assert sellable_surplus(state, gd, _ctx()) == {"golden_egg": 6}


def test_currency_is_never_sellable() -> None:
    """CURRENCY is the one `KEEP_ALL` reason — task coins are never sold."""
    gd = _gd()
    state = make_state(level=10, inventory={TASKS_COIN_CODE: 250})
    assert sellable_surplus(state, gd, _ctx()) == {}
    assert sellable_accumulation(state, gd, _ctx()) == {}


def test_healing_stock_is_bankable_but_not_sellable() -> None:
    """HEALING_CONSUMABLE feeds the IN-BAG ladder only, so `keep_in_bag` (and
    hence `bankable`) protects the heal stock from the sale even though
    `keep_owned` licenses it — `min` is what makes that true."""
    gd = _gd()
    state = make_state(level=10, inventory={"cooked_chicken": 4})
    assert sellable_surplus(state, gd, _ctx()) == {}


def test_goal_materials_are_never_sold() -> None:
    """GOAL_MATERIALS (the active objective step's `needed` map) is an in-bag
    reason — the gather pile the step is accumulating is not sold out from
    under it."""
    gd = _gd()
    state = make_state(level=10, inventory={"copper_bar": 40})
    ctx = _ctx(step_profile={"copper_bar": 40})
    assert sellable_surplus(state, gd, ctx) == {}


# --- the ratio gate (unchanged policy, now over the AUTHORITY's keep) --------


def test_ratio_gate_holds_back_a_small_surplus_while_the_bank_can_take_it() -> None:
    """`sellable_accumulation` still only sheds a HOARD (>= ACCUM_MULT x keep):
    banking is reversible and a sale is not, so a 2x pile banks instead."""
    gd = _gd()
    state = make_state(level=10, inventory={"copper_helmet": 2})
    ctx = _ctx(gear_keep={"copper_helmet": 1})
    assert sellable_surplus(state, gd, ctx) == {"copper_helmet": 1}
    assert sellable_accumulation(state, gd, ctx) == {}
    assert worst_accumulation_steps(state, gd, ctx) == 0


def test_ratio_gate_is_measured_against_the_AUTHORITY_keep_not_zero() -> None:
    """The gate is `held >= ACCUM_MULT x keep`, and `keep` is the AUTHORITY's
    (`held - surplus`), never 0. 6 helmets against a profile demand of 2: the
    licence is 4, but 6 < 5*2, so the bank takes them — a gate that read keep as 0
    would degenerate to `held >= 5` and sell a 3x pile the profile still wants."""
    gd = _gd()
    state = make_state(level=10, inventory={"copper_helmet": 6})
    ctx = _ctx(gear_keep={"copper_helmet": 2})
    assert sellable_surplus(state, gd, ctx) == {"copper_helmet": 4}
    assert sellable_accumulation(state, gd, ctx) == {}
    assert worst_accumulation_steps(state, gd, ctx) == 0
    # 10 held clears 5*2 → the same licence is now sold.
    ten = make_state(level=10, inventory={"copper_helmet": 10})
    assert sellable_accumulation(ten, gd, ctx) == {"copper_helmet": 8}


def test_worst_steps_is_geometric_over_the_authority_keep() -> None:
    gd = _gd()
    state = make_state(level=10, inventory={"copper_helmet": 40})
    ctx = _ctx(gear_keep={"copper_helmet": 1})
    assert sellable_accumulation(state, gd, ctx) == {"copper_helmet": 39}
    assert worst_accumulation_steps(state, gd, ctx) == 5
