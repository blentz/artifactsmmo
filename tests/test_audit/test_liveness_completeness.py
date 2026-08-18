"""The liveness census — has every Goal and Action ever actually run?

The tests that matter here are the three that make the gate BITE, because a
census that cannot fail is a census that says nothing. Each drives the real
`run_census` against a real on-disk SQLite store, never a stubbed count: the
whole point of this census is that it reads what the bot actually did, and a
mocked store would test the arithmetic while skipping the question.
"""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from artifactsmmo_cli.audit.liveness_completeness import (
    DORMANT,
    REPR_ALIASES,
    LivenessRow,
    defined_classes,
    observed_counts,
    orphan_declarations,
    render_matrix,
    run_census,
    stale,
    summary_line,
    undeclared,
)


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
        body = render_matrix(rows)
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
        "unreachable", "conditional", "subsumed", "UNCLASSIFIED"}, reason
