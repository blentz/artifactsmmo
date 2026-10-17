"""Pure core: rest before a fight, or fight now.

A fight's KILL SECONDS from some HP is the expected time to one kill and back
to full HP. Each try costs the fight, the rest back to full from where it ends
(a loss ends at 1 HP) and, on a loss, the walk back; tries repeat until one
wins, so the expectation is a try's mean cost over P(win) (renewal-reward, the
loop rate's own rule: `loop_rate_core.expected_xp_per_second`).

Resting first costs the rest of what is missing now, then the kill seconds
from full. It is the better choice exactly when

    rest_seconds + kill_seconds(full) < kill_seconds(now).

A tie fights now: a sure win costs the same seconds either way (one second per
percent rested, before or after), so the rest would buy nothing.

The fight gates' θ (`combat.predict_win`) asks another question: whether the
fight beats not fighting at all. So a fight can clear θ and still cost more
than resting for it: R2D2 v king_slime at 452/890 HP, 2026-10-17, P 0.633
against θ 0.552, about 211 s a kill against a 52 s rest and 86 s from full."""

from fractions import Fraction


def kill_seconds(p_win: Fraction, try_seconds: Fraction) -> Fraction | None:
    """Expected seconds to one kill when each try costs `try_seconds` and wins
    with probability `p_win`; None when the fight cannot be won."""
    if not 0 <= p_win <= 1 or try_seconds < 0:
        raise ValueError(f"p_win {p_win} or try_seconds {try_seconds} out of range")
    return None if p_win == 0 else try_seconds / p_win


def rest_first(rest_seconds: int, now: Fraction | None, full: Fraction | None) -> bool:
    """Rest before the fight: it wins from full (`full` is not None) and either
    loses now or costs more now than the rest and the fight from full. A fight
    full HP loses is a gear question, never a rest."""
    if full is None:
        return False
    return now is None or rest_seconds + full < now
