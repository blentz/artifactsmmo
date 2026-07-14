"""Tests for recyclable-surplus detection + RecycleSurplusGoal (proactive recycle)."""

from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.recycle_surplus import RecycleSurplusGoal
from artifactsmmo_cli.ai.inventory_keep import destroyable, keep_owned
from artifactsmmo_cli.ai.recycle_surplus import recyclable_surplus
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_helmet": ItemStats(code="copper_helmet", level=1, type_="helmet",
                                   crafting_skill="gearcrafting", crafting_level=1),
        "copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                  crafting_skill="gearcrafting", crafting_level=1),
        "iron_helmet": ItemStats(code="iron_helmet", level=10, type_="helmet",
                                 crafting_skill="gearcrafting", crafting_level=10),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        # The live hoard (Robby 2026-07-12): the best woodcutting TOOL, and a
        # weaponcrafting grind rung — so the skill grind keeps feeding the pile.
        "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon",
                                attack={"earth": 3}, skill_effects={"woodcutting": -10},
                                crafting_skill="weaponcrafting", crafting_level=1),
        # Equippable + crafting_skill but NO recipe (malformed/dropped gear):
        # recycling needs a recipe to recover materials, so it is excluded.
        "no_recipe_ring": ItemStats(code="no_recipe_ring", level=1, type_="ring",
                                    crafting_skill="jewelrycrafting", crafting_level=1),
    }
    gd._crafting_recipes = {"copper_helmet": {"copper_bar": 6},
                            "copper_boots": {"copper_bar": 8},
                            "copper_axe": {"copper_bar": 6},
                            "iron_helmet": {"iron_bar": 6}}
    gd._workshop_locations = {"gearcrafting": (2, 1), "jewelrycrafting": (5, 1),
                              "weaponcrafting": (3, 1)}
    return gd


def _ctx(**kw) -> SelectionContext:
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None,
                gear_review_active=False)
    base.update(kw)
    return SelectionContext(**base)


def test_surplus_includes_overstocked_recyclable_gear():
    """A craftable equippable held above its useful cap (1), skill met, workshop
    known, not protected, not equipped → surplus = held - 1."""
    gd = _gd()
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"copper_helmet": 9})
    assert recyclable_surplus(state, gd, _ctx()) == {"copper_helmet": 8}


def test_target_tool_hoard_keeps_ONE_and_recycles_the_REST():
    """THE live hoard (Robby 2026-07-12): 18 copper_axe — the axe is the best
    woodcutting tool AND a `target_tools` code, so the old blanket
    `recycle_protected_codes` fallback (`target_gear | target_tools`, used
    whenever no loadout profile is recorded) hid the WHOLE CODE from every
    recycle path while the weaponcrafting grind kept manufacturing more.

    A code-SET can only say "keep ALL copies". The keep authority says: keep the
    ONE the gather re-arm will equip (KeepReason.WORKING_KIT), recycle the 17."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 18})
    ctx = _ctx(target_tools=frozenset({"copper_axe"}))
    assert recyclable_surplus(state, gd, ctx) == {"copper_axe": 17}
    assert state.inventory["copper_axe"] - 17 == 1


def test_ferried_working_tool_is_never_recycled_even_with_bank_spares():
    """Destruction is bag-side, so it answers to the IN-BAG cap too. After the
    deposit path banks the 17 spares, the ONE axe left in the bag is the tool the
    gather re-arm is about to equip (WithdrawTools ferries it a cycle before
    OptimizeLoadout wears it). `destroyable` alone would license it — 18 owned,
    keep_owned 1 → 17 destroyable, and the only reachable copy is the working
    one. `keep_in_bag` (WORKING_KIT = 1) is what makes it untouchable."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 1}, bank_items={"copper_axe": 17})
    assert recyclable_surplus(state, gd, _ctx()) == {}


def test_surplus_excludes_gear_the_active_profile_demands():
    """Active-profile gear demand (KeepReason.GEAR_DEMAND) is an OWNED cap: 2
    boots demanded, 2 held → nothing destroyable."""
    gd = _gd()
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"copper_boots": 2})
    assert recyclable_surplus(state, gd, _ctx(gear_keep={"copper_boots": 2})) == {}


def test_profile_demand_is_a_cap_not_a_blanket():
    """...and the copies ABOVE the demand are still reclaimable — the caps-beat-
    blankets half of the same rule (gear_keep['copper_helmet']=1 once acted as
    'keep all 41')."""
    gd = _gd()
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"copper_helmet": 41},
                       equipment={"helmet_slot": "copper_helmet"})
    ctx = _ctx(gear_keep={"copper_helmet": 1})
    assert recyclable_surplus(state, gd, ctx) == {"copper_helmet": 40}


