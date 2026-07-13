from artifactsmmo_cli.ai.bank_drain import bank_drain_excess
from artifactsmmo_cli.ai.consumable_supply import HEAL_STOCK_FLOOR
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.inventory_caps import (
    CONSUMABLE_KEEP,
    KEEP_CEILING_FAR,
    useful_quantity_cap,
)
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
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.strategy_driver import Candidate, StrategyArbiter
from artifactsmmo_cli.ai.tiers.guards import GuardKind, SelectionContext
from artifactsmmo_cli.ai.tiers.means import MeansKind
from artifactsmmo_cli.ai.tiers.strategy import MetaGoal, ObtainItem, StrategyDecision
from artifactsmmo_cli.ai.world_state import WorldState
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


def test_keep_in_bag_combines_by_MAX_not_sum():
    """The COMBINATOR, with two reasons live at once and nothing to hide behind:
    the items-task axe wants 36 ore (COMMITTED_RECIPE) while the active step
    profile wants 50 (GOAL_MATERIALS). The cap is the LARGER demand, 50 — a
    `sum` combinator would keep 86 of the 60 held and bank nothing, which is the
    over-protection half of the hoard bug (the cap must never exceed every
    single reason; Lean `keep_is_a_reason`).

    Every other cap-level test has exactly ONE non-zero reason, so `sum` and
    `max` agree there and the defect would survive them all."""
    gd = _gd()
    state = make_state(level=10, inventory={"copper_ore": 60},
                       task_code="copper_axe", task_type="items",
                       task_total=1, task_progress=0)
    ctx = _ctx(step_profile={"copper_ore": 50})
    assert reason_quantity(KeepReason.COMMITTED_RECIPE, "copper_ore",
                           state, gd, ctx) == 36
    assert reason_quantity(KeepReason.GOAL_MATERIALS, "copper_ore",
                           state, gd, ctx) == 50
    assert keep_in_bag("copper_ore", state, gd, ctx) == 50
    assert bankable("copper_ore", state, gd, ctx) == 10


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
    tests alone.

    WORKING_KIT and COMBAT_WEAPON are in BOTH ladders: "keep ONE in the bag"
    (the copy the gather re-arm equips) and "never melt your LAST one" are two
    different obligations, and the second is an OWNERSHIP invariant. So are
    COMMITTED_RECIPE and GOAL_MATERIALS, for the same reason, since 2026-07-13:
    a LIVE craft chain's and a LIVE objective step's own materials must survive
    BOTH the deposit ladder and the destruction ladder."""
    assert frozenset({
        KeepReason.CURRENCY, KeepReason.ACTIVE_TASK, KeepReason.HEALING_CONSUMABLE,
        KeepReason.COMBAT_WEAPON, KeepReason.WORKING_KIT, KeepReason.COMMITTED_RECIPE,
        KeepReason.GOAL_MATERIALS,
    }) == IN_BAG_REASONS
    assert frozenset({
        KeepReason.CURRENCY, KeepReason.ACTIVE_TASK, KeepReason.COMBAT_WEAPON,
        KeepReason.WORKING_KIT, KeepReason.COMMITTED_RECIPE, KeepReason.GOAL_MATERIALS,
        KeepReason.EQUIPPED, KeepReason.GEAR_DEMAND, KeepReason.RECIPE_DEMAND,
    }) == OWNED_REASONS
    assert frozenset(KeepReason) == IN_BAG_REASONS | OWNED_REASONS
    # HEALING_CONSUMABLE is the ONE bag-only reason: its quantity is the heal
    # STOCK TARGET, so the surplus above it is BANKABLE. Its protection from
    # DESTRUCTION is RECIPE_DEMAND's CONSUMABLE_KEEP blanket, not this reason —
    # filing the target here as an owned floor would be strictly weaker.
    assert KeepReason.HEALING_CONSUMABLE not in OWNED_REASONS
    # ...and the ownership-only reasons must never pin BAG slots.
    for owned_only in (KeepReason.EQUIPPED, KeepReason.GEAR_DEMAND,
                       KeepReason.RECIPE_DEMAND):
        assert owned_only not in IN_BAG_REASONS
    # Everything else is in BOTH ladders: a live commitment (the task item, the
    # working kit, the craft chain, the step materials, currency) must survive
    # banking AND destruction.
    assert frozenset({
        KeepReason.CURRENCY, KeepReason.ACTIVE_TASK,
        KeepReason.COMBAT_WEAPON, KeepReason.WORKING_KIT,
        KeepReason.COMMITTED_RECIPE, KeepReason.GOAL_MATERIALS,
    }) == IN_BAG_REASONS & OWNED_REASONS


def test_working_kit_is_the_sole_reason_in_BOTH_caps():
    """Behavioural half of the cap-set pin, with NOTHING to hide behind: a
    non-empty `gear_keep` that SPEAKS FOR THE WEAPON SLOT but omits the axe
    suppresses `EQUIPPABLE_KEEP` in RECIPE_DEMAND *and* `_gear_demand`'s
    slot-silence floor, so WORKING_KIT is the ONLY non-zero reason for the axe. It
    must carry BOTH caps: keep 1 in the bag (17 of 18 bank) AND keep 1 owned
    (17 of 18 destroyable — never the last tool).

    If WORKING_KIT were filed IN_BAG-only, keep_owned would be 0 and all 18
    would be destroyable; if it were filed OWNED-only, keep_in_bag would be 0
    and DepositAll would bank the working tool."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 18})
    ctx = _ctx(gear_keep={"copper_dagger": 1})
    live = {r for r in KeepReason
            if reason_quantity(r, "copper_axe", state, gd, ctx) > 0}
    assert live == {KeepReason.WORKING_KIT}
    assert reason_quantity(KeepReason.WORKING_KIT, "copper_axe", state, gd, ctx) == 1
    assert keep_in_bag("copper_axe", state, gd, ctx) == 1
    assert bankable("copper_axe", state, gd, ctx) == 17
    assert keep_owned("copper_axe", state, gd, ctx) == 1
    assert destroyable("copper_axe", state, gd, ctx) == 17


