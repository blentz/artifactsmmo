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

    # l10_copper_adequate: full copper set but shield_slot is empty.
    # GEAR-FIRST re-derivation 2026-07-08 (Task-3 pursuit_value; user ruling):
    # the empty shield_slot's wooden_shield is a STRUCTURAL candidate scored by
    # combat-dominant pursuit_value (gain 8000), which outranks the empty
    # utility slot's small_health_potion (utility, gain 61) — so chosen_root is
    # ObtainItem(wooden_shield, shield_slot), not the potion (the flat-ranking
    # empty-utility pick that used to win). wooden_shield isn't craftable-now,
    # so the mapper resolves to GatherMaterials(ash_wood), first action
    # Gather(ash_tree). Combat/gear outranks potion-stocking; potion still
    # pursued once no structural upgrade remains.
    "l10_copper_adequate": Golden(
        goal_class="GatherMaterials(ash_wood",
        first_action="Gather(ash_tree"),

    # l12_taskgated_bag: GEAR-FIRST re-derivation 2026-07-08 (Task-3
    # pursuit_value; user ruling). The tree's chosen_root is
    # ObtainItem(iron_boots, boots_slot) (the GAP-1 attainability fix opened
    # iron_boots; combat-dominant pursuit_value ranks it over the utility
    # potion the flat scorer used to pick). iron_boots' closure resolves to
    # GatherMaterials(iron_ore) for the iron_bar leg. iron_ore's sole source
    # (iron_rocks) is mining-10-gated and the char is at mining 1, so the plan
    # grinds the gather skill planner-natively: first action LevelSkill(mining
    # ->10), then Gather(iron_rocks). This retired the old copper_bar skill-
    # grind route (prereq-graph ReachSkillLevel node), completed by the P3b
    # gather-skill-gate LevelSkill admission (2026-07-12).
    "l12_taskgated_bag": Golden(
        goal_class="GatherMaterials(iron_ore", first_action="LevelSkill(mining->10)"),
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
