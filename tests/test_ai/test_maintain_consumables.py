"""Tests for PLAN #6a: strategic heal-consumable supply.

Covers the shared pure helpers (consumable_supply), the MAINTAIN_CONSUMABLES
means predicate, its arbiter mapping, and MaintainConsumablesGoal.
"""

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.consumable_supply import (
    HEAL_STOCK_FLOOR,
    best_craftable_heal,
    best_held_heal,
    best_held_heal_restore,
    heal_stock,
    heal_stock_target,
    maintain_consumables_fires,
)
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.maintain_consumables import (
    MAINTAIN_CONSUMABLES_VALUE,
    MaintainConsumablesGoal,
)
from artifactsmmo_cli.ai.strategy_driver import map_means
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.means import MeansKind, active_means
from tests.test_ai.fixtures import make_state


def _gd(*, cook_level: int = 1) -> GameData:
    """GameData where cooking a 50-HP fish meal is the only heal recipe."""
    gd = GameData()
    gd._item_stats = {
        "cooked_fish": ItemStats(code="cooked_fish", level=1, type_="consumable",
                                 hp_restore=50, crafting_skill="cooking", crafting_level=cook_level),
        "raw_fish": ItemStats(code="raw_fish", level=1, type_="resource"),
        "apple": ItemStats(code="apple", level=1, type_="consumable", hp_restore=20),
    }
    gd._crafting_recipes = {"cooked_fish": {"raw_fish": 1}}
    gd._resource_drops = {"fishing_spot": "raw_fish"}
    gd._resource_locations = {"fishing_spot": [(2, 0)]}
    gd._workshop_locations = {"cooking": (3, 0)}
    return gd


def _state(**kw):
    base = dict(skills={"cooking": 5}, x=1, y=1)
    base.update(kw)
    return make_state(**base)


# ── consumable_supply pure helpers ───────────────────────────────────────────

def test_heal_stock_counts_only_restorers():
    gd = _gd()
    s = _state(inventory={"apple": 3, "cooked_fish": 2, "raw_fish": 9})
    assert heal_stock(s, gd) == 5  # apples + meals; raw_fish has no hp_restore


def test_heal_stock_ignores_zero_and_unknown():
    gd = _gd()
    s = _state(inventory={"apple": 0, "mystery": 4})
    assert heal_stock(s, gd) == 0


def test_best_held_heal_restore():
    gd = _gd()
    # a zero-qty entry is skipped; strongest held wins.
    assert best_held_heal_restore(_state(inventory={"apple": 0, "cooked_fish": 1}), gd) == 50
    assert best_held_heal_restore(_state(inventory={}), gd) == 0


def test_best_craftable_heal_picks_strongest_craftable():
    gd = _gd()
    assert best_craftable_heal(_state(inventory={}), gd) == "cooked_fish"


def test_best_craftable_heal_none_when_skill_gate_unmet():
    gd = _gd()
    s = _state(skills={"cooking": 1})  # recipe needs level 3
    gd._item_stats["cooked_fish"].crafting_level = 3
    assert best_craftable_heal(s, gd) is None


def test_best_craftable_heal_none_when_only_weaker_than_held():
    gd = _gd()
    # Holding an 80-restore heal; the only craftable is the 50 fish — not "better".
    gd._item_stats["elixir"] = ItemStats(code="elixir", level=1, type_="consumable", hp_restore=80)
    s = _state(inventory={"elixir": 1})
    assert best_craftable_heal(s, gd) is None


def test_best_craftable_heal_skips_non_craftable_and_non_heal():
    gd = _gd()
    gd._crafting_recipes["iron_sword"] = {"iron": 2}  # craftable but hp_restore 0 (non-heal)
    gd._item_stats["iron_sword"] = ItemStats(code="iron_sword", level=1, type_="weapon",
                                             crafting_skill="weaponcrafting", crafting_level=1)
    # a craftable heal with NO crafting_skill is skipped (can't actually be made by a skill).
    gd._crafting_recipes["apple"] = {"raw_fish": 2}
    assert best_craftable_heal(_state(inventory={}), gd) == "cooked_fish"


def test_maintain_fires_when_understocked_and_craftable():
    gd = _gd()
    assert maintain_consumables_fires(_state(inventory={"cooked_fish": 1}), gd) is True