def test_combat_weapon_is_the_sole_reason_in_BOTH_caps():
    """The COMBAT_WEAPON half of the same pin: the best fighting weapon is the
    only live reason (the profile speaks for the weapon slot but omits it — so
    neither the gear demand nor its slot-silence floor covers the dagger), and it
    carries both caps: one stays in the bag, and at least one stays OWNED."""
    gd = _gd()
    state = make_state(level=10, inventory={"copper_dagger": 18})
    ctx = _ctx(gear_keep={"copper_axe": 1})
    live = {r for r in KeepReason
            if reason_quantity(r, "copper_dagger", state, gd, ctx) > 0}
    assert live == {KeepReason.COMBAT_WEAPON}
    assert keep_in_bag("copper_dagger", state, gd, ctx) == 1
    assert bankable("copper_dagger", state, gd, ctx) == 17
    assert keep_owned("copper_dagger", state, gd, ctx) == 1
    assert destroyable("copper_dagger", state, gd, ctx) == 17


def test_banked_working_tool_is_never_the_last_one_destroyed():
    """THE DESTRUCTION HOLE. The state DepositAll now produces (1 axe kept in
    the bag, 17 banked) and then the bag copy is spent/equipped, leaving the
    character's ONLY woodcutting tool sitting entirely in the BANK.

    `keep_in_bag` protects nothing there (there is nothing in the bag to
    protect), so if WORKING_KIT answered only the BAG cap, `keep_owned` would be
    0 and a destructive consumer reading `destroyable` (the bank-drain path)
    would melt ALL 18 copies of the best tool the character owns. Zero tools
    left — strictly worse than the hoard bug this authority exists to fix.

    "Never destroy your last working tool" is an OWNERSHIP invariant: the kit
    selectors range over what is OWNED (bag + bank + equipped), so one copy
    survives wherever it is held."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={}, bank_items={"copper_axe": 18})
    ctx = _ctx(gear_keep={"copper_bar": 1})
    assert reason_quantity(KeepReason.WORKING_KIT, "copper_axe", state, gd, ctx) == 1
    assert keep_owned("copper_axe", state, gd, ctx) == 1
    assert destroyable("copper_axe", state, gd, ctx) == 17
    # The bag cap is inert on a code with no bag copies — nothing to hoard.
    assert bankable("copper_axe", state, gd, ctx) == 0


def test_banked_combat_weapon_is_never_the_last_one_destroyed():
    """The COMBAT_WEAPON half of the destruction hole: the best fighting weapon
    held entirely in the bank keeps ONE owned, so 17 of 18 are destroyable."""
    gd = _gd()
    state = make_state(level=10, inventory={}, bank_items={"copper_dagger": 18})
    ctx = _ctx(gear_keep={"copper_bar": 1})
    assert reason_quantity(KeepReason.COMBAT_WEAPON, "copper_dagger",
                           state, gd, ctx) == 1
    assert keep_owned("copper_dagger", state, gd, ctx) == 1
    assert destroyable("copper_dagger", state, gd, ctx) == 17


def test_working_tool_split_across_bag_and_bank_keeps_the_bag_copy():
    """The exact DepositAll-produced state, before the bag copy is spent: 1 axe
    in the bag, 17 in the bank. The bag copy is the one the gather re-arm
    equips, so it is NOT bankable — and it must not be melted either: the
    ownership cap keeps ONE of the 18, so 17 (the banked ones) are destroyable,
    not 18.

    `recycle_surplus` takes `min(bankable, destroyable)` and so was already safe
    here; a consumer reading `destroyable` alone (bank drain) was not."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 1}, bank_items={"copper_axe": 17})
    ctx = _ctx(gear_keep={"copper_bar": 1})
    assert keep_in_bag("copper_axe", state, gd, ctx) == 1
    assert bankable("copper_axe", state, gd, ctx) == 0
    assert keep_owned("copper_axe", state, gd, ctx) == 1
    assert destroyable("copper_axe", state, gd, ctx) == 17


