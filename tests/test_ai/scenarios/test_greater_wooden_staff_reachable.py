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
   the goal was admitted. Phase 3-2 deleted the admission gate itself (every
   goal's answer is the walk's own), so the admission tests went with it; the
   routing tests below are what this state still pins.

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

from artifactsmmo_cli.ai import obtain_item_routing
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.craft_plan_gen import decompose
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"
"""The REAL 321-recipe catalog, same loader every other scenario uses. A
hand-rolled recipe subset would prove nothing about the live failure."""

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


def _state_kwargs(state: WorldState) -> dict:
    """`_traced_state`'s arguments back out of a state, to vary one field."""
    return dict(character=state.character, level=state.level, xp=state.xp, max_xp=state.max_xp,
                hp=state.hp, max_hp=state.max_hp, gold=state.gold, x=state.x, y=state.y,
                skills=dict(state.skills), inventory=dict(state.inventory),
                inventory_max=state.inventory_max, inventory_slots_max=state.inventory_slots_max,
                bank_items=dict(state.bank_items or {}))


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


_CTX = SelectionContext(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                        initial_xp=0, task_exchange_min_coins=0, combat_monster=None)


def _decomposed(state: WorldState) -> list[Action]:
    """The plan the arbiter's producer gives (Phase 2d-b1: a committed upgrade
    decomposes; the search no longer has the LevelSkill macro to grind with)."""
    gd = _game_data()
    return decompose(_goal(), state, gd, _build_actions(state, gd), _CTX) or []


def test_staff_plans_from_r2d2s_traced_state() -> None:
    """Live trace: 0 plans in 702 rank-1 cycles, `timed_out` on every one. The
    staff needs weaponcrafting 10 against the traced 9, so the plan is that
    sub-grind's cycle, ending in the weaponcrafting craft that earns."""
    plan = _decomposed(_bank_covered_state())
    assert plan, "no plan; live trace: nodes 3873, depth 8, timed_out, plan_len 0"
    last = plan[-1]
    assert isinstance(last, CraftAction)
    stats = _game_data().item_stats(last.code)
    assert stats is not None and stats.crafting_skill == "weaponcrafting", [str(a) for a in plan]


def test_staff_plan_uses_the_banked_materials() -> None:
    """The materials were never missing. A plan that re-gathers 60 `spruce_wood`
    with 16 planks in the bank is the banked-regather bug, not a fix: no plan
    gathers spruce, and once the skill is met the plan withdraws the planks and
    crafts and equips the staff without a single gather."""
    assert not [a for a in _decomposed(_bank_covered_state())
                if isinstance(a, GatherAction) and a.resource_code == "spruce_tree"]
    skilled = _bank_covered_state()
    skilled = make_state(**{**_state_kwargs(skilled), "skills": {**_TRACED_SKILLS, "weaponcrafting": 10}})
    plan = _decomposed(skilled)
    assert any(isinstance(a, WithdrawItemAction) and a.code == "spruce_plank" for a in plan), \
        [str(a) for a in plan]
    assert not [a for a in plan if isinstance(a, GatherAction)], [str(a) for a in plan]
    assert repr(plan[-1]) == f"Equip({TARGET}->{SLOT})"


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
    goal = obtain_item_routing._equippable_goal(
        "greater_wooden_staff", "weapon_slot", state, gd)
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal._target_item == "spruce_wood"
    assert goal.needed == {"spruce_wood": 10}

    # Since Phase 2e the routed goal is the walk's.
    plan = decompose(goal, state, gd, _build_actions(state, gd), NO_PROFILE_CONTEXT)
    assert plan, "the routed goal must actually plan, not merely look small"


def test_banked_materials_still_route_to_the_craft():
    """Anti-starvation: once every direct prerequisite is satisfied — from the
    BANK, via a ready withdraw source — the traversal returns the root and the
    craft must fire. A routing that always gathered would never equip.

    Reuses `_bank_covered_state()` (16 spruce_plank + 98 blue_slimeball, R2D2's
    real traced bank) rather than a second fixture building the same state —
    the file already has it under that name."""
    gd, state = _game_data(), _bank_covered_state()
    goal = obtain_item_routing._equippable_goal(
        "greater_wooden_staff", "weapon_slot", state, gd)
    assert isinstance(goal, UpgradeEquipmentGoal)


def test_the_traversal_runs_once_per_decision(monkeypatch):
    """The helper re-derives the step when not given one. Threading it through
    must not double the walk — `actionable_step` is the expensive part."""
    calls = []
    real = obtain_item_routing.actionable_step

    def counting(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(obtain_item_routing, "actionable_step", counting)
    gd, state = _game_data(), _state_without_banked_planks()
    obtain_item_routing._equippable_goal(
        "greater_wooden_staff", "weapon_slot", state, gd)
    assert len(calls) == 1, f"actionable_step ran {len(calls)} times"
