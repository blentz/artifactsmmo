from artifactsmmo_cli.ai.action_kind import action_kind_of
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.rest import RestAction


def test_move_kind_and_target():
    assert action_kind_of(MoveAction(x=3, y=4)) == ("move", "3,4")


def test_gather_kind_and_target():
    assert action_kind_of(GatherAction(resource_code="copper_rocks")) == ("gather", "copper_rocks")


def test_fight_kind_and_target():
    assert action_kind_of(FightAction(monster_code="chicken")) == ("fight", "chicken")


def test_rest_kind_no_target():
    assert action_kind_of(RestAction()) == ("rest", None)


def test_unknown_action_is_other():
    assert action_kind_of(object()) == ("other", None)
