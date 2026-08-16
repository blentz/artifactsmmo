"""Task 8: the whole fleet-currency-turn-in chain, proved end to end.

Five characters wear `lich_race_medal` artifacts that double as the currency
for `lich_race_trophy` (price 10). Nobody is ever told to stop wearing
medals; the fleet still converts them. This is the scenario the earlier
tasks (dual-role recognition, the holdings ledger, the readiness core, the
exclusive buyer claim, `SelectionContext.turn_in`/`.recall`, the two goals,
and the re-equip reservation) were all built to make true, run for real
through `GamePlayer._resolve_turn_in` and `_decide_band` rather than through
any one component in isolation.

THE LIVE FLEET IS THE SHAPE THAT MATTERS (fix-round-3): Robby 27, C3P0 17,
R2D2 16, HAL 15, Lor 15 — every medal-wearer except Robby is BELOW the
level-20 trophy, and the shared bank starts with NO medals. The earlier
version of this scenario used two level-27 characters and a bank that already
held the whole price, so it exercised neither the below-level surrender path
(the one that makes the feature work at all) nor the account-wide bank, and
it passed cleanly against a build that livelocked on the live fleet.

`lich_race_trophy` is level 20, so only a level-20+ character can qualify as
a candidate BUYER (`medal_game_data`'s `lich_race_medal` is level 10,
wearable well below that): `_resolve_turn_in`'s rule 4 filters the others out
before the election. They are NOT left out of the turn-in — they reach it
through `_adopt_sibling_claim`, which stands a below-level holder down to a
sibling's LIVE claim (that path is why `selection_context.recall`'s "only on
a candidate buyer" wording was wrong and is now fixed).

The CONTROLLER RULING this scenario exercises: a non-buyer surrenders its
WHOLE holding, worn and carried, and it is done only when IT holds none —
never when the SHARED bank happens to hold a quota's worth, which is another
sibling's deposit and says nothing about this character.
"""

from dataclasses import replace
from datetime import datetime, timezone

from artifactsmmo_cli.ai.actions.unequip import UnequipAction
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
    """The state's `character` is forced to match the player's: goal selection
    keys the buyer role on `ctx.turn_in.buyer == state.character`
    (strategy_driver.map_means), so a state left on the fixture's default name
    would make every character look like a non-buyer."""
    player = GamePlayer(character=name)
    player._coordination = CoordinationStore(db_path=db, character=name)
    player.seed_offline(replace(state, character=name), _bank_gd())
    return player


WORN_PAIR = {"artifact1_slot": "lich_race_medal", "artifact2_slot": "lich_race_medal"}
"""Every character in the live fleet wears TWO medals (duplicate artifact
slots), so five characters hold exactly the price of one trophy and NOTHING
is in the bank to begin with — the fleet total has to come out of equipment."""


def _publish(db: str, name: str, worn: int) -> None:
    CoordinationStore(db_path=db, character=name).publish_holdings(
        {"lich_race_medal": worn} if worn else {}, NOW)