def test_zero_quantity_entry_is_not_surplus():
    """A drained stack can linger in the inventory map at qty 0 (the state is
    rebuilt from the API each cycle, but `apply` decrements in place during
    planning). It is not held, so it is not surplus — and it must not reach the
    keep authority, where `bankable` would happily report 0 and the goal would
    emit a Recycle x0."""
    gd = _gd()
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"copper_helmet": 0})
    assert recyclable_surplus(state, gd, _ctx()) == {}


def test_surplus_excludes_skill_gated_and_raw():
    """Skill-gated (iron_helmet lvl 10), raw materials (copper_ore), and
    recipe-less gear are not recyclable-surplus."""
    gd = _gd()
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"iron_helmet": 5, "copper_ore": 50, "no_recipe_ring": 3})
    out = recyclable_surplus(state, gd, _ctx())
    assert "iron_helmet" not in out      # skill gate (gearcrafting 1 < 10)
    assert "copper_ore" not in out       # raw / not equipment
    assert "no_recipe_ring" not in out   # equippable + skill but no recipe


def test_equipped_code_spares_above_cap_are_surplus():
    """Wearing one copy must NOT shield the BAG spares from recycling.

    Regression (trace 2026-07-05): Robby wore copper_helmet and hoarded 25
    spares — the old blanket `code in equipped` skip hid them from
    RecycleSurplus forever. KeepReason.EQUIPPED keeps exactly ONE: 25 held,
    keep 1 → surplus 24. The WORN copy is not in the inventory count, so it is
    never recycled."""
    gd = _gd()
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"copper_helmet": 25},
                       equipment={"helmet_slot": "copper_helmet"})
    assert recyclable_surplus(state, gd, _ctx()) == {"copper_helmet": 24}


def test_equipped_code_at_cap_is_not_surplus():
    """One spare in the bag for an equipped code sits AT the useful cap —
    nothing to recycle."""
    gd = _gd()
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"copper_helmet": 1},
                       equipment={"helmet_slot": "copper_helmet"})
    assert recyclable_surplus(state, gd, _ctx()) == {}


def test_task_item_is_never_recycled():
    """The items-task item is kept at its REMAINING demand (KeepReason
    .ACTIVE_TASK): 6 needed of 9, 6 held → nothing destroyable. Recycling the
    thing the task wants would be strictly worse than any hoard."""
    gd = _gd()
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"copper_helmet": 6},
                       task_code="copper_helmet", task_type="items",
                       task_total=9, task_progress=3)
    assert recyclable_surplus(state, gd, _ctx()) == {}


def _gd_with_crown() -> GameData:
    """`copper_crown` is craftable FROM copper_helmet — so copper_helmet carries
    a RECIPE_DEMAND of 3 as well as being gear in its own right."""
    gd = _gd()
    gd._crafting_recipes["copper_crown"] = {"copper_helmet": 3}
    gd._item_stats["copper_crown"] = ItemStats(
        code="copper_crown", level=1, type_="helmet",
        crafting_skill="gearcrafting", crafting_level=1)
    return gd


def test_recipe_demand_is_never_recycled():
    """An equippable that a known recipe CONSUMES is kept at that demand
    (KeepReason.RECIPE_DEMAND / `useful_quantity_cap`): 3 wanted, 3 held →
    nothing destroyable, even with no craft committed yet."""
    gd = _gd_with_crown()
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"copper_helmet": 3})
    assert recyclable_surplus(state, gd, _ctx()) == {}


def test_recipe_demand_surplus_above_the_demand_is_still_recycled():
    """...and the copies above the recipe demand ARE reclaimable (cap, not
    blanket). The cap is the demand times the craft BATCH_BUFFER (3 x 5 = 15,
    `inventory_caps.useful_quantity_cap`), so 20 held → 5 surplus."""
    gd = _gd_with_crown()
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"copper_helmet": 20})
    assert recyclable_surplus(state, gd, _ctx()) == {"copper_helmet": 5}


def test_currency_is_never_recyclable_surplus():
    """CURRENCY is the one KEEP_ALL reason: no copy is ever disposable. Coins are
    also not equippable, so the recyclability filter refuses them a second time —
    both halves are asserted so a taxonomy change cannot silently expose them."""
    gd = _gd()
    gd._item_stats["tasks_coin"] = ItemStats(code="tasks_coin", level=1,
                                             type_="currency")
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"tasks_coin": 40})
    assert recyclable_surplus(state, gd, _ctx()) == {}
    assert destroyable("tasks_coin", state, gd, _ctx()) == 0


