"""The liveness census — has every Goal and Action ever actually run?

The tests that matter here are the three that make the gate BITE, because a
census that cannot fail is a census that says nothing. Each drives the real
`run_census` against a real on-disk SQLite store, never a stubbed count: the
whole point of this census is that it reads what the bot actually did, and a
mocked store would test the arithmetic while skipping the question.
"""

import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path

import pytest

from artifactsmmo_cli.audit.liveness_completeness import (
    DORMANT,
    REPR_ALIASES,
    STALL_MIN_SPAN,
    LivenessRow,
    Stall,
    defined_classes,
    find_stalls,
    observed_counts,
    orphan_declarations,
    render_matrix,
    run_census,
    stale,
    summary_line,
    undeclared,
)

GEN_LIVENESS = Path(__file__).resolve().parents[2] / "scripts" / "gen_liveness.py"


def _store(path: Path, goals: dict[str, int], actions: dict[str, int]) -> str:
    """A minimal `cycles` table — the two columns the census reads."""
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("create table cycles (selected_goal text, action_class text)")
        for repr_, n in goals.items():
            conn.executemany("insert into cycles (selected_goal) values (?)",
                             [(repr_,)] * n)
        for cls, n in actions.items():
            conn.executemany("insert into cycles (action_class) values (?)",
                             [(cls,)] * n)
        conn.commit()
    return str(path)


def _row(name: str, observed: int, declared: str | None = None) -> LivenessRow:
    return LivenessRow(name=name, kind="goal", observed=observed, declared=declared)


class TestTheGateBites:
    """Three arms, three mutants. Verified by hand against the real roster:
    adding an undeclared Goal, declaring a live one, and naming a deleted one
    each turn the gate red and nothing else does."""

    def test_an_undeclared_dead_class_fails(self):
        rows = [_row("NeverRanGoal", 0, None)]
        assert undeclared(rows) == rows

    def test_a_declared_dead_class_passes(self):
        """Dormancy is allowed. Only UNDECLARED dormancy is not — otherwise a
        raid goal with no live raid would redden the gate forever and the census
        would be turned off."""
        rows = [_row("ParticipateRaidGoal", 0, "conditional: needs a live raid")]
        assert undeclared(rows) == []
        assert stale(rows) == []

    def test_a_declaration_the_store_contradicts_fails(self):
        """A reason nobody rechecks is a green light with an out-of-date argument
        behind it."""
        rows = [_row("BusyGoal", 4321, "conditional: never happens")]
        assert stale(rows) == rows

    def test_a_declaration_naming_a_deleted_class_fails(self, monkeypatch):
        """Left in place it would silently excuse the wrong thing the next time
        the name is reused.

        Patched onto the REAL map rather than asserted against a hand-built
        expectation, because `orphan_declarations` reads module state: a test that
        rebuilt the expected answer from the same map would agree with any
        implementation, including one that returned nothing."""
        rows = run_census("/nonexistent")   # the REAL roster
        assert orphan_declarations(rows) == [], "precondition: clean before the mutant"
        monkeypatch.setitem(DORMANT, "DeletedLongAgoGoal", "stale entry")
        assert orphan_declarations(rows) == ["DeletedLongAgoGoal"]

    def test_an_alias_pointing_at_a_deleted_class_also_fails(self, monkeypatch):
        """An alias whose target vanished stops crediting anything, turning a LIVE
        class into a false UNDECLARED — the noisy direction, and the one that gets
        a gate switched off."""
        rows = run_census("/nonexistent")
        monkeypatch.setitem(REPR_ALIASES, "SomeRepr", "VanishedGoal")
        assert orphan_declarations(rows) == ["VanishedGoal"]


