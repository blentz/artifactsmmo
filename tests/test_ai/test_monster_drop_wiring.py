"""Wiring for the proven `select_monster_for_drop` core onto a LIVE planner path.

Producibility (tiers/strategy._producible): a monster-drop item is producible iff
some monster dropping it is WINNABLE (else it would create an unreachable plan).

Emission + narrowing (GatherMaterialsGoal.relevant_actions): for a needed item that
is a monster drop, enumerate a FightAction per WINNABLE dropping monster, build a
MonsterDropCandidate per monster, call select_monster_for_drop, and keep ONLY the
winner FightAction (structurally identical to the existing GatherSelection narrowing).
"""
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.strategy_driver import objective_step_goal
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.strategy import _producible
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


def _ctx() -> SelectionContext:
    return SelectionContext(
        bank_accessible=True, bank_required_level=1, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=0, combat_monster=None,
    )


def _winnable_state(**overrides) -> object:
    """A character with real attack so predict_win can produce damage; the
    fixtures below give droppers low HP and no attack so they are winnable."""
    base = dict(level=1, x=0, y=0, max_hp=100, hp=100,
                attack={"fire": 30}, initiative=50)
    base.update(overrides)
    return make_state(**base)


def test_gather_feather_plans_via_fighting_chicken() -> None:
    """End-to-end: with FightAction.apply modelling the drop, GatherMaterials over
    a monster-drop material (feather <- chicken) is plannable as a sequence of
    fights. Before the apply fix this explored thousands of nodes and returned []
    (trace 2026-06-14 230824: GatherMaterials(feather) plan_len 0, 21868 nodes),
    so the bot could never obtain feather and fell to char-grind."""
    gd = GameData()
    gd._monster_level = {"chicken": 1}
    gd._monster_drops = {"chicken": [("feather", 8, 1, 1)]}
    gd._monster_locations = {"chicken": [(0, 1)]}
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"chicken": 10}
    state = _winnable_state(inventory={}, inventory_max=50)
    actions = [FightAction(monster_code="chicken", locations=frozenset({(0, 1)}))]
    goal = GatherMaterialsGoal(target_item="feather", needed={"feather": 2})
    plan = GOAPPlanner().plan(state, goal, actions, gd, budget_seconds=10.0)
    assert plan, "GatherMaterials(feather) must be plannable via fighting chicken"
    assert any(isinstance(a, FightAction) for a in plan)


def _gd_two_droppers() -> GameData:
    """raw_egg dropped by two WINNABLE monsters at different rates:
    chicken (rate 5, common) and rooster (rate 20, rare). Both have small HP
    and no attack, so predict_win=True against the _winnable_state player."""
    gd = GameData()
    gd._monster_level = {"chicken": 1, "rooster": 1}
    gd._monster_drops = {
        "chicken": [("raw_egg", 5, 1, 1)],
        "rooster": [("raw_egg", 20, 1, 1)],
    }
    gd._monster_locations = {"chicken": [(0, 1)], "rooster": [(0, 2)]}
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"chicken": 10, "rooster": 10}
    return gd


def _gd_unwinnable_dropper() -> GameData:
    """rare_hide dropped only by an UNWINNABLE monster (huge HP + attack)."""
    gd = GameData()
    gd._monster_level = {"dragon": 30}
    gd._monster_drops = {"dragon": [("rare_hide", 10, 1, 1)]}
    gd._monster_locations = {"dragon": [(5, 5)]}
    fill_monster_stat_defaults(gd)
    # Make the dragon genuinely unwinnable: high HP, lethal attack.
    gd._monster_hp = {"dragon": 100000}
    gd._monster_attack = {"dragon": {"fire": 10000}}
    gd._monster_initiative = {"dragon": 1000}
    return gd


# --- STEP 2: producibility ---------------------------------------------------


def test_producible_true_for_winnable_monster_drop() -> None:
    gd = _gd_two_droppers()
    state = _winnable_state()
    assert _producible("raw_egg", state, gd) is True


