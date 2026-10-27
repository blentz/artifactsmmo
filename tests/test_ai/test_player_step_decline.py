"""`GamePlayer._step_decline`: the root walk's question about a root's step,
answered the way the arbiter answers it (Phase 3-2)."""

from unittest.mock import MagicMock, patch

from artifactsmmo_cli.ai.bag_clear import SLOT_DECLINES, ClearPlan
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
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
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()

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


SLOT = "first_leg_inapplicable:Withdraw(iron_bar×6)"


def _full_bag(roomy_result: object, roomy_reasons: list[str], *, needs: bool = True,
              freed: int = 1, reasons: tuple[str, ...] = (SLOT,)) -> str | None:
    """The answer for ROOT when the walk declines on the real bag with
    `reasons` and answers `roomy_result` / `roomy_reasons` on the emptied bag
    (`bag_clear.roomy` raises the slot cap), with the plan's slot need and the
    clear's freed slots stubbed (Task 14a)."""
    player = GamePlayer(character="hero")
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
    state = make_state(inventory={"copper_ore": 1})

    def fake_decompose(g, at, game_data, actions, ctx, declined):
        if at.inventory_slots_max > state.inventory_slots_max:
            declined.extend(roomy_reasons)
            return roomy_result
        declined.extend(reasons)
        return None

    clear = ClearPlan(actions=(), freed=freed)
    with (patch("artifactsmmo_cli.ai.player.actionable_step", return_value=STEP),
          patch("artifactsmmo_cli.ai.player.objective_step_goal", return_value=MagicMock()),
          patch("artifactsmmo_cli.ai.player.decompose", side_effect=fake_decompose),
          patch("artifactsmmo_cli.ai.player.needs_slot", return_value=needs),
          patch("artifactsmmo_cli.ai.player.related_codes", return_value=frozenset()),
          patch("artifactsmmo_cli.ai.player.clear_actions", return_value=clear)):
        return player._step_decline(state, GameData(), NO_PROFILE_CONTEXT, [])(ROOT)


def test_a_step_the_clear_unblocks_is_served() -> None:
    assert _full_bag([MagicMock()], []) is None


def test_every_slot_decline_shape_asks_the_cleared_bag() -> None:
    for reason in SLOT_DECLINES:
        assert _full_bag([MagicMock()], [], reasons=(f"{reason}x",)) is None


def test_a_slot_decline_behind_another_is_still_asked() -> None:
    """Any slot-shaped decline, as the arbiter's `any` reads them."""
    assert _full_bag([MagicMock()], [], reasons=("infeasible:x", SLOT)) is None


def test_a_decline_the_cleared_bag_still_gives_is_its_reason() -> None:
    assert _full_bag(None, ["infeasible:iron_bar:no_route:iron_ore"]) == (
        "infeasible:iron_bar:no_route:iron_ore")


def test_a_cleared_bag_the_walk_hands_to_the_search_is_the_searchs() -> None:
    assert _full_bag(None, ["upgrade:ge_venue:iron_sword"]) is None


def test_a_cleared_plan_that_needs_no_slot_here_keeps_the_decline() -> None:
    assert _full_bag([MagicMock()], [], needs=False) == SLOT


def test_a_clear_that_frees_nothing_keeps_the_decline() -> None:
    assert _full_bag([MagicMock()], [], freed=0) == SLOT


def test_a_decline_no_full_bag_causes_is_not_asked_again() -> None:
    assert _full_bag([MagicMock()], [], reasons=("infeasible:x",)) == "infeasible:x"
