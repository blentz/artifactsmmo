"""FightScreen list/detail behaviour — pure logic, no running app."""

from artifactsmmo_cli.ai.fight_record import FightRecord
from artifactsmmo_cli.tui.screens.fight_screen import FightScreen


def make_record(started_at="2026-07-27T23:30:30.455000", **overrides) -> FightRecord:
    base = dict(
        started_at=started_at, result="win", turns=27, opponent="mushmush",
        logs=("Fight start: Robby HP: 485/485 vs Mushmush HP: 350/350",),
        hp_before=485, hp_after=275, xp=45, gold=12, drops=(),
    )
    base.update(overrides)
    return FightRecord(**base)


class TestOrdering:
    def test_records_are_newest_first(self):
        older = make_record("2026-07-27T22:00:00.000000")
        newer = make_record("2026-07-27T23:00:00.000000")

        screen = FightScreen([older, newer], character="Robby")

        assert [r.started_at for r in screen.records] == [
            newer.started_at, older.started_at]


class TestMerge:
    def test_dedupes_on_started_at(self):
        rec = make_record()
        screen = FightScreen([rec], character="Robby")

        screen.merge([make_record(rec.started_at, turns=99)])

        assert len(screen.records) == 1
        assert screen.records[0].turns == 27

    def test_keeps_distinct_fights(self):
        screen = FightScreen([make_record("2026-07-27T23:00:00.000000")],
                             character="Robby")

        screen.merge([make_record("2026-07-27T22:00:00.000000")])

        assert len(screen.records) == 2

    def test_merged_records_are_resorted(self):
        screen = FightScreen([make_record("2026-07-27T22:00:00.000000")],
                             character="Robby")

        screen.merge([make_record("2026-07-27T23:00:00.000000")])

        assert screen.records[0].started_at.startswith("2026-07-27T23:00")

    def test_existing_record_wins_so_session_hp_before_is_not_lost(self):
        """A session capture carries hp_before; the backfilled form cannot."""
        session = make_record(hp_before=485)
        screen = FightScreen([session], character="Robby")

        screen.merge([make_record(session.started_at, hp_before=None)])

        assert screen.records[0].hp_before == 485


class TestSessionBoundary:
    def test_session_records_are_tracked_separately_from_backfilled(self):
        session = make_record("2026-07-27T23:00:00.000000")
        screen = FightScreen([session], character="Robby")

        screen.merge([make_record("2026-07-27T22:00:00.000000")])

        assert screen.session_started_at == session.started_at

    def test_no_session_boundary_when_opened_with_nothing(self):
        assert FightScreen([], character="Robby").session_started_at is None


class TestDetail:
    def test_detail_renders_the_selected_record(self):
        screen = FightScreen([make_record()], character="Robby")

        lines = screen.detail_lines(0)

        assert "mushmush" in lines[0]
        assert any("Fight start" in line for line in lines)

    def test_detail_of_an_empty_list_is_a_placeholder(self):
        screen = FightScreen([], character="Robby")

        assert screen.detail_lines(0) == ["No fights recorded yet."]

    def test_detail_follows_the_index(self):
        screen = FightScreen([make_record("2026-07-27T23:00:00.000000",
                                          opponent="mushmush"),
                              make_record("2026-07-27T22:00:00.000000",
                                          opponent="chicken")],
                             character="Robby")

        assert "chicken" in screen.detail_lines(1)[0]
