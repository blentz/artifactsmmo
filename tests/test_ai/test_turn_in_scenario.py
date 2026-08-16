"""Task 8: the whole fleet-currency-turn-in chain, proved end to end.

Five characters wear `lich_race_medal` artifacts that double as the currency
for `lich_race_trophy` (price 10). Nobody is ever told to stop wearing
medals; the fleet still converts them. This is the scenario the earlier
tasks (dual-role recognition, the holdings ledger, the readiness core, the
exclusive buyer claim, `SelectionContext.turn_in`/`.recall`, the two goals,
and the re-equip reservation) were all built to make true, run for real
through `GamePlayer._resolve_turn_in` and `_decide_band` rather than through
any one component in isolation.

`lich_race_trophy` is level 20, so only a level-20+ character can ever
qualify as a candidate buyer (`medal_game_data`'s `lich_race_medal` is level
10, wearable well below that) — `_resolve_turn_in`'s rule 4 filters out
anything lower BEFORE it ever consults `claim_turn_in` / `turn_in_holder`, so
a below-level character never even learns an election exists (pinned by
`test_player_turn_in.py::test_a_character_below_the_item_level_does_not_
claim_the_turn_in`). Both Robby and HAL are level-20+ here and so both
independently qualify; Robby resolves first and wins the exclusive claim,
HAL loses and is handed the recall instead — the CONTROLLER RULING this
scenario exercises: a non-buyer surrenders its WHOLE holding, worn and
carried. HAL's plan must start by unequipping the medal it wears, not merely
depositing what it carries.
"""

from datetime import datetime, timezone

from artifactsmmo_cli.ai.goals.currency_turnin import CurrencyTurnInGoal
from artifactsmmo_cli.ai.goals.surrender_currency import SurrenderCurrencyGoal
from artifactsmmo_cli.ai.learning.coordination_store import CoordinationStore
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_dual_role_fixtures import medal_game_data

NOW = datetime.now(timezone.utc)
"""Computed once at import time, not a fixed calendar stamp: `publish_holdings`
rows expire `DEMAND_TTL_SECONDS` after the `now` passed to it, so a hardcoded
past timestamp goes stale before `_resolve_turn_in`'s own `datetime.now(utc)`
read ever sees it (same rationale as `test_player_turn_in.py`'s `NOW`)."""


def _bank_gd():
    """`medal_game_data()` sets no map data at all, fine for the currency-side
    resolution tests it exists for, but `_build_actions` (the factory) always
    resolves `game_data.bank_location()` up front and raises when no bank
    tile is known — a real live catalog always has one. Give it an
    unconditional bank tile so `_decide_band` can plan for real, following
    the same copy-don't-edit-the-shared-fixture precedent
    `test_turn_in_no_livelock.py`'s `_wearable_medal_game_data` set."""
    gd = medal_game_data()
    gd.world.bank_tile = (4, 1)
    gd.world.bank_tile_open = True
    gd.world.taskmaster_tile = (5, 1)
    gd.world.npc_tiles["archaeologist"] = (6, 1)
    gd._bank_capacity = 50
    return gd


def _player(db: str, name: str, state: WorldState) -> GamePlayer:
    player = GamePlayer(character=name)
    player._coordination = CoordinationStore(db_path=db, character=name)
    player.seed_offline(state, _bank_gd())
    return player


def test_five_characters_wearing_ten_medals_reach_the_trophy(tmp_path):
    """The whole point, end to end: nobody is told to stop wearing medals, and
    the fleet still converts them.

    Robby (level 27, the only character that can wear a level-20 trophy) is
    elected; HAL and R2D2 each surrender what they wear; the bank already
    holds the price outright (a snapshot of the shared account bank AFTER
    earlier surrenders landed — `CurrencyTurnInGoal`'s materialized withdraw
    is sized to the full price, not a shortfall: `test_currency_turnin_goals
    .py::test_buyer_plans_withdraw_then_purchase` pins the same precondition,
    so a bank holding less than the price is a goal with no plan, not a
    partial one)."""
    db = str(tmp_path / "coord.db")
    gd = _bank_gd()
    # Five characters, matching this module's docstring: Robby + HAL (each
    # WEARING one medal, resolved below) plus three more publishing worn
    # holdings so BOTH Robby's and HAL's own readiness check (rule 2,
    # `turn_in_ready_pure`) reaches the price from worn/carried holdings
    # ALONE — deliberately not from the bank, so HAL's own
    # `SurrenderCurrencyGoal` (satisfied whenever the bank alone already
    # holds >= its quota, regardless of who put it there) has real work left
    # to do when HAL resolves.
    for name, worn in (("R2D2", 3), ("C3P0", 3), ("BB8", 3)):
        CoordinationStore(db_path=db, character=name).publish_holdings(
            {"lich_race_medal": worn}, NOW)

    robby = _player(db, "Robby", make_state(
        level=27, hp=150, max_hp=150, equipment={"artifact1_slot": "lich_race_medal"},
        inventory={}, bank_items={"lich_race_medal": 10}))
    robby._resolve_turn_in(robby.state, gd)

    assert robby._turn_in.item_code == "lich_race_trophy"
    goal, plan, _ = robby._decide_band(robby.state, gd, robby._build_actions(), None)
    assert isinstance(goal, CurrencyTurnInGoal)
    assert plan, "the elected buyer must produce a plan, not just a goal"

    # HAL must ALSO independently qualify as a buyer candidate (level>=20,
    # `_resolve_turn_in` rules 2-4) before it ever consults `claim_turn_in` /
    # `turn_in_holder` — a character that fails those checks sees neither
    # `_turn_in` nor `_recall` change at all (`test_player_turn_in.py::
    # test_a_character_below_the_item_level_does_not_claim_the_turn_in` pins
    # this for a level-15 character). HAL here independently reaches the
    # SAME candidate Robby already claimed (own worn medal 1 + R2D2/C3P0/BB8's
    # published 9 = 10, no bank needed), loses the race (Robby resolved
    # first), and is handed the recall instead — the CONTROLLER RULING this
    # scenario exists to exercise. `bank_items={}` — FETCHED and empty, not
    # `None` ("never fetched", which `DepositItemAction.is_applicable` reads
    # via `bank_has_room` as no room at all and the surrender plan would be
    # unplannable for a different reason) — and specifically holding NONE of
    # this currency: any amount already banked would read HAL's own surrender
    # quota (its one worn medal) as satisfied before HAL does anything, and
    # there would be no plan to assert against.
    hal = _player(db, "HAL", make_state(
        level=27, hp=150, max_hp=150,
        equipment={"artifact1_slot": "lich_race_medal"}, inventory={},
        bank_items={}))
    hal._resolve_turn_in(hal.state, gd)
    assert hal._turn_in is not None and hal._turn_in.buyer == "Robby"
    hal_goal, hal_plan, _ = hal._decide_band(hal.state, gd, hal._build_actions(), None)

    assert isinstance(hal_goal, SurrenderCurrencyGoal)
    assert repr(hal_plan[0]) == "Unequip(artifact1_slot)"


