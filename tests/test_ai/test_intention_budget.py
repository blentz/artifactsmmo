"""The per-intention budget and the one-turn yield (Phase 4-2b): fairness
between competing intentions is an explicit budget, not focus aging."""

from unittest.mock import MagicMock, patch

from artifactsmmo_cli.ai.arbiter_select import (
    BAND_COLLECT,
    BAND_DISCRETIONARY,
    BAND_FALLBACK_STEP,
    BAND_GUARD,
    BAND_RAID,
    BAND_STEP,
    Candidate,
)
from artifactsmmo_cli.ai.decision_mechanism import Mechanism
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.intention_progress import (
    BUDGET_CYCLES,
    STALL_CYCLES,
    demote_yielded,
)
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.plan_cache import PlanCache
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state

YIELDED = "ReachSkill(jewelrycrafting->21)"


def _player(tmp_path=None) -> GamePlayer:
    store = (LearningStore(db_path=str(tmp_path / "b.db"), character="hero")
             if tmp_path is not None else None)
    return GamePlayer(character="hero", history=store)


def _cand(repr_: str, band: int) -> Candidate:
    return Candidate(goal=MagicMock(), is_means=band != BAND_GUARD, repr_=repr_, band=band)


def _order(candidates: list[Candidate]) -> list[tuple[str, int]]:
    return [(c.repr_, c.band) for c in candidates]


def _run(player: GamePlayer, goal, cycles: int) -> None:
    """`cycles` committed cycles that all progress (a successful leg)."""
    state = make_state()
    for _ in range(cycles):
        player._track_intention(goal, state, state, ok=True)


def test_an_intention_that_spends_its_budget_ends_and_its_goal_yields(tmp_path):
    """The yield names the committed GOAL: at the walk's wall there is no root
    to name, and the intention is a walk alternative (R2D2/HAL, 2026-10-05)."""
    goal = GrindCharacterXPGoal("vampire")
    player = _player(tmp_path)
    player._arbiter._committed_repr = repr(goal)
    _run(player, goal, BUDGET_CYCLES - 1)
    assert player._arbiter._committed_repr == repr(goal)
    _run(player, goal, 1)
    assert player._arbiter._committed_repr is None
    assert player._yield == (repr(goal), None)
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


def test_the_yielded_step_goes_behind_every_fallback():
    cands = [_cand("Rest", BAND_GUARD), _cand(YIELDED, BAND_STEP),
             _cand("Raid", BAND_RAID), _cand("Fallback(a)", BAND_FALLBACK_STEP),
             _cand("Fallback(b)", BAND_FALLBACK_STEP), _cand("Task", BAND_DISCRETIONARY)]
    assert _order(demote_yielded(cands, YIELDED)) == [
        ("Rest", BAND_GUARD), ("Raid", BAND_RAID),
        ("Fallback(a)", BAND_FALLBACK_STEP), ("Fallback(b)", BAND_FALLBACK_STEP),
        (YIELDED, BAND_FALLBACK_STEP), ("Task", BAND_DISCRETIONARY)]


def test_a_yielded_fallback_goes_behind_its_peers():
    """The wall case: no root, the intention is a fallback alternative."""
    cands = [_cand(YIELDED, BAND_FALLBACK_STEP), _cand("Fallback(b)", BAND_FALLBACK_STEP),
             _cand("Task", BAND_DISCRETIONARY)]
    assert _order(demote_yielded(cands, YIELDED)) == [
        ("Fallback(b)", BAND_FALLBACK_STEP), (YIELDED, BAND_FALLBACK_STEP),
        ("Task", BAND_DISCRETIONARY)]


def test_a_yielded_means_stays_in_its_band():
    """A collect-band means yields to its band peers only, never to a lower
    priority band."""
    cands = [_cand(YIELDED, BAND_COLLECT), _cand("Equip", BAND_COLLECT),
             _cand("Step", BAND_STEP)]
    assert _order(demote_yielded(cands, YIELDED)) == [
        ("Equip", BAND_COLLECT), (YIELDED, BAND_COLLECT), ("Step", BAND_STEP)]


def test_a_yield_with_no_peer_still_runs():
    """A yield, not a ban: with nothing else to try, the goal keeps its turn."""
    cands = [_cand(YIELDED, BAND_STEP)]
    assert _order(demote_yielded(cands, YIELDED)) == [(YIELDED, BAND_FALLBACK_STEP)]


