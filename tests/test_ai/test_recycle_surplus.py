"""Tests for recyclable-surplus detection + RecycleSurplusGoal (proactive recycle)."""

from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.recycle_surplus import RecycleSurplusGoal
from artifactsmmo_cli.ai.recycle_surplus import recyclable_surplus
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
        # Equippable + crafting_skill but NO recipe (malformed/dropped gear):
        # recycling needs a recipe to recover materials, so it is excluded.
        "no_recipe_ring": ItemStats(code="no_recipe_ring", level=1, type_="ring",
                                    crafting_skill="jewelrycrafting", crafting_level=1),
    }
    gd._crafting_recipes = {"copper_helmet": {"copper_bar": 6},
                            "copper_boots": {"copper_bar": 8},
                            "iron_helmet": {"iron_bar": 6}}
    gd._workshop_locations = {"gearcrafting": (2, 1), "jewelrycrafting": (5, 1)}
    return gd


def test_surplus_includes_overstocked_recyclable_gear():
    """A craftable equippable held above its useful cap (1), skill met, workshop
    known, not protected, not equipped → surplus = held - 1."""
    gd = _gd()
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"copper_helmet": 9})
    assert recyclable_surplus(state, gd, protected_codes=frozenset()) == {"copper_helmet": 8}


def test_surplus_excludes_committed_objective_gear():
    """Objective gear (protected) is never recycled even when overstocked."""
    gd = _gd()
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"copper_boots": 9})
    assert recyclable_surplus(state, gd, protected_codes=frozenset({"copper_boots"})) == {}


def test_surplus_excludes_skill_gated_and_raw():
    """Skill-gated (iron_helmet lvl 10), raw materials (copper_ore), and
    recipe-less gear are not recyclable-surplus."""
    gd = _gd()
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"iron_helmet": 5, "copper_ore": 50, "no_recipe_ring": 3})
    out = recyclable_surplus(state, gd, protected_codes=frozenset())
    assert "iron_helmet" not in out      # skill gate (gearcrafting 1 < 10)
    assert "copper_ore" not in out       # raw / not equipment
    assert "no_recipe_ring" not in out   # equippable + skill but no recipe


def test_equipped_code_spares_above_cap_are_surplus():
    """Wearing one copy must NOT shield the BAG spares from recycling.

    Regression (trace 2026-07-05): Robby wore copper_helmet and hoarded 25
    spares — the old blanket `code in equipped` skip hid them from
    RecycleSurplus forever. The useful cap (which already keeps >=1 for an
    equipped code) is the right guard: 25 held, cap 1 → surplus 24. The WORN
    copy is not in the inventory count, so it is never recycled."""
    gd = _gd()
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"copper_helmet": 25},
                       equipment={"helmet_slot": "copper_helmet"})
    assert recyclable_surplus(state, gd, protected_codes=frozenset()) == {"copper_helmet": 24}


def test_equipped_code_at_cap_is_not_surplus():
    """One spare in the bag for an equipped code sits AT the useful cap —
    nothing to recycle."""
    gd = _gd()
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"copper_helmet": 1},
                       equipment={"helmet_slot": "copper_helmet"})
    assert recyclable_surplus(state, gd, protected_codes=frozenset()) == {}


def test_goal_relevant_actions_recycles_surplus_not_deletes():
    """RecycleSurplusGoal emits a RecycleAction (recover materials) for surplus
    gear, with a quantity that fits free space."""
    gd = _gd()
    # Big bag so recovering bars fits (proactive, low-pressure).
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"copper_helmet": 9}, inventory_max=200)
    goal = RecycleSurplusGoal(game_data=gd, protected_codes=frozenset())
    actions = goal.relevant_actions([], state, gd)
    assert len(actions) == 1
    a = actions[0]
    assert isinstance(a, RecycleAction)
    assert a.code == "copper_helmet"
    assert a.workshop_location == (2, 1)
    assert 1 <= a.quantity <= 8
    assert a.is_applicable(state, gd)


def test_goal_satisfied_when_no_surplus():
    gd = _gd()
    state = make_state(level=5, skills={"gearcrafting": 1}, inventory={"copper_helmet": 1})
    goal = RecycleSurplusGoal(game_data=gd, protected_codes=frozenset())
    assert goal.is_satisfied(state) is True
    assert goal.value(state, gd) == 0.0


def _ctx(**kw):
    from artifactsmmo_cli.ai.tiers.guards import SelectionContext
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None,
                gear_review_active=False)
    base.update(kw)
    return SelectionContext(**base)


def test_fires_on_idle_surplus_not_under_pressure_or_objective():
    from artifactsmmo_cli.ai.tiers.means import MeansKind, _fires
    gd = _gd()
    # Idle (low fill), surplus copper_helmet, not objective -> fires.
    idle = make_state(level=5, skills={"gearcrafting": 1},
                      inventory={"copper_helmet": 9}, inventory_max=200)
    assert _fires(MeansKind.RECYCLE_SURPLUS, idle, gd, None, _ctx()) is True
    # Under space pressure (>=0.85 full) -> does NOT fire (no room to recover).
    pressured = make_state(level=5, skills={"gearcrafting": 1},
                           inventory={"copper_helmet": 9, "junk": 180}, inventory_max=200)
    assert _fires(MeansKind.RECYCLE_SURPLUS, pressured, gd, None, _ctx()) is False
    # Surplus is the committed objective gear -> protected, does NOT fire.
    assert _fires(MeansKind.RECYCLE_SURPLUS, idle, gd, None,
                  _ctx(target_gear=frozenset({"copper_helmet"}))) is False


def test_map_means_returns_recycle_goal():
    from artifactsmmo_cli.ai.tiers.means import MeansKind
    from artifactsmmo_cli.ai.strategy_driver import map_means
    g = map_means(MeansKind.RECYCLE_SURPLUS, _gd(), _ctx(), make_state())
    assert isinstance(g, RecycleSurplusGoal)


def test_surplus_excludes_when_no_workshop_known():
    """No workshop for the crafting skill -> cannot recycle -> not surplus."""
    gd = _gd()
    gd._workshop_locations = {}  # unknown workshop
    state = make_state(level=5, skills={"gearcrafting": 1}, inventory={"copper_helmet": 9})
    assert recyclable_surplus(state, gd, protected_codes=frozenset()) == {}


def test_goal_value_positive_with_surplus_and_metadata():
    gd = _gd()
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"copper_helmet": 9}, inventory_max=200)
    goal = RecycleSurplusGoal(game_data=gd, protected_codes=frozenset())
    assert goal.value(state, gd) == 20.0
    assert goal.is_satisfied(state) is False
    assert goal.desired_state(state, gd) == {"surplus_gear_recycled": True}
    assert goal.max_depth == 15
    assert repr(goal) == "RecycleSurplus"