def test_the_live_fleet_of_below_level_medal_wearers_reaches_the_trophy(tmp_path):
    """The whole point, end to end, on the LIVE fleet: nobody is told to stop
    wearing medals, only Robby can wear the trophy, the other four are below
    its level, and the bank starts empty — and the fleet still converts.

    THE BUG THIS TEST EXISTS FOR (fix-round-3, CRITICAL): the second sibling.
    `state.bank_items` is the ACCOUNT bank shared by all five children, so
    once C3P0's two medals land, a `SurrenderCurrencyGoal` satisfied by "the
    bank holds >= units" reports satisfied for R2D2, HAL and Lor as well, the
    arbiter skips them, and the fleet banks `max_i(own_i)` medals instead of
    the sum — Robby's `Withdraw(8)` is never applicable, and the claim renews
    forever. R2D2 below MUST still plan its surrender against a bank that
    already holds a full quota."""
    db = str(tmp_path / "coord.db")
    gd = _bank_gd()
    fleet = (("Robby", 27), ("C3P0", 17), ("R2D2", 16), ("HAL", 15), ("Lor", 15))
    for name, _level in fleet:
        _publish(db, name, 2)

    # --- the buyer is elected, and it is the ONLY level-20+ character.
    robby = _player(db, "Robby", make_state(
        level=27, hp=150, max_hp=150, equipment=dict(WORN_PAIR),
        inventory={}, bank_items={}))
    robby._resolve_turn_in(robby.state, gd)
    assert robby._turn_in is not None
    assert robby._turn_in.item_code == "lich_race_trophy"
    assert robby._turn_in.buyer == "Robby"
    assert robby._recall is None, "the buyer never surrenders to itself"

    # --- a BELOW-level holder stands down to that claim (`_adopt_sibling_claim`)
    # and plans the surrender: unequip first, since both its medals are worn.
    c3po = _player(db, "C3P0", make_state(
        level=17, hp=150, max_hp=150, equipment=dict(WORN_PAIR),
        inventory={}, bank_items={}))
    c3po._resolve_turn_in(c3po.state, gd)
    assert c3po._turn_in is not None and c3po._turn_in.buyer == "Robby"
    assert c3po._recall == ("lich_race_medal", 2)
    c3po_goal, c3po_plan, _ = c3po._decide_band(
        c3po.state, gd, c3po._build_actions(), None)
    assert isinstance(c3po_goal, SurrenderCurrencyGoal)
    # Both worn copies come off (the two slots are interchangeable, so the
    # order between them carries no meaning), and the deposit is sized to the
    # whole holding.
    assert sorted(repr(a) for a in c3po_plan if isinstance(a, UnequipAction)) == [
        "Unequip(artifact1_slot)", "Unequip(artifact2_slot)"]
    assert repr(c3po_plan[-1]) == "DepositItem(lich_race_medal×2)"

    # --- C3P0's deposit has landed. The bank is ACCOUNT-wide, so R2D2 now
    # reads two medals in it that are not its own. It must still surrender.
    _publish(db, "C3P0", 0)
    r2d2 = _player(db, "R2D2", make_state(
        level=16, hp=150, max_hp=150, equipment=dict(WORN_PAIR),
        inventory={}, bank_items={"lich_race_medal": 2}))
    r2d2._resolve_turn_in(r2d2.state, gd)
    assert r2d2._recall == ("lich_race_medal", 2)
    r2d2_goal, r2d2_plan, _ = r2d2._decide_band(
        r2d2.state, gd, r2d2._build_actions(), None)
    assert isinstance(r2d2_goal, SurrenderCurrencyGoal), (
        "a sibling's deposit must not satisfy THIS character's surrender")
    assert sorted(repr(a) for a in r2d2_plan if isinstance(a, UnequipAction)) == [
        "Unequip(artifact1_slot)", "Unequip(artifact2_slot)"]
    assert repr(r2d2_plan[-1]) == "DepositItem(lich_race_medal×2)"

    # --- all four siblings have surrendered: bank 8, Robby still wears 2.
    for name in ("R2D2", "HAL", "Lor"):
        _publish(db, name, 0)
    robby.state = make_state(
        character="Robby", level=27, hp=150, max_hp=150,
        equipment=dict(WORN_PAIR), inventory={},
        bank_items={"lich_race_medal": 8})
    robby._resolve_turn_in(robby.state, gd)
    assert robby._turn_in is not None and robby._turn_in.buyer == "Robby"
    goal, plan, _ = robby._decide_band(robby.state, gd, robby._build_actions(), None)
    assert isinstance(goal, CurrencyTurnInGoal)
    reprs = [repr(a) for a in plan]
    # Its own two worn medals fund 2 of the 10, so the bank supplies 8 — not
    # the full price (`buyer_bank_draw_pure`).
    assert sorted(r for r in reprs if r.startswith("Unequip")) == [
        "Unequip(artifact1_slot)", "Unequip(artifact2_slot)"], reprs
    assert "Withdraw(lich_race_medal×8)" in reprs, reprs
    assert reprs[-1] == "NpcBuy(lich_race_trophy×1@archaeologist)", reprs


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