def test_maintain_does_not_fire_when_stocked():
    gd = _gd()
    s = _state(inventory={"cooked_fish": HEAL_STOCK_FLOOR})
    assert maintain_consumables_fires(s, gd) is False


def test_maintain_does_not_fire_when_nothing_craftable():
    gd = _gd()
    gd._crafting_recipes = {}  # no recipes at all
    assert maintain_consumables_fires(_state(inventory={}), gd) is False


# ── means predicate (combat-active gate) ─────────────────────────────────────

def _ctx(**kw) -> SelectionContext:
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None)
    base.update(kw)
    return SelectionContext(**base)


def test_means_fires_only_when_combat_active():
    gd = _gd()
    s = _state(inventory={})  # understocked + craftable
    _, disc_combat = active_means(s, gd, None, _ctx(combat_monster="chicken"))
    _, disc_idle = active_means(s, gd, None, _ctx(combat_monster=None))
    assert MeansKind.MAINTAIN_CONSUMABLES in disc_combat
    assert MeansKind.MAINTAIN_CONSUMABLES not in disc_idle


def test_means_does_not_fire_when_stocked_even_in_combat():
    gd = _gd()
    s = _state(inventory={"cooked_fish": HEAL_STOCK_FLOOR})
    _, disc = active_means(s, gd, None, _ctx(combat_monster="chicken"))
    assert MeansKind.MAINTAIN_CONSUMABLES not in disc


# ── arbiter mapping ──────────────────────────────────────────────────────────

def test_map_means_routes_to_goal():
    gd = _gd()
    goal = map_means(MeansKind.MAINTAIN_CONSUMABLES, gd, _ctx(combat_monster="chicken"),
                     _state(inventory={}))
    assert isinstance(goal, MaintainConsumablesGoal)
    assert repr(goal) == "MaintainConsumables"


# ── goal behaviour ───────────────────────────────────────────────────────────

def test_goal_value_and_satisfaction():
    gd = _gd()
    goal = MaintainConsumablesGoal(game_data=gd)
    understocked = _state(inventory={})
    stocked = _state(inventory={"cooked_fish": HEAL_STOCK_FLOOR})
    assert goal.is_satisfied(understocked) is False
    assert goal.value(understocked, gd) == MAINTAIN_CONSUMABLES_VALUE
    assert goal.is_satisfied(stocked) is True
    assert goal.value(stocked, gd) == 0.0
    assert goal.desired_state(understocked, gd) == {"heal_stock_maintained": True}


def test_goal_relevant_actions_empty_when_nothing_craftable():
    gd = _gd()
    gd._crafting_recipes = {}
    goal = MaintainConsumablesGoal(game_data=gd)
    assert goal.relevant_actions([MoveAction(x=0, y=0)], _state(inventory={}), gd) == []


def test_goal_relevant_actions_filters_to_heal_closure():
    gd = _gd()
    goal = MaintainConsumablesGoal(game_data=gd)
    actions = [
        CraftAction(code="cooked_fish", quantity=1, workshop_location=(3, 0)),
        CraftAction(code="iron_sword", quantity=1, workshop_location=(5, 0)),  # unrelated
        GatherAction(resource_code="fishing_spot", locations=frozenset({(2, 0)})),
        GatherAction(resource_code="copper_rocks", locations=frozenset({(9, 9)})),  # unrelated
        WithdrawItemAction(code="raw_fish", quantity=1, bank_location=(4, 0)),
        WithdrawItemAction(code="gold_ore", quantity=1, bank_location=(4, 0)),  # unrelated
        MoveAction(x=1, y=1),
    ]
    out = goal.relevant_actions(actions, _state(inventory={}), gd)
    crafts = [a for a in out if isinstance(a, CraftAction)]
    gathers = [a for a in out if isinstance(a, GatherAction)]
    withdraws = [a for a in out if isinstance(a, WithdrawItemAction)]
    # the heal craft is rebatched to the full deficit (floor - 0 held = 5).
    assert len(crafts) == 1 and crafts[0].code == "cooked_fish" and crafts[0].quantity == HEAL_STOCK_FLOOR
    assert [g.resource_code for g in gathers] == ["fishing_spot"]
    assert [w.code for w in withdraws] == ["raw_fish"]
    assert any(isinstance(a, MoveAction) for a in out)


