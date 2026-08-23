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
    # RE-DERIVED WAVE 3a. The root is now ObtainItem(wooden_shield,
    # shield_slot) — the gear sheet comes from `gear_targets_with_blockers`,
    # which gears for `gear_target_tier`, and no scenario in this fixture
    # clears rung 1 (see tests/test_ai/test_progression_tree.py's module
    # docstring). copper_dagger is not on that sheet at all. The shield's
    # recipe needs 10 gathered ash_wood, so the descent bottoms out one ply
    # earlier than the smelted copper_bar chain did.
    "l10_weapon_upgrade": Golden(
        goal_class="GatherMaterials(ash_wood", first_action="Gather(ash_tree"),

    # l1_fresh: the legacy golden pinned GrindCharacterXP (starter-monster xp
    # grind) for a bare L1 character, but the TREE's rules differ by design:
    # an empty weapon_slot is a gain-from-zero structural upgrade
    # (has_structural_upgrade), so the tree's chosen_root is
    # ObtainItem(copper_dagger, weapon_slot) — gear-first wins pre-adequacy,
    # same as l10_weapon_upgrade's design intent (see the retired legacy
    # XFAIL_TODAY["l1_fresh"]/["l10_weapon_upgrade"] reasons). Nothing is
    # held or banked, so the recipe chain bottoms out at the raw material.
    #
    # RE-DERIVED WAVE 3a, and this one is worth reading closely because it is
    # the FALLBACK CHAIN doing its job, not a simple re-pin. The resolved root
    # is ObtainItem(wooden_stick) — the material gating the rung-1 weapon
    # target `wooden_staff` — and `objective_step_goal` maps it to
    # UpgradeEquipment(wooden_stick->weapon_slot), which the planner CANNOT
    # plan (nothing produces a wooden_stick in this fixture). The arbiter then
    # walks `fallback_steps`, and the first servable pair is the shield slot's
    # gather. `goals_tried` records both, in that order, which is exactly the
    # 2026-06-06 regression `_resolve_step_goal` exists to prevent: a root
    # whose goal does not plan must not drop the cycle into discretionary.
    "l1_fresh": Golden(
        goal_class="GatherMaterials(ash_wood", first_action="Gather(ash_tree"),

    # l10_copper_adequate: full copper set but shield_slot is empty.
    # RE-DERIVED 2026-08-04 (pursuit_value unification). `_utility_candidates`
    # joined `_structural_candidates` on `pursuit_value`, so the merged argmax
    # stopped comparing two rulers ~1000x apart. On the ONE ruler the shield
    # leads 52_800_000 to the potion's 6_000_000 — 8.8x, so the ACHIEVABILITY
    # factor (shield 905/1534 for 10 gathered ash_wood, potion 1 for
    # craftable-now) narrows without reversing it, and chosen_root is
    # ObtainItem(wooden_shield, shield_slot). This restores the 2026-07-08
    # "combat/gear pursuit outranks potion-stocking" ruling; the brief potion
    # win under the previous commit came from the two branches riding
    # incommensurate rulers, not from a judgement about potions. The shield
    # needs ash_wood gathered, so the goal is the gather descent.
    "l10_copper_adequate": Golden(
        goal_class="GatherMaterials(ash_wood",
        first_action="Gather(ash_tree"),

    # l12_taskgated_bag: GEAR-FIRST re-derivation 2026-07-08 (Task-3
    # pursuit_value; user ruling). The tree's chosen_root is
    # ObtainItem(iron_sword, weapon_slot), chosen_step ObtainItem(iron_ore, 10)
    # (combat-dominant pursuit_value ranks the weapon over the utility potion
    # the flat scorer used to pick; verified by re-running this scenario
    # against the pre-Task-5 `objective_step_goal` body -- chosen_root/step
    # are UNCHANGED by Task 5, root selection never calls the rewired code).
    #
    # RE-DERIVED 2026-08-22 (goal-decision-graph Task 5, PF-2): the character
    # is weaponcrafting 1 against iron_sword's crafting_level 10. Pre-Task-5,
    # iron_sword's recipe closure contains a monster-drop input (feather, from
    # chicken), so `_recipe_has_combat_drop_input` returned True and masked
    # the (correct, but unreached) crafting-skill gate -- the goal was
    # `GatherMaterials(iron_ore)`: gather materials for a sword the character
    # cannot craft at ANY quantity of iron_ore. This is the exact bug class
    # Task 5 fixes (weaponcrafting frozen at 10 fleet-wide, 2026-08-16 to
    # 2026-08-22): `CanICraftCurrentTier` now runs BEFORE the monster-drop
    # check, so a skill-gated root raises the skill instead. First action was
    # therefore LevelSkill(weaponcrafting->N), never a gather.
    #
    # RE-DERIVED WAVE 3a, and this is a LOSS worth naming rather than burying:
    # iron_sword is no longer a gear target here, so the weaponcrafting climb
    # this golden used to witness is gone from this scenario. The cause is the
    # tier model, not the graph — this scenario has no attack at all, so
    # `tier_cleared(1)` is False and `gear_target_tier` refuses to gear for a
    # rung whose band the character cannot clear. That refusal is the point of
    # `gear_target_tier` (its own docstring's Robby-at-30 case) and it is
    # arguably the better answer here: at zero attack, iron_sword's materials
    # come from monsters this character loses to. The skill-climb root IS
    # reachable post-flip — `plan Lor` resolves ReachSkillLevel(gearcrafting,
    # 10) against the live catalogue, recorded in the task-6 report — it is
    # this FIXTURE that can no longer exhibit it.
    "l12_taskgated_bag": Golden(
        goal_class="GatherMaterials(ash_wood", first_action="Gather(ash_tree"),
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
