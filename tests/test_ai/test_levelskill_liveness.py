"""Liveness obligations for the skill-gate mechanism (LIV-SKILL-1/2/3).

These tests are the point of the feature: a craft-skill gate must never leave the
planner without a forward action, the grind target must exist for any gating
craft skill (monotone progression), and the gating set must strictly shrink as a
skill is driven across its gate (no livelock)."""

from artifactsmmo_cli.ai.arbiter_select import Candidate
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.level_skill import LevelSkillGoal
from artifactsmmo_cli.ai.strategy_reorder import reorder_skill_candidates
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.skill_gates import GateSource, SkillGate, gating_skills
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from tests.test_ai.fixtures import make_state


def _progression_gd() -> GameData:
    """A craft skill with a recipe at every level 1..5 (monotone progression)."""
    gd = GameData()
    gd._item_stats = {
        f"wc_t{lvl}": ItemStats(code=f"wc_t{lvl}", level=lvl, type_="weapon",
                                crafting_skill="weaponcrafting", crafting_level=lvl)
        for lvl in range(1, 6)
    }
    gd._crafting_recipes = {f"wc_t{lvl}": {"bar": 1} for lvl in range(1, 6)}
    return gd


def test_liv_skill_1_gate_yields_a_forward_action():
    """A wanted item blocked solely by an under-leveled craft skill produces a
    plannable craft-one candidate (never a no-op)."""
    gd = _progression_gd()
    gates = {"weaponcrafting": SkillGate(required_level=5, source=GateSource.GEAR)}
    state = make_state(skills={"weaponcrafting": 2})

    class _Stub:
        def __init__(self, n): self._n = n
        def __repr__(self): return self._n

    cands = [
        Candidate(goal=_Stub("AcceptTask"), is_means=True, repr_="AcceptTask"),
        Candidate(goal=LevelSkillGoal("weaponcrafting", 5), is_means=True,
                  repr_="LevelSkill(weaponcrafting->5)"),
        Candidate(goal=_Stub("Wait"), is_means=True, repr_="Wait"),
    ]
    out, violations = reorder_skill_candidates(cands, gates, state, gd,
                                               has_paying_task=False)
    assert violations == []
    grind = [c for c in out if isinstance(c.goal, GatherMaterialsGoal)]
    assert len(grind) == 1  # a real forward action exists


def test_liv_skill_2_grind_target_total_over_progression():
    """For every level 1..max-1 of a monotone craft skill, a grind target exists."""
    gd = _progression_gd()
    for lvl in range(1, 5):
        state = make_state(skills={"weaponcrafting": lvl})
        assert skill_grind_target("weaponcrafting", state, gd) is not None


def test_liv_skill_3_gating_set_strictly_shrinks_as_skill_rises():
    """Driving the skill across the gate removes it from gating_skills and it is
    not re-added (no livelock)."""
    gd = _progression_gd()
    gd._item_stats["target_weapon"] = ItemStats(
        code="target_weapon", level=5, type_="weapon",
        crafting_skill="weaponcrafting", crafting_level=5)
    gd._crafting_recipes["target_weapon"] = {"wc_t5": 1}
    obj = CharacterObjective(
        target_char_level=50, target_skill_levels={},
        target_gear={"weapon_slot": "target_weapon"}, _game_data=gd, target_tools={})

    gated_levels = []
    for lvl in range(1, 6):
        state = make_state(skills={"weaponcrafting": lvl})
        gates = gating_skills(state, gd, obj, combat_weapon=None)
        gated_levels.append("weaponcrafting" in gates)
    assert gated_levels == [True, True, True, True, False]
