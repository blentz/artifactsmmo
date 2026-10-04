"""The intention's progress measure (Phase 4-2a): what "moved" means for each
goal family, and when an intention has stalled."""

from artifactsmmo_cli.ai.decision_mechanism import Mechanism
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.reach_skill import ReachSkillGoal
from artifactsmmo_cli.ai.goals.restore_hp import RestoreHPGoal
from artifactsmmo_cli.ai.intention_progress import (
    STALL_CYCLES,
    progress_measure,
    progressed,
)
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from tests.test_ai.fixtures import make_state


def test_a_character_grind_is_measured_in_character_xp():
    goal = GrindCharacterXPGoal("vampire")
    assert progress_measure(goal, make_state(level=30, xp=100)) == (30, 100)


def test_a_skill_grind_is_measured_in_that_skill_only():
    goal = ReachSkillGoal("weaponcrafting", 21)
    state = make_state(skills={"weaponcrafting": 20, "mining": 9},
                       skill_xp={"weaponcrafting": 450, "mining": 9000})
    assert progress_measure(goal, state) == (20, 450)


def test_other_goals_have_no_xp_measure():
    assert progress_measure(GatherMaterialsGoal("x", {"x": 1}), make_state()) is None


def test_a_successful_leg_or_rising_xp_is_progress():
    assert progressed((30, 100), (30, 140), ok=True)
    # a crafting climb's gather leg: it succeeded and pays no skill XP yet —
    # still progress (witnessed: 90 false stalls when this was not counted)
    assert progressed((20, 450), (20, 450), ok=True)
    # a failed action whose XP still rose (and wraps across a level) counts
    assert progressed((30, 19_000), (31, 5), ok=False)
    # a lost fight: no XP and a failed action is no progress
    assert not progressed((30, 100), (30, 100), ok=False)


def test_without_a_measure_a_successful_leg_is_progress():
    """Decomposition plans are proved to deliver (`CommittedLoop`), so for a
    goal with no XP measure a successful action of its plan is the progress."""
    assert progressed(None, None, ok=True)
    assert not progressed(None, None, ok=False)


def test_the_stall_bound_outlasts_a_fight_rest_cycle():
    """A fight-rest loop alternates, and only the committed goal's own cycles
    count; 20 of them with nothing moving is no transient."""
    assert STALL_CYCLES == 20


def _player_committed_to(goal) -> GamePlayer:
    player = GamePlayer(character="hero")
    player._arbiter._committed_repr = repr(goal)
    return player


def test_an_abandoned_intention_is_cleared_and_named(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "i.db"), character="hero")
    arbiter = StrategyArbiter(GOAPPlanner(), history=store)
    arbiter._committed_repr = "GrindCharacterXP(vampire)"
    store.save_intention("GrindCharacterXP(vampire)")
    arbiter.abandon_intention(Mechanism.INTENTION_STALLED, "stalled:20")
    assert arbiter._committed_repr is None
    assert store.load_intention() is None
    assert arbiter.events.drain() == [
        (Mechanism.INTENTION_STALLED, "GrindCharacterXP(vampire)", "stalled:20")]


def test_a_committed_grind_that_earns_nothing_stalls_on_its_twentieth_cycle():
    goal = GrindCharacterXPGoal("vampire")
    player = _player_committed_to(goal)
    flat = make_state(level=30, xp=100)
    for _ in range(STALL_CYCLES - 1):
        player._track_intention(goal, flat, flat, ok=False)
    assert player._arbiter._committed_repr == repr(goal)
    player._track_intention(goal, flat, flat, ok=False)
    assert player._arbiter._committed_repr is None


def test_progress_resets_the_stall_count():
    goal = GrindCharacterXPGoal("vampire")
    player = _player_committed_to(goal)
    flat = make_state(level=30, xp=100)
    for _ in range(STALL_CYCLES - 1):
        player._track_intention(goal, flat, flat, ok=False)
    player._track_intention(goal, flat, make_state(level=30, xp=131), ok=True)
    for _ in range(STALL_CYCLES - 1):
        player._track_intention(goal, flat, flat, ok=False)
    assert player._arbiter._committed_repr == repr(goal)


def test_an_interrupt_neither_progresses_nor_stalls_the_intention():
    """RestoreHP between fights is a guard's cycle, not the intention's."""
    goal = GrindCharacterXPGoal("vampire")
    player = _player_committed_to(goal)
    flat = make_state(level=30, xp=100)
    for _ in range(STALL_CYCLES * 3):
        player._track_intention(RestoreHPGoal(), flat, flat, ok=True)
    assert player._arbiter._committed_repr == repr(goal)
    assert player._intention_stall == 0


def test_a_new_commitment_starts_its_own_count():
    first, second = GrindCharacterXPGoal("vampire"), GrindCharacterXPGoal("spider")
    player = _player_committed_to(first)
    flat = make_state(level=30, xp=100)
    for _ in range(STALL_CYCLES - 1):
        player._track_intention(first, flat, flat, ok=False)
    player._arbiter._committed_repr = repr(second)
    player._track_intention(second, flat, flat, ok=False)
    assert player._arbiter._committed_repr == repr(second)
