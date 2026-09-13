"""RUNTIME ACTIVATION GATE for the 2026-09-13 BANK_EXPAND promotion.

`MeansKind.BANK_EXPAND` fired for two live characters against a 50/50 bank and
was selected ZERO times, because it sat in `DISCRETIONARY_ORDER` — below the
objective step, which a character essentially always has.
`audit/liveness_completeness.py` had carried `ExpandBankGoal` as
`unreachable: MeansKind.BANK_EXPAND is in the discretionary band` for exactly
that reason.

Band membership alone does not prove the promotion works, and no scenario
exercises it: every full-bank scenario on hand elects a GUARD (CRAFT_RELIEF for
`l20_relief_full_bank`, DISCARD/HP guards on the live fleet), and guards outrank
the whole collect band. So this drives the REAL `StrategyArbiter.select` from a
calm state where no guard fires and asserts the expansion outranks the grind —
the criterion a green unit suite does not establish on its own.

Local-helper convention (no cross-import of tests.test_ai.fixtures) follows
`test_equip_owned_gear_activation.py`, which this file mirrors.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.actions.bank_expansion import BuyBankExpansionAction
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.expand_bank import ExpandBankGoal
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

_BANK_CAPACITY = 20
_EXPANSION_COST = 100


@dataclass(frozen=True)
class _FakeDecision:
    chosen_step: object


def _ctx(**kw: object) -> SelectionContext:
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster="chicken",
                regear_level_up=False)
    base.update(kw)
    return SelectionContext(**base)


def _state(bank_item_count: int) -> WorldState:
    """Calm, combat-capable state: full HP, an almost-empty bag (so no discard,
    deposit or relief guard fires), an active chicken task, and a bank holding
    `bank_item_count` distinct codes against a 20-slot capacity."""
    return WorldState(
        character="Robby", level=10, xp=0, max_xp=1000, hp=150, max_hp=150,
        gold=5000, skills={}, x=0, y=0, inventory={}, inventory_max=100,
        inventory_slots_max=0,
        equipment=dict(_ALL_SLOTS), cooldown_expires=None,
        task_code="chicken", task_type="monsters", task_progress=0, task_total=10,
        task_lifecycle_phase=derive_task_lifecycle_phase("chicken", 0, 10),
        bank_items={f"banked{i}": 1 for i in range(bank_item_count)},
        bank_gold=None, bank_capacity=_BANK_CAPACITY, pending_items=None,
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
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_skill = {}
    gd._resource_drops = {}
    gd._bank_capacity = _BANK_CAPACITY
    gd._next_expansion_cost = _EXPANSION_COST
    return gd


def _select(bank_item_count: int):
    planner = GOAPPlanner()
    gd = _gd()
    actions = [
        FightAction(monster_code="chicken", locations=frozenset([(1, 0)])),
        BuyBankExpansionAction(bank_location=(4, 0), accessible=True),
    ]
    arbiter = StrategyArbiter(planner, history=None)
    arbiter.set_cycle(0)
    return arbiter.select(
        _FakeDecision(chosen_step=ReachCharLevel(11)),
        _state(bank_item_count), gd, actions, _ctx())


def test_expand_bank_goal_selected_over_the_objective_step():
    """15/20 = exactly the 75% trigger, price affordable, no guard firing: the
    arbiter must pick the expansion over the grind, and the plan must be the buy.

    This is the assertion that was FALSE before the promotion — the rung fired
    and lost to the step on every one of 4h of live cycles."""
    goal, plan, goals_tried = _select(bank_item_count=15)
    assert isinstance(goal, ExpandBankGoal), (goal, goals_tried)
    assert plan, "ExpandBankGoal must produce a non-empty plan"
    assert isinstance(plan[0], BuyBankExpansionAction), (plan[0], plan)


def test_a_bank_below_the_trigger_falls_through_to_the_grind():
    """Sanity control: the SAME state with 14/20 = 70% banked falls through to
    the grind. What flips the outcome is the fill crossing the trigger, not some
    other quirk of the fixture."""
    goal, plan, _ = _select(bank_item_count=14)
    assert isinstance(goal, GrindCharacterXPGoal), (goal, plan)