def test_a_better_banked_tool_never_unprotects_the_one_in_the_bag():
    """The ownership-scoped kit arm is ADDITIVE, never a displacement: with a
    strictly better axe in the BANK, the bag copy is still the tool the
    character is WORKING with, so it keeps its bag slot (bankable 0) — the bag
    cap never regressed — while the banked better axe is the one ownership
    protects from the melt."""
    gd = _gd()
    gd._item_stats["iron_axe"] = ItemStats(
        code="iron_axe", level=1, type_="weapon", subtype="tool",
        skill_effects={"woodcutting": -20}, crafting_skill="weaponcrafting",
        crafting_level=1)
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 1}, bank_items={"iron_axe": 4})
    ctx = _ctx(gear_keep={"copper_bar": 1})
    assert reason_quantity(KeepReason.WORKING_KIT, "copper_axe", state, gd, ctx) == 1
    assert keep_in_bag("copper_axe", state, gd, ctx) == 1
    assert bankable("copper_axe", state, gd, ctx) == 0
    assert reason_quantity(KeepReason.WORKING_KIT, "iron_axe", state, gd, ctx) == 1
    assert destroyable("iron_axe", state, gd, ctx) == 3


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


class _CtxSpyArbiter(StrategyArbiter):
    """The real arbiter, recording the `SelectionContext` and step goal it hands
    the goal layer. Nothing is stubbed — `_build_candidates` delegates to the
    real implementation — so what is asserted is what the live goals receive."""

    def __init__(self, planner: GOAPPlanner) -> None:
        super().__init__(planner, history=None)
        self.seen_ctx: SelectionContext | None = None
        self.seen_step_goal: Goal | None = None

    def _build_candidates(
        self,
        guard_kinds: list[GuardKind],
        collect_kinds: list[MeansKind],
        discretionary_kinds: list[MeansKind],
        step_goal: Goal | None,
        fallback_steps: list[MetaGoal],
        fallback_roots: list[MetaGoal],
        state: WorldState,
        game_data: GameData,
        ctx: SelectionContext,
        step_profile: dict[str, int] | None = None,
        chosen_root: MetaGoal | None = None,
    ) -> list[Candidate]:
        self.seen_ctx = ctx
        self.seen_step_goal = step_goal
        return super()._build_candidates(
            guard_kinds, collect_kinds, discretionary_kinds, step_goal,
            fallback_steps, fallback_roots, state, game_data, ctx, step_profile,
            chosen_root=chosen_root)


