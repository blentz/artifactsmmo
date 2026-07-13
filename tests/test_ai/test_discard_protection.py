"""Discard protection semantics: the keep authority licenses the DELETE, nothing else.

DISCARD is the LAST-RESORT route (`disposal_route`: recycle > deposit > delete) and
its DELETE arm is the only IRREVERSIBLE one that recovers nothing at all. So, exactly
like RECYCLE (Task 7) and SELL (Task 8), the licensed quantity is the CONJUNCTION of
the two caps:

    surplus = min(bankable, destroyable)

  * `destroyable` (bag+bank beyond `keep_owned`) LICENSES the destruction — it is
    irreversible, so it answers to OWNERSHIP, and bank copies count toward satisfying
    the cap because they are still owned.
  * `bankable` (bag beyond `keep_in_bag`) BOUNDS it to the copies that may leave the
    BAG at all. `KeepReason.WORKING_KIT` / `COMBAT_WEAPON` / `GOAL_MATERIALS` /
    `COMMITTED_RECIPE` / `HEALING_CONSUMABLE` live in the in-bag ladder, and
    `destroyable` alone would DELETE the one tool the gather re-arm is about to equip.

Before this migration the discard path sourced its floor from
`inventory_caps.useful_quantity_cap` (a "how many are USEFUL" heuristic) merged with
`guards.active_profile` — a recipe closure over the `target_gear | target_tools`
CODE-SET, i.e. "keep ALL copies of every BiS gear/tool code". That is the blanket this
epic exists to kill.

The pressure/watermark logic is UNCHANGED and still decides WHEN to shed
(`inventory_caps.overstocked_items` -> the proved `overstock_excess` core): below the
watermark the bag has real free slots and NOTHING is overstock.
"""

from artifactsmmo_cli.ai.discard_surplus import discardable_surplus
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
    gd = GameData()
    gd._item_stats = {
        "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon",
                                attack={"earth": 3}, skill_effects={"woodcutting": -10},
                                crafting_skill="weaponcrafting", crafting_level=1),
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   attack={"fire": 6},
                                   crafting_skill="weaponcrafting", crafting_level=1),
        "copper_helmet": ItemStats(code="copper_helmet", level=1, type_="helmet",
                                   crafting_skill="gearcrafting", crafting_level=1),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
        "golden_egg": ItemStats(code="golden_egg", level=1, type_="resource"),
        "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_="consumable",
                                    hp_restore=60),
        TASKS_COIN_CODE: ItemStats(code=TASKS_COIN_CODE, level=1, type_="currency"),
    }
    gd._crafting_recipes = {"copper_helmet": {"copper_bar": 6},
                            "copper_axe": {"copper_bar": 6}}
    return gd


def _pressured(**kw: object):
    """A bag at 100% QUANTITY pressure — the DISCARD watermark (0.85) is open, so
    `overstocked_items` is live. Below it nothing is overstock, by design."""
    inventory: dict[str, int] = kw.pop("inventory")  # type: ignore[assignment]
    used = sum(inventory.values())
    return make_state(level=10, inventory=inventory, inventory_max=used,
                      inventory_slots_max=max(1, len(inventory)), **kw)


# --- the migration itself ---------------------------------------------------


def test_unprofiled_tool_hoard_keeps_ONE_and_discards_the_REST() -> None:
    """Profiles-aware, `copper_axe` in no active profile: the authority keeps the
    ONE copy the gather re-arm wears (WORKING_KIT / COMBAT_WEAPON) and licenses the
    other 17 — a QUANTITY, never the `target_tools` blanket that hid all 18."""
    gd = _gd()
    state = _pressured(inventory={"copper_axe": 18}, skills={"weaponcrafting": 2})
    ctx = _ctx(gear_keep={"copper_helmet": 1})
    assert discardable_surplus(state, gd, ctx) == {"copper_axe": 17}


def test_ferried_working_tool_is_never_discarded() -> None:
    """One axe in the bag (ferried by WithdrawTools, equipped next cycle), 17 in the
    bank: `keep_owned` is 1 so `destroyable` is 17 — and every one of those 17 is
    UNREACHABLE from the bag. A bare `destroyable` DELETES the working copy;
    `bankable` (bag 1 − keep_in_bag 1 = 0) is what stops it."""
    gd = _gd()
    state = _pressured(inventory={"copper_axe": 1}, bank_items={"copper_axe": 17},
                       skills={"weaponcrafting": 2})
    assert discardable_surplus(state, gd, _ctx(gear_keep={"copper_helmet": 1})) == {}


