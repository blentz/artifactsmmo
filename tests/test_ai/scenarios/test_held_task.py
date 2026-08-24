"""The HELD TASK dimension of the scenario set.

`ScenarioCharacter.task` has existed since the harness was built and, until this
file, no scenario set it: 30 of 30 carried `task_code=None`, so
`combat_deficit._blocked_task_monster` returned `None` in every offline test and
everything downstream of it — `has_combat_deficit`, `deficit_upgrade_target`,
`GearLatch`, the `GEAR_REVIEW` guard — was reachable only through hand-built
states. Live, 21.1 % of cycles hold a task, and every one of them is a
`monsters` task.

Three scenarios now hold one, chosen to give the dimension three DISTINCT
values rather than three copies of one:

* `l12_gearcrafting_gap` — a task it can win (deficit False),
* `l13_drop_recipe_grind` — a task it cannot win, with gear that closes the gap,
* `l10_copper_adequate` — a task it cannot win, with NO gear that closes it.

Two properties this file is built to keep, both of them measured rather than
assumed:

1. **Not vacuous on the combat-stats axis.** At zero total attack every monster
   is unwinnable, so the deficit arm fires for reasons that have nothing to do
   with the task — measured, a `cow` task gives deficit in 30/30 scenarios with
   stats off and 9/30 with them on. All three scenarios therefore carry derived,
   non-zero attack, and `test_task_scenarios_are_not_vacuous_on_combat_stats`
   asserts it. A future edit that drops the flag turns these cells into noise,
   and that test is what says so.
2. **Three values, not one.** `test_the_three_task_values_are_distinct` fails if
   two of them ever collapse onto the same `(deficit, closable)` pair — which is
   how a dimension quietly stops discriminating.
"""

import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.combat_deficit import deficit_upgrade_target, has_combat_deficit
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.task_lifecycle import TaskLifecyclePhase

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"

WORKABLE = "l12_gearcrafting_gap"
UNWINNABLE_CLOSABLE = "l13_drop_recipe_grind"
UNWINNABLE_OPEN = "l10_copper_adequate"
TASK_SCENARIOS = (WORKABLE, UNWINNABLE_CLOSABLE, UNWINNABLE_OPEN)


@pytest.fixture(scope="module")
def gd() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def _state(name: str, game_data: GameData):
    return scenario_state(SCENARIOS[name], game_data)


def test_the_held_task_dimension_has_a_populated_side(gd: GameData) -> None:
    """The dimension is populated at all — and the fields are wired end to end."""
    holders = [n for n in SCENARIOS if SCENARIOS[n].task is not None]
    assert sorted(holders) == sorted(TASK_SCENARIOS)
    for name in TASK_SCENARIOS:
        code, kind, progress, total = SCENARIOS[name].task
        state = _state(name, gd)
        assert state.task_code == code
        assert state.task_type == kind == "monsters"
        assert (state.task_progress, state.task_total) == (progress, total)
        assert state.task_lifecycle_phase is TaskLifecyclePhase.IN_PROGRESS
        assert gd.monster_level(code) is not None, "the task monster must be real"


def test_task_scenarios_are_not_vacuous_on_combat_stats(gd: GameData) -> None:
    """Zero attack would make the deficit fire for a reason that is not the task.

    Measured: with `derive_combat_stats` off, a cow task gives
    `has_combat_deficit` in 30/30 scenarios; with it on, 9/30. A task cell on the
    zero-attack side therefore measures the harness, not the bot."""
    for name in TASK_SCENARIOS:
        assert SCENARIOS[name].derive_combat_stats
        state = _state(name, gd)
        assert any(state.attack.values()), f"{name} has no attack — cell is vacuous"


def test_the_three_task_values_are_distinct(gd: GameData) -> None:
    """Three cells, three answers. Collapse two and the dimension stops splitting."""
    seen = {
        name: (has_combat_deficit(_state(name, gd), gd),
               deficit_upgrade_target(_state(name, gd), gd) is not None)
        for name in TASK_SCENARIOS
    }
    assert len(set(seen.values())) == 3, seen


def test_workable_task_reaches_the_negative_deficit_arm(gd: GameData) -> None:
    """`_blocked_task_monster` names a monster AND `predict_win` says yes.

    The negative arm is only reachable with a task in hand: no task at all
    short-circuits before `predict_win` is ever called, which is why 30/30
    task-free scenarios proved nothing about it."""
    state = _state(WORKABLE, gd)
    assert state.task_code == "cow"
    assert has_combat_deficit(state, gd) is False
    assert deficit_upgrade_target(state, gd) is None


def test_unwinnable_task_names_the_gear_that_closes_it(gd: GameData) -> None:
    """The "I lost, so get gear" link, with an offline witness at last.

    Before this the ONLY route from a lost fight to a gear upgrade was a
    countdown timer, and the walk that replaced it had no scenario exercising
    its positive arm."""
    state = _state(UNWINNABLE_CLOSABLE, gd)
    assert has_combat_deficit(state, gd) is True
    target = deficit_upgrade_target(state, gd)
    assert target is not None
    item, slot = target
    assert slot == "weapon_slot"
    assert gd.item_stats(item) is not None


def test_unwinnable_task_with_no_closing_chain_names_nothing(gd: GameData) -> None:
    """The FALL-THROUGH arm: a deficit no gear in the catalogue closes.

    Paired with the test above on purpose — `None` here is only meaningful next
    to a case where the same call returns a target, otherwise it is
    indistinguishable from the function never running."""
    state = _state(UNWINNABLE_OPEN, gd)
    assert has_combat_deficit(state, gd) is True
    assert deficit_upgrade_target(state, gd) is None
