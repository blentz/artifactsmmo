"""Tests for the coordination tables: RoleLease and MaterialDemand, and the
CoordinationStore that operates on RoleLease."""

import multiprocessing
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session as SqlSession
from sqlmodel import SQLModel, create_engine, select

from artifactsmmo_cli.ai.learning.coordination_store import (
    LEASE_TTL_SECONDS,
    CoordinationStore,
    _require_utc,
)
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


_T0 = datetime(2026, 8, 1, tzinfo=timezone.utc)


def test_claim_succeeds_then_blocks_other_character(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    c3po = CoordinationStore(db_path=db, character="C3P0")
    try:
        assert hal.claim("miner", _T0) is True
        assert c3po.claim("miner", _T0) is False
        assert hal.live_leases(_T0) == {"miner": "HAL"}
    finally:
        hal.close()
        c3po.close()


def test_expired_lease_is_not_live_and_can_be_reclaimed(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    c3po = CoordinationStore(db_path=db, character="C3P0")
    later = _T0 + timedelta(seconds=LEASE_TTL_SECONDS + 1)
    try:
        assert hal.claim("miner", _T0) is True
        assert hal.live_leases(later) == {}
        assert c3po.claim("miner", later) is True
        assert c3po.live_leases(later) == {"miner": "C3P0"}
    finally:
        hal.close()
        c3po.close()


def test_renew_extends_expiry(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    mid = _T0 + timedelta(seconds=LEASE_TTL_SECONDS - 1)
    later = _T0 + timedelta(seconds=LEASE_TTL_SECONDS + 1)
    try:
        assert hal.claim("miner", _T0) is True
        hal.renew("miner", mid)
        assert hal.live_leases(later) == {"miner": "HAL"}
    finally:
        hal.close()


def test_release_frees_the_role(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    try:
        assert hal.claim("miner", _T0) is True
        hal.release("miner")
        assert hal.live_leases(_T0) == {}
    finally:
        hal.close()


def test_reclaiming_own_live_lease_is_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    try:
        assert hal.claim("miner", _T0) is True
        assert hal.claim("miner", _T0) is True
    finally:
        hal.close()


def test_character_property_returns_constructor_value(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    try:
        assert hal.character == "HAL"
    finally:
        hal.close()


def test_renew_is_noop_when_character_holds_no_lease(tmp_path: Path) -> None:
    """`renew` on a role this character never claimed touches nothing and
    raises nothing."""
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    try:
        hal.renew("miner", _T0)
        assert hal.live_leases(_T0) == {}
    finally:
        hal.close()


def test_release_is_noop_when_character_holds_no_lease(tmp_path: Path) -> None:
    """`release` on a role this character never claimed touches nothing and
    raises nothing."""
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    c3po = CoordinationStore(db_path=db, character="C3P0")
    try:
        assert c3po.claim("miner", _T0) is True
        hal.release("miner")
        assert hal.live_leases(_T0) == {"miner": "C3P0"}
    finally:
        hal.close()
        c3po.close()


def _break_engine(store: CoordinationStore) -> None:
    """Swap in a real engine whose SQLite URL points at a directory, so every
    SqlSession query against it raises OperationalError (a SQLAlchemyError).

    Mirrors `test_learning_store.py::_break_engine`: a genuine DB-layer fault
    (not a mock of the unit under test) that exercises the documented
    best-effort degradation contract.
    """
    bad_dir = tempfile.mkdtemp()
    store._engine = create_engine(f"sqlite:///{bad_dir}")


class TestDegradationOnDbError:
    """Every CoordinationStore method must swallow SQLAlchemyError and return
    its documented default, matching LearningStore's best-effort contract."""

    def test_claim_swallows_error_and_returns_false(self, tmp_path: Path, capsys) -> None:
        db = str(tmp_path / "coord.db")
        hal = CoordinationStore(db_path=db, character="HAL")
        _break_engine(hal)
        assert hal.claim("miner", _T0) is False
        assert "[coordination] claim failed" in capsys.readouterr().out

    def test_renew_swallows_error(self, tmp_path: Path, capsys) -> None:
        db = str(tmp_path / "coord.db")
        hal = CoordinationStore(db_path=db, character="HAL")
        assert hal.claim("miner", _T0) is True
        _break_engine(hal)
        hal.renew("miner", _T0)
        assert "[coordination] renew failed" in capsys.readouterr().out

    def test_release_swallows_error(self, tmp_path: Path, capsys) -> None:
        db = str(tmp_path / "coord.db")
        hal = CoordinationStore(db_path=db, character="HAL")
        assert hal.claim("miner", _T0) is True
        _break_engine(hal)
        hal.release("miner")
        assert "[coordination] release failed" in capsys.readouterr().out

    def test_live_leases_swallows_error_and_returns_empty(self, tmp_path: Path, capsys) -> None:
        db = str(tmp_path / "coord.db")
        hal = CoordinationStore(db_path=db, character="HAL")
        assert hal.claim("miner", _T0) is True
        _break_engine(hal)
        assert hal.live_leases(_T0) == {}
        assert "[coordination] live_leases failed" in capsys.readouterr().out


def test_claim_new_role_race_returns_false_on_integrity_error(tmp_path: Path) -> None:
    """Two characters both try to claim a role that neither holds yet. This
    reproduces the genuine race the docstring describes: HAL's `claim` reads
    "no row for this role" and decides to insert, but before it flushes,
    C3P0 concretely wins the row first (via a second, real engine/session on
    the same file) — so HAL's own insert collides with the real UNIQUE
    constraint and takes the `except IntegrityError` branch. This uses a real
    second connection to create genuine DB state, not a mock of the unit
    under test's return value."""
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    rival_engine = create_engine(f"sqlite:///{db}")

    def _rival_claims_first(session, flush_context, instances) -> None:
        with SqlSession(rival_engine) as rival_session:
            rival_session.add(RoleLease(
                role="miner", character="C3P0",
                claimed_at=_T0.isoformat(),
                expires_at=(_T0 + timedelta(seconds=LEASE_TTL_SECONDS)).isoformat(),
            ))
            rival_session.commit()

    # once=True: fires exactly once then self-removes. A plain event.remove()
    # called from inside the handler would mutate SQLAlchemy's listener deque
    # while it is being iterated ("deque mutated during iteration").
    event.listen(SqlSession, "before_flush", _rival_claims_first, once=True)
    try:
        assert hal.claim("miner", _T0) is False
        assert hal.live_leases(_T0) == {"miner": "C3P0"}
    finally:
        if event.contains(SqlSession, "before_flush", _rival_claims_first):
            event.remove(SqlSession, "before_flush", _rival_claims_first)
        rival_engine.dispose()
        hal.close()


# --- _require_utc: the TTL/liveness comparison's one precondition ---------

_NAIVE_NOW = datetime(2026, 8, 1)
_NON_UTC_NOW = datetime(2026, 8, 1, tzinfo=timezone(timedelta(hours=5)))


def test_require_utc_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="naive"):
        _require_utc(_NAIVE_NOW)


def test_require_utc_rejects_non_utc_offset() -> None:
    with pytest.raises(ValueError, match="offset"):
        _require_utc(_NON_UTC_NOW)


def test_require_utc_accepts_utc_aware_datetime() -> None:
    """No exception, no return value — a pure guard."""
    assert _require_utc(_T0) is None


def test_claim_rejects_naive_now(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    try:
        with pytest.raises(ValueError, match="naive"):
            hal.claim("miner", _NAIVE_NOW)
    finally:
        hal.close()


def test_claim_rejects_non_utc_offset_now(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    try:
        with pytest.raises(ValueError, match="offset"):
            hal.claim("miner", _NON_UTC_NOW)
    finally:
        hal.close()


def test_renew_rejects_naive_now(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    try:
        assert hal.claim("miner", _T0) is True
        with pytest.raises(ValueError, match="naive"):
            hal.renew("miner", _NAIVE_NOW)
    finally:
        hal.close()


def test_renew_rejects_non_utc_offset_now(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    try:
        assert hal.claim("miner", _T0) is True
        with pytest.raises(ValueError, match="offset"):
            hal.renew("miner", _NON_UTC_NOW)
    finally:
        hal.close()


def test_live_leases_rejects_naive_now(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    try:
        with pytest.raises(ValueError, match="naive"):
            hal.live_leases(_NAIVE_NOW)
    finally:
        hal.close()


def test_live_leases_rejects_non_utc_offset_now(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    try:
        with pytest.raises(ValueError, match="offset"):
            hal.live_leases(_NON_UTC_NOW)
    finally:
        hal.close()


# --- multi-process claim race: the one behaviour mocks cannot verify ------


def _claim_worker(db_path: str, character: str, role: str, barrier: object, out: object) -> None:
    """Module-level so it is picklable by multiprocessing's spawn start method.

    Waits on `barrier` AFTER the store is constructed (engine + schema +
    PRAGMAs) and BEFORE the claim, so all five children attempt `claim` at
    the same moment regardless of how long store construction took in each
    process. Without this, the children could serialize through construction
    and never actually contend for the row.
    """
    store = CoordinationStore(db_path=db_path, character=character)
    try:
        barrier.wait()
        out.put((character, store.claim(role, _T0)))
    finally:
        store.close()


def test_exactly_one_process_wins_a_contested_role(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    seed = CoordinationStore(db_path=db, character="seed")
    seed.close()  # create the schema before the children race on it

    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    names = ["HAL", "C3P0", "R2D2", "Robby", "KITT"]
    barrier = ctx.Barrier(len(names))
    procs = [
        ctx.Process(target=_claim_worker, args=(db, n, "miner", barrier, queue)) for n in names
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=30)
        assert p.exitcode == 0

    results = dict(queue.get() for _ in names)
    winners = [n for n, won in results.items() if won]
    assert len(winners) == 1

    check = CoordinationStore(db_path=db, character="observer")
    try:
        assert check.live_leases(_T0) == {"miner": winners[0]}
    finally:
        check.close()
