"""OptimizeLoadoutAction.execute must wait out each API call's cooldown.

Live livelock 2026-07-05 23:34-23:36 (~6 wasted calls/min): the gather re-arm
unequipped copper_dagger (cooldown starts), immediately issued the pickaxe
equip -> HTTP 499 -> half-swapped EMPTY weapon slot -> EquipOwnedGear refilled
the dagger by Rank -> next cycle re-armed again, forever. MoveAction documents
the composite-action idiom: block until the cooldown the server just set has
expired before the next call.
"""

import datetime as dt
from unittest.mock import MagicMock, patch

from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_pickaxe": ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                                    attack={"earth": 5}, skill_effects={"mining": -10}),
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   attack={"air": 6}, critical_strike=35),
    }
    return gd


def test_execute_waits_out_cooldown_between_unequip_and_equip() -> None:
    gd = _gd()
    action = OptimizeLoadoutAction(target_skill="mining", game_data=gd)
    state = make_state(inventory={"copper_pickaxe": 1},
                       equipment={"weapon_slot": "copper_dagger"},
                       skills={"mining": 12})
    # The unequip's server response carries a live cooldown; the equip that
    # follows must not be issued until it expires.
    cooldown_until = dt.datetime.now(tz=dt.timezone.utc) + dt.timedelta(seconds=2)
    unequipped = make_state(inventory={"copper_pickaxe": 1, "copper_dagger": 1},
                            skills={"mining": 12},
                            cooldown_expires=cooldown_until)
    equipped = make_state(inventory={"copper_dagger": 1},
                          equipment={"weapon_slot": "copper_pickaxe"},
                          skills={"mining": 12})
    calls: list[str] = []
    client = MagicMock()
    with patch("artifactsmmo_cli.ai.actions.optimize_loadout.UnequipAction") as mock_un, \
         patch("artifactsmmo_cli.ai.actions.optimize_loadout.EquipAction") as mock_eq, \
         patch("artifactsmmo_cli.ai.actions.optimize_loadout.time.sleep",
               side_effect=lambda s: calls.append(f"sleep:{s:.1f}")) as mock_sleep:
        mock_un.return_value.execute.side_effect = lambda st, cl: (calls.append("unequip"), unequipped)[1]
        mock_eq.return_value.is_applicable.return_value = True
        mock_eq.return_value.execute.side_effect = lambda st, cl: (calls.append("equip"), equipped)[1]
        action.execute(state, client)
    assert "unequip" in calls and "equip" in calls
    sleep_idx = next(i for i, c in enumerate(calls) if c.startswith("sleep"))
    assert calls.index("unequip") < sleep_idx < calls.index("equip"), calls
    assert mock_sleep.called
