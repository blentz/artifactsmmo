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
    DEMAND_TTL_SECONDS,
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


def test_store_creates_its_parent_directory(tmp_path: Path) -> None:
    """sqlite3 cannot create a DB inside a directory that does not exist. A
    `play --all` supervisor builds this store at the default cache path before
    anything else touches it, so on a machine that has never run with `--learn`
    the directory is genuinely absent — and the store must make it, exactly as
    LearningStore does."""
    db_path = tmp_path / "never" / "created" / "coord.db"
    assert not db_path.parent.exists()

    store = CoordinationStore(db_path=str(db_path), character="hero")
    try:
        assert store.claim("miner", datetime.now(tz=timezone.utc)) is True
    finally:
        store.close()
    assert db_path.exists()


def test_one_role_may_be_held_by_several_characters(engine) -> None:
    """`role` was UNIQUE, which made the roster a fixed five-way partition and
    forced four of five characters off the skill they were actually best at.
    Two characters on one role is now a legal, expected state."""
    with SqlSession(engine) as s:
        s.add(RoleLease(role="miner", character="HAL",
                        claimed_at="2026-08-01T00:00:00+00:00",
                        expires_at="2026-08-01T00:10:00+00:00"))
        s.add(RoleLease(role="miner", character="C3P0",
                        claimed_at="2026-08-01T00:00:00+00:00",
                        expires_at="2026-08-01T00:10:00+00:00"))
        s.commit()
    with SqlSession(engine) as s:
        rows = s.exec(select(RoleLease)).all()
        assert {row.character for row in rows} == {"HAL", "C3P0"}


def test_the_same_character_cannot_hold_one_role_twice(engine) -> None:
    """The replacement key, UNIQUE(role, character), and it is load-bearing:
    `live_leases` counts holders and `role_selection` DIVIDES a role's demand
    by that count, so a duplicated row would silently halve the demand the role
    advertises to every sibling."""
    with SqlSession(engine) as s:
        s.add(RoleLease(role="miner", character="HAL",
                        claimed_at="2026-08-01T00:00:00+00:00",
                        expires_at="2026-08-01T00:10:00+00:00"))
        s.commit()
    with SqlSession(engine) as s:
        s.add(RoleLease(role="miner", character="HAL",
                        claimed_at="2026-08-01T00:05:00+00:00",
                        expires_at="2026-08-01T00:15:00+00:00"))
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
    only a duplicate `(role, character)` pair triggers the UNIQUE constraint."""
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


def test_a_second_character_claiming_a_held_role_also_succeeds(tmp_path: Path) -> None:
    """The exclusivity removal at the store level: a sibling already holding a
    role is not an obstacle, and `live_leases` reports BOTH holders. This used
    to return False for C3P0 and report `{"miner": "HAL"}`."""
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    c3po = CoordinationStore(db_path=db, character="C3P0")
    try:
        assert hal.claim("miner", _T0) is True
        assert c3po.claim("miner", _T0) is True
        assert hal.live_leases(_T0) == {"miner": frozenset({"HAL", "C3P0"})}
    finally:
        hal.close()
        c3po.close()


def test_three_characters_can_hold_the_same_role_simultaneously(tmp_path: Path) -> None:
    """The owner's requirement, stated literally: "there may be times we need
    zero alchemists and three woodcutters"."""
    db = str(tmp_path / "coord.db")
    stores = [CoordinationStore(db_path=db, character=n)
              for n in ("HAL", "C3P0", "R2D2")]
    try:
        for store in stores:
            assert store.claim("logger", _T0) is True
        assert stores[0].live_leases(_T0) == {
            "logger": frozenset({"HAL", "C3P0", "R2D2"})}
    finally:
        for store in stores:
            store.close()


def test_a_role_nobody_claimed_is_absent_from_live_leases(tmp_path: Path) -> None:
    """Absent, never an empty set: "unobserved" and "observed to be zero" are
    the same fact here, and `.get(role, frozenset())` is the one read idiom."""
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    try:
        assert hal.claim("miner", _T0) is True
        assert "logger" not in hal.live_leases(_T0)
    finally:
        hal.close()


