"""The per-intention budget (Phase 4-2b) and the turn order it feeds (Phase
5-2c-iii-a): fairness between competing intentions is an explicit budget and a
least-recently-served rotation, not focus aging."""

from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.arbiter_select import (
    BAND_DISCRETIONARY,
    BAND_FALLBACK_STEP,
    BAND_GUARD,
    BAND_RAID,
    BAND_STEP,
    Candidate,
)
from artifactsmmo_cli.ai.decision_mechanism import Mechanism
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.restore_hp import RestoreHPGoal
from artifactsmmo_cli.ai.intention_progress import (
    BUDGET_CYCLES,
    EXIT_CYCLES,
    STALL_CYCLES,
    TURN_LOG_SIZE,
    record_turn,
    rotate,
    turn_key,
)
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.plan_cache import PlanCache
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.recovery import StuckExit
from tests.test_ai.fixtures import make_state

YIELDED = "ReachSkill(jewelrycrafting->21)"


def _player(tmp_path=None) -> GamePlayer:
    store = (LearningStore(db_path=str(tmp_path / "b.db"), character="hero")
             if tmp_path is not None else None)
    return GamePlayer(character="hero", history=store)


def _cand(repr_: str, band: int) -> Candidate:
    return Candidate(goal=MagicMock(), repr_=repr_, band=band)


def _order(candidates: list[Candidate]) -> list[tuple[str, int]]:
    return [(c.repr_, c.band) for c in candidates]


def _run(player: GamePlayer, goal, cycles: int) -> None:
    """`cycles` committed cycles that all progress (a successful leg)."""
    state = make_state()
    for _ in range(cycles):
        player._track_intention(goal, state, state, ok=True)


def test_an_intention_that_spends_its_budget_ends_and_its_turn_is_recorded(tmp_path):
    """The turn names the committed GOAL: at the walk's wall there is no root
    to name, and the intention is a walk alternative (R2D2/HAL, 2026-10-05)."""
    goal = GrindCharacterXPGoal("vampire")
    player = _player(tmp_path)
    player._arbiter._committed_repr = repr(goal)
    _run(player, goal, BUDGET_CYCLES - 1)
    assert player._arbiter._committed_repr == repr(goal)
    _run(player, goal, 1)
    assert player._arbiter._committed_repr is None
    assert player._turns == {repr(goal): 1}
    assert player.history.load_turns() == {repr(goal): 1}
    assert (Mechanism.INTENTION_BUDGET, repr(goal), f"budget:{BUDGET_CYCLES}") \
        in player._arbiter.events.drain()


def test_guard_cycles_under_the_commitment_spend_its_turn():
    """USER 2026-10-06: the guards run for the intention, so their cycles spend
    its turn. Live, Lor's death_knight grind was ~20% of its cycles (the rest
    potions and rest for it): one turn lasted ~6h and the task never got one."""
    goal = GrindCharacterXPGoal("vampire")
    player = _player()
    player._arbiter._committed_repr = repr(goal)
    state = make_state()
    for _ in range(BUDGET_CYCLES - 1):
        player._track_intention(RestoreHPGoal(), state, state, ok=True)
    assert player._arbiter._committed_repr == repr(goal)
    player._track_intention(goal, state, state, ok=True)
    assert player._arbiter._committed_repr is None
    assert player._turns == {repr(goal): 1}