def test_goal_relevant_actions_recycles_surplus_not_deletes():
    """RecycleSurplusGoal emits a RecycleAction (recover materials) for surplus
    gear, with a quantity that fits free space."""
    gd = _gd()
    # Big bag so recovering bars fits (proactive, low-pressure).
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"copper_helmet": 9}, inventory_max=200)
    goal = RecycleSurplusGoal(game_data=gd, ctx=_ctx())
    actions = goal.relevant_actions([], state, gd)
    assert len(actions) == 1
    a = actions[0]
    assert isinstance(a, RecycleAction)
    assert a.code == "copper_helmet"
    assert a.workshop_location == (2, 1)
    assert 1 <= a.quantity <= 8
    assert a.is_applicable(state, gd)


def test_goal_batch_recycle_is_stamped_with_the_owned_floor():
    """The goal builds its BATCH actions OUTSIDE `destructive_license`, so it must
    stamp `owned_floor = keep_owned` itself or the per-application bound is bypassed
    on this route (whole-branch review, CRITICAL 1). The floor never blocks the
    FIRST application — `recyclable_surplus` is bounded by `destroyable`, i.e. by
    `owned - keep_owned` — it blocks the SECOND."""
    gd = _gd()
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"copper_helmet": 9}, inventory_max=200)
    ctx = _ctx()
    floor = keep_owned("copper_helmet", state, gd, ctx)
    goal = RecycleSurplusGoal(game_data=gd, ctx=ctx)
    action = goal.relevant_actions([], state, gd)[0]
    assert action.owned_floor == floor
    assert action.is_applicable(state, gd)
    # Applying the same batch twice would destroy past `destroyable`: refused.
    assert not action.is_applicable(action.apply(state, gd), gd)


def test_goal_satisfied_when_no_surplus():
    gd = _gd()
    state = make_state(level=5, skills={"gearcrafting": 1}, inventory={"copper_helmet": 1})
    goal = RecycleSurplusGoal(game_data=gd, ctx=_ctx())
    assert goal.is_satisfied(state) is True
    assert goal.value(state, gd) == 0.0


def test_fires_on_idle_surplus_not_under_pressure_or_objective():
    from artifactsmmo_cli.ai.tiers.means import MeansKind, _fires
    gd = _gd()
    # Idle (low fill), surplus copper_helmet, nothing demands it -> fires.
    idle = make_state(level=5, skills={"gearcrafting": 1},
                      inventory={"copper_helmet": 9}, inventory_max=200)
    assert _fires(MeansKind.RECYCLE_SURPLUS, idle, gd, None, _ctx()) is True
    # Under space pressure (>=0.85 full) -> does NOT fire (no room to recover).
    pressured = make_state(level=5, skills={"gearcrafting": 1},
                           inventory={"copper_helmet": 9, "junk": 180}, inventory_max=200)
    assert _fires(MeansKind.RECYCLE_SURPLUS, pressured, gd, None, _ctx()) is False
    # The active profile demands all 9 -> nothing destroyable, does NOT fire.
    assert _fires(MeansKind.RECYCLE_SURPLUS, idle, gd, None,
                  _ctx(gear_keep={"copper_helmet": 9})) is False


def test_map_means_returns_recycle_goal():
    from artifactsmmo_cli.ai.strategy_driver import map_means
    from artifactsmmo_cli.ai.tiers.means import MeansKind
    g = map_means(MeansKind.RECYCLE_SURPLUS, _gd(), _ctx(), make_state())
    assert isinstance(g, RecycleSurplusGoal)


def test_surplus_excludes_when_no_workshop_known():
    """No workshop for the crafting skill -> cannot recycle -> not surplus."""
    gd = _gd()
    gd._workshop_locations = {}  # unknown workshop
    state = make_state(level=5, skills={"gearcrafting": 1}, inventory={"copper_helmet": 9})
    assert recyclable_surplus(state, gd, _ctx()) == {}


def test_goal_value_positive_with_surplus_and_metadata():
    gd = _gd()
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"copper_helmet": 9}, inventory_max=200)
    goal = RecycleSurplusGoal(game_data=gd, ctx=_ctx())
    # 9 held -> surplus 8 -> urgency 2 (hoard-scaled, see recycle_urgency).
    assert goal.value(state, gd) == 2 * 20.0
    assert goal.is_satisfied(state) is False
    assert goal.desired_state(state, gd) == {"surplus_gear_recycled": True}
    assert goal.max_depth == 15
    assert repr(goal) == "RecycleSurplus"
