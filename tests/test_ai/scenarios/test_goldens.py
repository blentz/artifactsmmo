"""Golden planner expectations per scenario, on THE engine — the progression
tree (Phase 4b flip: `StrategyEngine.decide` delegates to `decide_tree`).

Promoted from the Phase-4a acceptance set (formerly test_goldens_tree.py,
which ran with `GamePlayer(..., progression_tree=True)` — the flag died with
the flip). Assertions are CATEGORY-level (goal class + first action class),
never scores. The Phase-1 legacy EXPECTATIONS / strict XFAIL_TODAY /
CURRENT_TODAY pins were deleted at the flip, exactly as their docstrings
mandated: the strict xfails' design intent lives on in these goldens.

Derivation method (binding, from `.superpowers/sdd/task-3-brief.md`): for
each scenario, derive an expected goal class from the tree's rules, RUN it,
and record the actual `report.selected_goal`/`plan[0]` class. Where the
mapper's actual output differs from the guess, the golden is corrected in
place with a comment explaining the mapper path — never papered over. A
tree-driven scenario landing on a goal unrelated to both the chosen tree
root and the guards would be a BLOCKER (reported, not calibrated away); no
such case occurred here — every divergence below traces cleanly through
`objective_step_goal`'s recipe-materials walk from the tree's `chosen_root`.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.plan_report import PlanReport
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"


@dataclass(frozen=True)
class Golden:
    goal_class: str                 # PlanReport.selected_goal repr prefix
    first_action: str | None = None # repr prefix of plan[0]; None = don't pin


EXPECTATIONS: dict[str, Golden] = {
    # Guard scenarios: tertiary preemption is engine-independent (BINDING —
    # a failure here is a BLOCKER, not something to calibrate away). Both
    # match the derivation rule exactly, same as the legacy golden did.
    "l3_low_hp": Golden(goal_class="RestoreHP", first_action="Rest"),
    "l8_overstocked": Golden(goal_class="DiscardOverstock", first_action="DepositItem"),

    # l10_weapon_upgrade: tree's chosen_root is ObtainItem(copper_dagger,
    # weapon_slot) (weapon slot lags a tier, band inadequate — see
    # test_plan_from_state.test_plan_from_state_decision_is_the_tree_decision).
    # The rule guessed UpgradeEquipment OR GatherMaterials; actual is
    # GatherMaterials — the recipe needs copper_bar (smelted), the bank only
    # holds raw copper_ore/iron_ore, so objective_step_goal's fallback walk
    # resolves to the first unmet recipe input rather than a direct equip.
    "l10_weapon_upgrade": Golden(
        goal_class="GatherMaterials(copper_bar", first_action="Withdraw(copper_ore"),

    # l1_fresh: the legacy golden pinned GrindCharacterXP (starter-monster xp
    # grind) for a bare L1 character, but the TREE's rules differ by design:
    # an empty weapon_slot is a gain-from-zero structural upgrade
    # (has_structural_upgrade), so the tree's chosen_root is
    # ObtainItem(copper_dagger, weapon_slot) — gear-first wins pre-adequacy,
    # same as l10_weapon_upgrade's design intent (see the retired legacy
    # XFAIL_TODAY["l1_fresh"]/["l10_weapon_upgrade"] reasons). Nothing is
    # held or banked, so the recipe chain bottoms out at the raw material:
    # GatherMaterials(copper_ore, {copper_ore:10}), first action Gather.
    "l1_fresh": Golden(
        goal_class="GatherMaterials(copper_ore", first_action="Gather"),

    # l10_copper_adequate: full copper set (band-adequate: a winnable
    # monster exists and no positive-gain structural upgrade remains for
    # equipped slots) but utility1_slot is EMPTY — an empty consumable slot
    # is still a gain-from-zero candidate the tree targets, so chosen_root
    # is ObtainItem(small_health_potion, utility1_slot), same as legacy's
    # (buggy, flat-ranking) empty-utility-slot pick — but here it's the
    # DESIGNED outcome, not a defect: the bank holds the potion's sunflower
    # mats (20), so the goal resolves straight to
    # UpgradeEquipment(small_health_potion->utility1_slot) with a Withdraw
    # first action, not the guessed GrindCharacterXP.
    "l10_copper_adequate": Golden(
        goal_class="UpgradeEquipment(small_health_potion->utility1_slot",
        first_action="Withdraw(sunflower"),

    # l12_taskgated_bag: same empty-utility1_slot branch as
    # l10_copper_adequate (chosen_root ObtainItem(small_health_potion,
    # utility1_slot)) rather than the guessed ReachCurrency/bag-funding
    # root — the tree ranks the empty gear slot over the task-funding
    # branch here. Unlike l10_copper_adequate, the bank holds no sunflower
    # (only cowhide/feather), so the mapper falls through to the raw
    # material gather: GatherMaterials(sunflower, {sunflower:3}), first
    # action Gather(sunflower_field).
    "l12_taskgated_bag": Golden(
        goal_class="GatherMaterials(sunflower", first_action="Gather(sunflower_field"),
}


def _run(name: str) -> PlanReport:
    player = GamePlayer(character=name, history=None)
    player.seed_offline(scenario_state(SCENARIOS[name]),
                        load_bundle_game_data(BUNDLE))
    return player.plan_from_state()


@pytest.mark.parametrize("name", sorted(EXPECTATIONS))
def test_scenario_golden(name: str) -> None:
    report = _run(name)
    golden = EXPECTATIONS[name]
    # selected_goal is a Goal instance (Goal.__repr__ == class name), not a
    # str — compare against its repr, same as the plan[0] check below.
    assert repr(report.selected_goal).startswith(golden.goal_class), (
        name, repr(report.selected_goal), [g.get("goal") for g in report.goals_tried])
    if golden.first_action is not None:
        assert report.plan and repr(report.plan[0]).startswith(golden.first_action), (
            name, report.plan)


@pytest.mark.parametrize("name", sorted(EXPECTATIONS))
def test_scenario_planner_never_empty(name: str) -> None:
    """Liveness: every scenario must produce SOME selected goal and try
    candidates, and the plan must be non-empty OR the goal is the WAIT
    class — an empty arbitration is a liveness bug regardless of scenario."""
    report = _run(name)
    assert report.selected_goal
    assert report.goals_tried
    assert report.plan or repr(report.selected_goal).startswith("WaitGoal")