def test_alternating_commitments_still_spend_their_turns():
    """Live C3P0 2026-10-11: `GrindCharacterXP(vampire)` and its food
    `GatherMaterials(cooked_trout)` swapped the commitment every 1-3 cycles;
    a budget reset on every switch never filled, neither recorded a turn, and
    `GatherMaterials(king_slimeball)` (turn 41) waited behind them for hours.
    The budget is summed per goal across commitments."""
    grind, food = GrindCharacterXPGoal("vampire"), RestoreHPGoal()
    player = _player()
    state = make_state()
    for _ in range(BUDGET_CYCLES // 2 - 1):
        for goal in (grind, food):
            player._arbiter._committed_repr = repr(goal)
            player._track_intention(goal, state, state, ok=True)
            player._track_intention(goal, state, state, ok=True)
    assert player._turns == {}
    player._arbiter._committed_repr = repr(grind)
    player._track_intention(grind, state, state, ok=True)
    player._track_intention(grind, state, state, ok=True)
    assert repr(grind) in player._turns and repr(food) not in player._turns
    assert repr(grind) not in player._budget_spent  # a recorded turn starts afresh


def test_the_budget_spend_survives_a_restart(tmp_path):
    """A restart resumed with zeroed counts, so every restart handed each goal
    a fresh budget and postponed the turn of the goal behind them (live C3P0,
    2026-10-11). The spend is stored per goal and resumed; a recorded turn
    clears its goal's row."""
    goal = GrindCharacterXPGoal("vampire")
    player = _player(tmp_path)
    player._arbiter._committed_repr = repr(goal)
    _run(player, goal, 30)
    reborn = GamePlayer(character="hero", history=player.history)
    reborn._offline_timing = committed_timing()
    reborn._resume_turns()
    assert reborn._budget_spent == {repr(goal): 30}
    reborn._arbiter._committed_repr = repr(goal)
    _run(reborn, goal, BUDGET_CYCLES - 30)
    assert reborn._turns == {repr(goal): 1}
    assert reborn.history.load_budget_spent() == {}


def test_progress_does_not_reset_the_budget():
    """The budget is fairness, not liveness: a grind that progresses every
    cycle still yields after its turn."""
    goal = GrindCharacterXPGoal("vampire")
    player = _player()
    player._arbiter._committed_repr = repr(goal)
    _run(player, goal, BUDGET_CYCLES)
    assert player._arbiter._committed_repr is None


def test_the_served_step_goes_behind_every_fallback():
    cands = [_cand("Rest", BAND_GUARD), _cand(YIELDED, BAND_STEP),
             _cand("Raid", BAND_RAID), _cand("Fallback(a)", BAND_FALLBACK_STEP),
             _cand("Fallback(b)", BAND_FALLBACK_STEP), _cand("Task", BAND_DISCRETIONARY)]
    assert _order(rotate(cands, {YIELDED: 1})) == [
        ("Rest", BAND_GUARD), ("Raid", BAND_RAID),
        ("Fallback(a)", BAND_FALLBACK_STEP), ("Fallback(b)", BAND_FALLBACK_STEP),
        (YIELDED, BAND_FALLBACK_STEP), ("Task", BAND_DISCRETIONARY)]


def test_a_served_fallback_goes_behind_its_peers():
    """The wall case: no root, the intention is a fallback alternative."""
    cands = [_cand(YIELDED, BAND_FALLBACK_STEP), _cand("Fallback(b)", BAND_FALLBACK_STEP),
             _cand("Task", BAND_DISCRETIONARY)]
    assert _order(rotate(cands, {YIELDED: 1})) == [
        ("Fallback(b)", BAND_FALLBACK_STEP), (YIELDED, BAND_FALLBACK_STEP),
        ("Task", BAND_DISCRETIONARY)]


def test_a_served_means_stays_in_its_band():
    """A served means goes behind its band peers only, never behind a lower
    priority band."""
    cands = [_cand(YIELDED, BAND_RAID), _cand("Raid", BAND_RAID),
             _cand("Idle", BAND_DISCRETIONARY)]
    assert _order(rotate(cands, {YIELDED: 1})) == [
        ("Raid", BAND_RAID), (YIELDED, BAND_RAID), ("Idle", BAND_DISCRETIONARY)]


def test_a_served_goal_with_no_peer_still_runs():
    """A turn order, not a ban: with nothing else to try, the goal runs."""
    cands = [_cand(YIELDED, BAND_STEP)]
    assert _order(rotate(cands, {YIELDED: 1})) == [(YIELDED, BAND_FALLBACK_STEP)]


def test_no_turns_or_absent_goals_leave_the_order_alone():
    cands = [_cand("Step", BAND_STEP), _cand("Fallback(a)", BAND_FALLBACK_STEP)]
    assert rotate(cands, {}) is cands
    assert _order(rotate(cands, {YIELDED: 1})) == _order(cands)


def test_the_least_recently_served_goal_comes_first():
    """THE DEFECT (2026-10-05): one remembered yield gave A, B, A, B — a third
    alternative never ran. In turn order, a never-served goal leads, then the
    served ones oldest first."""
    cands = [_cand("A", BAND_STEP), _cand("B", BAND_FALLBACK_STEP),
             _cand("C", BAND_FALLBACK_STEP), _cand("D", BAND_FALLBACK_STEP)]
    assert _order(rotate(cands, {"A": 1, "B": 2})) == [
        ("C", BAND_FALLBACK_STEP), ("D", BAND_FALLBACK_STEP),
        ("A", BAND_FALLBACK_STEP), ("B", BAND_FALLBACK_STEP)]
    assert _order(rotate(cands, {"A": 3, "B": 2, "C": 4, "D": 1})) == [
        ("D", BAND_FALLBACK_STEP), ("B", BAND_FALLBACK_STEP),
        ("A", BAND_FALLBACK_STEP), ("C", BAND_FALLBACK_STEP)]


def test_every_goal_gets_a_turn_before_any_gets_a_second():
    """Four always-plannable goals, each turn spent: the order of turns is a
    cycle through all four, then repeats."""
    names = ["A", "B", "C", "D"]
    cands = [_cand(names[0], BAND_STEP), *(_cand(n, BAND_FALLBACK_STEP) for n in names[1:])]
    turns: dict[str, int] = {}
    served = []
    for _ in range(8):
        head = rotate(cands, turns)[0].repr_
        served.append(head)
        turns = record_turn(turns, head)
    assert served == names + names


def test_the_turn_log_keeps_the_most_recent():
    turns: dict[str, int] = {}
    for i in range(TURN_LOG_SIZE + 3):
        turns = record_turn(turns, f"G{i}")
    assert len(turns) == TURN_LOG_SIZE
    assert "G0" not in turns and f"G{TURN_LOG_SIZE + 2}" in turns
    assert turns[f"G{TURN_LOG_SIZE + 2}"] == TURN_LOG_SIZE + 3
    assert record_turn({"A": 4, "B": 9}, "A") == {"A": 10, "B": 9}


def test_the_player_hands_its_turns_to_the_arbiter():
    player = _player()
    player._strategy = MagicMock()
    player._turns = {YIELDED: 1}
    with (patch.object(player._arbiter, "select", return_value=(None, [], [])) as select,
          patch.object(player, "_record_decision_targets", return_value=None),
          patch.object(player, "_selection_context", return_value=MagicMock())):
        player._decide_band(make_state(), GameData(), [])
    assert select.call_args.kwargs["turns"] == {YIELDED: 1}


def test_the_turns_survive_a_restart(tmp_path):
    player = _player(tmp_path)
    goal = GrindCharacterXPGoal("vampire")
    player._arbiter._committed_repr = repr(goal)
    _run(player, goal, BUDGET_CYCLES)
    restarted = GamePlayer(character="hero", history=player.history)
    restarted._offline_timing = committed_timing()
    restarted._resume_turns()
    assert restarted._turns == {repr(goal): 1}
    assert _player()._resume_turns() is None and _player()._turns == {}


def test_a_stalled_intention_records_no_turn():
    """A stall ends the intention without a turn: the goal did not spend a
    budget, so it keeps its place."""
    player = _player()
    taker = GrindCharacterXPGoal("spider")
    player._arbiter._committed_repr = repr(taker)
    state = make_state(level=30, xp=100)
    for _ in range(STALL_CYCLES):
        player._track_intention(taker, state, state, ok=False)
    assert player._arbiter._committed_repr is None
    assert player._turns == {}


def _cache(goal) -> PlanCache:
    return PlanCache(selected_goal=goal, plan=[MagicMock()], crafting_target=None,
                     plan_level=1, goal_repr=repr(goal))


def test_an_ended_intention_drops_its_plan_here_and_in_the_store(tmp_path):
    """Phase 4-3a: after the budget the abandoned climb's cached plan ran 4-7
    more cycles (Lor, HAL, 2026-10-05). The plan belongs to the intention."""
    goal = GrindCharacterXPGoal("vampire")
    player = _player(tmp_path)
    player._arbiter._committed_repr = repr(goal)
    player._plan_cache = _cache(goal)
    player.history.save_plan_commitment(repr(goal), "{}", ["Fight(vampire)"], 0, None, 5)
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


def _unproductive(player: GamePlayer, cycles: int) -> None:
    """`cycles` committed cycles with no progress, re-committing whenever a
    stall ends the intention — the exit window spans intentions."""
    goal = GrindCharacterXPGoal("vampire")
    state = make_state(level=30, xp=100)
    for _ in range(cycles):
        player._arbiter._committed_repr = repr(goal)
        player._track_intention(goal, state, state, ok=False)


def test_no_progress_across_intentions_for_the_exit_window_stops_the_run():
    """Phase 4-3c: the only StuckExit. Stalls end each intention every
    STALL_CYCLES, and the window keeps counting through them."""
    player = _player()
    _unproductive(player, EXIT_CYCLES - 1)
    with pytest.raises(StuckExit, match=f"{EXIT_CYCLES} committed cycles"):
        _unproductive(player, 1)


def test_any_progress_restarts_the_exit_window():
    player = _player()
    _unproductive(player, EXIT_CYCLES - 1)
    goal = GrindCharacterXPGoal("vampire")
    player._arbiter._committed_repr = repr(goal)
    _run(player, goal, 1)  # a successful leg
    assert player._cycles_without_progress == 0
    _unproductive(player, EXIT_CYCLES - 1)


def test_a_turn_is_kept_per_kind_of_work_not_per_quantity():
    """Live C3P0 2026-10-12: the trout carry spent its turn at 60 and came
    back at 20, a NEW goal by its repr, at the front again."""
    assert turn_key("GatherMaterials(cooked_trout, {cooked_trout:20}, carry)") == \
        "GatherMaterials(cooked_trout, carry)"
    assert turn_key("GatherMaterials(iron_bar, {iron_bar:6})") == "GatherMaterials(iron_bar)"
    assert turn_key("SupplyBank(cooked_shrimpx20)") == "SupplyBank(cooked_shrimp)"
    assert turn_key("GrindCharacterXP(vampire)") == "GrindCharacterXP(vampire)"
    resized = _cand("GatherMaterials(cooked_trout, {cooked_trout:20}, carry)", BAND_STEP)
    waiting = _cand("GatherMaterials(king_slimeball, {king_slimeball:6})", BAND_FALLBACK_STEP)
    turns = record_turn(record_turn({}, "GatherMaterials(king_slimeball, {king_slimeball:6})"),
                        "GatherMaterials(cooked_trout, {cooked_trout:60}, carry)")
    assert turns == {"GatherMaterials(king_slimeball)": 1, "GatherMaterials(cooked_trout, carry)": 2}
    assert [c.repr_ for c in rotate([resized, waiting], turns)] == [waiting.repr_, resized.repr_]


def test_a_resized_goal_keeps_spending_the_same_budget(tmp_path):
    big = GatherMaterialsGoal("cooked_trout", {"cooked_trout": 60})
    small = GatherMaterialsGoal("cooked_trout", {"cooked_trout": 20})
    player = _player()
    for goal, cycles in ((big, BUDGET_CYCLES - 1), (small, 1)):
        player._arbiter._committed_repr = repr(goal)
        _run(player, goal, cycles)
    assert list(player._turns) == [turn_key(repr(big))]


def test_rows_from_before_the_key_fold_into_it(tmp_path):
    player = _player(tmp_path)
    player.history.save_turns({"GatherMaterials(trout, {trout:60})": 3,
                               "GatherMaterials(trout, {trout:20})": 5})
    player.history.save_budget_spent({"GatherMaterials(trout, {trout:60})": 30,
                                      "GatherMaterials(trout, {trout:20})": 12})
    player._resume_turns()
    assert player._turns == {"GatherMaterials(trout)": 5}
    assert player._budget_spent == {"GatherMaterials(trout)": 42}