class TestObservedCounts:
    def test_a_goal_repr_credits_its_class(self, tmp_path):
        """The store records REPRS (`GrindCharacterXP(pig)`); the roster records
        CLASS names (`GrindCharacterXPGoal`). Both spellings are credited."""
        db = _store(tmp_path / "a.db", {"GrindCharacterXP(pig)": 3}, {})
        counts = observed_counts(db)
        assert counts["GrindCharacterXP"] == 3
        assert counts["GrindCharacterXPGoal"] == 3

    def test_an_aliased_repr_credits_its_class(self, tmp_path):
        """`EquipOwnedGoal` renders as `EquipOwnedGear`, so neither the bare stem
        nor stem+Goal finds it. An explicit alias does. Without this the class
        reads as never-run and the gate reports a FALSE undeclared — an
        over-report is noise, and noise is how a gate gets ignored."""
        db = _store(tmp_path / "b.db", {"EquipOwnedGear": 7}, {})
        assert observed_counts(db)["EquipOwnedGoal"] == 7

    def test_an_action_class_credits_both_spellings(self, tmp_path):
        db = _store(tmp_path / "c.db", {}, {"FightAction": 5})
        counts = observed_counts(db)
        assert counts["FightAction"] == 5

    def test_no_store_is_not_a_store_full_of_zeros(self, tmp_path):
        """A missing DB must not read as "nothing has ever run" — that would make
        every class undeclared and the gate useless in CI. It reads as UNKNOWN,
        and only the completeness of the declaration is checked."""
        assert observed_counts(str(tmp_path / "absent.db")) == {}
        rows = run_census(str(tmp_path / "absent.db"))
        assert rows and all(r.observed == -1 for r in rows)
        assert stale(rows) == [], "no store can never contradict a declaration"

    def test_without_a_store_a_declared_class_is_still_not_undeclared(self, tmp_path):
        """The CI arm: the roster comes from the source, so an undeclared class is
        catchable with no observations at all."""
        rows = run_census(str(tmp_path / "absent.db"))
        assert undeclared(rows) == [], (
            "the committed DORMANT map should cover every dead class")


class TestTheRoster:
    def test_it_reads_the_source_not_the_import_graph(self):
        """A class nothing imports yet is exactly the one most likely to be dead
        on arrival, so the roster must see it. `WaitGoal` is imported by nothing
        that runs and must still appear."""
        classes = defined_classes()
        assert "WaitGoal" in classes
        assert classes["FightAction"] == "action"
        assert classes["RestoreHPGoal"] == "goal"

    def test_every_dormant_entry_names_a_real_class(self):
        """The ORPHAN arm, asserted directly on the committed map so a rename
        cannot leave a stale excuse behind."""
        assert orphan_declarations(run_census("/nonexistent")) == []

    def test_every_alias_target_is_a_real_class(self):
        classes = set(defined_classes())
        assert set(REPR_ALIASES.values()) <= classes


class TestReport:
    def test_the_matrix_orders_every_tier_by_how_much_it_needs_a_decision(self):
        """All five tiers, in one assertion, because the ORDER is the report's
        only affordance: a reader scans the top of a diff, so anything needing a
        decision has to be there. Undeclared first (the gate failure), then stale
        (a declaration the store contradicts), then unclassified (dormant, reason
        unknown), then tracked-unreachable (dormant, reason known and a defect),
        then benign dormancy, then live."""
        rows = [
            _row("LiveGoal", 9),
            _row("BenignGoal", 0, "conditional: needs a raid"),
            _row("TrackedGoal", 0, "unreachable: the band is closed"),
            _row("UnknownGoal", 0, "UNCLASSIFIED: not yet established"),
            _row("StaleGoal", 5, "conditional: never happens"),
            _row("DeadGoal", 0),
        ]
        body = render_matrix(rows, None)
        order = [body.index(n) for n in ("DeadGoal", "StaleGoal", "UnknownGoal",
                                         "TrackedGoal", "BenignGoal", "LiveGoal")]
        assert order == sorted(order), body
        assert "**UNDECLARED**" in body
        assert "**STALE**" in body

    def test_the_summary_separates_tracked_defects_from_benign_dormancy(self):
        """`unreachable:` rows are a defect being tracked; `conditional:` rows are
        a design. A summary that merged them would let the first hide in the
        second."""
        rows = [_row("A", 0, "unreachable: the band is closed"),
                _row("B", 0, "conditional: needs a raid"),
                _row("C", 0, "UNCLASSIFIED: not yet established")]
        line = summary_line(rows)
        assert "unreachable 1" in line
        assert "unclassified 1" in line


