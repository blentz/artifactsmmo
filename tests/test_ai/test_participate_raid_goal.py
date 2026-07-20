"""ParticipateRaidGoal unit behaviour.

The goal shipped covered only by the l48 scenario pair -- an integration path.
That is how its `is_satisfied` contract ended up undocumented by any test even
though it was the single hardest thing to get right: a never-satisfied goal gives
A* no goal test, so the search runs to max_depth, returns no plan, and the
candidate is silently REJECTED. The raid was unselectable for exactly that reason
until the xp floor was added.
"""

from datetime import datetime, timedelta, timezone

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.participate_raid import (
    RAID_PARTICIPATION_VALUE,
    ParticipateRaidGoal,
)
from artifactsmmo_cli.ai.raid_info import RaidInfo
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

_RAID = "enchanted_fairy"
_BOSS = "pixie"


def _goal(xp_floor: int = 100) -> ParticipateRaidGoal:
    return ParticipateRaidGoal(raid_code=_RAID, monster_code=_BOSS, xp_floor=xp_floor)


def test_unsatisfied_at_the_floor():
    """One engagement is the unit of work, so the goal is open until XP moves."""
    assert _goal(xp_floor=100).is_satisfied(make_state(xp=100)) is False


def test_satisfied_once_xp_rises_above_the_floor():
    assert _goal(xp_floor=100).is_satisfied(make_state(xp=101)) is True


def test_unsatisfied_below_the_floor():
    """Defensive: a lower XP than the floor is not 'done'. Cannot happen in a
    forward plan, but the predicate must not read as satisfied by accident."""
    assert _goal(xp_floor=100).is_satisfied(make_state(xp=99)) is False


def test_relevant_actions_keeps_only_the_boss_fight():
    """The goal narrows to its OWN boss. Without this it would admit every fight
    in the catalog and plan an unrelated grind under a raid banner."""
    boss = FightAction(monster_code=_BOSS, locations=frozenset({(1, 0)}))
    other = FightAction(monster_code="chicken", locations=frozenset({(2, 0)}))
    catalog = [boss, other, MoveAction(x=0, y=0), RestAction()]
    out = _goal().relevant_actions(catalog, make_state(), GameData())
    assert out == [boss]


def test_relevant_actions_empty_when_the_boss_fight_is_absent():
    """The factory only emits the raid fight while the window is open, so a shut
    window leaves this goal with nothing -- it must not invent an action."""
    catalog = [FightAction(monster_code="chicken", locations=frozenset({(2, 0)}))]
    assert _goal().relevant_actions(catalog, make_state(), GameData()) == []


def test_value_is_the_discretionary_constant():
    """Vestigial for routing (the arbiter selects by band position, not value)
    but pinned so it cannot drift into reading as a priority claim it cannot
    make -- it must stay below the survival floor."""
    assert _goal().value(make_state(), GameData()) == RAID_PARTICIPATION_VALUE
    assert RAID_PARTICIPATION_VALUE < 50.0


def test_repr_names_the_raid_not_the_boss():
    """Sticky commitment keys on repr, and the RAID is the thing whose window
    opens and shuts; two raids sharing a boss must not collide."""
    assert repr(_goal()) == f"ParticipateRaid({_RAID})"


def test_desired_state_is_empty_so_the_goal_test_is_is_satisfied():
    """Pairs with is_satisfied: the planner goal-tests via is_satisfied, so a
    non-empty desired_state here would add a second, divergent goal test."""
    assert _goal().desired_state(make_state(), GameData()) == {}


# ─── the two _raid_candidates gates, exercised directly ──────────────────────
# Both are refusals the raid design turns on, and both shipped uncovered: a raid
# with no known tile, and one the character cannot survive. A gate that is never
# exercised is a gate nobody has checked refuses anything.

def _raid_info() -> RaidInfo:
    now = datetime.now(timezone.utc)
    return RaidInfo(code=_RAID, name=_RAID, monster=_BOSS, status="active",
                    next_start_at=now + timedelta(days=1), remaining_hp=5000,
                    total_hp=10000, window_ends_at=now + timedelta(hours=1))


def _raid_gd(*, tiles: bool, hurts: bool) -> GameData:
    gd = GameData()
    gd._item_stats = {"x": ItemStats(code="x", level=1, type_="resource")}
    gd._monster_level = {_BOSS: 40}
    gd._monster_hp = {_BOSS: 100}
    gd._monster_attack = {_BOSS: {"air": 400 if hurts else 1}}
    gd._monster_resistance = {_BOSS: {}}
    if tiles:
        gd.world.raid_locations = {_RAID: [(-4, 10)]}
    fill_monster_stat_defaults(gd)
    return gd


def _candidates(gd, state):
    return StrategyArbiter._raid_candidates(
        StrategyArbiter.__new__(StrategyArbiter), state, gd)


def test_raid_with_no_known_tile_is_not_offered():
    state = make_state(level=48, hp=1000, max_hp=1000,
                       attack={"air": 50}, raids=[_raid_info()])
    assert _candidates(_raid_gd(tiles=False, hurts=False), state) == []


def test_unsurvivable_raid_is_not_offered():
    """A boss that would drop the character below the critical floor in one
    engagement: rest first, do not go."""
    state = make_state(level=48, hp=1000, max_hp=1000,
                       attack={"air": 50}, raids=[_raid_info()])
    assert _candidates(_raid_gd(tiles=True, hurts=True), state) == []


def test_survivable_raid_with_a_tile_is_offered():
    """Non-vacuity: the same shape that passes both gates DOES produce a goal,
    so the two refusals above are measuring the gates and not a broken fixture."""
    state = make_state(level=48, hp=1000, max_hp=1000,
                       attack={"air": 50}, raids=[_raid_info()])
    out = _candidates(_raid_gd(tiles=True, hurts=False), state)
    assert [repr(g) for g in out] == [f"ParticipateRaid({_RAID})"]
