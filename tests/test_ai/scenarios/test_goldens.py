"""Golden planner expectations per scenario, on the CURRENT engine.

Assertions are CATEGORY-level (goal class + first action class), never
scores — they must survive the progression-tree flip (spec 2026-07-06).
Where the current engine's known misbehavior contradicts the DESIGNED
expectation, the golden is marked xfail with the design intent in the
reason: those xfails are the tree's acceptance tests, flipped in Phase 4."""

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
    "l1_fresh": Golden(goal_class="GrindCharacterXP", first_action="Fight"),
    # Current engine: critical-pressure (96% used) DiscardOverstock (value 85,
    # the >=95% CRITICAL tier) legitimately outranks DepositInventory's ramped
    # value (~58.7 at 96%) — this is the intended pressure-ladder escalation
    # (thresholds.py PRESSURE_CRITICAL_FRACTION), not a flat-ranking bug. The
    # goal still clears the bag via the proved disposal_route: plan[0] is a
    # real DepositItem for the bankable overstocked feather.
    "l8_overstocked": Golden(goal_class="DiscardOverstock", first_action="DepositItem"),
    "l3_low_hp": Golden(goal_class="RestoreHP"),
    "l10_weapon_upgrade": Golden(goal_class="UpgradeEquipment"),
    "l10_copper_adequate": Golden(goal_class="GrindCharacterXP"),
    "l12_taskgated_bag": Golden(goal_class="ReachCurrency"),
}

# Scenarios whose CURRENT-engine outcome is known to differ from the design
# intent (the flat-ranking bugs that motivated the progression tree). The
# golden encodes the DESIGN; xfail documents today's divergence.
XFAIL_TODAY: dict[str, str] = {
    "l1_fresh": (
        "same empty-utility-slot defect as l10_copper_adequate: even a bare "
        "L1 character's chosen_root is the bootstrap small_health_potion "
        "(utility1_slot) over the starter-monster xp grind; tree flips this"),
    "l10_copper_adequate": (
        "flat ranking picks the empty-utility potion root (EMPTY_SLOT_URGENCY "
        "2.5) over xp — the potion/slime alternation; tree flips this"),
    "l10_weapon_upgrade": (
        "occupied-slot weapon upgrade scores ~1.0 and loses to grind/skill "
        "roots in the flat ranking; tree makes gear-first win pre-adequacy"),
    "l12_taskgated_bag": (
        "bag root may lose the flat ranking to grind roots even though the "
        "funding pipeline is plannable; tree drives it as the gear branch"),
}


def _run(name: str) -> PlanReport:
    player = GamePlayer(character=name, history=None)
    player.seed_offline(scenario_state(SCENARIOS[name]),
                        load_bundle_game_data(BUNDLE))
    return player.plan_from_state()


@pytest.mark.parametrize("name", sorted(EXPECTATIONS))
def test_scenario_golden(name: str) -> None:
    if name in XFAIL_TODAY:
        pytest.xfail(XFAIL_TODAY[name])
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
    """Every scenario must produce SOME selected goal and try candidates —
    an empty arbitration is a liveness bug regardless of which engine runs."""
    report = _run(name)
    assert report.selected_goal
    assert report.goals_tried