def _gather_gd() -> GameData:
    """`ash_plank <- 10 ash_wood`, the ash_wood gathered from an ash_tree: an
    active GatherMaterials step accumulating a raw material in the bag — the
    shape of the livelock this keep reason exists to stop."""
    gd = GameData()
    gd._item_stats = {
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource",
                               crafting_skill="woodcutting", crafting_level=1),
        "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"ash_plank": {"ash_wood": 10}}
    gd._resource_drops = {"ash_tree": "ash_wood"}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    gd._resource_locations = {"ash_tree": [(2, 2)]}
    gd._workshop_locations = {"woodcutting": (1, 5)}
    gd._bank_location = (4, 0)
    return gd


def test_goal_materials_is_LIVE_end_to_end_through_the_arbiter():
    """GOAL_MATERIALS is worth nothing unless something POPULATES
    `ctx.step_profile`: the reason was DEAD ON ARRIVAL (the field was always
    `{}`) until `StrategyArbiter.select` bound the resolved step goal's needed
    map onto the ctx.

    So drive the REAL arbiter — real `StrategyDecision`, real step-goal
    resolution, real `_step_protection_profile` — and assert on the ctx the goal
    layer ACTUALLY receives (`_build_candidates` is delegated to, not stubbed):
    the material the active GatherMaterials step is accumulating (10 ash_wood,
    the recipe closure of the 1 ash_plank it needs) is kept in the bag, which is
    the protection `bank_selection` documents the loss of as a gather livelock —
    DepositAll banks the materials out from under the gather, undoing the
    withdraw. The surplus ABOVE the needed quantity still banks: the old
    `profile_codes` frozenset was a code-SET, so it pinned the whole growing
    pile in the bag instead.

    This test FAILS if `step_profile` stays `{}` — the control at the bottom is
    the same state with a bare ctx, where nothing keeps the wood at all."""
    planner = GOAPPlanner()
    gd = _gather_gd()
    surplus = 7
    needed_wood = 10  # ash_plank's recipe: the closure of the step's needed plank
    state = make_state(
        level=10, hp=100, max_hp=100,
        skills={"woodcutting": 1},
        inventory={"ash_wood": needed_wood + surplus}, inventory_max=110,
    )
    step = ObtainItem("ash_plank", 1)
    decision = StrategyDecision(interrupt=None, chosen_root=step, chosen_step=step,
                                desired_state={})
    arbiter = _CtxSpyArbiter(planner)
    arbiter.set_cycle(0)
    arbiter.select(decision, state, gd, [], _ctx())

    step_goal = arbiter.seen_step_goal
    assert isinstance(step_goal, GatherMaterialsGoal), step_goal
    assert step_goal.needed == {"ash_plank": 1}, step_goal.needed

    ctx = arbiter.seen_ctx
    assert ctx is not None
    # The live wiring: the resolved gather goal's material map reached the ctx...
    assert ctx.step_profile == {"ash_plank": 1, "ash_wood": needed_wood}
    assert reason_quantity(KeepReason.GOAL_MATERIALS, "ash_wood",
                           state, gd, ctx) == needed_wood
    # ...so the gather's own materials survive a DepositAll...
    assert keep_in_bag("ash_wood", state, gd, ctx) >= needed_wood
    # ...and ONLY the needed quantity does — the surplus above it still banks.
    assert bankable("ash_wood", state, gd, ctx) == surplus

    # Control: the SAME state with an unpopulated ctx keeps nothing in the bag,
    # so every assertion above is carried by `step_profile`, not by a sibling
    # reason quietly holding the wood.
    bare = _ctx()
    assert keep_in_bag("ash_wood", state, gd, bare) == 0
    assert bankable("ash_wood", state, gd, bare) == needed_wood + surplus


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


