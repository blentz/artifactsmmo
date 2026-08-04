"""Cross-character coordination over the shared learning DB.

`LearningStore` is single-character by construction: every read filters
`character == self._character`, and that invariant is load-bearing (learned
action costs and success rates must not blend across characters at different
levels with different gear). This class is the ONLY place in the codebase that
queries the coordination tables without a character filter, so the
"reads siblings" surface stays auditable in one file.

Opens the SAME sqlite file `LearningStore` does (children all receive one
`--learn-db` path from `MultiRun._child_argv`), with the same WAL settings.

Every method takes `now` rather than reading the clock, so TTL behaviour is
tested by injecting time instead of sleeping.

Best-effort, matching `LearningStore`'s contract: a `SQLAlchemyError` degrades
to the empty view (no siblings), which is present-day single-character
behaviour. Handled here and NOT re-handled upstream.
"""

import weakref
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import Connection, text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session as SqlSession
from sqlmodel import SQLModel, create_engine, select

from artifactsmmo_cli.ai.learning.models import MaterialDemand, RoleLease
from artifactsmmo_cli.ai.learning.schema_init import exclusive_schema_lock

LEASE_TTL_SECONDS = 600
"""Seconds a lease survives without renewal. Renewed every cycle, so this only
has to exceed the longest LEGITIMATE gap between cycles — not the action
cooldown, but a capped Retry-After backoff or a long planner search. Ten
minutes clears both, and costs at most ten minutes of an unworked role against
sessions that run for hours."""

DEMAND_TTL_SECONDS = 600
"""Seconds a published demand row survives without republication. Same clock as
LEASE_TTL_SECONDS on purpose: a crashed character's demand stops being served
at the same moment its role frees up, so there is exactly ONE liveness rule in
the coordination system."""


def _migrate_role_lease_unique_index(conn: Connection) -> None:
    """One-shot fix-up for `role_leases` on a pre-existing learning DB (2026-08-03).

    `RoleLease`'s uniqueness moved from `UNIQUE(role)` to `UNIQUE(role,
    character)` when roles stopped being an exclusive resource — see
    `RoleLease`'s docstring in `models.py` for why. `SQLModel.metadata
    .create_all` only creates tables that do not exist; it never alters an
    existing table's indexes. So every `learning.db` that predates this
    change still carries the old `CREATE UNIQUE INDEX ix_role_leases_role ON
    role_leases (role)`. With that index in place the second character to
    claim any role hits a UNIQUE-constraint violation on insert, and the
    whole non-exclusive-roles feature is silently dead on any existing
    install — the same class of "old cache, dead feature" bug the
    `delta_skill_xp_json` / `consumables_expended_json` migrations in
    `LearningStore.__init__` fixed for the cycles table.

    Detects the stale index via `PRAGMA index_list` / `PRAGMA index_info`
    rather than assuming it is there: a database created fresh under the
    current model already has the compound uniqueness (as a table-level
    `UniqueConstraint`, which SQLite implements as an autoindex) and no
    index whose columns are exactly `["role"]`, so the search below finds
    nothing and this is a no-op on it. Migrating in place — drop the stale
    single-column unique index, recreate a plain (non-unique) index on
    `role` alone to match the model's `Field(index=True)`, then add a
    UNIQUE index on `(role, character)` — preserves every existing lease
    row. Rows are TTL-bounded and would survive losing them, but nothing
    here requires that: an index rebuild touches no row data.
    """
    unique_role_only: str | None = None
    for row in conn.exec_driver_sql("PRAGMA index_list(role_leases)"):
        name, is_unique = row[1], row[2]
        if not is_unique:
            continue
        cols = [info[2] for info in conn.exec_driver_sql(f"PRAGMA index_info({name})")]
        if cols == ["role"]:
            unique_role_only = name
    if unique_role_only is None:
        return
    conn.exec_driver_sql(f"DROP INDEX {unique_role_only}")
    conn.exec_driver_sql("CREATE INDEX ix_role_leases_role ON role_leases (role)")
    conn.exec_driver_sql("CREATE UNIQUE INDEX uq_role_lease_holder ON role_leases (role, character)")


