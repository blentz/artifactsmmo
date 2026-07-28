"""Pure fight renderers — no Textual app needed."""

from artifactsmmo_cli.ai.fight_record import FightDrop, FightRecord
from artifactsmmo_cli.tui.fight_format import (
    fight_detail_lines,
    fight_row_label,
    fight_summary_line,
)


def make_record(**overrides) -> FightRecord:
    base = dict(
        started_at="2026-07-27T23:30:30.455000",
        result="win",
        turns=27,
        opponent="mushmush",
        logs=(
            "Fight start: Robby HP: 485/485 vs Mushmush HP: 350/350",
            "Turn 13: Robby used fire attack and dealt 18 damage (Critical strike). "
            "Mushmush HP: 188/350",
        ),
        hp_before=485,
        hp_after=275,
        xp=45,
        gold=12,
        drops=(FightDrop(code="mushmush_hat", quantity=1),),
    )
    base.update(overrides)
    return FightRecord(**base)


class TestSummaryLine:
    def test_win_shows_structured_fields(self):
        line = fight_summary_line(make_record())

        assert "win" in line
        assert "27t" in line
        assert "485->275" in line
        assert "xp 45" in line
        assert "gold 12" in line
        assert "mushmush_hat x1" in line

    def test_loss_is_rendered_red(self):
        line = fight_summary_line(make_record(result="loss", hp_after=0))

        assert "[red]loss[/red]" in line

    def test_win_is_rendered_green(self):
        assert "[green]win[/green]" in fight_summary_line(make_record())

    def test_no_drops_omits_the_drops_clause(self):
        assert "drops" not in fight_summary_line(make_record(drops=()))

    def test_multiple_drops_are_all_listed(self):
        line = fight_summary_line(make_record(drops=(
            FightDrop(code="mushmush_hat", quantity=1),
            FightDrop(code="mushroom", quantity=3),
        )))

        assert "mushmush_hat x1" in line
        assert "mushroom x3" in line

    def test_unknown_pre_fight_hp_renders_as_a_question_mark(self):
        """Backfilled records have no starting HP; never invent one."""
        line = fight_summary_line(make_record(hp_before=None))

        assert "?->275" in line
        assert "0->275" not in line


class TestRowLabel:
    def test_includes_result_time_opponent_and_turns(self):
        label = fight_row_label(make_record())

        assert "win" in label
        assert "23:30:30" in label
        assert "mushmush" in label
        assert "27t" in label

    def test_unknown_pre_fight_hp_renders_as_a_question_mark(self):
        assert "?->275" in fight_row_label(make_record(hp_before=None))


class TestDetailLines:
    def test_header_then_verbatim_transcript(self):
        lines = fight_detail_lines(make_record())

        assert "mushmush" in lines[0]
        assert "27" in lines[0]
        assert lines[-1].endswith("Mushmush HP: 188/350")

    def test_transcript_is_not_reformatted(self):
        rec = make_record()

        lines = fight_detail_lines(rec)

        assert rec.logs[0] in "\n".join(lines)

    def test_square_brackets_are_escaped_for_rich_markup(self):
        """RichLog(markup=True) would treat a literal '[' as markup."""
        rec = make_record(logs=("Turn 1: Robby used [special] attack.",))

        joined = "\n".join(fight_detail_lines(rec))

        assert "\\[special]" in joined

    def test_critical_strike_is_emphasised(self):
        joined = "\n".join(fight_detail_lines(make_record()))

        assert "[bold]Critical strike[/bold]" in joined

    def test_blocked_is_emphasised(self):
        rec = make_record(logs=("Turn 2: Mushmush Blocked the attack.",))

        joined = "\n".join(fight_detail_lines(rec))

        assert "[bold]Blocked[/bold]" in joined

    def test_emphasis_is_a_plain_substring_search_that_can_miss(self):
        """No parsing: reworded server text simply renders unemphasised."""
        rec = make_record(logs=("Turn 1: Robby landed a devastating blow.",))

        joined = "\n".join(fight_detail_lines(rec))

        assert "bold" not in joined

    def test_empty_transcript_still_renders_the_header(self):
        lines = fight_detail_lines(make_record(logs=()))

        assert "mushmush" in lines[0]