# ---------------------------------------------------------------------------
# The level-distance ceiling must never bound the OWNERSHIP cap.
#
# `inventory_caps.level_distance_keep_ceiling` is a HOARDING policy — "is this
# item worth the space, given how far its level sits from mine". It answers a
# SPACE question, so it belongs on the space gates (`overstocked_items`,
# `bank_drain`'s `junk_excess`). Applied to `keep_owned` it bounded the cap that
# licenses DESTRUCTION, and these two defects fell straight out of it (found by
# the census's level-distance band, 2026-07-13). Both are pinned at a character
# level >= LEVEL_BAND_FAR (10) above the item's, where the tightest ceiling
# (KEEP_CEILING_FAR = 5) bites.
# ---------------------------------------------------------------------------

def test_far_out_of_band_heals_are_never_destroyable():
    """I2. `CONSUMABLE_KEEP = 999` is a BLANKET ("consumables stack, so capping
    low frees zero slots while throwing away survival value") and it must hold at
    every level distance. The ceiling clamped it to 5, so a level-20 character
    holding 30 `cooked_chicken` (item level 1) had `keep_owned = 5` and 25 heals
    were SELL/DELETE fodder.

    The bag cap is unchanged — the heal STOCK TARGET is 5, so 25 stay BANKABLE.
    That is the whole point of the two-cap split: bankable (reversible) is not
    destroyable (not)."""
    gd = _gd()
    ctx = _ctx()
    far = make_state(level=20, inventory={"cooked_chicken": 30})
    assert keep_owned("cooked_chicken", far, gd, ctx) == CONSUMABLE_KEEP
    assert destroyable("cooked_chicken", far, gd, ctx) == 0
    # The surplus above the stock target is still shed to the BANK, as before.
    assert keep_in_bag("cooked_chicken", far, gd, ctx) == HEAL_STOCK_FLOOR
    assert bankable("cooked_chicken", far, gd, ctx) == 30 - HEAL_STOCK_FLOOR

    # ...and the in-band character (distance 4, no ceiling) always agreed: the
    # two bands now give the SAME ownership answer, which is the invariant.
    near = make_state(level=5, inventory={"cooked_chicken": 30})
    assert keep_owned("cooked_chicken", near, gd, ctx) == CONSUMABLE_KEEP
    assert destroyable("cooked_chicken", near, gd, ctx) == 0


def test_far_out_of_band_task_chain_is_never_drained_from_the_bank():
    """I3. A LIVE items-task's own chain material, banked. `keep_in_bag` said 300
    (COMMITTED_RECIPE: 5 daggers x 8 ore x ... the transitive chain) while the
    ceiling clamped `keep_owned` to 5 — a 60x disagreement between the two caps on
    the SAME material — so `bank_drain` was licensed to pull 35 of the task's own
    copper_ore out of the bank and onto the discard ladder.

    The bag-side `min(bankable, destroyable)` masked it while the task root stayed
    chosen (nothing in the bag to shed), which is exactly why it needed the
    OWNERSHIP cap to say no: one cycle on a different root drops `keep_in_bag` to
    0 and the copies become bag-destroyable."""
    gd = _gd()
    ctx = _ctx()
    far = make_state(level=20, skills={"weaponcrafting": 2}, inventory={},
                     bank_items={"copper_ore": 40},
                     task_code="copper_dagger", task_type="items",
                     task_total=5, task_progress=0)
    # The chain demand is 5 x 8 = 40 ore; the ownership cap must cover it...
    assert reason_quantity(KeepReason.COMMITTED_RECIPE, "copper_ore",
                           far, gd, ctx) == 40
    assert keep_owned("copper_ore", far, gd, ctx) >= 40
    assert destroyable("copper_ore", far, gd, ctx) == 0
    # ...so the drain takes nothing: the task's own materials stay banked.
    assert bank_drain_excess(far, gd, ctx) == {}