def test_the_buyer_snapshot_carries_the_turn_in_block_with_role_buyer(tmp_path):
    """`_notify_observer`'s `CycleSnapshot.turn_in` is the trace surface this
    task adds: the elected buyer's snapshot must carry the resolved turn-in
    with `role: "buyer"`."""
    db = str(tmp_path / "coord.db")
    gd = medal_game_data()
    for name, worn in (("HAL", 3), ("R2D2", 3)):
        CoordinationStore(db_path=db, character=name).publish_holdings(
            {"lich_race_medal": worn}, NOW)

    robby = _player(db, "Robby", make_state(
        level=27, equipment={"artifact1_slot": "lich_race_medal"},
        inventory={}, bank_items={"lich_race_medal": 3}))
    robby._resolve_turn_in(robby.state, gd)

    seen: list = []
    robby._cycle_observer = seen.append
    robby._notify_observer("CurrencyTurnIn(lich_race_trophy)", "Buy()", "ok", [])

    snap = seen[0]
    assert snap.turn_in == {
        "item": "lich_race_trophy",
        "currency": "lich_race_medal",
        "price": 10,
        "fleet_total": 10,
        "buyer": "Robby",
        "role": "buyer",
    }


def test_the_holder_snapshot_carries_the_turn_in_block_with_role_holder(tmp_path):
    """The losing candidate's snapshot names the SAME turn-in, but with
    `role: "holder"` — a trace reader must be able to tell buyer from holder
    without cross-referencing the character name against another record."""
    db = str(tmp_path / "coord.db")
    gd = medal_game_data()
    for name, worn in (("HAL", 3), ("R2D2", 3)):
        CoordinationStore(db_path=db, character=name).publish_holdings(
            {"lich_race_medal": worn}, NOW)

    robby = _player(db, "Robby", make_state(
        level=27, equipment={"artifact1_slot": "lich_race_medal"},
        inventory={}, bank_items={"lich_race_medal": 3}))
    robby._resolve_turn_in(robby.state, gd)

    # HAL must independently qualify as a buyer candidate (level>=20; rule 2
    # readiness) before it ever consults `claim_turn_in`/`turn_in_holder` —
    # see the main scenario test's comment for the full reasoning. Only the
    # readiness math matters here (no plan is built in this test), so
    # `bank_items` is set generously rather than reasoned about precisely.
    hal = _player(db, "HAL", make_state(
        level=27, equipment={"artifact1_slot": "lich_race_medal"}, inventory={},
        bank_items={"lich_race_medal": 10}))
    hal._resolve_turn_in(hal.state, gd)

    seen: list = []
    hal._cycle_observer = seen.append
    hal._notify_observer("SurrenderCurrency(lich_race_medal)", "Unequip()", "ok", [])

    snap = seen[0]
    assert snap.turn_in is not None
    assert snap.turn_in["role"] == "holder"
    assert snap.turn_in["buyer"] == "Robby"


def test_an_uninvolved_character_snapshot_carries_turn_in_none(tmp_path):
    """Emitted on EVERY character, including the uninvolved ones (as None),
    so a trace reader can tell "no turn-in was possible" apart from "this
    child never looked" — same distinction `supply_target` already draws."""
    db = str(tmp_path / "coord.db")
    lonely = _player(db, "Lonely", make_state(level=5, inventory={}))
    lonely._resolve_turn_in(lonely.state, medal_game_data())

    seen: list = []
    lonely._cycle_observer = seen.append
    lonely._notify_observer("Idle()", "Move()", "ok", [])

    snap = seen[0]
    assert snap.turn_in is None