def test_no_yield_or_an_absent_goal_leaves_the_order_alone():
    cands = [_cand("Step", BAND_STEP), _cand("Fallback(a)", BAND_FALLBACK_STEP)]
    assert demote_yielded(cands, None) is cands
    assert _order(demote_yielded(cands, YIELDED)) == _order(cands)


def test_the_player_hands_its_yield_to_the_arbiter():
    player = _player()
    player._strategy = MagicMock()
    player._yield = (YIELDED, None)
    with (patch.object(player._arbiter, "select", return_value=(None, [], [])) as select,
          patch.object(player, "_record_decision_targets", return_value=None),
          patch.object(player, "_selection_context", return_value=MagicMock())):
        player._decide_band(make_state(), GameData(), [], None)
    assert select.call_args.kwargs["yielded"] == YIELDED


def test_the_yield_lasts_for_the_next_intention_and_then_clears():
    player = _player()
    player._yield = (YIELDED, None)
    taker = GrindCharacterXPGoal("spider")
    player._arbiter._committed_repr = repr(taker)
    _run(player, taker, 1)
    assert player._yield == (YIELDED, repr(taker))
    player._arbiter._committed_repr = None
    _run(player, taker, 1)
    assert player._yield is None


def test_the_yield_survives_a_restart(tmp_path):
    player = _player(tmp_path)
    player._yield = (YIELDED, None)
    player._persist_yield()
    restarted = GamePlayer(character="hero", history=player.history)
    restarted._resume_yield()
    assert restarted._yield == (YIELDED, None)
    restarted._yield = None
    restarted._persist_yield()
    again = GamePlayer(character="hero", history=player.history)
    again._resume_yield()
    assert again._yield is None


def test_a_holder_that_stalls_ends_the_yield():
    """However the holder's intention ends — here a stall — the yield's turn
    is over with it."""
    player = _player()
    player._yield = (YIELDED, None)
    taker = GrindCharacterXPGoal("spider")
    player._arbiter._committed_repr = repr(taker)
    state = make_state(level=30, xp=100)
    player._track_intention(taker, state, state, ok=True)
    assert player._yield == (YIELDED, repr(taker))
    for _ in range(STALL_CYCLES):
        player._track_intention(taker, state, state, ok=False)
    assert player._arbiter._committed_repr is None
    assert player._yield is None


def test_no_commitment_yet_keeps_waiting_for_a_holder():
    player = _player()
    player._yield = (YIELDED, None)
    player._advance_yield(None)
    assert player._yield == (YIELDED, None)


def _cache(goal) -> PlanCache:
    return PlanCache(selected_goal=goal, plan=[MagicMock()], crafting_target=None,
                     latch_active=False, goal_repr=repr(goal))


def test_an_ended_intention_drops_its_plan_here_and_in_the_store(tmp_path):
    """Phase 4-3a: after the budget the abandoned climb's cached plan ran 4-7
    more cycles (Lor, HAL, 2026-10-05). The plan belongs to the intention."""
    goal = GrindCharacterXPGoal("vampire")
    player = _player(tmp_path)
    player._arbiter._committed_repr = repr(goal)
    player._plan_cache = _cache(goal)
    player.history.save_plan_commitment(repr(goal), "{}", ["Fight(vampire)"], 0, None, False)
    _run(player, goal, BUDGET_CYCLES)
    assert player._plan_cache is None
    assert player.history.load_plan_commitment() is None


def test_a_stalled_intention_drops_its_plan():
    goal = GrindCharacterXPGoal("vampire")
    player = _player()
    player._arbiter._committed_repr = repr(goal)
    player._plan_cache = _cache(goal)
    state = make_state(level=30, xp=100)
    for _ in range(STALL_CYCLES):
        player._track_intention(goal, state, state, ok=False)
    assert player._plan_cache is None


def test_a_cached_plan_of_another_goal_is_not_the_intentions():
    goal = GrindCharacterXPGoal("vampire")
    player = _player()
    player._arbiter._committed_repr = repr(goal)
    other = _cache(GrindCharacterXPGoal("spider"))
    player._plan_cache = other
    _run(player, goal, BUDGET_CYCLES)
    assert player._plan_cache is other