def test_far_out_of_band_goal_step_materials_are_never_destroyable():
    """I3, the objective-step half. `GOAL_MATERIALS` (the active step's own
    material map) had NO owned-side representation at all: `useful_quantity_cap`
    has no term for `ctx.step_profile`, so the step's materials leaned entirely on
    the RECIPE_DEMAND heuristic happening to be generous — and the ceiling took
    that away too. 60 banked `ash_wood` against a step needing 59 drained 55.

    The step here demands MORE than the heuristic (200 > the fixture's
    `5 x max_recipe_demand` = 180), so GOAL_MATERIALS is the sole reason holding
    the line — the case that proves it must feed `keep_owned` in its own right and
    not lean on a sibling. The drain still takes the GENUINE surplus (50 above the
    step's demand): this is a protection, not a new blanket."""
    gd = _gd()
    ctx = _ctx(step_profile={"copper_ore": 200})
    far = make_state(level=20, inventory={}, bank_items={"copper_ore": 250})
    assert reason_quantity(KeepReason.GOAL_MATERIALS, "copper_ore",
                           far, gd, ctx) == 200
    assert reason_quantity(KeepReason.RECIPE_DEMAND, "copper_ore",
                           far, gd, ctx) == 180  # the sibling is NOT enough
    assert keep_owned("copper_ore", far, gd, ctx) == 200
    assert destroyable("copper_ore", far, gd, ctx) == 50
    assert bank_drain_excess(far, gd, ctx) == {"copper_ore": 50}


def test_the_ceiling_still_governs_the_SPACE_gates():
    """The other direction: the ceiling is not dead, it is RE-HOMED. It still
    bounds `useful_quantity_cap` for every caller that asks a SPACE question — the
    overstock gate and the bank-drain junk policy both take the default
    `level_ceiling=True` — and it still declines to HOARD far-out-of-band stock.
    Only the DESTRUCTION cap stopped listening to it."""
    gd = _gd()
    far = make_state(level=20, inventory={"cooked_chicken": 30})
    # SPACE question: still clamped to KEEP_CEILING_FAR.
    assert useful_quantity_cap("cooked_chicken", far, gd) == KEEP_CEILING_FAR
    # OWNERSHIP question: the demand, unclamped.
    assert useful_quantity_cap("cooked_chicken", far, gd,
                               level_ceiling=False) == CONSUMABLE_KEEP


def test_chain_reasons_feed_BOTH_caps():
    """The registry pin for the fix: a LIVE craft chain and a LIVE objective step
    protect their materials from BANKING *and* from DESTRUCTION. They were bag-only,
    and their only owned-side cover was the RECIPE_DEMAND heuristic — which knows
    nothing about `state.crafting_target` and nothing about `ctx.step_profile`."""
    assert KeepReason.COMMITTED_RECIPE in IN_BAG_REASONS
    assert KeepReason.COMMITTED_RECIPE in OWNED_REASONS
    assert KeepReason.GOAL_MATERIALS in IN_BAG_REASONS
    assert KeepReason.GOAL_MATERIALS in OWNED_REASONS
    # HEALING_CONSUMABLE stays bag-only ON PURPOSE: its quantity is the stock
    # TARGET (5), which would be a strictly WEAKER owned floor than the
    # CONSUMABLE_KEEP=999 blanket RECIPE_DEMAND already gives it.
    assert KeepReason.HEALING_CONSUMABLE in IN_BAG_REASONS
    assert KeepReason.HEALING_CONSUMABLE not in OWNED_REASONS


# ---------------------------------------------------------------------------
# GEAR_DEMAND's slot-silence floor (whole-branch review, finding 4).
# ---------------------------------------------------------------------------

