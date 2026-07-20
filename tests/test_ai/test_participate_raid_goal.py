"""ParticipateRaidGoal unit behaviour.

The goal shipped covered only by the l48 scenario pair -- an integration path.
That is how its `is_satisfied` contract ended up undocumented by any test even
though it was the single hardest thing to get right: a never-satisfied goal gives
A* no goal test, so the search runs to max_depth, returns no plan, and the
candidate is silently REJECTED. The raid was unselectable for exactly that reason
until the xp floor was added.
"""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.participate_raid import (
    RAID_PARTICIPATION_VALUE,
    ParticipateRaidGoal,
)
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