def test_not_producible_for_unwinnable_monster_drop() -> None:
    gd = _gd_unwinnable_dropper()
    state = make_state(level=1)
    assert _producible("rare_hide", state, gd) is False


def test_not_producible_for_winnable_dropper_with_no_spawn_location() -> None:
    """A needed item dropped only by a WINNABLE monster that has NO known spawn
    location is NOT producible: relevant_actions would emit no FightAction (the
    fight-is-None guard), so marking it producible creates a stuck plan."""
    gd = GameData()
    gd._monster_level = {"chicken": 1}
    gd._monster_drops = {"chicken": [("raw_egg", 5, 1, 1)]}
    gd._monster_locations = {}  # winnable, but nowhere to fight it
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"chicken": 10}
    state = _winnable_state()
    assert _producible("raw_egg", state, gd) is False


def test_producible_true_for_winnable_dropper_with_spawn_location() -> None:
    """Symmetric positive: the SAME winnable dropper WITH a known spawn location
    is producible (existing behavior preserved — a FightAction can be emitted)."""
    gd = GameData()
    gd._monster_level = {"chicken": 1}
    gd._monster_drops = {"chicken": [("raw_egg", 5, 1, 1)]}
    gd._monster_locations = {"chicken": [(0, 1)]}
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"chicken": 10}
    state = _winnable_state()
    assert _producible("raw_egg", state, gd) is True


def test_producible_still_true_for_craftable() -> None:
    gd = GameData()
    gd._crafting_recipes = {"iron_helm": {"iron_bar": 5}}
    state = make_state(level=1)
    assert _producible("iron_helm", state, gd) is True


def test_producible_false_for_unknown_item() -> None:
    gd = GameData()
    state = make_state(level=1)
    assert _producible("phantom_item", state, gd) is False


# --- STEP 4 / STEP 5: live emission + narrowing (the liveness proof) ---------


def test_relevant_actions_emits_only_winner_fight_for_drop() -> None:
    """Integration / liveness: a needed monster-drop item dropped by 2 winnable
    monsters at different rates → relevant_actions emits ONLY the
    select_monster_for_drop winner FightAction (chicken, rate 5 < rooster 20)."""
    gd = _gd_two_droppers()
    state = _winnable_state()
    goal = GatherMaterialsGoal(target_item="raw_egg", needed={"raw_egg": 3})
    actions = [
        FightAction(monster_code="chicken", locations=frozenset([(0, 1)])),
        FightAction(monster_code="rooster", locations=frozenset([(0, 2)])),
    ]
    relevant = goal.relevant_actions(actions, state, gd)
    fights = [a for a in relevant if isinstance(a, FightAction)]
    assert [f.monster_code for f in fights] == ["chicken"], (
        f"expected only the winner (chicken), got {[f.monster_code for f in fights]}"
    )


def test_relevant_actions_no_fight_for_unwinnable_drop() -> None:
    """An item dropped only by an unwinnable monster → no FightAction emitted
    (existing fail behavior: not producible, nothing to fight)."""
    gd = _gd_unwinnable_dropper()
    state = make_state(level=1, x=0, y=0)
    goal = GatherMaterialsGoal(target_item="rare_hide", needed={"rare_hide": 1})
    actions = [FightAction(monster_code="dragon", locations=frozenset([(5, 5)]))]
    relevant = goal.relevant_actions(actions, state, gd)
    assert not any(isinstance(a, FightAction) for a in relevant)


def test_relevant_actions_single_winnable_dropper_kept() -> None:
    """Single winnable dropper: its FightAction survives (no narrowing needed)."""
    gd = GameData()
    gd._monster_level = {"chicken": 1}
    gd._monster_drops = {"chicken": [("raw_egg", 5, 1, 1)]}
    gd._monster_locations = {"chicken": [(0, 1)]}
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"chicken": 10}
    state = _winnable_state()
    goal = GatherMaterialsGoal(target_item="raw_egg", needed={"raw_egg": 2})
    actions = [FightAction(monster_code="chicken", locations=frozenset([(0, 1)]))]
    relevant = goal.relevant_actions(actions, state, gd)
    fights = [a for a in relevant if isinstance(a, FightAction)]
    assert [f.monster_code for f in fights] == ["chicken"]


