"""Live regression: play-trace-R2D2-20260812-003250.jsonl.

`UpgradeEquipment(greater_wooden_staff->weapon_slot)` was the rank-1 objective
on 702 of that trace's 1700 cycles and produced a plan on ZERO of them
(`plan_len 0` on every one; nodes 556-12063, depth 6-13, `timed_out` true,
e.g. cycle 0's `nodes 3873, depth 8`), while the shared bank held 16
`spruce_plank` and 98 `blue_slimeball` against a recipe needing 6 and 2. The
character then fell through to `GrindCharacterXP(red_slime)` every cycle,
which is why 31.3 hours of runtime read as "the bot chose to grind XP".

Two distinct states are pinned here, because the live failure has two distinct
halves and the epic's fix only touches one of them:

1. `_traced_state()` — the bank-covered state named above. The withdraw route
   (`Withdraw(spruce_plank) -> LevelSkill -> Craft -> Equip`) exists, so the
   goal must be admitted, planned within the 15 s budget, and must NOT
   re-gather 60 `spruce_wood` past 16 banked planks. HONESTY NOTE: this half
   is a *live-state* regression pin, not a discriminator for this branch —
   measured against the pre-branch tree (merge-base f751fb96) the same
   assertions already held (`plan_len 5`, `nodes_explored 3942`, no timeout).
   It pins the behaviour the trace says was missing; it does not prove the
   batched-gather work is what restored it.

2. `_traced_state_without_banked_planks()` — the SAME character with the
   planks gone from the bank, which is the state the epic's root cause is
   actually about: 6 `spruce_plank` <- 60 `spruce_wood`. Pre-branch,
   `min_plan_length` scored that chain at 63 against `max_depth` 32 and
   `is_plannable` refused admission before A* ever ran (the "65 against 32"
   figure in the task brief is the empty-bank variant of the same count).
   Post-branch the mint term counts batched gather STEPS, the score is 4, and
   the goal is admitted. That admission flip is the assertion in this file
   that fails on the pre-branch tree.

RESIDUAL, deliberately not asserted here (see the task-10 report): from state
2 a plan does now exist and the real planner does find it — `LevelSkill ->
Gather(spruce_tree x60) -> Withdraw(blue_slimeball) -> Craft(spruce_plank x6)
-> Craft(greater_wooden_staff) -> Equip`, 23214 nodes explored — but it takes
23.0 s of search, past the 15 s budget. Pinning that would put a 23-second
search in the suite and would pin a number the branch has not yet brought
under budget, so it is reported rather than asserted.
"""

import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai import strategy_driver
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.min_plan_length import min_plan_length
from artifactsmmo_cli.ai.planner import GOAPPlanner, PlanStats
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"
"""The REAL 321-recipe catalog, same loader every other scenario uses. A
hand-rolled recipe subset would prove nothing about the live failure."""

BUDGET_SECONDS = 15.0
"""The production per-goal search budget (`strategy_driver._SEARCH_BUDGET_SECONDS`
after Task 11/12). The test must pass under what the bot actually gets."""

TARGET = "greater_wooden_staff"
SLOT = "weapon_slot"

# Skills/level/position/gold as of the trace's final cycle. weaponcrafting 9 is
# BELOW the recipe's crafting_level 10, so every plan below must route through a
# LevelSkill leg — that is expected, not a failure.
_TRACED_SKILLS = {"mining": 12, "woodcutting": 13, "fishing": 1,
                  "weaponcrafting": 9, "gearcrafting": 9, "jewelrycrafting": 3,
                  "cooking": 5, "alchemy": 4}


def _game_data() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def _traced_state(bank_items: dict[str, int]) -> WorldState:
    """R2D2 at the trace's last cycle. `inventory_used`/`inventory_max` in the
    trace are 64/130; the trace does not record inventory CONTENTS, and the
    brief's state is "empty of the relevant items", so the inventory is left
    empty — the withdraw legs below therefore run against maximum headroom,
    which is the state most favourable to planning and so the strictest place
    to assert a failure would have been real."""
    return make_state(
        character="R2D2", level=16, xp=656, max_xp=5100, hp=295, max_hp=335,
        gold=8237, x=6, y=1, skills=dict(_TRACED_SKILLS),
        inventory={}, inventory_max=130, inventory_slots_max=20,
        bank_items=bank_items,
    )


def _bank_covered_state() -> WorldState:
    return _traced_state({"spruce_plank": 16, "blue_slimeball": 98})


def _state_without_banked_planks() -> WorldState:
    """The same character with the planks gone: the 6 planks must now come from
    60 `spruce_wood`, which is the chain the epic exists to make reachable."""
    return _traced_state({"blue_slimeball": 98})


def _goal() -> UpgradeEquipmentGoal:
    return UpgradeEquipmentGoal(committed_target=(TARGET, SLOT))


def _build_actions(state: WorldState, gd: GameData) -> list[Action]:
    """The REAL production action pool (~1900 actions), not a hand-picked list:
    the goal's own `relevant_actions` narrowing is part of what is under test."""
    return build_actions(gd, state, CharacterObjective.from_game_data(gd),
                         bank_accessible=True, task_exchange_min_coins=0)


@pytest.fixture(scope="module")
def traced_run() -> tuple[list[Action], PlanStats]:
    """One planner run over the traced bank-covered state, shared by the three
    assertions that read it (the search costs a couple of seconds)."""
    gd = _game_data()
    state = _bank_covered_state()
    planner = GOAPPlanner()
    plan = planner.plan(state, _goal(), _build_actions(state, gd), gd, None,
                        budget_seconds=BUDGET_SECONDS)
    return plan, planner.last_stats


