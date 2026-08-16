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
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session as SqlSession
from sqlmodel import SQLModel, col, create_engine, select

from artifactsmmo_cli.ai.learning.models import (
    BankStockClaim,
    GeOrderClaim,
    HoldingLedger,
    MaterialDemand,
    RoleLease,
    TurnInClaim,
)
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

BANK_CLAIM_TTL_SECONDS = 60
"""Seconds a bank-stock claim survives. DELIBERATELY MUCH SHORTER than the two
above, and derived from the cycle cadence rather than picked.

A role is held for a whole production run, so its lease is renewed every cycle
and only has to outlive the longest legitimate gap BETWEEN cycles (600s). A
bank-stock claim is the opposite: it is written once, immediately before one
withdraw request, and is never renewed. Its job is to cover the settlement
window — from the moment this character commits the withdraw until a sibling's
own `bank_items` catches up — and nothing longer.

LOWER BOUND (must not expire mid-withdraw). Between the claim and the outcome
the character does: `_acquire_action()` (may block on this child's share of the
per-IP action budget), the withdraw request itself, then `_sync_bank`'s paged
`/my/bank/items` + `/my/bank` reads on the account bucket. That is bounded by
one cycle, and a cycle is cooldown-bound — the bot sleeps 15-25s between
actions (`RateGovernor`'s docstring records the same figure, and it is why the
governor adds no latency to a cooldown-bound bot).

UPPER BOUND (a crashed character must not starve the fleet). A claim outlives
its writer only on a crash, and until it expires the units are invisible to
every sibling's drain licence. At 60s that costs at most two cycles of one
code's shed; at LEASE_TTL_SECONDS it would cost twenty, and the shed rungs are
the ones that were already starved (`DrainBankJunkGoal`).

60s = two cycles at the upper end of that observed 15-25s cadence, which is
"the withdraw plus a whole cycle of slack" — the smallest value that covers the
lower bound twice over while staying an order of magnitude under the lease."""

GE_ORDER_CLAIM_TTL_SECONDS = 60
"""Seconds a GE order-cancel claim survives. Written once immediately before one
cancel request and never renewed — the same shape as BANK_CLAIM_TTL_SECONDS, and
sized against the same settlement window, so the two deliberately share a value
rather than each inventing one.

LOWER BOUND (must outlive the cancel's settlement). Between the claim and a
sibling being able to see the truth for itself, this character does
`_acquire_action()` (which may block on its share of the per-IP action budget),
then the cancel request. The sibling learns the order is gone from its OWN next
`_reconcile_open_orders`, which re-reads `/my/grandexchange/orders` every cycle —
so the window to cover is one cycle, and a cycle is 15-25s when cooldown-bound.

UPPER BOUND (a crashed character must not hide a live order). A claim outlives
its writer only on a crash, and until it expires that order is invisible to
every sibling's `cancel_targets` — capital nobody frees. The TTL is therefore
what bounds the escape hatch that `CancelOrdersGoal`'s liveness argument rests
on: no posted order's capital can be locked for longer than one claim's TTL past
the cycle it ages out on.

60s is two cycles at the upper end of that cadence: it covers the settlement
window twice over while costing at most one extra minute of locked capital
against sessions that run for hours."""


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


