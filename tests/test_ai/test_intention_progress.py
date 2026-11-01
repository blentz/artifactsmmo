"""The intention's progress measure (Phase 4-2a): what "moved" means for each
goal family, and when an intention has stalled."""

from fractions import Fraction

import pytest

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.decision_mechanism import Mechanism
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.reach_skill import ReachSkillGoal
from artifactsmmo_cli.ai.goals.restore_hp import RestoreHPGoal
from artifactsmmo_cli.ai.impossible_drop_error import ImpossibleDropError
from artifactsmmo_cli.ai.intention_progress import (
    BUDGET_CYCLES,
    STALL_CYCLES,
    drop_key,
    dry_within_luck,
    leg_progressed,
    progress_measure,
    progressed,
    step_chance,
    step_delivered,
)
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
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
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
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


def _shrimp_world() -> GameData:
    gd = GameData()
    gd.recipes_catalog.resource_drops = {"shrimp_spot": "shrimp"}
    return gd


def _ticket_gather() -> GatherAction:
    return GatherAction(resource_code="shrimp_spot", drop_item_override="event_ticket",
                        learned_drops=LearnedDrops.empty())


def test_a_gather_whose_drop_did_not_land_delivers_nothing():
    """The ticket farm (live 2026-10-31): `Gather(shrimp_spot->event_ticket)`
    succeeds whether or not the 1-in-200 ticket lands. It delivers only when
    the ticket count rose; a gather for the primary drop, or an action
    planned for no drop, delivers by succeeding."""
    gd = _shrimp_world()
    dry = make_state(inventory={"shrimp": 1})
    landed = make_state(inventory={"shrimp": 1, "event_ticket": 1})
    assert not step_delivered(_ticket_gather(), make_state(), dry, gd)
    assert step_delivered(_ticket_gather(), make_state(), landed, gd)
    primary = GatherAction(resource_code="shrimp_spot", learned_drops=LearnedDrops.empty())
    assert step_delivered(primary, make_state(), dry, gd)
    assert step_delivered(RestAction(), make_state(), make_state(), gd)


def test_a_dry_drop_farm_ends_on_the_stall_exit():
    """25 shrimp gathers with no ticket: the committed farm is abandoned as
    stalled on its twentieth dry cycle, not handed a full budget every turn."""
    goal = GatherMaterialsGoal("event_ticket", {"event_ticket": 100})
    player = _player_committed_to(goal)
    gd = _shrimp_world()
    before = make_state(inventory={"shrimp": 3})
    after = make_state(inventory={"shrimp": 4})
    ended = None
    for cycle in range(1, 26):
        ok = step_delivered(_ticket_gather(), before, after, gd)
        player._track_intention(goal, before, after, ok=ok)
        if player._arbiter._committed_repr is None:
            ended = cycle
            break
    assert ended == STALL_CYCLES


def test_a_dry_streak_is_luck_until_its_99th_percentile():
    """A legitimate rare drop is not stalled by chance: at p = 1/50 the 99th
    percentile dry streak is ceil(ln 0.01 / ln 0.98) = 228, so 100 dry
    attempts are still luck and 300 are not. A sure drop forgives none; an
    action planned for no drop is never dry."""
    assert dry_within_luck(100, Fraction(1, 50))
    assert dry_within_luck(228, Fraction(1, 50))
    assert not dry_within_luck(229, Fraction(1, 50))
    assert not dry_within_luck(300, Fraction(1, 50))
    assert dry_within_luck(0, Fraction(1))
    assert not dry_within_luck(1, Fraction(1))
    assert dry_within_luck(10_000, None)


def test_the_chance_of_a_planned_drop_is_the_learned_one():
    """`step_chance`: a gather's planned drop at its resource's row (the prior
    1/rate, nothing observed), a gather for the primary drop a sure one, and
    an action planned for no drop none."""
    gd = _shrimp_world()
    gd.recipes_catalog.resource_drops_full = {
        "shrimp_spot": [("shrimp", 1, 1, 1), ("event_ticket", 200, 1, 1)]}
    gd._resource_skill = {"shrimp_spot": ("fishing", 1)}
    assert step_chance(_ticket_gather(), make_state(), gd) == Fraction(1, 200)
    primary = GatherAction(resource_code="shrimp_spot", learned_drops=LearnedDrops.empty())
    assert step_chance(primary, make_state(), gd) == 1
    assert step_chance(RestAction(), make_state(), gd) is None


