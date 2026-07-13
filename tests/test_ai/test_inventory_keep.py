from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.inventory_keep import (
    IN_BAG_REASONS,
    KEEP_ALL,
    OWNED_REASONS,
    KeepReason,
    bankable,
    destroyable,
    keep_in_bag,
    keep_owned,
    reason_quantity,
)
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from tests.test_ai.fixtures import make_state


def _ctx(**kw: object) -> SelectionContext:
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None,
                gear_review_active=False)
    base.update(kw)
    return SelectionContext(**base)


def _gd() -> GameData:
    """Two-level recipe chain, deliberately: `copper_axe <- 6 copper_bar` and
    `copper_bar <- 6 copper_ore`. A depth-1 fixture cannot see the difference
    between a DIRECT and a TRANSITIVE COMMITTED_RECIPE demand — that blind spot
    hid a bug where the task's own deep sub-material was bankable.

    `copper_dagger <- 8 copper_ore` is a SECOND, DISJOINT root over the same
    leaf material: one root alone cannot see the difference between combining
    the two committed roots with `max` and with `sum`."""
    gd = GameData()
    gd._item_stats = {
        "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon",
                                subtype="tool", skill_effects={"woodcutting": -10},
                                crafting_skill="weaponcrafting", crafting_level=1),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                crafting_skill="mining", crafting_level=1),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   subtype="dagger", attack={"attack_fire": 12}),
        "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_="consumable",
                                    hp_restore=50),
        "apple": ItemStats(code="apple", level=1, type_="consumable", hp_restore=20),
    }
    gd._crafting_recipes = {
        "copper_axe": {"copper_bar": 6},
        "copper_bar": {"copper_ore": 6},
        "copper_dagger": {"copper_ore": 8},
    }
    gd._workshop_locations = {"weaponcrafting": (3, 1), "mining": (1, 5)}
    return gd


def test_working_kit_keeps_ONE_in_bag_not_the_hoard():
    """The axe bug, at the authority level: kit is a QUANTITY of 1, so 18 held
    leaves 17 bankable. A blanket would leave 0."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 18})
    ctx = _ctx()
    assert reason_quantity(KeepReason.WORKING_KIT, "copper_axe", state, gd, ctx) == 1
    assert keep_in_bag("copper_axe", state, gd, ctx) == 1
    assert bankable("copper_axe", state, gd, ctx) == 17


def test_currency_is_the_only_blanket():
    gd = _gd()
    state = make_state(level=10, inventory={"tasks_coin": 40})
    ctx = _ctx()
    assert keep_owned("tasks_coin", state, gd, ctx) == KEEP_ALL
    assert destroyable("tasks_coin", state, gd, ctx) == 0


def test_destroyable_counts_bank_copies_toward_owned():
    """keep_owned is about OWNERSHIP, so bank copies satisfy it: holding 1 in the
    bag and 5 in the bank with a gear demand of 2 leaves 4 destroyable."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 1},
                       bank_items={"copper_axe": 5})
    ctx = _ctx(gear_keep={"copper_axe": 2})
    assert keep_owned("copper_axe", state, gd, ctx) == 2
    assert destroyable("copper_axe", state, gd, ctx) == 4


def test_caps_are_never_negative():
    gd = _gd()
    state = make_state(level=10, inventory={})
    ctx = _ctx()
    assert bankable("copper_axe", state, gd, ctx) == 0
    assert destroyable("copper_axe", state, gd, ctx) == 0


def test_active_task_keeps_remaining_qty_not_the_whole_stack():
    gd = _gd()
    state = make_state(level=10, inventory={"copper_bar": 30},
                       task_code="copper_bar", task_type="items",
                       task_total=10, task_progress=4)
    ctx = _ctx()
    assert reason_quantity(KeepReason.ACTIVE_TASK, "copper_bar", state, gd, ctx) == 6


