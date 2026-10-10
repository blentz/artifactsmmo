"""RestoreHP's A* choice against the loop model's recovery choice, with the
chosen food in the bag (`docs/PLAN_consumable_utility.md` increment 5, item 3).

The loop rate prices a fight's recovery with `loop_rate_core.recovery_choice`
(held food free); RestoreHP plans the same recovery over seconds-priced Rest /
UseConsumable. On these states they agree: eat when eating is cheaper, rest
when Rest wins."""

from fractions import Fraction

from artifactsmmo_cli.ai.actions.consumable import UseConsumableAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.restore_hp import RestoreHPGoal
from artifactsmmo_cli.ai.loop_rate import EAT_SECONDS
from artifactsmmo_cli.ai.loop_rate_core import recovery_choice
from artifactsmmo_cli.ai.planner import GOAPPlanner
from tests.test_ai.fixtures import make_state

_CHEESE = {"cheese": ItemStats(code="cheese", level=1, type_="consumable", hp_restore=150)}


def _plan(hp: int, held: int) -> list[str]:
    gd = GameData()
    gd._item_stats = dict(_CHEESE)
    state = make_state(hp=hp, max_hp=1000, inventory={"cheese": held})
    plan = GOAPPlanner().plan(state, RestoreHPGoal(),
                              [RestAction(), UseConsumableAction(_item_stats=_CHEESE)], gd)
    return [repr(a) for a in plan]


def _loop_choice(hp: int, held: int) -> tuple[Fraction, tuple[int, ...]]:
    return recovery_choice(1000 - hp, 1000, [(150, None, held)], EAT_SECONDS)


def test_it_eats_the_chosen_food_when_the_loop_model_says_eating_is_cheaper() -> None:
    # 300 missing: two cheeses close it (3 s) where a Rest costs 30 s.
    assert _loop_choice(700, 2) == (Fraction(3), (2,))
    assert _plan(700, 2) == ["UseConsumable"]  # two cheeses, ONE use


def test_it_rests_when_the_loop_model_says_rest_wins() -> None:
    # 20 missing: a Rest at its 3 s floor ties one eat, and the tie keeps the
    # food (fewer units); A* rests rather than overheal a 150-hp cheese.
    assert _loop_choice(980, 2) == (Fraction(3), (0,))
    assert _plan(980, 2) == ["Rest"]
