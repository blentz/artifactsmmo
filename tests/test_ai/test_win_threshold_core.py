"""The win threshold a fight's measured loss cost implies (spec 2026-10-15
fight-gates-odds §2)."""

from fractions import Fraction

from artifactsmmo_cli.ai.win_threshold_core import FightCostRow, win_thresholds_from_rows


def _fight(monster: str, won: bool, secs: int) -> FightCostRow:
    return ("FightAction", f"Fight({monster})", "ok" if won else "error:fight_lost", secs)


def _rest(secs: int) -> FightCostRow:
    return ("RestAction", "Rest", "ok", secs)


def _move(secs: int) -> FightCostRow:
    return ("MoveAction", "Move(0,0)", "ok", secs)


def _loop(won: list[bool], monster: str = "cyclops", close: bool = True) -> list[FightCostRow]:
    """Each win costs 10 + 50 = 60 s, each loss 10 + 90 + 20 = 120 s; a closing
    fight (whose own window stays open) ends the last one."""
    rows: list[FightCostRow] = []
    for w in won:
        rows += [_fight(monster, w, 10), _rest(50 if w else 90)]
        if not w:
            rows.append(_move(20))
    return [*rows, _fight(monster, True, 10)] if close else rows


def test_theta_is_the_loss_cost_share() -> None:
    assert win_thresholds_from_rows(_loop([True] * 5 + [False] * 5)) == {"cyclops": Fraction(2, 3)}


def test_theta_weights_by_sample_counts() -> None:
    # 10 wins at 60 s and 5 losses at 120 s: means 60 and 120, theta 2/3 still.
    assert win_thresholds_from_rows(_loop([True] * 10 + [False] * 5)) == {"cyclops": Fraction(2, 3)}


def test_fewer_than_five_losses_gives_no_entry() -> None:
    assert win_thresholds_from_rows(_loop([True] * 9 + [False] * 4)) == {}


def test_fewer_than_five_wins_gives_no_entry() -> None:
    # 3 wins in the loop; the closing win's window never closes.
    assert win_thresholds_from_rows(_loop([True] * 3 + [False] * 9)) == {}


def test_window_counts_rest_and_move_only() -> None:
    rows = _loop([True] * 5 + [False] * 5)
    rows.insert(1, ("CraftAction", "Craft(x)", "ok", 999))
    assert win_thresholds_from_rows(rows) == {"cyclops": Fraction(2, 3)}


def test_other_fight_outcomes_are_skipped_and_end_the_window() -> None:
    rows = [("FightAction", "Fight(cyclops)", "error:cooldown", 0), _rest(5000)]
    rows += _loop([True] * 5 + [False] * 5)
    assert win_thresholds_from_rows(rows) == {"cyclops": Fraction(2, 3)}


def test_trailing_open_window_is_skipped() -> None:
    rows = [*_loop([True] * 5 + [False] * 5, close=False), _fight("cyclops", False, 10), _rest(5000)]
    assert win_thresholds_from_rows(rows) == {"cyclops": Fraction(2, 3)}


def test_monsters_are_kept_apart() -> None:
    rows = _loop([True] * 5 + [False] * 5, close=False) + _loop([False] * 5 + [True] * 5, "imp")
    assert win_thresholds_from_rows(rows) == {"cyclops": Fraction(2, 3), "imp": Fraction(2, 3)}


def test_zero_second_fights_are_no_evidence() -> None:
    rows: list[FightCostRow] = []
    for w in [True] * 5 + [False] * 5:
        rows.append(_fight("cyclops", w, 0))
    rows.append(_fight("cyclops", True, 0))
    assert win_thresholds_from_rows(rows) == {}