def test_healing_consumable_caps_at_stock_target_not_the_whole_stack():
    """Instance #5 of the blanket bug, fixed: the real cap is the stock
    target, so surplus above it is bankable rather than hoarded forever."""
    gd = _gd()
    state = make_state(level=10, inventory={"cooked_chicken": 40})
    ctx = _ctx()
    assert reason_quantity(KeepReason.HEALING_CONSUMABLE, "cooked_chicken",
                           state, gd, ctx) == 5
    assert bankable("cooked_chicken", state, gd, ctx) == 35


def test_healing_target_is_an_aggregate_charged_to_the_best_heal_only():
    """The stock target is an AGGREGATE across every heal code (that is what
    `consumable_supply.heal_stock` sums), so charging it to EVERY heal code
    would keep N x target. Only the strongest held heal carries it; the weaker
    codes are fully bankable (never sold/deleted — in_bag cap only).

    The bag also holds a non-heal item and a spent (qty 0) stack: neither may
    win the "best heal" selection."""
    gd = _gd()
    state = make_state(level=10, inventory={"cooked_chicken": 10, "apple": 10,
                                            "copper_bar": 3, "copper_ore": 0})
    ctx = _ctx()
    assert reason_quantity(KeepReason.HEALING_CONSUMABLE, "copper_bar",
                           state, gd, ctx) == 0
    assert reason_quantity(KeepReason.HEALING_CONSUMABLE, "cooked_chicken",
                           state, gd, ctx) == 5
    assert reason_quantity(KeepReason.HEALING_CONSUMABLE, "apple",
                           state, gd, ctx) == 0
    assert bankable("cooked_chicken", state, gd, ctx) == 5
    assert bankable("apple", state, gd, ctx) == 10


def test_committed_recipe_keeps_crafting_target_materials_transitively():
    """`copper_axe <- 6 copper_bar <- 36 copper_ore`: the DEEP material is
    protected with a real quantity, not silently 0."""
    gd = _gd()
    state = make_state(level=10, inventory={"copper_bar": 20, "copper_ore": 50},
                       crafting_target="copper_axe")
    ctx = _ctx()
    assert reason_quantity(KeepReason.COMMITTED_RECIPE, "copper_bar",
                           state, gd, ctx) == 6
    assert reason_quantity(KeepReason.COMMITTED_RECIPE, "copper_ore",
                           state, gd, ctx) == 36
    assert reason_quantity(KeepReason.COMMITTED_RECIPE, "cooked_chicken",
                           state, gd, ctx) == 0


def test_committed_recipe_protects_the_items_tasks_deep_submaterial():
    """The freeze repro: an items-task delivers `copper_axe`, the bag holds the
    ORE two levels down. A direct-recipe quantity returns 0 for the ore, so
    DepositAll banks the task's own sub-material and PursueTask starves."""
    gd = _gd()
    state = make_state(level=10, inventory={"copper_ore": 60},
                       task_code="copper_axe", task_type="items",
                       task_total=1, task_progress=0)
    ctx = _ctx()
    assert reason_quantity(KeepReason.COMMITTED_RECIPE, "copper_ore",
                           state, gd, ctx) == 36
    assert keep_in_bag("copper_ore", state, gd, ctx) == 36
    assert bankable("copper_ore", state, gd, ctx) == 24


def test_committed_recipe_scales_with_the_remaining_task_quantity():
    """A 5-axe items-task needs 30 bars (and 180 ore), not one axe's worth; the
    demand shrinks as the task progresses."""
    gd = _gd()
    state = make_state(level=10, inventory={"copper_bar": 40},
                       task_code="copper_axe", task_type="items",
                       task_total=5, task_progress=0)
    ctx = _ctx()
    assert reason_quantity(KeepReason.COMMITTED_RECIPE, "copper_bar",
                           state, gd, ctx) == 30
    assert reason_quantity(KeepReason.COMMITTED_RECIPE, "copper_ore",
                           state, gd, ctx) == 180

    done = make_state(level=10, inventory={"copper_bar": 40},
                      task_code="copper_axe", task_type="items",
                      task_total=5, task_progress=3)
    assert reason_quantity(KeepReason.COMMITTED_RECIPE, "copper_bar",
                           done, gd, ctx) == 12


