"""`DepositAllAction.execute` must bank a trip's codes in BATCHES, not one call
per code.

Live Robby 2026-09-13, `learning.db`: `DepositAllAction` carried a 2.07%
`error:cooldown` rate over 1404 executions — 18x `FightAction`'s 0.114% and the
worst of any action class. The failed rows all show items already gone from the
bag (`delta_inv_used` -1 to -29) alongside ~1.5s of cooldown remaining, i.e. the
FIRST deposit succeeded and minted the server's per-action cooldown and the
SECOND call, issued ~1.5s later with no wait, came back HTTP 499.

`/my/{name}/action/bank/deposit/item` takes a LIST body (`openapi.json`:
`min_items: 1, max_items: 20`), so a trip of <=20 codes is ONE request and ONE
cooldown. Only a trip wider than the server's cap needs a second call, and that
one waits the cooldown out first — the `MoveAction` composite-action idiom.

Batching is what makes this cheap rather than merely correct: the per-IP request
budget is the fleet's binding constraint, and a 21-code trip went from 21
requests to 2.
"""

import json
from unittest.mock import MagicMock, patch

from artifactsmmo_api_client.types import UNSET

from artifactsmmo_cli.ai.actions.deposit_all import DEPOSIT_BATCH_MAX, DepositAllAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd(codes: list[str]) -> GameData:
    gd = GameData()
    gd._item_stats = {c: ItemStats(code=c, level=1, type_="resource") for c in codes}
    gd._npc_stock = {"merchant": {c: 5 + i for i, c in enumerate(codes)}}
    gd._monster_level = {"chicken": 1}
    gd._bank_capacity = 200
    return gd


def _char_schema():
    """Minimal mock CharacterSchema, parked at the bank with no cooldown."""
    char = MagicMock()
    char.name = "testchar"
    char.level = 5
    char.xp = 0
    char.max_xp = 500
    char.hp = 100
    char.max_hp = 150
    char.gold = 50
    char.x = 4
    char.y = 0
    char.inventory_max_items = 200
    char.inventory = UNSET
    char.cooldown_expiration = UNSET
    char.task = ""
    char.task_type = ""
    char.task_progress = 0
    char.task_total = 0
    for slot in ["weapon_slot", "shield_slot", "helmet_slot", "body_armor_slot",
                 "leg_armor_slot", "boots_slot", "ring1_slot", "ring2_slot",
                 "amulet_slot", "artifact1_slot", "artifact2_slot", "artifact3_slot",
                 "utility1_slot", "utility2_slot", "bag_slot", "rune_slot",
                 "mining_level", "woodcutting_level", "fishing_level", "weaponcrafting_level",
                 "gearcrafting_level", "jewelrycrafting_level", "cooking_level", "alchemy_level"]:
        setattr(char, slot, 1 if "_level" in slot else "")
    return char


def _api_result():
    result = MagicMock()
    result.data = MagicMock()
    result.data.character = _char_schema()
    return result


def _setup(n_codes: int) -> tuple[DepositAllAction, object]:
    codes = [f"ore{i:02d}" for i in range(n_codes)]
    gd = _gd(codes)
    action = DepositAllAction(bank_location=(4, 0), accessible=True, game_data=gd)
    state = make_state(x=4, y=0, inventory={c: 3 for c in codes},
                       inventory_max=200, bank_items={})
    return action, state


def test_a_trip_within_the_cap_is_one_request():
    action, state = _setup(3)
    assert len(action._deposits(state)) == 3

    with patch("artifactsmmo_cli.ai.actions.deposit_all.deposit_item",
               return_value=_api_result()) as api:
        action.execute(state, MagicMock())

    assert api.call_count == 1
    body = api.call_args.kwargs["body"]
    assert [(item.code, item.quantity) for item in body] == action._deposits(state)


def test_no_wait_when_a_single_request_covers_the_trip():
    """The cooldown a deposit sets is the PLAYER LOOP's to sleep out. Waiting
    inside `execute` after the last batch would bill the same cooldown twice."""
    action, state = _setup(3)

    with patch("artifactsmmo_cli.ai.actions.deposit_all.deposit_item",
               return_value=_api_result()):
        with patch("artifactsmmo_cli.ai.actions.deposit_all.wait_out_cooldown") as wait:
            action.execute(state, MagicMock())

    wait.assert_not_called()


def test_a_trip_wider_than_the_cap_splits_into_capped_batches():
    n = DEPOSIT_BATCH_MAX + 5
    action, state = _setup(n)
    expected = action._deposits(state)
    assert len(expected) == n

    with patch("artifactsmmo_cli.ai.actions.deposit_all.deposit_item",
               return_value=_api_result()) as api:
        with patch("artifactsmmo_cli.ai.actions.deposit_all.wait_out_cooldown"):
            action.execute(state, MagicMock())

    assert api.call_count == 2
    sent = [[(i.code, i.quantity) for i in call.kwargs["body"]] for call in api.call_args_list]
    assert [len(batch) for batch in sent] == [DEPOSIT_BATCH_MAX, 5]
    assert [item for batch in sent for item in batch] == expected


def test_the_cooldown_is_waited_out_between_batches_but_not_after_the_last():
    """One wait for two batches: before batch 2, never after batch 2."""
    action, state = _setup(DEPOSIT_BATCH_MAX + 5)

    with patch("artifactsmmo_cli.ai.actions.deposit_all.deposit_item",
               return_value=_api_result()):
        with patch("artifactsmmo_cli.ai.actions.deposit_all.wait_out_cooldown") as wait:
            action.execute(state, MagicMock())

    assert wait.call_count == 1


def test_the_batch_cap_matches_the_published_server_limit():
    """`openapi.json` declares `max_items: 20` on the deposit request body. A
    batch over it is a 422 the planner cannot see coming."""
    with open("openapi.json", encoding="utf-8") as fp:
        spec = json.load(fp)
    body = (spec["paths"]["/my/{name}/action/bank/deposit/item"]["post"]
            ["requestBody"]["content"]["application/json"]["schema"])
    assert body["max_items"] == DEPOSIT_BATCH_MAX