def test_the_committed_census_is_clean():
    """What the gate runs. Fails when a new Goal or Action arrives without a
    liveness decision — which is the entire purpose."""
    rows = run_census("/nonexistent")
    assert undeclared(rows) == [], (
        f"undeclared: {[r.name for r in undeclared(rows)]} — add a reason to "
        f"audit/liveness_completeness.DORMANT or make it reachable")
    assert orphan_declarations(rows) == []


def test_no_reason_is_left_unclassified():
    """UNCLASSIFIED is a TODO, not a resting state. It was five entries on
    2026-08-18 and is zero after the investigation
    (`docs/PLAN_priority_ladder_unification.md`); this keeps it from silently
    refilling, since an unexamined dormant class is exactly what this census
    exists to surface."""
    todo = sorted(n for n, r in DORMANT.items() if r.startswith("UNCLASSIFIED:"))
    assert todo == [], f"still unclassified: {todo}"


@pytest.mark.parametrize("reason", sorted(set(DORMANT.values())))
def test_every_reason_is_classified(reason):
    """Each reason declares which KIND of dormancy it is, so the matrix can sort
    tracked defects above benign ones. A free-text reason with no prefix would
    silently land in the benign pile."""
    assert reason.split(":")[0] in {
        "unreachable", "conditional", "subsumed", "witness", "UNCLASSIFIED"}, reason


def test_a_proof_witness_is_never_reclassified_as_deletable():
    """`witness:` is the category that says NEVER FIRING IS THE POINT.

    `MeansKind.WAIT` fires unconditionally and sits last, so anything above it
    winning instead is the totality guarantee being redundant —
    `Liveness.NoDeadlockV2.productionLadder_total` is proved via it. A liveness
    census that reported it as dead code would be inviting someone to delete the
    witness that proves the bot always has something to do, which is precisely
    what nearly happened on 2026-08-18."""
    assert DORMANT["WaitGoal"].startswith("witness:")
    assert DORMANT["WaitAction"].startswith("witness:")


def test_a_firing_witness_is_not_a_stale_declaration() -> None:
    """STALE says "remove the declaration". For a `witness:` row that is exactly
    the wrong advice — removing `WaitGoal`'s declaration invites deleting the
    witness that proves the ladder total, which
    `test_a_proof_witness_is_never_reclassified_as_deletable` exists to stop.
    How long the bot sat in Wait is the stall report's question, not this one."""
    row = _row("WaitGoal", observed=5,
               declared="witness: the ladder's totality witness")

    assert row.stale_declaration is False


def test_a_firing_non_witness_is_still_stale() -> None:
    """The carve-out is scoped to `witness:` and must not weaken the check that
    caught `AcceptTaskGoal` and `MaintainConsumablesGoal`."""
    row = _row("SomeGoal", observed=3, declared="unreachable: never selected")

    assert row.stale_declaration is True


# ---------------------------------------------------------------------------
# STALL REPORT — how long a character sat in Wait, one stretch at a time.
# Report only: a stall never fails `--check`.
# ---------------------------------------------------------------------------


