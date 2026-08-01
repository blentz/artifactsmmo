"""Tests for the coordination tables: RoleLease and MaterialDemand."""

from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session as SqlSession
from sqlmodel import SQLModel, create_engine, select

from artifactsmmo_cli.ai.learning.models import MaterialDemand, RoleLease


@pytest.fixture(name="engine")
def _engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'coord.db'}")
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_role_is_unique(engine) -> None:
    with SqlSession(engine) as s:
        s.add(RoleLease(role="miner", character="HAL",
                        claimed_at="2026-08-01T00:00:00+00:00",
                        expires_at="2026-08-01T00:10:00+00:00"))
        s.commit()
    with SqlSession(engine) as s:
        s.add(RoleLease(role="miner", character="C3P0",
                        claimed_at="2026-08-01T00:00:00+00:00",
                        expires_at="2026-08-01T00:10:00+00:00"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_material_demand_roundtrip(engine) -> None:
    with SqlSession(engine) as s:
        s.add(MaterialDemand(character="HAL", item_code="copper_bar", quantity=6,
                             expires_at="2026-08-01T00:10:00+00:00"))
        s.commit()
    with SqlSession(engine) as s:
        row = s.exec(select(MaterialDemand)).one()
        assert (row.character, row.item_code, row.quantity) == ("HAL", "copper_bar", 6)


def test_role_lease_minimal_construction() -> None:
    """Direct construction with all required fields, no persistence."""
    lease = RoleLease(
        role="miner",
        character="HAL",
        claimed_at="2026-08-01T00:00:00+00:00",
        expires_at="2026-08-01T00:10:00+00:00",
    )
    assert lease.id is None
    assert lease.role == "miner"
    assert lease.character == "HAL"


def test_material_demand_minimal_construction() -> None:
    """Direct construction with all required fields, no persistence."""
    demand = MaterialDemand(
        character="HAL",
        item_code="copper_bar",
        quantity=6,
        expires_at="2026-08-01T00:10:00+00:00",
    )
    assert demand.id is None
    assert demand.character == "HAL"
    assert demand.item_code == "copper_bar"
    assert demand.quantity == 6


def test_multiple_distinct_roles_allowed(engine) -> None:
    """Two different roles held by different characters is not a conflict —
    only a duplicate `role` value triggers the UNIQUE constraint."""
    with SqlSession(engine) as s:
        s.add(RoleLease(role="miner", character="HAL",
                        claimed_at="2026-08-01T00:00:00+00:00",
                        expires_at="2026-08-01T00:10:00+00:00"))
        s.add(RoleLease(role="woodcutter", character="C3P0",
                        claimed_at="2026-08-01T00:00:00+00:00",
                        expires_at="2026-08-01T00:10:00+00:00"))
        s.commit()
    with SqlSession(engine) as s:
        rows = s.exec(select(RoleLease)).all()
        assert {row.role for row in rows} == {"miner", "woodcutter"}


def test_material_demand_allows_same_item_for_multiple_characters(engine) -> None:
    """MaterialDemand has no uniqueness constraint (unlike RoleLease): two
    characters can both declare demand for the same item_code."""
    with SqlSession(engine) as s:
        s.add(MaterialDemand(character="HAL", item_code="copper_bar", quantity=6,
                             expires_at="2026-08-01T00:10:00+00:00"))
        s.add(MaterialDemand(character="C3P0", item_code="copper_bar", quantity=3,
                             expires_at="2026-08-01T00:10:00+00:00"))
        s.commit()
    with SqlSession(engine) as s:
        rows = s.exec(select(MaterialDemand)).all()
        assert {(row.character, row.quantity) for row in rows} == {("HAL", 6), ("C3P0", 3)}