def test_goal_relevant_actions_includes_craftable_intermediate():
    gd = _gd()
    # cooked_fish now goes through a craftable intermediate (fish_fillet).
    gd._crafting_recipes = {"cooked_fish": {"fish_fillet": 1}, "fish_fillet": {"raw_fish": 1}}
    gd._item_stats["fish_fillet"] = ItemStats(code="fish_fillet", level=1, type_="resource",
                                              crafting_skill="cooking", crafting_level=1)
    goal = MaintainConsumablesGoal(game_data=gd)
    actions = [
        CraftAction(code="cooked_fish", quantity=1, workshop_location=(3, 0)),
        CraftAction(code="fish_fillet", quantity=1, workshop_location=(3, 0)),
    ]
    out = goal.relevant_actions(actions, _state(inventory={}), gd)
    assert any(isinstance(a, CraftAction) and a.code == "fish_fillet" for a in out)


def test_goal_repr():
    assert repr(MaintainConsumablesGoal(game_data=_gd())) == "MaintainConsumables"


# ── best_held_heal (returns code, not value) ─────────────────────────────────

def _gd_with_craftable_heal(code: str, *, hp_restore: int,
                             craft_skill: str = "cooking") -> GameData:
    """Minimal GameData where `code` is a craftable heal consumable."""
    gd = GameData()
    gd._item_stats = {
        code: ItemStats(code=code, level=1, type_="consumable",
                        hp_restore=hp_restore, crafting_skill=craft_skill,
                        crafting_level=1),
    }
    gd._crafting_recipes = {code: {"raw_material": 1}}
    gd._resource_drops = {}
    gd._resource_locations = {}
    gd._workshop_locations = {craft_skill: (0, 0)}
    return gd


def test_best_held_heal_returns_code_of_strongest():
    gd = _gd()
    # cooked_fish (50) beats apple (20)
    s = _state(inventory={"apple": 2, "cooked_fish": 1})
    assert best_held_heal(s, gd) == "cooked_fish"


def test_best_held_heal_returns_none_when_no_heals_held():
    gd = _gd()
    assert best_held_heal(_state(inventory={}), gd) is None


def test_best_held_heal_skips_zero_qty():
    gd = _gd()
    s = _state(inventory={"cooked_fish": 0, "apple": 1})
    assert best_held_heal(s, gd) == "apple"


def test_best_held_heal_tiebreak_on_smallest_code():
    gd = _gd()
    # apple and zfood both hp_restore=20 → "apple" wins lexically
    gd._item_stats["zfood"] = ItemStats(code="zfood", level=1, type_="consumable", hp_restore=20)
    s = _state(inventory={"zfood": 1, "apple": 1})
    assert best_held_heal(s, gd) == "apple"


# ── heal_stock_target clamp ───────────────────────────────────────────────────

def test_heal_stock_target_clamps_to_floor():
    assert heal_stock_target(0) == HEAL_STOCK_FLOOR
    assert heal_stock_target(1) == HEAL_STOCK_FLOOR


def test_heal_stock_target_clamps_to_max_stack():
    assert heal_stock_target(200) == 100


def test_heal_stock_target_passthrough_in_range():
    assert heal_stock_target(50) == 50


# ── maintain_consumables_fires with desired_stock ─────────────────────────────

def test_maintain_fires_until_desired_stack_when_marginal_target_demands_more():
    # holds 8 heals; a marginal target wants 50 -> still under-stocked -> fires
    state = _state(inventory={"small_health_potion": 8},
                   skills={"alchemy": 5})
    gd = _gd_with_craftable_heal("small_health_potion", hp_restore=60, craft_skill="alchemy")
    assert maintain_consumables_fires(state, gd, desired_stock=50) is True


def test_maintain_does_not_fire_when_held_meets_desired():
    state = _state(inventory={"small_health_potion": 50},
                   skills={"alchemy": 5})
    gd = _gd_with_craftable_heal("small_health_potion", hp_restore=60, craft_skill="alchemy")
    assert maintain_consumables_fires(state, gd, desired_stock=50) is False