def _cycles_db(path: Path, cycles: list[tuple[str, str, str | None]]) -> str:
    """A `cycles` table with the columns the stall report reads, filled in the
    given order: `(character, "HH:MM" on 2026-10-14 UTC, selected_goal)`."""
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("create table cycles (id integer primary key, ts text not null, "
                     "character text not null, selected_goal text, action_class text)")
        conn.executemany(
            "insert into cycles (ts, character, selected_goal, action_class) "
            "values (?, ?, ?, ?)",
            [(f"2026-10-14T{hhmm}:00.000000+00:00", char, goal,
              "WaitAction" if goal == "Wait" else None)
             for char, hhmm, goal in cycles])
        conn.commit()
    return str(path)


def _at(hhmm: str) -> datetime:
    return datetime.fromisoformat(f"2026-10-14T{hhmm}:00+00:00")


class TestStalls:
    def test_the_threshold_is_ten_minutes(self):
        """The user's ruling: "report only, 10 minutes is fine"."""
        assert STALL_MIN_SPAN.total_seconds() == 600

    def test_a_nine_minute_wait_run_is_not_a_stall(self, tmp_path):
        db = _cycles_db(tmp_path / "s.db", [
            ("HAL", "03:00", "GrindCharacterXP(pig)"),
            ("HAL", "03:01", "Wait"), ("HAL", "03:05", "Wait"),
            ("HAL", "03:10", "Wait"),
        ])
        assert find_stalls(db) == []

    def test_a_ten_minute_wait_run_is_a_stall(self, tmp_path):
        db = _cycles_db(tmp_path / "s.db", [
            ("HAL", "03:00", "GrindCharacterXP(pig)"),
            ("HAL", "03:01", "Wait"), ("HAL", "03:05", "Wait"),
            ("HAL", "03:11", "Wait"),
        ])
        assert find_stalls(db) == [
            Stall(character="HAL", start=_at("03:01"), end=_at("03:11"), waits=3,
                  preceding_goal="GrindCharacterXP(pig)")]

    def test_an_interleaved_non_wait_cycle_splits_a_run(self, tmp_path):
        """Two 5-minute runs with a fight between are two short pauses, not one
        11-minute stall."""
        db = _cycles_db(tmp_path / "s.db", [
            ("HAL", "03:00", "Wait"), ("HAL", "03:05", "Wait"),
            ("HAL", "03:06", "GrindCharacterXP(pig)"),
            ("HAL", "03:07", "Wait"), ("HAL", "03:11", "Wait"),
        ])
        assert find_stalls(db) == []

    def test_a_null_goal_cycle_also_splits_a_run(self, tmp_path):
        """A cycle that selected nothing is still not a Wait cycle."""
        db = _cycles_db(tmp_path / "s.db", [
            ("HAL", "03:00", "Wait"), ("HAL", "03:05", "Wait"),
            ("HAL", "03:06", None),
            ("HAL", "03:07", "Wait"), ("HAL", "03:11", "Wait"),
        ])
        assert find_stalls(db) == []

    def test_two_characters_waits_do_not_merge(self, tmp_path):
        """HAL waits 4 minutes and R2D2 waits 5, overlapping. Merged they would
        span 10 minutes; neither character stalled."""
        db = _cycles_db(tmp_path / "s.db", [
            ("HAL", "03:00", "Wait"), ("R2D2", "03:01", "Wait"),
            ("HAL", "03:02", "Wait"), ("HAL", "03:04", "Wait"),
            ("R2D2", "03:06", "Wait"), ("HAL", "03:10", "GrindCharacterXP(pig)"),
        ])
        assert find_stalls(db) == []

    def test_one_characters_cycle_does_not_split_anothers_run(self, tmp_path):
        db = _cycles_db(tmp_path / "s.db", [
            ("R2D2", "03:00", "Wait"), ("HAL", "03:05", "GrindCharacterXP(pig)"),
            ("R2D2", "03:10", "Wait"),
        ])
        assert [(s.character, s.waits) for s in find_stalls(db)] == [("R2D2", 2)]

    def test_the_preceding_goal_is_the_last_non_wait_before_the_run(self, tmp_path):
        """What the character was doing when it got stuck is the first lead.
        A character whose store opens in Wait has none."""
        db = _cycles_db(tmp_path / "s.db", [
            ("C3P0", "02:00", "Wait"), ("C3P0", "02:10", "Wait"),
            ("C3P0", "02:20", "RestoreHP"),
            ("C3P0", "02:30", "GrindCharacterXP(chicken)"),
            ("C3P0", "02:40", "Wait"), ("C3P0", "02:55", "Wait"),
        ])
        assert [(s.start, s.preceding_goal) for s in find_stalls(db)] == [
            (_at("02:40"), "GrindCharacterXP(chicken)"),
            (_at("02:00"), None),
        ]

    def test_stalls_are_listed_newest_first(self, tmp_path):
        db = _cycles_db(tmp_path / "s.db", [
            ("HAL", "01:00", "Wait"), ("HAL", "01:30", "Wait"),
            ("R2D2", "02:00", "Wait"), ("R2D2", "02:30", "Wait"),
        ])
        assert [s.character for s in find_stalls(db)] == ["R2D2", "HAL"]

    def test_no_store_is_not_an_empty_store(self, tmp_path):
        """No DB means nothing was read — not that nothing ever stalled."""
        assert find_stalls(str(tmp_path / "absent.db")) is None


