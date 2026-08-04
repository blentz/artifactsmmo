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


def _create_legacy_role_leases_schema(db_path: Path) -> None:
    """Build a `role_leases` table matching the pre-2026-08-03 schema: UNIQUE
    on `role` alone, verified live on the real `learning.db`:

        CREATE TABLE role_leases (id INTEGER NOT NULL, role VARCHAR NOT NULL,
                                  character VARCHAR NOT NULL, claimed_at VARCHAR NOT NULL,
                                  expires_at VARCHAR NOT NULL, PRIMARY KEY (id))
        CREATE UNIQUE INDEX ix_role_leases_role ON role_leases (role)
        CREATE INDEX ix_role_leases_character ON role_leases (character)

    Built directly against a `tmp_path` file (never by copying a real DB) and
    seeded with one lease row, so migration tests can also assert the row
    survives."""
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE role_leases (id INTEGER NOT NULL, role VARCHAR NOT NULL, "
            "character VARCHAR NOT NULL, claimed_at VARCHAR NOT NULL, "
            "expires_at VARCHAR NOT NULL, PRIMARY KEY (id))"
        )
        conn.exec_driver_sql("CREATE UNIQUE INDEX ix_role_leases_role ON role_leases (role)")
        conn.exec_driver_sql("CREATE INDEX ix_role_leases_character ON role_leases (character)")
        conn.exec_driver_sql(
            "INSERT INTO role_leases (role, character, claimed_at, expires_at) "
            "VALUES ('miner', 'HAL', '2026-08-01T00:00:00+00:00', '2026-08-01T00:10:00+00:00')"
        )
        conn.commit()
    engine.dispose()


def _role_lease_index_defs(db_path: Path) -> dict[str, tuple[bool, list[str]]]:
    """{index_name: (is_unique, [columns])} for role_leases, read via PRAGMA.
    Used to assert the migration's end state without depending on whichever
    name SQLite happens to give the compound-unique index."""
    engine = create_engine(f"sqlite:///{db_path}")
    result: dict[str, tuple[bool, list[str]]] = {}
    with engine.connect() as conn:
        for row in conn.exec_driver_sql("PRAGMA index_list(role_leases)"):
            name, is_unique = row[1], bool(row[2])
            cols = [info[2] for info in conn.exec_driver_sql(f"PRAGMA index_info({name})")]
            result[name] = (is_unique, cols)
    engine.dispose()
    return result


def test_legacy_unique_role_only_index_is_migrated(tmp_path: Path) -> None:
    """A database carrying the stale UNIQUE(role) index — verified live on the
    real learning.db, where it silently killed non-exclusive roles — is fixed
    up on open: the stale index is gone, a UNIQUE(role, character) index
    exists instead, the pre-existing lease row survives untouched, and a
    second character can now hold the same role."""
    db_path = tmp_path / "legacy.db"
    _create_legacy_role_leases_schema(db_path)
    assert _role_lease_index_defs(db_path)["ix_role_leases_role"] == (True, ["role"])

    store = CoordinationStore(db_path=str(db_path), character="C3P0")
    try:
        # Claimed WHILE the seeded HAL lease is still live (it expires at
        # 00:10). `claim` sweeps expired rows, so claiming at wall-clock `now`
        # would delete the very row this test is asserting the migration
        # preserved and prove nothing about the migration.
        assert store.claim("miner", datetime(2026, 8, 1, 0, 5, tzinfo=timezone.utc)) is True
    finally:
        store.close()

    defs_after = _role_lease_index_defs(db_path)
    assert not any(is_unique and cols == ["role"] for is_unique, cols in defs_after.values()), (
        "stale UNIQUE(role)-only index must be gone"
    )
    assert any(
        is_unique and set(cols) == {"role", "character"} for is_unique, cols in defs_after.values()
    ), "a UNIQUE(role, character) index must exist after migration"

    engine = create_engine(f"sqlite:///{db_path}")
    with SqlSession(engine) as s:
        rows = s.exec(select(RoleLease)).all()
    engine.dispose()
    assert {row.character for row in rows if row.role == "miner"} == {"HAL", "C3P0"}
    hal_row = next(row for row in rows if row.character == "HAL")
    assert (hal_row.claimed_at, hal_row.expires_at) == (
        "2026-08-01T00:00:00+00:00", "2026-08-01T00:10:00+00:00",
    ), "the pre-existing HAL row must survive the migration untouched"


