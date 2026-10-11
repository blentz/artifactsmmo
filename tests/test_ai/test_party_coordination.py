"""Party cards and party leases in the coordination store
(docs/PLAN_group_fights.md increment 4a)."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlmodel import Session as SqlSession
from sqlmodel import create_engine

from artifactsmmo_cli.ai.learning.coordination_store import (
    DEMAND_TTL_SECONDS,
    PARTY_LEASE_TTL_SECONDS,
    CoordinationStore,
)
from artifactsmmo_cli.ai.learning.models import PartyLeaseRow
from artifactsmmo_cli.ai.party_card import card_json, card_state
from artifactsmmo_cli.ai.party_lease_core import PartyLease, assembled, on_tile, ready
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_coordination_store import _break_engine

T0 = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
TILE = ("overworld", 3, -1)


def _stores(tmp_path: Path, *names: str) -> list[CoordinationStore]:
    db = str(tmp_path / "coord.db")
    return [CoordinationStore(db_path=db, character=n) for n in names]


def test_a_card_round_trips_what_a_party_fight_reads() -> None:
    state = make_state(character="Lor", level=32, hp=446, max_hp=705, x=3, y=-1,
                       attack={"fire": 40}, resistance={"water": 21}, dmg=33,
                       dmg_elements={"fire": 46}, critical_strike=15, initiative=275,
                       equipment={"weapon_slot": "elderwood_staff"}, inventory={"rat_hide": 6},
                       cooldown_expires=T0, bank_items={"small_health_potion": 4})
    state = replace(state, wisdom=25, prospecting=75, utility1_slot_quantity=3, layer="overworld")
    back = card_state(card_json(state))
    for name in ("character", "level", "hp", "max_hp", "gold", "skills", "x", "y", "layer",
                 "inventory", "inventory_max", "inventory_slots_max", "equipment",
                 "cooldown_expires", "bank_items", "wisdom", "prospecting", "attack", "dmg",
                 "dmg_elements", "resistance", "critical_strike", "initiative",
                 "utility1_slot_quantity", "utility2_slot_quantity"):
        assert getattr(back, name) == getattr(state, name), name
    assert card_state(card_json(replace(state, cooldown_expires=None))).cooldown_expires is None


def test_siblings_read_each_others_live_cards(tmp_path: Path) -> None:
    hal, lor = _stores(tmp_path, "HAL", "Lor")
    hal.publish_party_card(card_json(make_state(character="HAL")), T0)
    lor.publish_party_card(card_json(make_state(character="Lor", level=3)), T0)
    lor.publish_party_card(card_json(make_state(character="Lor", level=4)), T0)  # replaced
    assert [card_state(c).level for c in hal.sibling_party_cards(T0)] == [4]
    assert [card_state(c).character for c in lor.sibling_party_cards(T0)] == ["HAL"]
    assert hal.sibling_party_cards(T0 + timedelta(seconds=DEMAND_TTL_SECONDS)) == []


def test_one_party_per_boss_and_per_character(tmp_path: Path) -> None:
    hal, lor, r2 = _stores(tmp_path, "HAL", "Lor", "R2D2")
    assert hal.claim_party("duskworm", ("Lor",), TILE, T0)
    # the boss is HAL's; HAL renews it with other members
    assert not r2.claim_party("duskworm", ("C3P0",), TILE, T0)
    assert hal.claim_party("duskworm", ("Lor", "R2D2"), TILE, T0)
    # Lor and R2D2 are taken: no other lease may name them
    assert not r2.claim_party("lich", ("C3P0",), TILE, T0)
    assert not lor.claim_party("lich", (), TILE, T0)
    lease = PartyLease("duskworm", "HAL", ("Lor", "R2D2"), *TILE)
    assert hal.party_lease_for(T0) == lease == lor.party_lease_for(T0) == r2.party_lease_for(T0)


def test_a_lease_expires_and_is_released_only_by_its_leader(tmp_path: Path) -> None:
    hal, lor, r2 = _stores(tmp_path, "HAL", "Lor", "R2D2")
    assert hal.claim_party("duskworm", ("Lor",), TILE, T0)
    later = T0 + timedelta(seconds=PARTY_LEASE_TTL_SECONDS)
    assert lor.party_lease_for(later) is None
    assert r2.claim_party("duskworm", ("Lor",), TILE, later)  # the expired row taken over
    hal.release_party("duskworm")  # not HAL's any more: no-op
    assert lor.party_lease_for(later) == PartyLease("duskworm", "R2D2", ("Lor",), *TILE)
    r2.release_party("duskworm")
    assert lor.party_lease_for(later) is None
    r2.release_party("duskworm")  # nothing left: no-op


def test_a_rival_inserting_first_wins_the_boss(tmp_path: Path) -> None:
    """Two leaders read "no lease for duskworm"; the rival's insert lands
    first, so UNIQUE(boss) fails HAL's commit and the claim reports False."""
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    rival = create_engine(f"sqlite:///{db}")

    def _rival_first(session, flush_context, instances) -> None:  # type: ignore[no-untyped-def]
        with SqlSession(rival) as s:
            s.add(PartyLeaseRow(boss="duskworm", leader="R2D2", members="Lor",
                                layer="overworld", x=3, y=-1, claimed_at=T0.isoformat(),
                                expires_at=(T0 + timedelta(seconds=60)).isoformat()))
            s.commit()

    event.listen(SqlSession, "before_flush", _rival_first, once=True)
    try:
        assert hal.claim_party("duskworm", ("Lor",), TILE, T0) is False
    finally:
        if event.contains(SqlSession, "before_flush", _rival_first):
            event.remove(SqlSession, "before_flush", _rival_first)
        rival.dispose()
        hal.close()


def test_every_party_call_degrades_on_a_broken_store(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    (hal,) = _stores(tmp_path, "HAL")
    _break_engine(hal)
    hal.publish_party_card("{}", T0)
    assert hal.sibling_party_cards(T0) == []
    assert hal.claim_party("duskworm", (), TILE, T0) is False
    assert hal.party_lease_for(T0) is None
    hal.release_party("duskworm")
    out = capsys.readouterr().out
    for name in ("publish_party_card", "sibling_party_cards", "claim_party", "party_lease_for",
                 "release_party"):
        assert f"[coordination] {name} failed" in out


def test_naive_now_is_refused(tmp_path: Path) -> None:
    (hal,) = _stores(tmp_path, "HAL")
    with pytest.raises(ValueError):
        hal.claim_party("duskworm", (), TILE, datetime(2026, 10, 11))


def test_assembled_means_every_member_ready_on_the_tile() -> None:
    lease = PartyLease("duskworm", "HAL", ("Lor", "R2D2"), *TILE)
    here = make_state(character="Lor", x=3, y=-1)
    assert on_tile(here, lease) and not on_tile(replace(here, layer="underground"), lease)
    assert ready(here, lease, T0) and ready(replace(here, cooldown_expires=T0), lease, T0)
    assert not ready(replace(here, cooldown_expires=T0 + timedelta(seconds=1)), lease, T0)
    assert not ready(replace(here, x=4), lease, T0)
    r2 = replace(here, character="R2D2")
    assert assembled(lease, {"Lor": here, "R2D2": r2}, T0)
    assert not assembled(lease, {"Lor": here}, T0)
    assert not assembled(lease, {"Lor": here, "R2D2": replace(r2, y=0)}, T0)
