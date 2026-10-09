"""What a fight's learned loss rate adds to the price of one win
(`docs/PLAN_loss_risk.md`, proved in `Formal.LossRisk`).

USER 2026-10-08, "Price the loss risk": a drop or grind fight's cost includes
its learned loss rate. Expected fights per win is `1/p`; each loss is charged
its death plus recovery.

With `p = wins / samples` the expected LOSSES per win are `1/p - 1 =
(samples - wins) / wins`, so the surcharge per win is that times the cost of
one loss. Below `min_samples` fights there is no evidence and the surcharge is
zero — the same warmup the learned-loss veto (`combat.is_winnable`) applies, so
a cold fight is priced by the prediction alone. `wins = 0` past the warmup is
the veto's territory and never priced in production; it is charged every loss
against one win so the function stays total.

Exact arithmetic: the result is `losses * cost_num / (max(wins, 1) * cost_den)`.
"""

from fractions import Fraction


def loss_surcharge(samples: int, wins: int, min_samples: int,
                   cost_num: int, cost_den: int) -> Fraction:
    """Fight-equivalents the expected losses add to one win."""
    if samples < min_samples:
        return Fraction(0)
    losses = max(samples - wins, 0)
    return Fraction(losses * cost_num, max(wins, 1) * cost_den)
