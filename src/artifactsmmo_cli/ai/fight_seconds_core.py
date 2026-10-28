"""Pure core: the seconds a fight costs, from its length (spec 2026-10-18 §2.9).

The server's fight cooldown grows with the fight's TURNS and shrinks with the
fighter's HASTE, above a minimum. So a fight's seconds are

    fight_seconds = max(floor, turns × s_turn × (1 − h·haste))

`s_turn` (seconds per turn), `h` (the share of a turn one point of haste
removes) and `floor` (the minimum cooldown) are learned from observed fights
(`fit`), never assumed. A flat seconds-per-fight made kill speed invisible to
every rate: a faster-killing piece could not pay.

Proved in `Formal.FightSeconds` (monotone in turns, antitone in haste for
`h ≥ 0`, never below the floor) and diffed by
`formal/diff/test_fight_seconds_diff.py`.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from fractions import Fraction

from artifactsmmo_cli.ai.fight_terms_core import MAX_TURNS


def fight_seconds(turns: Fraction, s_turn: Fraction, h: Fraction, haste: int,
                  floor: Fraction) -> Fraction:
    """`max(floor, turns × s_turn × (1 − h·haste))`. A haste whose effect would
    remove the whole fight leaves the floor."""
    if turns < 0 or s_turn < 0 or not 0 <= h < 1 or haste < 0 or floor < 0:
        raise ValueError(f"fight_seconds out of range: turns {turns}, s_turn {s_turn}, "
                         f"h {h}, haste {haste}, floor {floor}")
    return max(floor, turns * s_turn * (1 - h * haste))


def server_turns(rounds: int, win: bool, player_first: bool) -> int:
    """The server's `fight.turns` of a fight the combat model ends in round
    `rounds` (each round is one turn of each side; the server counts each
    side's turn). A win ends on the player's turn and a loss on the monster's,
    so the side that moves first ends its own round one turn early. A fight
    that never started (round 0) has no turns."""
    if rounds <= 0:
        return 0
    ends_on_first_mover = win == player_first
    return 2 * rounds - (1 if ends_on_first_mover else 0)


def expected_turns(endings: Sequence[tuple[Fraction, bool, int]], player_first: bool) -> Fraction:
    """The probability-weighted mean of `server_turns` over a fight's
    `(prob, win, rounds)` endings, capped at `MAX_TURNS`."""
    total = sum((prob * server_turns(rounds, win, player_first)
                 for prob, win, rounds in endings), Fraction(0))
    return min(Fraction(MAX_TURNS), total)


@dataclass(frozen=True)
class FightSecondsModel:
    """`(s_turn, h, floor)` fitted to `samples` observed fights.
    `haste_identified` is False when every observation had the same haste: `h`
    is then 0 and `s_turn` the seconds per turn at that haste."""

    s_turn: Fraction
    h: Fraction
    floor: Fraction
    haste_identified: bool
    samples: int

    def seconds(self, turns: Fraction, haste: int) -> Fraction:
        """A fight's seconds at `turns` (expected) for a fighter with `haste`."""
        return fight_seconds(turns, self.s_turn, self.h, haste, self.floor)


@dataclass(frozen=True)
class FitSums:
    """The sufficient statistics of `fit` over the fights folded in so far:
    the least-squares sums, the least cooldown, the hastes seen and the count
    of fights kept (a positive cooldown). Exact (`Fraction`) and independent of
    the order fights are folded in, so a fold of new fights into old sums is
    the sums of all of them: an incremental fit equals a cold one."""

    kept: int
    s11: Fraction
    s12: Fraction
    s22: Fraction
    y1: Fraction
    y2: Fraction
    floor: Fraction | None
    hastes: frozenset[int]


NO_FIGHTS = FitSums(0, Fraction(0), Fraction(0), Fraction(0), Fraction(0), Fraction(0), None,
                    frozenset())
"""The sums of no fight."""


def fit_sums(samples: Iterable[tuple[int, int, float]], sums: FitSums = NO_FIGHTS) -> FitSums:
    """`sums` with the `(turns, haste, cooldown)` fights of `samples` folded
    in. A cooldown of 0 or less is no observation of a fight's length (a
    refused or simulated action) and is dropped; a kept fight with negative
    turns or haste raises."""
    kept = [(turns, haste, Fraction(cooldown)) for turns, haste, cooldown in samples
            if cooldown > 0]
    if any(turns < 0 or haste < 0 for turns, haste, _ in kept):
        raise ValueError("a fight with negative turns or haste")
    if not kept:
        return sums
    least = min(c for _, _, c in kept)
    return FitSums(
        sums.kept + len(kept),
        sums.s11 + sum((Fraction(t * t) for t, _, _ in kept), Fraction(0)),
        sums.s12 + sum((Fraction(t * t * a) for t, a, _ in kept), Fraction(0)),
        sums.s22 + sum((Fraction(t * t * a * a) for t, a, _ in kept), Fraction(0)),
        sums.y1 + sum((t * c for t, _, c in kept), Fraction(0)),
        sums.y2 + sum((t * a * c for t, a, c in kept), Fraction(0)),
        least if sums.floor is None else min(sums.floor, least),
        sums.hastes | {a for _, a, _ in kept})


def solve(sums: FitSums) -> tuple[Fraction, Fraction, Fraction]:
    """`(s_turn, h, floor)` from the sums of the observed fights.

    Least squares on `cooldown ≈ a·turns + b·(turns·haste)`, through the origin,
    gives `s_turn = a` and `h = −b / a`. When the haste never varies the two
    terms cannot be told apart: `h` is 0 and `s_turn` is the one-term fit, the
    seconds per turn AT that haste. A fitted `h` below 0 (haste that slows a
    fight) is clamped to 0, refitting `s_turn` alone. No positive cooldowns
    give an `h` of 1 or more (the fit would predict a fight of no seconds at
    one point of haste); `fight_seconds` refuses one at use. No observations at
    all raise. `floor` is the least observed cooldown."""
    if sums.floor is None:
        raise ValueError("no fight with a positive cooldown to fit fight seconds on")
    s11, s12, s22, y1, y2, floor = sums.s11, sums.s12, sums.s22, sums.y1, sums.y2, sums.floor
    if s11 == 0:
        raise ValueError("every observed fight has 0 turns")
    det = s11 * s22 - s12 * s12
    if det == 0:
        return y1 / s11, Fraction(0), floor
    a = (y1 * s22 - y2 * s12) / det
    b = (s11 * y2 - s12 * y1) / det
    if a <= 0:
        raise ValueError(f"fitted seconds per turn {a} is not positive")
    h = -b / a
    if h < 0:
        return y1 / s11, Fraction(0), floor
    return a, h, floor


def fit(samples: Sequence[tuple[int, int, float]]) -> tuple[Fraction, Fraction, Fraction]:
    """`(s_turn, h, floor)` fitted to observed `(turns, haste, cooldown)`
    fights: `solve` of their `fit_sums`."""
    return solve(fit_sums(samples))
