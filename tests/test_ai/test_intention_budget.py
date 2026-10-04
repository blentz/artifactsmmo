"""The per-intention budget and the one-turn yield (Phase 4-2b): fairness
between competing roots is an explicit budget, not focus aging."""

from unittest.mock import MagicMock

from artifactsmmo_cli.ai.decision_mechanism import Mechanism
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.intention_progress import BUDGET_CYCLES, STALL_CYCLES
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from tests.test_ai.fixtures import make_state

ROOT = ObtainItem(code="life_ring", quantity=1, slot="ring1_slot")
OTHER = ObtainItem(code="iron_boots", quantity=1, slot="boots_slot")


def _player(tmp_path=None) -> GamePlayer:
    store = (LearningStore(db_path=str(tmp_path / "b.db"), character="hero")
             if tmp_path is not None else None)
    player = GamePlayer(character="hero", history=store)
    player._last_decision = MagicMock(chosen_root=ROOT)
    return player


def _run(player: GamePlayer, goal, cycles: int) -> None:
    """`cycles` committed cycles that all progress (a successful leg)."""
    state = make_state()
    for _ in range(cycles):
        player._track_intention(goal, state, state, ok=True)


def test_an_intention_that_spends_its_budget_ends_and_its_root_yields(tmp_path):
    goal = GrindCharacterXPGoal("vampire")
    player = _player(tmp_path)
    player._arbiter._committed_repr = repr(goal)
    _run(player, goal, BUDGET_CYCLES - 1)
    assert player._arbiter._committed_repr == repr(goal)
    _run(player, goal, 1)
    assert player._arbiter._committed_repr is None
    assert player._yield == (repr(ROOT), None)
    assert (Mechanism.INTENTION_BUDGET, repr(goal), f"budget:{BUDGET_CYCLES}") \
        in player._arbiter.events.drain()


def test_progress_does_not_reset_the_budget():
    """The budget is fairness, not liveness: a grind that progresses every
    cycle still yields after its turn."""
    goal = GrindCharacterXPGoal("vampire")
    player = _player()
    player._arbiter._committed_repr = repr(goal)
    _run(player, goal, BUDGET_CYCLES)
    assert player._arbiter._committed_repr is None


def test_the_yielded_root_is_declined_for_one_turn():
    player = _player()
    player._yield = (repr(ROOT), None)
    decline = player._step_decline(make_state(), GameData(), NO_PROFILE_CONTEXT, [])
    assert decline(ROOT) == "yielded:budget"


def test_the_yield_lasts_for_the_next_intention_and_then_clears():
    player = _player()
    player._yield = (repr(ROOT), None)
    taker = GrindCharacterXPGoal("spider")
    player._arbiter._committed_repr = repr(taker)
    _run(player, taker, 1)
    assert player._yield == (repr(ROOT), repr(taker))
    player._arbiter._committed_repr = None
    _run(player, taker, 1)
    assert player._yield is None


def test_the_yield_survives_a_restart(tmp_path):
    player = _player(tmp_path)
    player._yield = (repr(ROOT), None)
    player._persist_yield()
    restarted = GamePlayer(character="hero", history=player.history)
    restarted._resume_yield()
    assert restarted._yield == (repr(ROOT), None)
    restarted._yield = None
    restarted._persist_yield()
    again = GamePlayer(character="hero", history=player.history)
    again._resume_yield()
    assert again._yield is None


def test_a_holder_that_stalls_ends_the_yield():
    """However the holder's intention ends — here a stall — the yield's turn
    is over with it."""
    player = _player()
    player._yield = (repr(ROOT), None)
    taker = GrindCharacterXPGoal("spider")
    player._arbiter._committed_repr = repr(taker)
    state = make_state(level=30, xp=100)
    player._track_intention(taker, state, state, ok=True)
    assert player._yield == (repr(ROOT), repr(taker))
    for _ in range(STALL_CYCLES):
        player._track_intention(taker, state, state, ok=False)
    assert player._arbiter._committed_repr is None
    assert player._yield is None


def test_no_commitment_yet_keeps_waiting_for_a_holder():
    player = _player()
    player._yield = (repr(ROOT), None)
    player._advance_yield(None)
    assert player._yield == (repr(ROOT), None)