def test_a_rare_drop_farm_is_not_stalled_by_chance():
    """The run loop's rule (`GamePlayer` sums the dry streak): a 1-in-50 farm
    99 cycles dry is luck, so the intention holds; past its 228-attempt
    percentile, 20 more dry cycles stall it."""
    goal = GatherMaterialsGoal("event_ticket", {"event_ticket": 100})
    player = _player_committed_to(goal)
    flat = make_state()
    for streak in range(1, BUDGET_CYCLES):
        player._track_intention(goal, flat, flat, ok=dry_within_luck(streak, Fraction(1, 50)))
    assert player._arbiter._committed_repr == repr(goal)
    assert player._intention_stall == 0
    dry = _player_committed_to(goal)
    for streak in range(229, 229 + STALL_CYCLES - 1):
        dry._track_intention(goal, flat, flat, ok=dry_within_luck(streak, Fraction(1, 50)))
    assert dry._arbiter._committed_repr == repr(goal)
    dry._track_intention(goal, flat, flat, ok=dry_within_luck(300, Fraction(1, 50)))
    assert dry._arbiter._committed_repr is None


def test_a_zero_chance_drop_is_a_named_pricing_bug():
    """Review M1: a leg planned for a drop of chance 0 has no percentile
    (ln(1 - 0) = 0); it is a pricing bug, raised by name."""
    with pytest.raises(ImpossibleDropError):
        dry_within_luck(1, Fraction(0))


def test_a_planned_drop_is_keyed_on_its_source_and_item():
    """`drop_key`: the gather's resource or the fight's monster, with the item;
    None for an action planned for no drop."""
    gd = _shrimp_world()
    assert drop_key(_ticket_gather(), gd) == ("shrimp_spot", "event_ticket")
    fight = FightAction(monster_code="chicken", drop_target=("feather", 8),
                        learned_drops=LearnedDrops.empty())
    assert drop_key(fight, gd) == ("chicken", "feather")
    assert drop_key(MoveAction(x=1, y=1), gd) is None


def _ticket_world() -> GameData:
    gd = _shrimp_world()
    gd.recipes_catalog.resource_drops_full = {
        "shrimp_spot": [("shrimp", 1, 1, 1), ("event_ticket", 2, 1, 1)]}
    gd._resource_skill = {"shrimp_spot": ("fishing", 1)}
    return gd


def test_only_its_own_drop_moves_a_dry_streak():
    """Review C1: the streak is kept per `(source, item)`. A dry attempt adds
    one; the drop landing resets its key only; a leg planned for no drop is
    progress and leaves every streak as it was; a failed leg is no progress
    and adds nothing. At 1 in 2 the eighth dry attempt is past luck (7)."""
    gd = _ticket_world()
    dry = make_state(inventory={"shrimp": 1})
    landed = make_state(inventory={"shrimp": 1, "event_ticket": 1})
    streaks = {("chicken", "feather"): 5}
    for _ in range(7):
        assert leg_progressed(streaks, _ticket_gather(), make_state(), dry, True, gd)
        assert leg_progressed(streaks, MoveAction(x=1, y=1), make_state(), dry, True, gd)
    assert not leg_progressed(streaks, _ticket_gather(), make_state(), dry, False, gd)
    assert streaks == {("chicken", "feather"): 5, ("shrimp_spot", "event_ticket"): 7}
    assert not leg_progressed(streaks, _ticket_gather(), make_state(), dry, True, gd)
    assert streaks[("shrimp_spot", "event_ticket")] == 8
    assert leg_progressed(streaks, _ticket_gather(), make_state(), landed, True, gd)
    assert streaks == {("chicken", "feather"): 5, ("shrimp_spot", "event_ticket"): 0}