def test_combat_weapon_keeps_one_in_bag():
    gd = _gd()
    state = make_state(level=10, inventory={"copper_dagger": 5})
    ctx = _ctx()
    assert reason_quantity(KeepReason.COMBAT_WEAPON, "copper_dagger",
                           state, gd, ctx) == 1
    assert reason_quantity(KeepReason.COMBAT_WEAPON, "copper_bar",
                           state, gd, ctx) == 0
    assert keep_in_bag("copper_dagger", state, gd, ctx) == 1
    assert bankable("copper_dagger", state, gd, ctx) == 4


def test_equipped_keeps_one_owned():
    gd = _gd()
    state = make_state(level=10, inventory={"copper_dagger": 3},
                       equipment={"weapon_slot": "copper_dagger"})
    ctx = _ctx()
    assert reason_quantity(KeepReason.EQUIPPED, "copper_dagger", state, gd, ctx) == 1
    assert reason_quantity(KeepReason.EQUIPPED, "copper_bar", state, gd, ctx) == 0


def test_goal_materials_reads_the_step_profile():
    """GOAL_MATERIALS must be able to be NON-ZERO — `ctx.step_profile` is a real
    `SelectionContext` field (populated by the player in Task 2), not a shim."""
    gd = _gd()
    state = make_state(level=10, inventory={"copper_bar": 20})
    ctx = _ctx(step_profile={"copper_bar": 12})
    assert reason_quantity(KeepReason.GOAL_MATERIALS, "copper_bar",
                           state, gd, ctx) == 12
    assert reason_quantity(KeepReason.GOAL_MATERIALS, "copper_ore",
                           state, gd, ctx) == 0
    assert keep_in_bag("copper_bar", state, gd, ctx) == 12
    assert bankable("copper_bar", state, gd, ctx) == 8
    assert reason_quantity(KeepReason.GOAL_MATERIALS, "copper_bar",
                           state, gd, _ctx()) == 0


def test_recipe_demand_is_the_useful_quantity_cap():
    """RECIPE_DEMAND delegates to `useful_quantity_cap`: recipe demand 6 x
    BATCH_BUFFER 5 = 30 (char level 1 keeps the level-distance ceiling off)."""
    gd = _gd()
    state = make_state(level=1, inventory={"copper_bar": 60})
    ctx = _ctx()
    assert reason_quantity(KeepReason.RECIPE_DEMAND, "copper_bar",
                           state, gd, ctx) == 30
    assert keep_owned("copper_bar", state, gd, ctx) == 30
    assert destroyable("copper_bar", state, gd, ctx) == 30


