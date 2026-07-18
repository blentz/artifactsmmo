import json
from dataclasses import dataclass

from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
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
    game_data_stub = object()
    player._resume_plan_cache(make_state(), game_data_stub)  # type: ignore[arg-type]
    assert player._plan_cache is not None
    assert player._plan_cache.crafting_target == "copper_ring"
    assert player._plan_cache.selected_goal.__class__.__name__ == "GatherMaterialsGoal"


def test_resume_discards_when_step_not_applicable(tmp_path):
    store = _store(tmp_path)
    store.save_plan_commitment(
        "GatherMaterials(...)", _GATHER_JSON, ["StepA", "StepB"], 0, "copper_ring", False)
    player = GamePlayer(character="hero", dry_run=True, history=store)
    # StepB is not applicable — validation must reject and leave cache None
    player._build_actions = lambda: [_Act("StepA"), _Act("StepB", applicable=False)]  # type: ignore[attr-defined]
    game_data_stub = object()
    player._resume_plan_cache(make_state(), game_data_stub)  # type: ignore[arg-type]
    assert player._plan_cache is None


def test_resume_discards_when_no_game_data(tmp_path):
    store = _store(tmp_path)
    store.save_plan_commitment(
        "GatherMaterials(...)", _GATHER_JSON, ["StepA", "StepB"], 0, "copper_ring", False)
    player = GamePlayer(character="hero", dry_run=True, history=store)
    player._build_actions = lambda: [_Act("StepA"), _Act("StepB")]  # type: ignore[attr-defined]
    player._resume_plan_cache(make_state(), None)  # no game_data -> early discard
    assert player._plan_cache is None


def test_resume_discards_when_cursor_at_plan_end(tmp_path):
    store = _store(tmp_path)
    # cursor == len(plan): the remaining tail is empty -> nothing to rebuild
    store.save_plan_commitment(
        "GatherMaterials(...)", _GATHER_JSON, ["StepA", "StepB"], 2, "copper_ring", False)
    player = GamePlayer(character="hero", dry_run=True, history=store)
    player._build_actions = lambda: [_Act("StepA"), _Act("StepB")]  # type: ignore[attr-defined]
    game_data_stub = object()
    player._resume_plan_cache(make_state(), game_data_stub)  # type: ignore[arg-type]
    assert player._plan_cache is None


def test_resume_uses_persisted_cursor(tmp_path):
    store = _store(tmp_path)
    # Cursor=1 means StepA was already completed — resume should start from StepB.
    store.save_plan_commitment(
        "GatherMaterials(...)", _GATHER_JSON,
        ["StepA", "StepB", "StepC"], 1, None, False)
    player = GamePlayer(character="hero", dry_run=True, history=store)
    player._build_actions = lambda: [  # type: ignore[attr-defined]
        _Act("StepA"), _Act("StepB"), _Act("StepC")]
    game_data_stub = object()
    player._resume_plan_cache(make_state(), game_data_stub)  # type: ignore[arg-type]
    assert player._plan_cache is not None
    # tail from cursor=1 is [StepB, StepC] — length 2
    assert len(player._plan_cache.plan) == 2
    assert repr(player._plan_cache.plan[0]) == "StepB"
