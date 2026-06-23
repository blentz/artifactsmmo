import json
from dataclasses import dataclass

from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.learning.store import LearningStore
from tests.test_ai.fixtures import make_state


@dataclass
class _Act:
    name: str
    applicable: bool = True

    def is_applicable(self, state, game_data):
        return self.applicable

    def __repr__(self):
        return self.name


def _store(tmp_path):
    s = LearningStore(db_path=str(tmp_path / "l.db"), character="hero")
    s.start_session()
    return s


_GATHER_JSON = json.dumps(
    {"type": "GatherMaterialsGoal", "target_item": "copper_ring",
     "needed": {"copper_ore": 6}})


def test_resume_discards_when_step_unmatchable(tmp_path):
    store = _store(tmp_path)
    store.save_plan_commitment(
        "GatherMaterials(...)", _GATHER_JSON, ["NoSuchAction()"], 0, None, False)
    player = GamePlayer(character="hero", dry_run=True, history=store)
    player._build_actions = lambda: []  # type: ignore[attr-defined]
    player._resume_plan_cache(make_state(), None)
    assert player._plan_cache is None


def test_resume_skips_when_goal_not_plan_bearing(tmp_path):
    store = _store(tmp_path)
    store.save_plan_commitment("Deposit", "{}", ["StepA"], 0, None, False)
    player = GamePlayer(character="hero", dry_run=True, history=store)
    player._build_actions = lambda: [_Act("StepA")]  # type: ignore[attr-defined]
    player._resume_plan_cache(make_state(), None)
    assert player._plan_cache is None


def test_resume_rehydrates_when_all_steps_applicable(tmp_path):
    store = _store(tmp_path)
    store.save_plan_commitment(
        "GatherMaterials(...)", _GATHER_JSON, ["StepA", "StepB"], 0, "copper_ring", False)
    player = GamePlayer(character="hero", dry_run=True, history=store)
    player._build_actions = lambda: [_Act("StepA"), _Act("StepB")]  # type: ignore[attr-defined]
    player._resume_plan_cache(make_state(), None)
    assert player._plan_cache is not None
    assert player._plan_cache.crafting_target == "copper_ring"
    assert player._plan_cache.selected_goal.__class__.__name__ == "GatherMaterialsGoal"
