"""FightScreen list/detail behaviour — pure logic, no running app."""

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.fight_record import FightRecord
from artifactsmmo_cli.tui.screens.fight_screen import FightScreen


def _snap(**overrides) -> CycleSnapshot:
    base = dict(
        cycle_index=1, timestamp="2026-07-27T23:00:00Z", character="Robby",
        x=0, y=0, level=1, xp=0, max_xp=100, hp=100, max_hp=100, gold=0,
        selected_goal="g", action="Fight(mushmush)", outcome="ok",
    )
    base.update(overrides)
    return CycleSnapshot(**base)


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
    def test_the_boundary_is_the_oldest_session_record(self):
        oldest = make_record("2026-07-27T22:00:00.000000")
        screen = FightScreen([make_record("2026-07-27T23:00:00.000000"), oldest],
                             character="Robby")

        assert screen.session_floor == oldest.instant

    def test_merging_backfill_does_not_lower_the_boundary(self):
        """Only fights this session WATCHED move the floor; server history
        below it must not be mistaken for session-captured."""
        session = make_record("2026-07-27T23:00:00.000000")
        screen = FightScreen([session], character="Robby")

        screen.merge([make_record("2026-07-27T22:00:00.000000")])

        assert screen.session_floor == session.instant

    def test_no_session_boundary_when_opened_with_nothing(self):
        assert FightScreen([], character="Robby").session_floor is None


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


class TestBackfill:
    def test_load_older_merges_fetched_records(self):
        fetched = [make_record("2026-07-27T22:00:00.000000")]
        screen = FightScreen([make_record("2026-07-27T23:00:00.000000")],
                             character="Robby", fetch_older=lambda page: fetched)

        screen.load_older_sync()

        assert len(screen.records) == 2

    def test_load_older_advances_the_page(self):
        pages = []

        def fetch(page):
            pages.append(page)
            return [make_record(f"2026-07-27T2{page}:00:00.000000")]

        screen = FightScreen([], character="Robby", fetch_older=fetch)

        screen.load_older_sync()
        screen.load_older_sync()

        assert pages == [1, 2]

    def test_load_older_without_a_fetcher_is_inert(self):
        screen = FightScreen([make_record()], character="Robby")

        screen.load_older_sync()

        assert len(screen.records) == 1

    def test_status_reports_an_empty_page(self):
        screen = FightScreen([], character="Robby", fetch_older=lambda page: [])

        screen.load_older_sync()

        assert "no older" in screen.status_text.lower()

    def test_status_distinguishes_a_failed_request_from_an_empty_one(self):
        """An empty result and a failed request must not look the same."""
        def boom(page):
            raise RuntimeError("HTTP 500")

        screen = FightScreen([], character="Robby", fetch_older=boom)

        screen.load_older_sync()

        assert "HTTP 500" in screen.status_text
        assert "no older" not in screen.status_text.lower()

    def test_a_failed_request_does_not_advance_the_page(self):
        """Pressing 'm' again must retry the same page, not skip it."""
        attempts = []

        def flaky(page):
            attempts.append(page)
            raise RuntimeError("HTTP 500")

        screen = FightScreen([], character="Robby", fetch_older=flaky)

        screen.load_older_sync()
        screen.load_older_sync()

        assert attempts == [1, 1]

    def test_status_reports_how_many_were_added(self):
        screen = FightScreen([], character="Robby",
                             fetch_older=lambda page: [make_record()])

        screen.load_older_sync()

        assert "1" in screen.status_text


class TestLiveUpdate:
    def test_a_non_fight_snapshot_is_ignored(self):
        screen = FightScreen([make_record()], character="Robby")

        screen.update_snapshot(_snap())

        assert len(screen.records) == 1

    def test_a_fight_snapshot_is_merged(self):
        screen = FightScreen([], character="Robby")
        rec = make_record("2026-07-27T23:00:00.000000")

        screen.update_snapshot(_snap(fight=rec))

        assert screen.records == [rec]
        assert screen.session_floor == rec.instant


class TestSessionFloor:
    """No exact cross-source key exists (the two endpoints stamp the same fight
    ~66 ms apart), so overlap is prevented STRUCTURALLY instead of matched
    heuristically: backfill only reaches fights older than the oldest fight this
    session watched."""

    def test_backfill_drops_anything_at_or_newer_than_the_session_floor(self):
        session = [make_record("2026-07-28T14:00:00.000000"),
                   make_record("2026-07-28T15:00:00.000000")]
        # the server's stamp for the SAME 14:00 fight, ~66ms off and tz-aware
        twin = make_record("2026-07-28T14:00:00.066000+00:00")
        newer = make_record("2026-07-28T16:00:00.000000+00:00")
        older = make_record("2026-07-28T13:00:00.000000")
        screen = FightScreen(session, character="Robby",
                             fetch_older=lambda page: [twin, newer, older])

        screen.load_older_sync()

        assert len(screen.records) == 3          # 2 session + only the older one
        assert screen.records[-1].started_at == older.started_at

    def test_the_floor_is_the_oldest_session_fight_not_the_newest(self):
        screen = FightScreen([make_record("2026-07-28T15:00:00.000000"),
                              make_record("2026-07-28T14:00:00.000000")],
                             character="Robby")

        assert screen.session_floor == make_record("2026-07-28T14:00:00.000000").instant

    def test_no_session_fights_means_backfill_is_unrestricted(self):
        screen = FightScreen([], character="Robby",
                             fetch_older=lambda page: [make_record()])

        screen.load_older_sync()

        assert len(screen.records) == 1

    def test_a_fight_arriving_live_establishes_the_floor(self):
        screen = FightScreen([], character="Robby",
                             fetch_older=lambda page: [make_record("2026-07-28T16:00:00.000000")])
        screen.update_snapshot(_snap(fight=make_record("2026-07-28T15:00:00.000000")))

        screen.load_older_sync()

        assert len(screen.records) == 1          # the 16:00 backfill is newer, dropped

    def test_skipped_backfill_is_reported_never_silent(self):
        screen = FightScreen([make_record("2026-07-28T14:00:00.000000")],
                             character="Robby",
                             fetch_older=lambda page: [
                                 make_record("2026-07-28T15:00:00.000000"),
                                 make_record("2026-07-28T13:00:00.000000")])

        screen.load_older_sync()

        assert "1" in screen.status_text and "skipped" in screen.status_text.lower()

    def test_rows_are_ordered_by_instant_across_the_tz_boundary(self):
        screen = FightScreen([make_record("2026-07-28T15:00:00.000000+00:00")],
                             character="Robby",
                             fetch_older=lambda page: [make_record("2026-07-28T14:00:00.000000")])

        screen.load_older_sync()

        assert [r.instant.hour for r in screen.records] == [15, 14]
