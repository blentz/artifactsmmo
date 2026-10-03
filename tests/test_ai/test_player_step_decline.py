"""`GamePlayer._step_decline`: the root walk's question about a root's step,
answered the way the arbiter answers it (Phase 3-2)."""

from unittest.mock import MagicMock, patch

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from tests.test_ai.fixtures import make_state

ROOT = ObtainItem(code="iron_sword", quantity=1, slot="weapon_slot")
STEP = ObtainItem(code="iron_bar", quantity=6)


def _decline(goal: object, decompose_result: object, reasons: list[str]) -> str | None:
    """Run the player's answer for ROOT with the step goal and the walk's
    result stubbed, and record what reached `decompose`."""
    player = GamePlayer(character="hero")

    def fake_decompose(g, state, game_data, actions, ctx, declined):
        declined.extend(reasons)
        return decompose_result

    with (patch("artifactsmmo_cli.ai.player.actionable_step", return_value=STEP) as step,
          patch("artifactsmmo_cli.ai.player.objective_step_goal", return_value=goal) as sg,
          patch("artifactsmmo_cli.ai.player.decompose", side_effect=fake_decompose)):
        answer = player._step_decline(make_state(), GameData(), NO_PROFILE_CONTEXT, [])(ROOT)
    step.assert_called_once()
    assert sg.call_args.args[0] == STEP
    assert sg.call_args.kwargs["root"] == ROOT
    return answer


def test_a_step_with_no_goal_cannot_be_served() -> None:
    assert _decline(None, None, []) == "no_step_goal"


def test_a_planned_step_is_served() -> None:
    assert _decline(MagicMock(), [MagicMock()], []) is None


def test_a_final_decline_is_the_named_reason() -> None:
    assert _decline(MagicMock(), None, ["infeasible:backpack:no_route:backpack"]) \
        == "infeasible:backpack:no_route:backpack"


def test_a_search_handoff_is_left_to_the_search() -> None:
    assert _decline(MagicMock(), None, ["upgrade:ge_venue:iron_boots"]) is None


def test_a_shape_the_walk_does_not_serve_is_left_to_the_search() -> None:
    assert _decline(MagicMock(), None, []) is None
