"""`GamePlayer._committed_fight_monster`: the fight the committed intention has
ahead, which the potion guard sizes its stock for (2026-10-06).

Live Lor: the stock was sized for the first winnable in-band monster (`rat`),
which Lor never fought — ~258 sunflower gathers in three hours for potions the
server drank in cow and wolf fights Lor won anyway."""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.plan_cache import PlanCache
from artifactsmmo_cli.ai.player import GamePlayer


def _cache(goal_repr: str, plan, cursor: int = 0) -> PlanCache:  # type: ignore[no-untyped-def]
    return PlanCache(selected_goal=GrindCharacterXPGoal("wolf"), plan=list(plan),
                     crafting_target=None, plan_level=10, goal_repr=goal_repr, cursor=cursor)


def _fight(monster: str) -> FightAction:
    return FightAction(monster_code=monster, locations=frozenset({(1, 0)}))


def test_no_intention_no_fight() -> None:
    assert GamePlayer(character="hero", history=None)._committed_fight_monster() is None


def test_the_first_fight_left_in_the_intentions_plan() -> None:
    player = GamePlayer(character="hero", history=None)
    player._arbiter._committed_repr = "Grind"
    player._plan_cache = _cache("Grind", [_fight("cow"), RestAction(), _fight("wolf")], cursor=1)
    assert player._committed_fight_monster() == "wolf"


def test_an_intention_that_fights_nothing_has_no_fight() -> None:
    player = GamePlayer(character="hero", history=None)
    player._arbiter._committed_repr = "Climb"
    player._plan_cache = _cache("Climb", [RestAction()])
    assert player._committed_fight_monster() is None


def test_the_fight_survives_an_interrupt_that_replaces_the_cache() -> None:
    """A rest, or the potion batch itself, caches its own plan: the fight it
    interrupts is still the one ahead, or the batch would stop half made."""
    player = GamePlayer(character="hero", history=None)
    player._arbiter._committed_repr = "Grind"
    player._plan_cache = _cache("Grind", [_fight("wolf")])
    assert player._committed_fight_monster() == "wolf"
    player._plan_cache = _cache("CraftPotionsGoal", [RestAction()])
    assert player._committed_fight_monster() == "wolf"


def test_a_new_commitment_forgets_the_old_fight() -> None:
    player = GamePlayer(character="hero", history=None)
    player._arbiter._committed_repr = "Grind"
    player._plan_cache = _cache("Grind", [_fight("wolf")])
    assert player._committed_fight_monster() == "wolf"
    player._arbiter._committed_repr = "Climb"
    player._plan_cache = None
    assert player._committed_fight_monster() is None