def test_expired_lease_is_not_live_and_can_be_reclaimed(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    c3po = CoordinationStore(db_path=db, character="C3P0")
    later = _T0 + timedelta(seconds=LEASE_TTL_SECONDS + 1)
    try:
        assert hal.claim("miner", _T0) is True
        assert hal.live_leases(later) == {}
        assert c3po.claim("miner", later) is True
        assert c3po.live_leases(later) == {"miner": frozenset({"C3P0"})}
    finally:
        hal.close()
        c3po.close()


def test_reclaiming_an_expired_own_lease_reuses_the_row(tmp_path: Path) -> None:
    """`claim` on a role this character already has a (lapsed) row for must
    UPDATE that row, not insert a second one — the UNIQUE(role, character) key
    would reject the insert, and a duplicate would corrupt the holder count."""
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    later = _T0 + timedelta(seconds=LEASE_TTL_SECONDS + 1)
    try:
        assert hal.claim("miner", _T0) is True
        assert hal.claim("miner", later) is True
        assert hal.live_leases(later) == {"miner": frozenset({"HAL"})}
    finally:
        hal.close()
    engine = create_engine(f"sqlite:///{db}")
    try:
        with SqlSession(engine) as s:
            rows = s.exec(select(RoleLease)).all()
            assert len(rows) == 1
            assert rows[0].claimed_at == later.isoformat()
    finally:
        engine.dispose()


def test_renew_extends_expiry(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    mid = _T0 + timedelta(seconds=LEASE_TTL_SECONDS - 1)
    later = _T0 + timedelta(seconds=LEASE_TTL_SECONDS + 1)
    try:
        assert hal.claim("miner", _T0) is True
        hal.renew("miner", mid)
        assert hal.live_leases(later) == {"miner": frozenset({"HAL"})}
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


def test_release_drops_only_the_releasing_characters_row(tmp_path: Path) -> None:
    """With several holders, `release` must remove exactly one of them — it
    filters on `character`, and a release that dropped every row for the role
    would evict siblings that never asked to leave."""
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    c3po = CoordinationStore(db_path=db, character="C3P0")
    try:
        assert hal.claim("miner", _T0) is True
        assert c3po.claim("miner", _T0) is True
        hal.release("miner")
        assert hal.live_leases(_T0) == {"miner": frozenset({"C3P0"})}
    finally:
        hal.close()
        c3po.close()


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
        assert hal.live_leases(_T0) == {"miner": frozenset({"C3P0"})}
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

    def test_publish_demand_swallows_error(self, tmp_path: Path, capsys) -> None:
        db = str(tmp_path / "coord.db")
        hal = CoordinationStore(db_path=db, character="HAL")
        _break_engine(hal)
        hal.publish_demand({"copper_bar": 6}, _T0)
        assert "[coordination] publish_demand failed" in capsys.readouterr().out

    def test_sibling_demand_swallows_error_and_returns_empty(self, tmp_path: Path, capsys) -> None:
        db = str(tmp_path / "coord.db")
        hal = CoordinationStore(db_path=db, character="HAL")
        _break_engine(hal)
        assert hal.sibling_demand(_T0) == {}
        assert "[coordination] sibling_demand failed" in capsys.readouterr().out


def test_a_rival_taking_the_role_mid_claim_does_not_fail_the_claim(tmp_path: Path) -> None:
    """The race that USED to be decisive, now proven benign.

    HAL's `claim` reads "no row for me on this role" and decides to insert;
    before it flushes, C3P0 concretely takes the role first (a second, real
    engine/session on the same file). Under UNIQUE(`role`) that collided and
    HAL lost the role. Under UNIQUE(`role`, `character`) the two writes are to
    different rows: HAL's insert lands, and BOTH characters hold `miner`.

    This is why `claim` no longer carries an `except IntegrityError` branch —
    there is no interleaving of two DIFFERENT characters' claims that can
    violate the new key. A real second connection creating genuine DB state,
    not a mock of the unit under test.
    """
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
        assert hal.claim("miner", _T0) is True
        assert hal.live_leases(_T0) == {"miner": frozenset({"HAL", "C3P0"})}
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


def _construct_worker(db_path: str, character: str, barrier: object, out: object) -> None:
    """Module-level so it is picklable by multiprocessing's spawn start method.

    Waits on `barrier` BEFORE the store is constructed, so every child runs
    `SQLModel.metadata.create_all` against the SAME empty file at the same
    moment. Nothing is caught here: a store that cannot survive a concurrent
    sibling must surface as a non-zero exit code, exactly as it did in
    production (the child process died).
    """
    barrier.wait()
    store = CoordinationStore(db_path=db_path, character=character)
    try:
        out.put(character)
    finally:
        store.close()


def test_concurrent_first_open_of_an_unseeded_db_creates_the_schema_once(tmp_path: Path) -> None:
    """The PRODUCTION shape: five siblings open a coordination DB that does not
    exist yet, within about a second of each other, and nothing has created the
    schema for them.

    A live `play --all` run killed a child with
    `OperationalError: table role_leases already exists`: SQLAlchemy's
    `checkfirst` probe and the `CREATE TABLE` it decides to issue are not
    atomic across processes, so a loser of that race raised. The sibling
    `test_exactly_one_process_wins_a_contested_role` cannot catch this — it
    seeds the schema first and only races on `claim`. The fix is
    `MultiRun._seed_coordination_schema`, which makes the supervisor create the
    schema once before any child exists; this test pins the store-level
    contract that the concurrent-open itself must not kill a child.
    """
    db = str(tmp_path / "coord.db")
    assert not Path(db).exists()

    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    names = ["HAL", "C3P0", "R2D2", "Robby", "KITT"]
    barrier = ctx.Barrier(len(names))
    procs = [ctx.Process(target=_construct_worker, args=(db, n, barrier, queue)) for n in names]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=30)
        assert p.exitcode == 0, f"a child died opening the unseeded coordination DB: {p.exitcode}"

    assert sorted(queue.get() for _ in names) == sorted(names)

    check = CoordinationStore(db_path=db, character="observer")
    try:
        assert check.claim("miner", _T0) is True
    finally:
        check.close()


def test_every_process_claiming_one_role_is_recorded_exactly_once(tmp_path: Path) -> None:
    """Replaces `test_exactly_one_process_wins_a_contested_role`.

    "Exactly one winner" was the property EXCLUSIVITY bought, and it is gone on
    purpose — it is the mechanism that stranded four of five characters on
    skills they had not trained. What matters now is that the lease table is a
    correct multi-holder registry under real concurrency, and that is three
    facts, none of which the old test could have caught:

      * nobody loses — all five `claim` calls return True, so no character is
        silently pushed to a second-choice role by scheduling order;
      * nobody is dropped — `live_leases` names all five, because a holder
        missing from the count would make the role look emptier than it is and
        recruit yet another sibling;
      * nobody is doubled — exactly five ROWS, because `role_selection` divides
        this role's demand by the holder count, and a duplicate row would halve
        the demand the role advertises to the whole fleet.

    Five real spawned processes on one SQLite file: the interleaving is the
    thing under test, so it cannot be simulated in-process.
    """
    db = str(tmp_path / "coord.db")
    # Seeded on purpose: this test isolates the CLAIM race, so the schema must
    # already exist when the children start. The unseeded case — five siblings
    # racing on `create_all` itself, which is what production does — is covered
    # by `test_concurrent_first_open_of_an_unseeded_db_creates_the_schema_once`
    # above, and by MultiRun's supervisor-seeding tests.
    seed = CoordinationStore(db_path=db, character="seed")
    seed.close()

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
    assert results == {n: True for n in names}

    check = CoordinationStore(db_path=db, character="observer")
    try:
        assert check.live_leases(_T0) == {"miner": frozenset(names)}
    finally:
        check.close()

    engine = create_engine(f"sqlite:///{db}")
    try:
        with SqlSession(engine) as s:
            assert len(s.exec(select(RoleLease)).all()) == len(names)
    finally:
        engine.dispose()


# --- demand board -----------------------------------------------------------


def test_sibling_demand_sums_across_characters_and_excludes_self(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    c3po = CoordinationStore(db_path=db, character="C3P0")
    try:
        hal.publish_demand({"copper_bar": 6, "ash_plank": 2}, _T0)
        c3po.publish_demand({"copper_bar": 4}, _T0)
        assert hal.sibling_demand(_T0) == {"copper_bar": 4}
        assert c3po.sibling_demand(_T0) == {"copper_bar": 6, "ash_plank": 2}
    finally:
        hal.close()
        c3po.close()


def test_publish_demand_replaces_prior_rows(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    obs = CoordinationStore(db_path=db, character="observer")
    try:
        hal.publish_demand({"copper_bar": 6, "ash_plank": 2}, _T0)
        hal.publish_demand({"copper_bar": 1}, _T0)
        assert obs.sibling_demand(_T0) == {"copper_bar": 1}
    finally:
        hal.close()
        obs.close()


def test_expired_demand_is_not_served(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    obs = CoordinationStore(db_path=db, character="observer")
    later = _T0 + timedelta(seconds=DEMAND_TTL_SECONDS + 1)
    try:
        hal.publish_demand({"copper_bar": 6}, _T0)
        assert obs.sibling_demand(later) == {}
    finally:
        hal.close()
        obs.close()


def test_empty_demand_clears_the_board(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    obs = CoordinationStore(db_path=db, character="observer")
    try:
        hal.publish_demand({"copper_bar": 6}, _T0)
        hal.publish_demand({}, _T0)
        assert obs.sibling_demand(_T0) == {}
    finally:
        hal.close()
        obs.close()


def test_publish_demand_skips_zero_quantity(tmp_path: Path) -> None:
    """A zero-quantity entry must not persist a row: it would advertise a
    need that does not exist, and a sibling would produce something nobody
    wants."""
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    obs = CoordinationStore(db_path=db, character="observer")
    try:
        hal.publish_demand({"copper_bar": 0}, _T0)
        assert obs.sibling_demand(_T0) == {}
    finally:
        hal.close()
        obs.close()


def test_publish_demand_skips_negative_quantity(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    obs = CoordinationStore(db_path=db, character="observer")
    try:
        hal.publish_demand({"copper_bar": -3}, _T0)
        assert obs.sibling_demand(_T0) == {}
    finally:
        hal.close()
        obs.close()


def test_publish_demand_mixed_mapping_publishes_only_positive_entries(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    obs = CoordinationStore(db_path=db, character="observer")
    try:
        hal.publish_demand({"copper_bar": 6, "ash_plank": 0}, _T0)
        assert obs.sibling_demand(_T0) == {"copper_bar": 6}
    finally:
        hal.close()
        obs.close()


def test_publish_demand_rejects_naive_now(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    try:
        with pytest.raises(ValueError, match="naive"):
            hal.publish_demand({"copper_bar": 6}, _NAIVE_NOW)
    finally:
        hal.close()


def test_publish_demand_rejects_non_utc_offset_now(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    try:
        with pytest.raises(ValueError, match="offset"):
            hal.publish_demand({"copper_bar": 6}, _NON_UTC_NOW)
    finally:
        hal.close()


def test_sibling_demand_rejects_naive_now(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    try:
        with pytest.raises(ValueError, match="naive"):
            hal.sibling_demand(_NAIVE_NOW)
    finally:
        hal.close()


def test_sibling_demand_rejects_non_utc_offset_now(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    try:
        with pytest.raises(ValueError, match="offset"):
            hal.sibling_demand(_NON_UTC_NOW)
    finally:
        hal.close()