def _migrate_material_demand_self_servable(conn: Connection) -> None:
    """One-shot fix-up for `material_demand` on a pre-existing learning DB
    (2026-08-16). Follows `_migrate_role_lease_unique_index`'s shape exactly:
    detect with `PRAGMA`, alter in place, preserve every row, no-op on a
    fresh DB.

    `MaterialDemand` grew a `self_servable` column so the "serve a sibling's
    request" rung can finally tell "nobody nearby can make this" apart from
    "the requester could make this itself but asked anyway" — see the
    column's docstring in `models.py`. `SQLModel.metadata.create_all` only
    creates tables that do not exist; it never alters an existing table's
    columns. So every `learning.db` that predates this change still has a
    `material_demand` table with no `self_servable` column. Without this
    migration the first `publish_demand` call raises `OperationalError:
    table material_demand has no column named self_servable`, the
    surrounding `except SQLAlchemyError` swallows it, and the demand board
    silently stops updating — the exact "old cache, dead feature" failure
    `_migrate_role_lease_unique_index` exists to prevent, now recurring on a
    different table.

    Detects the missing column via `PRAGMA table_info` rather than assuming
    it is absent: a database created fresh under the current model already
    has the column, so the search below finds it and this is a no-op.
    Migrating in place — `ALTER TABLE ... ADD COLUMN self_servable BOOLEAN
    NOT NULL DEFAULT 1` — preserves every existing row and backfills them
    with the same safe default the model declares (`True`, i.e. SQLite `1`),
    so a legacy row reads as "the requester can handle this itself" rather
    than suddenly flooding the fleet with requests nobody asked for."""
    columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(material_demand)")]
    if "self_servable" in columns:
        return
    conn.exec_driver_sql(
        "ALTER TABLE material_demand ADD COLUMN self_servable BOOLEAN NOT NULL DEFAULT 1"
    )


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
            _migrate_material_demand_self_servable(conn)
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
        """The ONE liveness clock: `MaterialDemand`, `HoldingLedger` and
        `TurnInClaim` all expire on `DEMAND_TTL_SECONDS` and shared three
        byte-identical copies of this line until they were collapsed here.
        The bank-stock and GE-order claims keep their own methods because
        they genuinely differ — each carries its own TTL constant."""
        return (now + timedelta(seconds=DEMAND_TTL_SECONDS)).isoformat()

    def publish_demand(self, demand: Mapping[str, int], self_servable: frozenset[str],
                       now: datetime) -> None:
        """Replace this character's demand rows wholesale.

        Replace rather than merge: demand is a snapshot of what is unmet RIGHT
        NOW, so an item that dropped off the closure must stop being served
        immediately. Merging would leave satisfied demand on the board until
        its TTL, and siblings would keep producing into a bank nobody drains.

        `self_servable` is the set of item codes THIS character — the
        requester — could produce itself, stamped onto every row this call
        writes. A frozenset rather than a parallel `Mapping[str, bool]`
        because the flag is a property of the requester as a whole, not of
        any one item's quantity, and a set keyed the same way as `demand`
        cannot fall out of step with `demand`'s own keys the way a second
        dict could. A code in `demand` but absent from `self_servable` is
        stored `self_servable=False` — the requester genuinely cannot make
        it, which is the case the "serve a sibling's request" rung needs to
        finally distinguish from "could make it but asked anyway"."""
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
                                             expires_at=expiry,
                                             self_servable=item_code in self_servable))
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

    def sibling_demand_asymmetric(self, now: datetime) -> frozenset[str]:
        """Item codes for which at least one UNEXPIRED, OTHER-character demand
        row is `self_servable=False` — the codes worth a sibling's cycle,
        because someone who asked for them genuinely cannot make them.

        The aggregation across rows for the same code is OR, not AND, and
        that is the entire point of the column: if ANY live asker cannot make
        an item, that item is worth producing for the fleet. A second asker
        who happens to be able to make it does not cancel the first one's
        need — it is a DIFFERENT character's row, describing a DIFFERENT
        character's situation, and the first one's request is still sitting
        there unfilled. Reducing with AND instead would let one
        self-servable asker mask every genuinely-stuck asker for the same
        code, which is exactly the case `self_servable` was added to stop
        being invisible (see `MaterialDemand.self_servable`'s docstring).

        Modelled on `sibling_demand`'s shape exactly — same "other characters
        only" filter, same unexpired predicate, one query — because the
        liveness and ownership rules are identical; only the aggregation
        (OR over booleans vs. sum over quantities) and the return shape
        (frozenset of codes vs. quantity dict) differ. A frozenset, not a
        dict: the caller's only question is membership ("is this code
        asymmetric?"), and there is no quantity to attach to the answer —
        `sibling_demand` already reports how much is wanted; this reports
        which of those wants nobody who asked for it can fill themselves."""
        _require_utc(now)
        stamp = now.isoformat()
        try:
            with SqlSession(self._engine) as s:
                rows = s.exec(
                    select(MaterialDemand).where(
                        MaterialDemand.expires_at > stamp,
                        MaterialDemand.character != self._character,
                        col(MaterialDemand.self_servable).is_(False),
                    )
                ).all()
        except SQLAlchemyError as e:
            print(f"[coordination] sibling_demand_asymmetric failed: {e}")
            return frozenset()
        return frozenset(row.item_code for row in rows)

    def publish_holdings(self, holdings: Mapping[str, int], now: datetime) -> None:
        """Replace this character's `HoldingLedger` rows wholesale.

        Modelled line-for-line on `publish_demand`: holdings are a snapshot of
        what this character wears plus carries RIGHT NOW, so a unit spent
        (turned in, sold, un-equipped and dropped) must stop counting toward
        the fleet total immediately. Merging would leave a spent medal on the
        board until its TTL, and a sibling could reach the turn-in threshold
        against units that no longer exist.

        Uses `DEMAND_TTL_SECONDS`, the same clock as `MaterialDemand` and
        `RoleLease`, on purpose: the coordination system has exactly ONE
        liveness rule, and a second TTL constant here would be a second one."""
        _require_utc(now)
        expiry = self._demand_expiry(now)
        try:
            with SqlSession(self._engine) as s:
                stale = s.exec(
                    select(HoldingLedger).where(
                        HoldingLedger.character == self._character
                    )
                ).all()
                for row in stale:
                    s.delete(row)
                # Flush the deletes before the inserts: HoldingLedger, unlike
                # MaterialDemand, is UNIQUE on (character, item_code), so a
                # same-code republish inserts a row whose key a still-pending
                # delete has not yet vacated. Unflushed, SQLAlchemy's unit of
                # work would order that INSERT ahead of the DELETE within one
                # flush and the UNIQUE constraint would reject it.
                s.flush()
                for item_code, quantity in holdings.items():
                    if quantity > 0:
                        s.add(HoldingLedger(character=self._character,
                                            item_code=item_code,
                                            quantity=quantity,
                                            expires_at=expiry))
                s.commit()
        except SQLAlchemyError as e:
            print(f"[coordination] publish_holdings failed: {e}")

    def sibling_holdings(self, now: datetime) -> dict[str, int]:
        """Unexpired holdings summed by item across every OTHER character.
        Modelled line-for-line on `sibling_demand`: this character's own row
        is excluded on purpose, because the caller adds its own holdings from
        live state, which is fresher than anything it published."""
        _require_utc(now)
        stamp = now.isoformat()
        totals: dict[str, int] = {}
        try:
            with SqlSession(self._engine) as s:
                rows = s.exec(
                    select(HoldingLedger).where(
                        HoldingLedger.expires_at > stamp,
                        HoldingLedger.character != self._character,
                    )
                ).all()
        except SQLAlchemyError as e:
            print(f"[coordination] sibling_holdings failed: {e}")
            return {}
        for row in rows:
            totals[row.item_code] = totals.get(row.item_code, 0) + row.quantity
        return totals

    def _bank_claim_expiry(self, now: datetime) -> str:
        return (now + timedelta(seconds=BANK_CLAIM_TTL_SECONDS)).isoformat()

    def claim_bank_stock(self, claims: Mapping[str, int], now: datetime) -> None:
        """Record that THIS character is taking `claims` out of the shared bank.

        Replace-wholesale, exactly like `publish_demand` and for the same
        reason: a character executes ONE action at a time, so it has at most
        one live withdraw intent, and the rows from a previous withdraw are
        stale the moment a new one is committed. Merging would leave a settled
        withdraw's units invisible to every sibling until their TTL.

        WHEN IT IS RELEASED — this is the one place the design deviates from
        "release on success", so it is stated rather than assumed. The reason a
        claim must be released is that a claim outliving its withdraw is stock
        nobody can touch. On a FAILED withdraw the stock is still in the bank
        and that reason bites exactly, so `release_bank_stock` is called
        immediately (see `GamePlayer._execute`). On a SUCCESSFUL withdraw the
        units are GONE, so the claim withholds nothing that exists — what it
        does is shadow the sibling snapshots that still show them, which is the
        whole race: `bank_items` is only re-read after that sibling's OWN bank
        action or every `BANK_REFRESH_INTERVAL` actions, so releasing on
        success would collapse the useful window to one HTTP round-trip and
        leave the mechanism inert. It is therefore left to expire on
        `BANK_CLAIM_TTL_SECONDS`, which is sized for exactly that settlement
        window.

        Non-positive quantities are dropped rather than stored (mirrors
        `publish_demand`): a claim on zero units is not a claim, and storing it
        would make `sibling_bank_claims` carry rows that can never subtract
        anything.

        Also SWEEPS EXPIRED ROWS of every character, in the same transaction
        and for the same reason `claim` does it on `role_leases`: this is the
        only place a row is ever ADDED, so the sweep runs at exactly the
        cadence the table grows, and `sibling_bank_claims` already excludes
        every row it deletes."""
        _require_utc(now)
        stamp = now.isoformat()
        expiry = self._bank_claim_expiry(now)
        try:
            with SqlSession(self._engine) as s:
                for stale in s.exec(
                    select(BankStockClaim).where(
                        BankStockClaim.character == self._character
                    )
                ).all():
                    s.delete(stale)
                # Flush the deletes before the inserts: BankStockClaim, like
                # HoldingLedger, is UNIQUE on (character, item_code), so a
                # same-code reclaim inserts a row whose key a still-pending
                # delete has not yet vacated. Unflushed, SQLAlchemy's unit of
                # work would order that INSERT ahead of the DELETE within one
                # flush and the UNIQUE constraint would reject it.
                s.flush()
                for item_code, quantity in claims.items():
                    if quantity > 0:
                        s.add(BankStockClaim(character=self._character,
                                             item_code=item_code,
                                             quantity=quantity,
                                             claimed_at=stamp,
                                             expires_at=expiry))
                for dead in s.exec(
                    select(BankStockClaim).where(BankStockClaim.expires_at <= stamp)
                ).all():
                    s.delete(dead)
                s.commit()
        except SQLAlchemyError as e:
            print(f"[coordination] claim_bank_stock failed: {e}")

    def release_bank_stock(self) -> None:
        """Drop every bank-stock claim this character holds. No-op if it holds
        none.

        Called when a withdraw FAILED: the units are still in the bank, so a
        surviving claim is stock nobody can touch for up to
        `BANK_CLAIM_TTL_SECONDS`. All of them rather than one code, because
        `claim_bank_stock` replaces wholesale — this character's rows are
        exactly the one withdraw that just failed."""
        try:
            with SqlSession(self._engine) as s:
                for row in s.exec(
                    select(BankStockClaim).where(
                        BankStockClaim.character == self._character
                    )
                ).all():
                    s.delete(row)
                s.commit()
        except SQLAlchemyError as e:
            print(f"[coordination] release_bank_stock failed: {e}")

    def sibling_bank_claims(self, now: datetime) -> dict[str, int]:
        """Unexpired bank-stock claims summed by item across every OTHER
        character. The THIRD deliberately unfiltered read.

        Own claims are excluded because the reader subtracts this from its own
        bank view to decide what it may still take: subtracting its own
        in-flight withdraw would make it stop planning the very drain it is
        already executing."""
        _require_utc(now)
        stamp = now.isoformat()
        totals: dict[str, int] = {}
        try:
            with SqlSession(self._engine) as s:
                rows = s.exec(
                    select(BankStockClaim).where(
                        BankStockClaim.expires_at > stamp,
                        BankStockClaim.character != self._character,
                    )
                ).all()
        except SQLAlchemyError as e:
            print(f"[coordination] sibling_bank_claims failed: {e}")
            return {}
        for row in rows:
            totals[row.item_code] = totals.get(row.item_code, 0) + row.quantity
        return totals

    def _ge_order_claim_expiry(self, now: datetime) -> str:
        return (now + timedelta(seconds=GE_ORDER_CLAIM_TTL_SECONDS)).isoformat()

    def claim_ge_order(self, order_id: str, now: datetime) -> None:
        """Record that THIS character is cancelling the account's GE order
        `order_id`, so siblings drop it from their own cancel targets instead of
        racing us to it for an HTTP 404.

        ACCUMULATES rather than replacing (see `GeOrderClaim`): `cancel_targets`
        can report several ids at once and they are worked one per cycle, so an
        earlier claim must survive the next one.

        Re-claiming an id this character already holds UPDATES that row's expiry
        rather than inserting a second one — the unique key makes a duplicate
        unrepresentable, and a re-claim is a fresh intent whose TTL should run
        from now.

        Also SWEEPS EXPIRED ROWS of every character, in the same transaction and
        for the same reason `claim` and `claim_bank_stock` do: this is the only
        place a row is ever ADDED, so the sweep runs at exactly the cadence the
        table grows, and `sibling_order_claims` already excludes every row it
        deletes."""
        _require_utc(now)
        stamp = now.isoformat()
        try:
            with SqlSession(self._engine) as s:
                row = s.exec(
                    select(GeOrderClaim).where(
                        GeOrderClaim.character == self._character,
                        GeOrderClaim.order_id == order_id,
                    )
                ).first()
                if row is not None:
                    row.claimed_at = stamp
                    row.expires_at = self._ge_order_claim_expiry(now)
                    s.add(row)
                else:
                    s.add(GeOrderClaim(character=self._character, order_id=order_id,
                                       claimed_at=stamp,
                                       expires_at=self._ge_order_claim_expiry(now)))
                # AFTER the write, so re-claiming our own LAPSED row updates it
                # rather than being swept away and re-inserted — same ordering,
                # and same reason, as `claim`'s sweep.
                for dead in s.exec(
                    select(GeOrderClaim).where(GeOrderClaim.expires_at <= stamp)
                ).all():
                    s.delete(dead)
                s.commit()
        except SQLAlchemyError as e:
            print(f"[coordination] claim_ge_order failed: {e}")

    def release_ge_orders(self) -> None:
        """Drop every GE order-cancel claim this character holds. No-op if it
        holds none.

        Called when a cancel provably did not happen: the order is still open,
        so a surviving claim hides a live order — and the capital it locks —
        from every sibling for the rest of its TTL. All of them rather than one
        id because a character executes ONE action at a time, so at most one
        claim can be in flight and any others are already settled or expiring."""
        try:
            with SqlSession(self._engine) as s:
                for row in s.exec(
                    select(GeOrderClaim).where(
                        GeOrderClaim.character == self._character
                    )
                ).all():
                    s.delete(row)
                s.commit()
        except SQLAlchemyError as e:
            print(f"[coordination] release_ge_orders failed: {e}")

    def sibling_order_claims(self, now: datetime) -> frozenset[str]:
        """Unexpired GE order ids claimed by every OTHER character. The FOURTH
        deliberately unfiltered read.

        A frozenset, not a mapping: the only question a caller asks is
        membership ("is a sibling already cancelling this id?"). There is no
        quantity to sum and no order to impose.

        Own claims are excluded for the same reason `sibling_bank_claims`
        excludes them: subtracting its own in-flight cancel would make a
        character stop planning the very cancel it is executing."""
        _require_utc(now)
        stamp = now.isoformat()
        try:
            with SqlSession(self._engine) as s:
                rows = s.exec(
                    select(GeOrderClaim).where(
                        GeOrderClaim.expires_at > stamp,
                        GeOrderClaim.character != self._character,
                    )
                ).all()
        except SQLAlchemyError as e:
            print(f"[coordination] sibling_order_claims failed: {e}")
            return frozenset()
        return frozenset(row.order_id for row in rows)

    def claim_turn_in(self, item_code: str, now: datetime) -> bool:
        """Elect THIS character to spend the fleet's currency turning in
        `item_code`, and report whether it holds the claim afterwards.

        This is the mechanism that stops five children from each recalling
        the same medals: `HoldingLedger`/`sibling_holdings` let every
        character see the SAME fleet total cross a turn-in threshold on the
        SAME cycle, so seeing it is not enough — exactly one of them must
        also win this claim before acting on it.

        Modelled on `RoleLease.claim`'s PRE-2026-08-03 shape (see this
        file's git history at `fd71410c`), NOT on the CURRENT `claim` above:
        `role_leases` stopped contending when its key widened to `(role,
        character)`, but a turn-in needs the opposite — `TurnInClaim` is
        UNIQUE on `item_code` ALONE (see its docstring), so there is at most
        one row per item and taking that row over IS the election.

        A live incumbent that is a DIFFERENT character blocks the claim
        (`False`). An incumbent that has EXPIRED, or is this character's OWN
        prior claim, is taken over / renewed in place — the renewal case is
        what lets a multi-cycle turn-in keep its claim across actions
        without losing it to its own next call.

        IntegrityError IS still reachable here, unlike in `claim` above:
        two characters can simultaneously read "no row for this item_code"
        and both attempt to insert. `TurnInClaim`'s key is genuinely
        exclusive, so the loser's insert collides for real and must report
        `False` rather than propagate — the loser simply did not win the
        election and tries again, or stands down, next cycle."""
        _require_utc(now)
        stamp = now.isoformat()
        try:
            with SqlSession(self._engine) as s:
                row = s.exec(
                    select(TurnInClaim).where(TurnInClaim.item_code == item_code)
                ).first()
                if row is not None:
                    if row.character != self._character and row.expires_at > stamp:
                        return False
                    row.character = self._character
                    row.claimed_at = stamp
                    row.expires_at = self._demand_expiry(now)
                    s.add(row)
                else:
                    s.add(TurnInClaim(item_code=item_code, character=self._character,
                                      claimed_at=stamp,
                                      expires_at=self._demand_expiry(now)))
                s.commit()
                return True
        except IntegrityError:
            return False
        except SQLAlchemyError as e:
            print(f"[coordination] claim_turn_in failed: {e}")
            return False

    def turn_in_holder(self, item_code: str, now: datetime) -> str | None:
        """The character currently holding a LIVE claim on `item_code`, or
        `None` if nobody does. Unlike `claim_turn_in`, this never writes: a
        caller checking whether a SIBLING already holds the election (so it
        can stand down) must not itself take the claim over just by
        asking."""
        _require_utc(now)
        stamp = now.isoformat()
        try:
            with SqlSession(self._engine) as s:
                row = s.exec(
                    select(TurnInClaim).where(
                        TurnInClaim.item_code == item_code,
                        TurnInClaim.expires_at > stamp,
                    )
                ).first()
        except SQLAlchemyError as e:
            print(f"[coordination] turn_in_holder failed: {e}")
            return None
        return row.character if row is not None else None

    def release_turn_in(self, item_code: str) -> None:
        """Drop this character's claim on `item_code`. No-op if it holds
        none — including when a SIBLING holds it: this only ever touches
        this character's own row, matching `release`'s and
        `release_bank_stock`'s own-row-only discipline, so a stale or
        mistaken release can never evict a sibling's live election."""
        try:
            with SqlSession(self._engine) as s:
                row = s.exec(
                    select(TurnInClaim).where(
                        TurnInClaim.item_code == item_code,
                        TurnInClaim.character == self._character,
                    )
                ).first()
                if row is None:
                    return
                s.delete(row)
                s.commit()
        except SQLAlchemyError as e:
            print(f"[coordination] release_turn_in failed: {e}")

    def close(self) -> None:
        self._engine.dispose()