def test_bank_copies_satisfy_the_owned_cap_but_do_not_widen_the_bag_licence() -> None:
    """6 axes in the bag + 12 in the bank: `keep_owned` 1 → 17 destroyable, but only
    6 are reachable and one of THOSE is the working copy. min(bankable 5, 17) = 5."""
    gd = _gd()
    state = _pressured(inventory={"copper_axe": 6}, bank_items={"copper_axe": 12},
                       skills={"weaponcrafting": 2})
    assert discardable_surplus(state, gd,
                               _ctx(gear_keep={"copper_helmet": 1})) == {"copper_axe": 5}


# --- NO REGRESSION on destruction (the irreversible route) -------------------


def test_equipped_copy_is_never_discarded() -> None:
    gd = _gd()
    state = _pressured(inventory={"copper_helmet": 1},
                       equipment={"helmet_slot": "copper_helmet"})
    assert discardable_surplus(state, gd, _ctx()) == {}
    spares = _pressured(inventory={"copper_helmet": 9},
                        equipment={"helmet_slot": "copper_helmet"})
    assert discardable_surplus(spares, gd, _ctx()) == {"copper_helmet": 8}


def test_profile_gear_demand_is_a_cap_not_a_blanket() -> None:
    gd = _gd()
    state = _pressured(inventory={"copper_helmet": 12})
    assert discardable_surplus(state, gd, _ctx(gear_keep={"copper_helmet": 2})) == {
        "copper_helmet": 10}


def test_recipe_demand_is_never_discarded() -> None:
    """RECIPE_DEMAND: the copper_bar the axe/helmet recipes consume is not deleted."""
    gd = _gd()
    state = _pressured(inventory={"copper_bar": 6})
    assert discardable_surplus(state, gd, _ctx()) == {}


def test_active_task_item_is_never_discarded() -> None:
    gd = _gd()
    state = _pressured(inventory={"golden_egg": 11}, task_code="golden_egg",
                       task_type="items", task_progress=0, task_total=5)
    assert discardable_surplus(state, gd, _ctx()) == {"golden_egg": 6}


def test_currency_is_never_discarded() -> None:
    """CURRENCY is the one `KEEP_ALL` reason. Deleting coins is unrecoverable."""
    gd = _gd()
    state = _pressured(inventory={TASKS_COIN_CODE: 250})
    assert discardable_surplus(state, gd, _ctx()) == {}


def test_last_combat_weapon_is_never_discarded() -> None:
    gd = _gd()
    state = _pressured(inventory={"copper_dagger": 1})
    assert discardable_surplus(state, gd, _ctx(gear_keep={"copper_helmet": 1})) == {}


def test_healing_stock_is_never_discarded() -> None:
    """HEALING_CONSUMABLE is an IN-BAG reason, so `bankable` (and hence the `min`)
    protects the heal stock from the DELETE — banking it is the correct move."""
    gd = _gd()
    state = _pressured(inventory={"cooked_chicken": 4})
    assert discardable_surplus(state, gd, _ctx()) == {}


def test_goal_materials_are_never_discarded() -> None:
    """GOAL_MATERIALS (the active objective step's `needed` map): the gather pile the
    step is accumulating is not deleted out from under it."""
    gd = _gd()
    state = _pressured(inventory={"copper_bar": 40})
    assert discardable_surplus(state, gd, _ctx(step_profile={"copper_bar": 40})) == {}


def test_committed_recipe_inputs_are_never_discarded() -> None:
    """COMMITTED_RECIPE: the in-flight craft's own transitive inputs."""
    gd = _gd()
    state = _pressured(inventory={"copper_bar": 6}, crafting_target="copper_helmet")
    assert discardable_surplus(state, gd, _ctx()) == {}


# --- the pressure gate (unchanged: it decides WHEN, not WHAT) ----------------


def test_nothing_is_overstock_below_the_watermark() -> None:
    """SPACE-DRIVEN (spec 2026-06-07): with real free slots NOTHING is overstock, even
    a hoard the authority would license. The watermark decides WHEN to shed."""
    gd = _gd()
    roomy = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 18}, inventory_max=200)
    assert discardable_surplus(roomy, gd, _ctx(gear_keep={"copper_helmet": 1})) == {}