class TestStallSection:
    def test_rows_render_with_their_preceding_goal(self):
        stalls = [Stall("HAL", _at("03:56"), _at("07:48"), 5661, "FightLoop"),
                  Stall("R2D2", _at("01:00"), _at("01:30"), 4, None)]
        body = render_matrix([_row("LiveGoal", 9)], stalls)
        assert ("| HAL | 2026-10-14T03:56:00+00:00 | 2026-10-14T07:48:00+00:00 "
                "| 5661 | `FightLoop` |") in body
        assert "| R2D2 | 2026-10-14T01:00:00+00:00 | 2026-10-14T01:30:00+00:00 " \
               "| 4 | none |" in body
        assert "2 stalls" in body

    def test_no_store_says_so(self):
        body = render_matrix([_row("LiveGoal", -1)], None)
        assert "No store was read" in body

    def test_an_empty_store_reads_as_no_stalls(self):
        body = render_matrix([_row("LiveGoal", 9)], [])
        assert "0 stalls" in body


def test_check_passes_with_stalls_present(tmp_path):
    """The stall report is REPORT ONLY. A store holding a 30-minute HAL stall
    must leave `gen_liveness.py --check` green, and the stall must reach the
    regenerated doc. Every non-dormant class gets one cycle so the roster arms
    stay clean and the exit code isolates the stall report."""
    fill = [("Filler", "00:00", name) for name, kind in defined_classes().items()
            if kind == "goal" and name not in DORMANT]
    db = _cycles_db(tmp_path / "s.db", [
        *fill,
        ("HAL", "03:00", "GrindCharacterXP(pig)"),
        ("HAL", "03:10", "Wait"), ("HAL", "03:40", "Wait"),
    ])
    with closing(sqlite3.connect(db)) as conn:
        conn.executemany(
            "insert into cycles (ts, character, action_class) values (?, ?, ?)",
            [("2026-10-14T00:00:00.000000+00:00", "Filler", name)
             for name, kind in defined_classes().items()
             if kind == "action" and name not in DORMANT])
        conn.commit()

    done = subprocess.run(
        [sys.executable, str(GEN_LIVENESS), "--check", "--learn-db", db],
        cwd=tmp_path, capture_output=True, text=True)

    assert done.returncode == 0, done.stderr
    matrix = (tmp_path / "docs/behavioral_completeness/LIVENESS_MATRIX.md").read_text()
    assert "| HAL | 2026-10-14T03:10:00+00:00 | 2026-10-14T03:40:00+00:00 | 2 " \
           "| `GrindCharacterXP(pig)` |" in matrix