def _require_utc(now: datetime) -> None:
    """Guard the ONE invariant the whole TTL/liveness design rests on.

    Every liveness decision here (`claim`'s expiry check, `live_leases`'
    filter, `_expiry`'s stored value) compares `expires_at` and `stamp` as
    ISO 8601 STRINGS, lexicographically (`expires_at > stamp`), never as
    parsed datetimes. That comparison only agrees with true temporal order
    when every `now` that ever produced one of those strings is a UTC,
    timezone-aware datetime:

    - A naive datetime's `.isoformat()` carries no offset at all
      ("2026-08-01T00:00:00"), so it can't be compared against an aware
      string in any consistent way.
    - A non-UTC-but-aware datetime's `.isoformat()` sorts by its LOCAL
      wall-clock digits, not by the instant it names — e.g. an instant at
      "+05:00" prints an earlier-looking clock time than the same instant
      converted to UTC, so its string can sort as "older" than a genuinely
      earlier UTC timestamp. Mixing offsets would silently corrupt every
      lease's expiry comparison.

    Both failure modes are silent (no exception without this guard) and
    would corrupt every liveness decision in `CoordinationStore` — leases
    expiring early or never. This project's rule is to fail loudly on bad
    input rather than coerce it (e.g. assuming a naive datetime means UTC),
    so both cases raise `ValueError` naming the actual problem instead of
    being normalised.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError(
            f"CoordinationStore requires a timezone-aware UTC datetime; got a naive "
            f"datetime {now!r}. A naive datetime's isoformat() carries no offset, so "
            f"expires_at > stamp string comparisons cannot be trusted."
        )
    if now.utcoffset() != timedelta(0):
        raise ValueError(
            f"CoordinationStore requires a UTC datetime (offset +00:00); got {now!r} "
            f"with offset {now.utcoffset()}. A non-UTC offset's isoformat() sorts by "
            f"local wall-clock digits, not by the instant it names, which silently "
            f"corrupts the expires_at > stamp lexicographic comparison."
        )


class CoordinationStore:
    """Lease + demand board over the shared learning DB. Cross-character reads
    live here and nowhere else."""

    def __init__(self, db_path: str, character: str) -> None:
        # Same first line as LearningStore.__init__, and for the same reason:
        # sqlite3 will not create the DB inside a directory that does not exist
        # ("unable to open database file"). This store is the FIRST thing a
        # `play --all` supervisor builds at the default cache path, so on a
        # machine that has never run with `--learn` there is no
        # ~/.cache/artifactsmmo to open into. It surfaced as an order-dependent
        # failure of the home-guard test, which only passed when the
        # LearningStore case happened to run first in the same process and
        # create the directory as a side effect.
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(f"sqlite:///{db_path}")
        # Dispose the engine's pooled SQLite connection when this store is
        # garbage-collected, so callers that forget close() don't leak a
        # connection (raises ResourceWarning). Bound to the engine, not self —
        # mirrors LearningStore.__init__.
        self._finalizer = weakref.finalize(self, self._engine.dispose)
        # Under the exclusive writer lock, NOT bare: every child of one
        # `play --all` supervisor opens this same file within about a second,
        # and an unlocked `create_all` lets them all probe an empty file and
        # all decide to CREATE. That killed a child in production with
        # "table role_leases already exists". See `schema_init`.
        with exclusive_schema_lock(self._engine) as conn:
            SQLModel.metadata.create_all(conn)
            _migrate_role_lease_unique_index(conn)
        with self._engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            conn.commit()
        self._character = character

    @property
    def character(self) -> str:
        return self._character

    def _expiry(self, now: datetime) -> str:
        return (now + timedelta(seconds=LEASE_TTL_SECONDS)).isoformat()

    def claim(self, role: str, now: datetime) -> bool:
        """Record that THIS character holds `role`, and returns whether it does.

        Roles are not exclusive (see `RoleLease`), so there is nothing to win
        and nothing to lose: a sibling already holding `role` is not an
        obstacle, it is a fact `role_selection` already priced in when it
        divided the role's demand by the holder count. The claim writes this
        character's own `(role, character)` row and refreshes its TTL — the
        same operation whether nobody, one sibling, or four siblings hold it.

        `False` therefore means one thing only: the write did not land, because
        the DB itself failed. The caller must not then believe it holds the
        role (it would renew a lease that does not exist and supply for a role
        no board entry shows it serving).

        NO IntegrityError HANDLING, deliberately. Under the old UNIQUE(`role`)
        key the constraint violation WAS the concurrency control — two
        characters inserting the same role collided and one lost. The key is
        now UNIQUE(`role`, `character`), which only two writers for the SAME
        character could violate, and `play --all` runs exactly one process per
        character (`MultiRun._child_argv`), each holding one `CoordinationStore`
        pinned to one name. The old `except IntegrityError` branch is
        unreachable under the new key, so it is gone rather than kept as a
        second, dead level of error handling.

        Also SWEEPS EXPIRED ROWS, of every character, in the same transaction.
        `role_leases` otherwise only ever grows: nothing deletes a lapsed lease
        (`release` deletes only a role the caller is voluntarily giving up), so
        the table accumulates one tombstone per (character, role-ever-held) and
        anyone reading it directly sees characters apparently holding several
        roles at once. Behaviour was never wrong — `live_leases` filters on
        `expires_at` — but a table that has to be read through a filter to be
        understood is a table that will be misread, and it was. Swept HERE
        because this is the only place a row is ever ADDED, so the sweep runs at
        exactly the cadence the table grows and adds no write to the steady
        state (`renew`, the every-cycle writer, stays a pure extend).

        Also DROPS THIS CHARACTER'S OTHER ROLES. A character holds at most one
        role, but that invariant lives only in `GamePlayer._role`, in memory —
        nothing in the DB enforced it. A restart loses that in-memory value
        (resets to `None`) while the character's previous `role_leases` row
        survives, live, for up to `LEASE_TTL_SECONDS`. Claiming a new role after
        such a restart then left BOTH rows live: the old role's holder count
        stayed inflated for up to ten minutes (dividing its demand by too many
        holders, so it under-recruited), and anyone reading the table saw one
        character apparently holding two roles at once. The normal, in-process
        switch never hit this — `release()` already deletes the old row before
        the new `claim`, and `decide_role`'s reclaim path re-claims the SAME
        role — so this delete is a no-op there, live rows for OTHER characters
        are untouched (filtered on `character`), and it cannot touch the row
        just written above (filtered on `role != role`)."""
        _require_utc(now)
        stamp = now.isoformat()
        try:
            with SqlSession(self._engine) as s:
                row = s.exec(
                    select(RoleLease).where(
                        RoleLease.role == role,
                        RoleLease.character == self._character,
                    )
                ).first()
                if row is not None:
                    # Re-claim of a role we already have a row for (live or
                    # lapsed). `claimed_at` is refreshed too: this is a new
                    # holding, and the field's only reader wants when THIS
                    # holding began.
                    row.claimed_at = stamp
                    row.expires_at = self._expiry(now)
                    s.add(row)
                else:
                    s.add(RoleLease(role=role, character=self._character,
                                    claimed_at=stamp, expires_at=self._expiry(now)))
                for other in s.exec(
                    select(RoleLease).where(
                        RoleLease.character == self._character,
                        RoleLease.role != role,
                    )
                ).all():
                    s.delete(other)
                # `<= stamp` is the exact complement of `live_leases`' `> stamp`
                # liveness test, read off the same `now` and compared the same
                # lexicographic way, so every row deleted here was already
                # excluded from the holder COUNT that divides a role's demand.
                # The sweep therefore cannot move any allocation decision — and
                # expiry is monotone, so a row dead at `now` is dead at every
                # later read too.
                #
                # AFTER the write above, not before: our own row is flushed by
                # the time this query runs and carries a fresh future expiry, so
                # re-claiming our own LAPSED lease still UPDATES that row rather
                # than sweeping it away and inserting a second one.
                for dead in s.exec(
                    select(RoleLease).where(RoleLease.expires_at <= stamp)
                ).all():
                    s.delete(dead)
                s.commit()
                return True
        except SQLAlchemyError as e:
            print(f"[coordination] claim failed: {e}")
            return False

    def renew(self, role: str, now: datetime) -> None:
        """Extend this character's lease on `role`. No-op if it holds none.

        The no-op is the whole difference from `claim`, and it is load-bearing
        now that holder COUNT drives demand splitting: a caller whose `claim`
        failed but whose `self._role` is momentarily stale must not have its
        per-cycle renewal quietly insert a lease row, inflating the divisor
        every sibling sees for that role."""
        _require_utc(now)
        try:
            with SqlSession(self._engine) as s:
                row = s.exec(
                    select(RoleLease).where(
                        RoleLease.role == role,
                        RoleLease.character == self._character,
                    )
                ).first()
                if row is None:
                    return
                row.expires_at = self._expiry(now)
                s.add(row)
                s.commit()
        except SQLAlchemyError as e:
            print(f"[coordination] renew failed: {e}")

    def release(self, role: str) -> None:
        """Drop this character's lease on `role`. No-op if it holds none."""
        try:
            with SqlSession(self._engine) as s:
                row = s.exec(
                    select(RoleLease).where(
                        RoleLease.role == role,
                        RoleLease.character == self._character,
                    )
                ).first()
                if row is None:
                    return
                s.delete(row)
                s.commit()
        except SQLAlchemyError as e:
            print(f"[coordination] release failed: {e}")

    def live_leases(self, now: datetime) -> dict[str, frozenset[str]]:
        """`{role: {character, ...}}` over UNEXPIRED leases only, across ALL
        characters. One of the two deliberately unfiltered reads.

        A SET of holders, not one holder: roles stopped being exclusive, so
        `dict[role, character]` could no longer express the state the whole
        design now turns on. A role with no live holder is ABSENT from the
        result rather than mapped to an empty set — the same "unobserved is
        not zero" discipline the rest of the coordination surface follows, and
        it keeps `.get(role, frozenset())` the single reading idiom.

        Frozenset rather than a list or tuple because the two things callers
        ask are membership ("do I hold this?") and cardinality ("how many
        siblings am I splitting this role's demand with?"). Neither has an
        order, and an unordered type keeps a caller from inventing one as a
        tiebreak."""
        _require_utc(now)
        stamp = now.isoformat()
        holders: dict[str, set[str]] = {}
        try:
            with SqlSession(self._engine) as s:
                rows = s.exec(select(RoleLease).where(RoleLease.expires_at > stamp)).all()
        except SQLAlchemyError as e:
            print(f"[coordination] live_leases failed: {e}")
            return {}
        for row in rows:
            holders.setdefault(row.role, set()).add(row.character)
        return {role: frozenset(names) for role, names in holders.items()}

    def _demand_expiry(self, now: datetime) -> str:
        return (now + timedelta(seconds=DEMAND_TTL_SECONDS)).isoformat()

    def publish_demand(self, demand: Mapping[str, int], now: datetime) -> None:
        """Replace this character's demand rows wholesale.

        Replace rather than merge: demand is a snapshot of what is unmet RIGHT
        NOW, so an item that dropped off the closure must stop being served
        immediately. Merging would leave satisfied demand on the board until
        its TTL, and siblings would keep producing into a bank nobody drains."""
        _require_utc(now)
        expiry = self._demand_expiry(now)
        try:
            with SqlSession(self._engine) as s:
                stale = s.exec(
                    select(MaterialDemand).where(
                        MaterialDemand.character == self._character
                    )
                ).all()
                for row in stale:
                    s.delete(row)
                for item_code, quantity in demand.items():
                    if quantity > 0:
                        s.add(MaterialDemand(character=self._character,
                                             item_code=item_code,
                                             quantity=quantity,
                                             expires_at=expiry))
                s.commit()
        except SQLAlchemyError as e:
            print(f"[coordination] publish_demand failed: {e}")

    def sibling_demand(self, now: datetime) -> dict[str, int]:
        """Unexpired demand summed by item across every OTHER character. The
        second of the two deliberately unfiltered reads."""
        _require_utc(now)
        stamp = now.isoformat()
        totals: dict[str, int] = {}
        try:
            with SqlSession(self._engine) as s:
                rows = s.exec(
                    select(MaterialDemand).where(
                        MaterialDemand.expires_at > stamp,
                        MaterialDemand.character != self._character,
                    )
                ).all()
        except SQLAlchemyError as e:
            print(f"[coordination] sibling_demand failed: {e}")
            return {}
        for row in rows:
            totals[row.item_code] = totals.get(row.item_code, 0) + row.quantity
        return totals

    def close(self) -> None:
        self._engine.dispose()