def _slot_gd() -> GameData:
    """Three equippable types across three DIFFERENT slots — the shape a recorded
    profile cannot cover: `pick_loadout` under a `Combat` purpose names no ring
    (a ring's benefit against the monster is 0, so the empty-slot gate skips it)
    and under a `Gather` purpose names almost nothing at all."""
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   attack={"attack_fire": 12},
                                   crafting_skill="weaponcrafting", crafting_level=1),
        "copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                 hp_bonus=10, crafting_skill="jewelrycrafting",
                                 crafting_level=1),
        "iron_ring": ItemStats(code="iron_ring", level=1, type_="ring",
                               hp_bonus=40, crafting_skill="jewelrycrafting",
                               crafting_level=1),
        "copper_helmet": ItemStats(code="copper_helmet", level=1, type_="helmet",
                                   hp_bonus=15, crafting_skill="gearcrafting",
                                   crafting_level=1),
        "iron_helmet": ItemStats(code="iron_helmet", level=1, type_="helmet",
                                 hp_bonus=60, crafting_skill="gearcrafting",
                                 crafting_level=1),
    }
    gd._crafting_recipes = {}
    gd._workshop_locations = {"weaponcrafting": (3, 1), "gearcrafting": (2, 1),
                              "jewelrycrafting": (5, 1)}
    return gd


def test_gear_in_a_slot_the_profile_never_names_keeps_one():
    """THE DESTRUCTION HOLE (2026-07-13). A profile is recorded from `pick_loadout`
    under a Combat or Gather purpose, and NEITHER covers every slot — probed against
    the committed bundle, a Combat profile names no ring/rune/utility and a Gather
    profile names only artifacts. But ANY non-empty `gear_keep` switches
    `EQUIPPABLE_KEEP` off for EVERY equippable (`useful_quantity_cap`'s
    profiles-aware mode), so the character's only copper_ring had `keep_owned = 0`
    and every copy was recycle/sell/delete fodder.

    The profile omitting a slot it cannot speak about is not a licence to destroy
    what sits in it: keep 1, exactly the profile-less floor."""
    gd = _slot_gd()
    state = make_state(level=10, inventory={"copper_ring": 3})
    ctx = _ctx(gear_keep={"copper_dagger": 1})  # a combat profile: weapon slot only
    assert reason_quantity(KeepReason.GEAR_DEMAND, "copper_ring", state, gd, ctx) == 1
    assert keep_owned("copper_ring", state, gd, ctx) == 1
    assert destroyable("copper_ring", state, gd, ctx) == 2


def test_gear_in_a_slot_the_profile_DOES_name_is_reclaimable():
    """The de-blanketing this epic is about is untouched: where the profile CAN
    speak, its number is the whole answer. 3 copper_helmet under a profile that
    wants an iron_helmet keeps ZERO — the helmet slot is spoken for."""
    gd = _slot_gd()
    state = make_state(level=10, inventory={"copper_helmet": 3},
                       bank_items={"iron_helmet": 1})
    ctx = _ctx(gear_keep={"iron_helmet": 1})
    assert reason_quantity(KeepReason.GEAR_DEMAND, "copper_helmet", state, gd, ctx) == 0
    assert keep_owned("copper_helmet", state, gd, ctx) == 0
    assert destroyable("copper_helmet", state, gd, ctx) == 3


def test_slot_silent_gear_that_is_DOMINATED_is_still_reclaimable():
    """The floor is keep-1-WITH-DOMINANCE, not keep-1-blindly: a slot-silent code
    whose strictly-better owned peers already fill every slot it could take is the
    first thing the discard ladder should pick (the `wooden_stick` rule)."""
    gd = _slot_gd()
    # 2 iron_ring owned fills BOTH ring slots and out-values copper_ring.
    state = make_state(level=10, inventory={"copper_ring": 3, "iron_ring": 2})
    ctx = _ctx(gear_keep={"copper_dagger": 1})
    assert reason_quantity(KeepReason.GEAR_DEMAND, "copper_ring", state, gd, ctx) == 0
    assert destroyable("copper_ring", state, gd, ctx) == 3
    # ...while the dominator itself keeps its slot-silent copy.
    assert reason_quantity(KeepReason.GEAR_DEMAND, "iron_ring", state, gd, ctx) == 1