def test_gear_demand_has_no_blanket_fallback():
    """DELIBERATE de-blanketing: `guards._gear_protected`'s profile-less arm was
    the CODE-SET `target_gear | target_tools` (= keep ALL copies of every BiS
    code — another reason all 18 axes were hoarded). It is NOT reinstated: with
    an empty `gear_keep` a `target_tools` code held x18 keeps exactly 1 (via the
    EQUIPPED/RECIPE_DEMAND `EQUIPPABLE_KEEP`) and 17 are disposable."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 18})
    ctx = _ctx(target_gear=frozenset(), target_tools=frozenset({"copper_axe"}))
    assert ctx.gear_keep == {}
    assert reason_quantity(KeepReason.GEAR_DEMAND, "copper_axe", state, gd, ctx) == 0
    assert keep_owned("copper_axe", state, gd, ctx) == 1
    assert destroyable("copper_axe", state, gd, ctx) == 17


def test_gear_demand_is_the_profile_keep_count():
    gd = _gd()
    state = make_state(level=10, inventory={"copper_axe": 5})
    ctx = _ctx(gear_keep={"copper_axe": 3})
    assert reason_quantity(KeepReason.GEAR_DEMAND, "copper_axe", state, gd, ctx) == 3
    assert keep_owned("copper_axe", state, gd, ctx) == 3


def test_reason_cap_sets_are_exactly_the_registry():
    """The two cap sets are load-bearing, so pin them DIRECTLY. Every `max()`
    over a cap set can mask a mis-filed reason behind a larger sibling, which
    is how a mis-filed WORKING_KIT / GEAR_DEMAND survived the behavioural
    tests alone."""
    assert frozenset({
        KeepReason.CURRENCY, KeepReason.ACTIVE_TASK, KeepReason.HEALING_CONSUMABLE,
        KeepReason.COMBAT_WEAPON, KeepReason.WORKING_KIT, KeepReason.COMMITTED_RECIPE,
        KeepReason.GOAL_MATERIALS,
    }) == IN_BAG_REASONS
    assert frozenset({
        KeepReason.CURRENCY, KeepReason.ACTIVE_TASK, KeepReason.EQUIPPED,
        KeepReason.GEAR_DEMAND, KeepReason.RECIPE_DEMAND,
    }) == OWNED_REASONS
    assert frozenset(KeepReason) == IN_BAG_REASONS | OWNED_REASONS
    # The bag-only reasons must never gate DESTRUCTION...
    for bag_only in (KeepReason.HEALING_CONSUMABLE, KeepReason.COMBAT_WEAPON,
                     KeepReason.WORKING_KIT, KeepReason.COMMITTED_RECIPE,
                     KeepReason.GOAL_MATERIALS):
        assert bag_only not in OWNED_REASONS
    # ...and the ownership-only reasons must never pin BAG slots.
    for owned_only in (KeepReason.EQUIPPED, KeepReason.GEAR_DEMAND,
                       KeepReason.RECIPE_DEMAND):
        assert owned_only not in IN_BAG_REASONS


def test_working_kit_is_bag_only_when_it_is_the_sole_reason():
    """Behavioural half of the cap-set pin, with NOTHING to hide behind: a
    non-empty `gear_keep` that omits the axe drives every OWNED reason to 0, so
    all 18 axes are destroyable. If WORKING_KIT were (also) an OWNED reason,
    keep_owned would be 1 and only 17 would be destroyable."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 18})
    ctx = _ctx(gear_keep={"copper_bar": 1})
    assert reason_quantity(KeepReason.WORKING_KIT, "copper_axe", state, gd, ctx) == 1
    assert keep_owned("copper_axe", state, gd, ctx) == 0
    assert destroyable("copper_axe", state, gd, ctx) == 18


def test_committed_recipe_ADDS_the_demand_of_two_disjoint_roots():
    """The two committed roots are DIFFERENT items, so their material demands
    ADD. `copper_dagger` (in-flight craft, 8 copper_ore) and an items-task for
    `copper_axe` (36 copper_ore) together need 44 ore. Combining by `max` keeps
    only 36: the 8-ore shortfall is banked by DepositAll and must be withdrawn
    straight back — deposit/withdraw churn.

    Both roots are exercised in both directions (the deeper root is not always
    the larger contributor) via `copper_bar`, which only the axe root wants."""
    gd = _gd()
    state = make_state(level=10, inventory={"copper_ore": 60},
                       crafting_target="copper_dagger",
                       task_code="copper_axe", task_type="items",
                       task_total=1, task_progress=0)
    ctx = _ctx()
    assert reason_quantity(KeepReason.COMMITTED_RECIPE, "copper_ore",
                           state, gd, ctx) == 44
    assert keep_in_bag("copper_ore", state, gd, ctx) == 44
    assert bankable("copper_ore", state, gd, ctx) == 16
    # The axe root alone wants bars; the dagger root contributes nothing there.
    assert reason_quantity(KeepReason.COMMITTED_RECIPE, "copper_bar",
                           state, gd, ctx) == 6