def test_arbiter_path_obtainitem_drop_emits_winner_fight() -> None:
    """End-to-end liveness: the arbiter bridge maps an ObtainItem(monster_drop)
    step to a GatherMaterialsGoal, whose relevant_actions emits ONLY the
    select_monster_for_drop winner FightAction — proving select_monster_for_drop
    is invoked on a genuine planner path, not just a unit test."""
    gd = _gd_two_droppers()
    state = _winnable_state()
    step = ObtainItem("raw_egg", 3)
    goal = objective_step_goal(step, state, gd, _ctx())
    assert isinstance(goal, GatherMaterialsGoal)
    actions = [
        FightAction(monster_code="chicken", locations=frozenset([(0, 1)])),
        FightAction(monster_code="rooster", locations=frozenset([(0, 2)])),
    ]
    relevant = goal.relevant_actions(actions, state, gd)
    fights = [a for a in relevant if isinstance(a, FightAction)]
    assert [f.monster_code for f in fights] == ["chicken"]


def test_relevant_actions_skips_dropper_with_no_fight_action() -> None:
    """A dropping monster with NO FightAction in the action set is skipped
    (line guard: fight is None), and the winnable dropper that DOES have one
    is still emitted."""
    gd = _gd_two_droppers()
    state = _winnable_state()
    goal = GatherMaterialsGoal(target_item="raw_egg", needed={"raw_egg": 1})
    # Only chicken has a FightAction; rooster (also a dropper) has none.
    actions = [FightAction(monster_code="chicken", locations=frozenset([(0, 1)]))]
    relevant = goal.relevant_actions(actions, state, gd)
    fights = [a for a in relevant if isinstance(a, FightAction)]
    assert [f.monster_code for f in fights] == ["chicken"]


def test_relevant_actions_dropper_with_no_locations_uses_zero_distance() -> None:
    """A winnable dropper whose FightAction carries no locations → distance 0;
    selection still emits it as the sole winner."""
    gd = GameData()
    gd._monster_level = {"chicken": 1}
    gd._monster_drops = {"chicken": [("raw_egg", 5, 1, 1)]}
    gd._monster_locations = {"chicken": []}
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"chicken": 10}
    state = _winnable_state()
    goal = GatherMaterialsGoal(target_item="raw_egg", needed={"raw_egg": 1})
    actions = [FightAction(monster_code="chicken", locations=frozenset())]
    relevant = goal.relevant_actions(actions, state, gd)
    fights = [a for a in relevant if isinstance(a, FightAction)]
    assert [f.monster_code for f in fights] == ["chicken"]


def test_relevant_actions_drops_unwinnable_dropper_keeps_winnable() -> None:
    """Mixed: a winnable and an unwinnable monster drop the same item → only the
    winnable one's FightAction is enumerated; selection runs over winnable only."""
    gd = GameData()
    gd._monster_level = {"chicken": 1, "dragon": 30}
    gd._monster_drops = {
        "chicken": [("raw_egg", 5, 1, 1)],
        "dragon": [("raw_egg", 1, 1, 1)],  # better rate but unwinnable
    }
    gd._monster_locations = {"chicken": [(0, 1)], "dragon": [(5, 5)]}
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"chicken": 10, "dragon": 100000}
    gd._monster_attack = {"chicken": {}, "dragon": {"fire": 10000}}
    gd._monster_initiative = {"chicken": 0, "dragon": 1000}
    state = _winnable_state()
    goal = GatherMaterialsGoal(target_item="raw_egg", needed={"raw_egg": 1})
    actions = [
        FightAction(monster_code="chicken", locations=frozenset([(0, 1)])),
        FightAction(monster_code="dragon", locations=frozenset([(5, 5)])),
    ]
    relevant = goal.relevant_actions(actions, state, gd)
    fights = [a for a in relevant if isinstance(a, FightAction)]
    assert [f.monster_code for f in fights] == ["chicken"]