def test_slot_silence_floor_is_off_when_no_profile_is_active():
    """With an EMPTY `gear_keep` the floor is not this reason's job at all — the
    profile-less case is served by RECIPE_DEMAND's `EQUIPPABLE_KEEP` blanket, and
    charging it here too would double-count nothing but confuse the census's
    binding check."""
    gd = _slot_gd()
    state = make_state(level=10, inventory={"copper_ring": 3})
    ctx = _ctx()
    assert reason_quantity(KeepReason.GEAR_DEMAND, "copper_ring", state, gd, ctx) == 0
    assert keep_owned("copper_ring", state, gd, ctx) == 1  # RECIPE_DEMAND's blanket


def test_slot_silence_floor_ignores_non_equippables():
    """A resource has no slot to be silent about."""
    gd = _slot_gd()
    state = make_state(level=10, inventory={"copper_ore": 30})
    ctx = _ctx(gear_keep={"copper_dagger": 1})
    assert reason_quantity(KeepReason.GEAR_DEMAND, "copper_ore", state, gd, ctx) == 0


# ---------------------------------------------------------------------------
# The means predicates must see the BOUND step profile (whole-branch review,
# finding 3).
# ---------------------------------------------------------------------------

def test_means_predicates_fire_on_the_BOUND_step_profile():
    """`active_means` used to be called with the ctx BEFORE `step_profile` was bound
    onto it, so the three means that ask the keep authority what may be shed —
    SELL_IDLE, RECYCLE_SURPLUS, DRAIN_BANK_JUNK — evaluated on an EMPTY profile while
    the goals they map to ran on the full one. The predicate over-fires, the goal
    reports itself satisfied, and the arbiter carries a zero-length plan candidate.

    Here the bank holds EXACTLY the wood the active step's 40 ash_plank need. On the
    unbound ctx the drain licenses 350 of them (the control below); on the bound ctx
    it licenses none, so DRAIN_BANK_JUNK must not fire at all."""
    gd = _gather_gd()
    wood = 400  # closure of 40 ash_plank
    state = make_state(level=10, hp=100, max_hp=100, skills={"woodcutting": 1},
                       inventory={}, inventory_max=110,
                       bank_items={"ash_wood": wood})
    step = ObtainItem("ash_plank", 40)
    decision = StrategyDecision(interrupt=None, chosen_root=step, chosen_step=step,
                                desired_state={})
    arbiter = _CtxSpyArbiter(GOAPPlanner())
    arbiter.set_cycle(0)
    arbiter.select(decision, state, gd, [], _ctx())

    ctx = arbiter.seen_ctx
    assert ctx is not None and ctx.step_profile.get("ash_wood") == wood
    assert bank_drain_excess(state, gd, ctx) == {}
    assert MeansKind.DRAIN_BANK_JUNK.value not in arbiter.last_fires["discretionary"]

    # Control: on the ctx the predicate USED to see (no step profile), the drain
    # licenses hundreds of the step's own materials — which is exactly the
    # over-fire.
    assert bank_drain_excess(state, gd, _ctx())["ash_wood"] > 0


def test_slot_silence_floor_ignores_codes_the_catalog_does_not_know():
    """A `gear_keep` entry (or a queried code) the catalog has no stats for cannot
    contribute a SLOT — the authority reads game data or reads nothing, it never
    invents a slot for an unknown item."""
    gd = _slot_gd()
    state = make_state(level=10, inventory={"copper_ring": 3})
    # An unknown code in the profile contributes no covered slot, so the ring's slot
    # is still silent and its floor still applies.
    ctx = _ctx(gear_keep={"phantom_item": 1})
    assert reason_quantity(KeepReason.GEAR_DEMAND, "copper_ring", state, gd, ctx) == 1
    # An unknown QUERIED code has no slots at all -> no floor.
    assert reason_quantity(KeepReason.GEAR_DEMAND, "phantom_item", state, gd, ctx) == 1
    assert reason_quantity(KeepReason.GEAR_DEMAND, "other_phantom", state, gd, ctx) == 0