def test_committed_recipe_counts_a_shared_root_ONCE_not_twice():
    """The guard `max` was there for: when the in-flight craft IS the task item,
    the two roots are ONE root. It is counted once, at the larger quantity — a
    5-axe task with an axe in flight wants 180 ore, not 180 + 36."""
    gd = _gd()
    state = make_state(level=10, inventory={"copper_ore": 300},
                       crafting_target="copper_axe",
                       task_code="copper_axe", task_type="items",
                       task_total=5, task_progress=0)
    ctx = _ctx()
    assert reason_quantity(KeepReason.COMMITTED_RECIPE, "copper_ore",
                           state, gd, ctx) == 180
    assert reason_quantity(KeepReason.COMMITTED_RECIPE, "copper_bar",
                           state, gd, ctx) == 30

    # ...and the shared root never DROPS below the in-flight craft's own unit:
    # a fully-delivered task contributes no root at all, the craft still does.
    spent = make_state(level=10, inventory={"copper_ore": 300},
                       crafting_target="copper_axe",
                       task_code="copper_axe", task_type="items",
                       task_total=5, task_progress=5)
    assert reason_quantity(KeepReason.COMMITTED_RECIPE, "copper_ore",
                           spent, gd, ctx) == 36


def test_healing_target_is_GREEDILY_FILLED_across_held_heals():
    """The aggregate target (5) may not be charged to one code that cannot
    carry it. cooked_chicken x3 (the stronger heal) + apple x10: charging all 5
    to the chicken keeps 3 real copies and leaves all 10 apples bankable — after
    DepositAll the actual `heal_stock` is 3, BELOW the target, so
    `MaintainConsumables` re-fires and crafts more. Churn.

    Greedy fill, strongest first: chicken keeps its 3, apple keeps the missing
    2, and the AGGREGATE kept is exactly the target."""
    gd = _gd()
    state = make_state(level=10, inventory={"cooked_chicken": 3, "apple": 10})
    ctx = _ctx()
    chicken = reason_quantity(KeepReason.HEALING_CONSUMABLE, "cooked_chicken",
                              state, gd, ctx)
    apple = reason_quantity(KeepReason.HEALING_CONSUMABLE, "apple", state, gd, ctx)
    assert chicken == 3
    assert apple == 2
    assert chicken + apple == 5  # == heal_stock_target(HEAL_STOCK_FLOOR)
    assert bankable("cooked_chicken", state, gd, ctx) == 0
    assert bankable("apple", state, gd, ctx) == 8


def test_healing_fill_stops_at_the_target_and_never_over_keeps():
    """The fill is a CAP, not a floor: once the target is met the weaker heals
    keep 0, and a heal code that is not held at all keeps 0 (no phantom fill).
    Held heals short of the target keep everything they have — the fill never
    invents copies."""
    gd = _gd()
    # Target met by the strongest alone -> the weaker heal keeps nothing.
    met = make_state(level=10, inventory={"cooked_chicken": 5, "apple": 10})
    ctx = _ctx()
    assert reason_quantity(KeepReason.HEALING_CONSUMABLE, "cooked_chicken",
                           met, gd, ctx) == 5
    assert reason_quantity(KeepReason.HEALING_CONSUMABLE, "apple", met, gd, ctx) == 0

    # Whole stock short of the target -> every held copy is kept, none invented.
    short = make_state(level=10, inventory={"cooked_chicken": 1, "apple": 2})
    assert reason_quantity(KeepReason.HEALING_CONSUMABLE, "cooked_chicken",
                           short, gd, ctx) == 1
    assert reason_quantity(KeepReason.HEALING_CONSUMABLE, "apple", short, gd, ctx) == 2
    # A heal code that is not held keeps 0 rather than reserving a share.
    assert reason_quantity(KeepReason.HEALING_CONSUMABLE, "cooked_chicken",
                           make_state(level=10, inventory={"apple": 9}), gd, ctx) == 0


def test_gear_demand_is_owned_only_when_it_is_the_sole_reason():
    """Behavioural half of the cap-set pin, other direction: gear demand is the
    only non-zero reason for these bars, and it must NOT pin them in the bag —
    all 10 stay bankable. If GEAR_DEMAND were (also) an in-bag reason,
    keep_in_bag would be 4 and only 6 would be bankable."""
    gd = _gd()
    state = make_state(level=10, inventory={"copper_bar": 10})
    ctx = _ctx(gear_keep={"copper_bar": 4})
    assert reason_quantity(KeepReason.GEAR_DEMAND, "copper_bar", state, gd, ctx) == 4
    assert keep_in_bag("copper_bar", state, gd, ctx) == 0
    assert bankable("copper_bar", state, gd, ctx) == 10