def test_staff_goal_is_admitted_by_is_plannable() -> None:
    """The reachability gate must admit the goal — a False here means A* never
    runs and the objective is silently abandoned every cycle."""
    gd = _game_data()
    assert _goal().is_plannable(_bank_covered_state(), gd) is True


def test_staff_plans_from_r2d2s_traced_state(
    traced_run: tuple[list[Action], PlanStats],
) -> None:
    """Live trace: 0 plans in 702 rank-1 cycles, `timed_out` on every one."""
    plan, stats = traced_run
    assert plan, (
        "no plan; live trace: nodes 3873, depth 8, timed_out, plan_len 0")
    assert not stats.timed_out, stats
    assert not stats.node_capped, stats
    assert stats.max_depth_reached <= _goal().max_depth, stats


def test_staff_plan_uses_the_banked_materials(
    traced_run: tuple[list[Action], PlanStats],
) -> None:
    """The materials were never missing. A plan that re-gathers 60 `spruce_wood`
    with 16 planks in the bank is the banked-regather bug, not a fix — so the
    withdraw must be present AND no gather may appear at all."""
    plan, _stats = traced_run
    assert any(isinstance(a, WithdrawItemAction) and a.code == "spruce_plank"
               for a in plan), [str(a) for a in plan]
    assert not [a for a in plan if isinstance(a, GatherAction)], (
        "re-gathered raw wood past 16 banked spruce_plank",
        [str(a) for a in plan])


def test_from_scratch_plank_chain_is_admitted() -> None:
    """THE DISCRIMINATOR. Without the planks banked the target needs 60
    `spruce_wood` through one recipe leaf. The pre-branch mint term counted raw
    UNITS, scoring the chain at 63 against `max_depth` 32, so `is_plannable`
    returned False and the goal was dropped without a search. Batched gathers
    make one gather serve the whole leaf, so the score is 4 and the goal is
    admitted. Both halves are asserted (the score AND the verdict) so a change
    that flips the verdict for an unrelated reason cannot pass quietly."""
    gd = _game_data()
    state = _state_without_banked_planks()
    owned = dict(state.inventory)
    for code, qty in (state.bank_items or {}).items():
        owned[code] = owned.get(code, 0) + qty
    assert owned.get("spruce_plank", 0) == 0
    # Bound the score in a local so a failure prints the two integers, not the
    # whole 321-recipe GameData repr.
    scored = min_plan_length(TARGET, 1, gd.crafting_recipes, owned,
                             gd.max_gather_yield, equip=True)
    assert scored <= _goal().max_depth, (scored, _goal().max_depth)
    assert _goal().is_plannable(state, gd) is True


def test_from_scratch_routes_to_the_achievable_step_not_the_equippable():
    """The bug this fixes: `is_plannable` maxes at 15 against max_depth 32 over
    all 321 real recipes, so it never rejects, and the arbiter planned a
    100,080-node / ~49.5s UpgradeEquipment search instead of a 2-node gather.

    `actionable_step` already returned ObtainItem('spruce_wood', 10) here.
    Nothing was asking it.

    The identity assertions alone (goal type/target/needed) cannot
    distinguish a genuinely cheap routed goal from one that is merely
    smaller in name but still explosive to plan — review found exactly that
    gap once (`gather_step_target` returning a ROOT by name that then took
    102,286 nodes / 10.6s to fail, where the identity check alone would have
    read as a 3-node pass). The spec's actual requirement — "plan within the
    15s budget without timing out" — is asserted here directly by running
    the real planner over the real 321-recipe action pool."""
    gd, state = _game_data(), _state_without_banked_planks()
    goal = strategy_driver._equippable_goal(
        "greater_wooden_staff", "weapon_slot", state, gd)
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal._target_item == "spruce_wood"
    assert goal.needed == {"spruce_wood": 10}

    planner = GOAPPlanner()
    plan = planner.plan(state, goal, _build_actions(state, gd), gd, None,
                        budget_seconds=BUDGET_SECONDS)
    assert plan, "the routed goal must actually plan, not merely look small"
    assert not planner.last_stats.timed_out, planner.last_stats


def test_banked_materials_still_route_to_the_craft():
    """Anti-starvation: once every direct prerequisite is satisfied — from the
    BANK, via a ready withdraw source — the traversal returns the root and the
    craft must fire. A routing that always gathered would never equip.

    Reuses `_bank_covered_state()` (16 spruce_plank + 98 blue_slimeball, R2D2's
    real traced bank) rather than a second fixture building the same state —
    the file already has it under that name."""
    gd, state = _game_data(), _bank_covered_state()
    goal = strategy_driver._equippable_goal(
        "greater_wooden_staff", "weapon_slot", state, gd)
    assert isinstance(goal, UpgradeEquipmentGoal)


def test_the_traversal_runs_once_per_decision(monkeypatch):
    """The helper re-derives the step when not given one. Threading it through
    must not double the walk — `actionable_step` is the expensive part."""
    calls = []
    real = strategy_driver.actionable_step

    def counting(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(strategy_driver, "actionable_step", counting)
    gd, state = _game_data(), _state_without_banked_planks()
    strategy_driver._equippable_goal(
        "greater_wooden_staff", "weapon_slot", state, gd)
    assert len(calls) == 1, f"actionable_step ran {len(calls)} times"