def test_role_lease_migration_is_idempotent(tmp_path: Path) -> None:
    """Opening an already-migrated table a second time must not touch it
    again: same index set before and after, and no rows added or lost."""
    db_path = tmp_path / "legacy.db"
    _create_legacy_role_leases_schema(db_path)

    CoordinationStore(db_path=str(db_path), character="HAL").close()
    defs_first = _role_lease_index_defs(db_path)

    CoordinationStore(db_path=str(db_path), character="C3P0").close()
    defs_second = _role_lease_index_defs(db_path)

    assert defs_first == defs_second
    engine = create_engine(f"sqlite:///{db_path}")
    with SqlSession(engine) as s:
        rows = s.exec(select(RoleLease)).all()
    engine.dispose()
    assert len(rows) == 1  # the original HAL row; the second open claimed nothing


def test_fresh_database_role_leases_untouched_by_migration(tmp_path: Path) -> None:
    """A database created straight from the current model already has the
    compound UNIQUE (a table-level constraint, which SQLite implements as an
    autoindex) and no single-column UNIQUE(role) at all, so the migration
    detects nothing to fix and is a pure no-op."""
    db_path = tmp_path / "fresh.db"
    store = CoordinationStore(db_path=str(db_path), character="HAL")
    store.close()

    defs = _role_lease_index_defs(db_path)
    assert not any(is_unique and cols == ["role"] for is_unique, cols in defs.values())
    assert any(is_unique and set(cols) == {"role", "character"} for is_unique, cols in defs.values())

    store2 = CoordinationStore(db_path=str(db_path), character="C3P0")
    try:
        assert store2.claim("miner", datetime.now(tz=timezone.utc)) is True
    finally:
        store2.close()


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


def _lease_rows(db: str) -> set[tuple[str, str]]:
    """Every `(role, character)` in `role_leases`, live or lapsed — the view
    someone gets who reads the table directly instead of through
    `live_leases`."""
    engine = create_engine(f"sqlite:///{db}")
    try:
        with SqlSession(engine) as s:
            return {(row.role, row.character) for row in s.exec(select(RoleLease)).all()}
    finally:
        engine.dispose()


def test_a_claim_sweeps_expired_lease_rows(tmp_path: Path) -> None:
    """RESIDUAL 3. Nothing used to delete a lapsed lease, so `role_leases`
    accumulated one tombstone per (character, role-ever-held) and read as if
    every character held several roles at once. `claim` is the only place a row
    is ever added, so it is where the sweep belongs.

    The claimer here (KITT) is a THIRD character, never a holder of `miner` or
    `logger`: the one-role-per-character cleanup `claim` also does is scoped
    to the CLAIMER's own rows, so a claimer with no prior role of its own
    isolates the expired-row sweep from that cleanup. HAL's dead `miner` row
    (expired, different character) is what the sweep is expected to remove;
    C3P0's renewed `logger` row (live, different character) is what it must
    leave alone."""
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    c3po = CoordinationStore(db_path=db, character="C3P0")
    kitt = CoordinationStore(db_path=db, character="KITT")
    later = _T0 + timedelta(seconds=LEASE_TTL_SECONDS + 1)
    try:
        assert hal.claim("miner", _T0) is True
        assert c3po.claim("logger", _T0) is True
        # Both rows have lapsed by `later`; C3P0 renews only its own.
        c3po.renew("logger", later)
        assert _lease_rows(db) == {("miner", "HAL"), ("logger", "C3P0")}

        assert kitt.claim("fisher", later) is True

        # HAL's dead `miner` row is gone; the live rows are untouched.
        assert _lease_rows(db) == {("logger", "C3P0"), ("fisher", "KITT")}
    finally:
        hal.close()
        c3po.close()
        kitt.close()


