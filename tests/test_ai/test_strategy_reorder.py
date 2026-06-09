"""Tests for reorder_skill_candidates: the gating ordering policy."""

from artifactsmmo_cli.ai.arbiter_select import Candidate
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.level_skill import LevelSkillGoal
from artifactsmmo_cli.ai.strategy_reorder import reorder_skill_candidates
from artifactsmmo_cli.ai.tiers.skill_gates import GateSource, SkillGate
from tests.test_ai.fixtures import make_state


class _Stub:
    """A minimal non-LevelSkill goal whose repr drives the ordering anchors."""
    def __init__(self, name: str) -> None:
        self._name = name
    def __repr__(self) -> str:
        return self._name


def _cand(goal, is_means=True) -> Candidate:
    return Candidate(goal=goal, is_means=is_means, repr_=repr(goal))


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {"copper_dagger": {"copper_bar": 6}}
    return gd


def _reprs(cands):
    return [c.repr_ for c in cands]


def test_non_gating_levelskill_demoted_before_wait():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 1})
    cands = [
        _cand(_Stub("PursueTask(x)")),
        _cand(_Stub("AcceptTask")),
        _cand(LevelSkillGoal("weaponcrafting", 5)),
        _cand(_Stub("Wait")),
    ]
    out, violations = reorder_skill_candidates(cands, gates={}, state=state,
                                               game_data=gd, has_paying_task=True)
    assert violations == []
    assert _reprs(out) == ["PursueTask(x)", "AcceptTask",
                           "LevelSkill(weaponcrafting->5)", "Wait"]


def test_task_item_gate_inserts_before_pursue_as_craft_one():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 1})
    gates = {"weaponcrafting": SkillGate(required_level=5, source=GateSource.TASK_ITEM)}
    cands = [
        _cand(_Stub("PursueTask(x)")),
        _cand(_Stub("AcceptTask")),
        _cand(LevelSkillGoal("weaponcrafting", 5)),
        _cand(_Stub("Wait")),
    ]
    out, violations = reorder_skill_candidates(cands, gates, state, gd,
                                               has_paying_task=True)
    assert violations == []
    assert _reprs(out) == ["GatherMaterials(copper_dagger)", "PursueTask(x)",
                           "AcceptTask", "Wait"]
    grind = out[0].goal
    assert isinstance(grind, GatherMaterialsGoal)


def test_gear_gate_with_paying_task_inserts_after_pursue():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 1})
    gates = {"weaponcrafting": SkillGate(required_level=5, source=GateSource.GEAR)}
    cands = [
        _cand(_Stub("PursueTask(x)")),
        _cand(_Stub("AcceptTask")),
        _cand(LevelSkillGoal("weaponcrafting", 5)),
        _cand(_Stub("Wait")),
    ]
    out, _ = reorder_skill_candidates(cands, gates, state, gd, has_paying_task=True)
    assert _reprs(out) == ["PursueTask(x)", "GatherMaterials(copper_dagger)",
                           "AcceptTask", "Wait"]


def test_gear_gate_no_paying_task_inserts_after_accept():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 1})
    gates = {"weaponcrafting": SkillGate(required_level=5, source=GateSource.GEAR)}
    cands = [
        _cand(_Stub("AcceptTask")),
        _cand(LevelSkillGoal("weaponcrafting", 5)),
        _cand(_Stub("Wait")),
    ]
    out, _ = reorder_skill_candidates(cands, gates, state, gd, has_paying_task=False)
    assert _reprs(out) == ["AcceptTask", "GatherMaterials(copper_dagger)", "Wait"]


def test_gating_skill_without_craft_target_reports_violation():
    gd = GameData()
    gd._item_stats = {
        "iron_dagger": ItemStats(code="iron_dagger", level=10, type_="weapon",
                                 crafting_skill="weaponcrafting", crafting_level=10),
    }
    gd._crafting_recipes = {"iron_dagger": {"iron_bar": 6}}
    state = make_state(skills={"weaponcrafting": 1})
    gates = {"weaponcrafting": SkillGate(required_level=10, source=GateSource.GEAR)}
    cands = [
        _cand(_Stub("AcceptTask")),
        _cand(LevelSkillGoal("weaponcrafting", 5)),
        _cand(_Stub("Wait")),
    ]
    _out, violations = reorder_skill_candidates(cands, gates, state, gd,
                                                has_paying_task=False)
    assert violations == ["weaponcrafting"]


def test_no_levelskill_candidates_is_identity():
    gd = _gd()
    state = make_state()
    cands = [_cand(_Stub("PursueTask(x)")), _cand(_Stub("Wait"))]
    out, violations = reorder_skill_candidates(cands, gates={}, state=state,
                                               game_data=gd, has_paying_task=True)
    assert out is cands and violations == []
