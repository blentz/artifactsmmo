"""Task 4 RUNTIME ACTIVATION GATE: prove `EquipOwnedGoal` actually fires
through the REAL `StrategyArbiter.select` path, not merely that its unit
tests pass in isolation.

Mirrors `tests/test_ai/test_strategy_driver.py::test_select_returns_objective_step_when_calm`
(the calm-state "step wins" baseline) but adds an owned, unequipped
`novice_guide` artifact to a Robby-shaped state (level 10, all artifact
slots empty, otherwise combat-capable so a real GrindCharacterXP step
candidate exists). This is the regression lock that EquipOwnedGoal is
reachable THROUGH THE ARBITER and outranks the grind/step tier — the
exact criterion the prior gather fix failed (correct-in-unit-test but
inert at runtime).

`tests/ai/` has no `__init__.py` (unlike `tests/test_ai/`), so this file
follows the local-helper convention already used by
`tests/ai/test_equip_owned_arbiter.py` rather than cross-importing
`tests.test_ai.fixtures` / `tests.test_ai._monster_fixture`.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.equip_owned_gear import EquipOwnedGoal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import ReachCharLevel
from artifactsmmo_cli.ai.world_state import WorldState

_ALL_SLOTS: dict[str, str | None] = {
    "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
    "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
    "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
    "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
    "utility1_slot": None, "utility2_slot": None, "bag_slot": None, "rune_slot": None,
}


@dataclass(frozen=True)
class _FakeDecision:
    chosen_step: object


def _ctx(**kw: object) -> SelectionContext:
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster="chicken",
                gear_review_active=False)
    base.update(kw)
    return SelectionContext(**base)


def _state(inventory: dict[str, int]) -> WorldState:
    """Robby-shaped combat-capable state: level 10, full HP, active chicken
    task (so AcceptTask/step-suppression rules don't interfere), ALL
    artifact slots (and every other slot) empty."""
    return WorldState(
        character="Robby", level=10, xp=0, max_xp=1000, hp=150, max_hp=150, gold=0,
        skills={}, x=0, y=0, inventory=dict(inventory), inventory_max=100,
        inventory_slots_max=len(inventory),
        equipment=dict(_ALL_SLOTS), cooldown_expires=None,
        task_code="chicken", task_type="monsters", task_progress=0, task_total=10,
        task_lifecycle_phase=derive_task_lifecycle_phase("chicken", 0, 10),
        bank_items=None, bank_gold=None, bank_capacity=None, pending_items=None,
    )


def _gd() -> GameData:
    gd = GameData()
    gd._monster_locations = {"chicken": [(1, 0)]}
    gd._monster_level = {"chicken": 1}
    gd._monster_hp = {"chicken": 0}
    gd._monster_attack = {"chicken": {}}
    gd._monster_resistance = {"chicken": {}}
    gd._monster_critical_strike = {"chicken": 0}
    gd._monster_initiative = {"chicken": 0}
    gd._monster_type = {"chicken": "normal"}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._bank_location = (4, 0)
    gd._item_stats = {
        "novice_guide": ItemStats(code="novice_guide", level=10, type_="artifact",
                                  hp_bonus=25, wisdom=25, prospecting=25),
    }
    gd._crafting_recipes = {}
    gd._resource_skill = {}
    gd._resource_drops = {}
    return gd


def test_equip_owned_goal_selected_over_grind():
    """Robby-shaped state: level 10, owns an unequipped `novice_guide`
    artifact, ALL artifact slots empty, otherwise combat-capable (a
    plannable chicken-grind FightAction exists). The real arbiter must
    select EquipOwnedGoal (COLLECT band) over GrindCharacterXPGoal
    (STEP band), and the winning plan's first action must be the equip.

    Sanity control: with the SAME state but no novice_guide owned, the
    same arbiter falls through to GrindCharacterXPGoal — proving the
    equip candidate, not some other config quirk, is what wins."""
    planner = GOAPPlanner()
    gd = _gd()
    actions = [FightAction(monster_code="chicken", locations=frozenset([(1, 0)]))]
    ctx = _ctx()

    arbiter = StrategyArbiter(planner, history=None)
    arbiter.set_cycle(0)
    decision = _FakeDecision(chosen_step=ReachCharLevel(11))
    goal, plan, goals_tried = arbiter.select(
        decision, _state({"novice_guide": 1}), gd, actions, ctx)

    assert isinstance(goal, EquipOwnedGoal), (goal, goals_tried)
    assert goal.fills == {"artifact1_slot": "novice_guide"}
    assert plan, "EquipOwnedGoal must produce a non-empty plan"
    first = plan[0]
    assert isinstance(first, EquipAction), (first, plan)
    assert first.code == "novice_guide"
    assert first.slot == "artifact1_slot"

    # Sanity control: without the owned artifact, grind wins instead — the
    # candidate that flips the outcome is the equip, not some other quirk.
    control_arbiter = StrategyArbiter(planner, history=None)
    control_arbiter.set_cycle(0)
    control_goal, control_plan, _ = control_arbiter.select(
        _FakeDecision(chosen_step=ReachCharLevel(11)), _state({}), gd, actions, ctx)
    assert isinstance(control_goal, GrindCharacterXPGoal), (control_goal, control_plan)