def test_sweeping_expired_rows_does_not_change_the_live_holder_count(tmp_path: Path) -> None:
    """The sweep must be invisible to allocation. `live_leases` already filters
    on the same `expires_at` comparison off the same clock, so every row the
    sweep deletes was already excluded from the holder count that divides a
    role's demand — the view before and after must be identical."""
    db = str(tmp_path / "coord.db")
    holders = [CoordinationStore(db_path=db, character=n) for n in ("HAL", "C3P0")]
    joiner = CoordinationStore(db_path=db, character="K9")
    later = _T0 + timedelta(seconds=LEASE_TTL_SECONDS + 1)
    try:
        for store in holders:
            assert store.claim("miner", later) is True
        # Tombstones seeded directly rather than through `claim`, which would
        # sweep them itself: the point is the state a long session leaves
        # behind, not how it got there.
        engine = create_engine(f"sqlite:///{db}")
        try:
            with SqlSession(engine) as s:
                for role, name in (("alchemist", "HAL"), ("logger", "C3P0"),
                                   ("fisher", "R2D2")):
                    s.add(RoleLease(role=role, character=name,
                                    claimed_at=_T0.isoformat(),
                                    expires_at=(_T0 + timedelta(seconds=1)).isoformat()))
                s.commit()
        finally:
            engine.dispose()
        before = joiner.live_leases(later)
        assert before == {"miner": frozenset({"HAL", "C3P0"})}
        assert len(_lease_rows(db)) == 5

        assert joiner.claim("miner", later) is True

        assert _lease_rows(db) == {("miner", "HAL"), ("miner", "C3P0"), ("miner", "K9")}
        # The only difference in the live view is the joiner itself.
        assert joiner.live_leases(later) == {"miner": before["miner"] | {"K9"}}
    finally:
        for store in holders:
            store.close()
        joiner.close()


def test_claiming_a_new_role_drops_this_characters_other_role(tmp_path: Path) -> None:
    """The restart bug: `GamePlayer._role` is in-memory only and resets to
    `None` on restart, but the character's previous `role_leases` row
    survives, live, in the DB. Claiming a different role after such a
    restart must leave exactly one live row for this character — the new
    one — not two."""
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    try:
        assert hal.claim("miner", _T0) is True
        assert hal.claim("logger", _T0) is True
        assert _lease_rows(db) == {("logger", "HAL")}
    finally:
        hal.close()


def test_claiming_a_new_role_does_not_touch_a_siblings_row_for_the_old_role(tmp_path: Path) -> None:
    """The cleanup is scoped strictly to THIS character: a sibling's row for
    the role being abandoned must survive untouched."""
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    c3po = CoordinationStore(db_path=db, character="C3P0")
    try:
        assert hal.claim("miner", _T0) is True
        assert c3po.claim("miner", _T0) is True
        assert hal.claim("logger", _T0) is True
        assert _lease_rows(db) == {("miner", "C3P0"), ("logger", "HAL")}
    finally:
        hal.close()
        c3po.close()


def test_claiming_a_new_role_moves_the_live_holder_count(tmp_path: Path) -> None:
    """Holder count is what actually drives demand splitting
    (`role_selection._effective_demand`), so the property under test is
    `live_leases`, not the raw table: A's count must drop by exactly one and
    B's must rise by exactly one."""
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    c3po = CoordinationStore(db_path=db, character="C3P0")
    try:
        assert hal.claim("miner", _T0) is True
        assert c3po.claim("miner", _T0) is True
        assert hal.live_leases(_T0) == {"miner": frozenset({"HAL", "C3P0"})}

        assert hal.claim("logger", _T0) is True

        assert hal.live_leases(_T0) == {
            "miner": frozenset({"C3P0"}),
            "logger": frozenset({"HAL"}),
        }
    finally:
        hal.close()
        c3po.close()


def test_reclaiming_the_held_role_is_idempotent_and_keeps_the_row(tmp_path: Path) -> None:
    """Claiming the role you already hold must remain a no-op on the table —
    the `role != role` filter that drops other-role rows must not also
    sweep away the row `claim` just wrote for the SAME role."""
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    try:
        assert hal.claim("miner", _T0) is True
        assert hal.claim("miner", _T0) is True
        assert _lease_rows(db) == {("miner", "HAL")}
        assert hal.live_leases(_T0) == {"miner": frozenset({"HAL"})}
    finally:
        hal.close()


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
