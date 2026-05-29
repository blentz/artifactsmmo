"""Pure warm-up gate helpers extracted from `LearningStore`.

The `LearningStore` median/success-rate functions both gate on a minimum
sample count (`len(rows) >= 5`) before computing the aggregate. Below the
gate they return a documented default (`None` for the median, `1.0` for
success rate). Extracting the gate to pure helpers lets the contract be
modeled and pinned formally without coupling to SQLAlchemy.

These helpers are imported and applied inside `store.py` at the call sites
that already performed the gating inline.
"""

import statistics

WARMUP_MIN_SAMPLES = 5
"""Number of recent samples required before a learned estimate is trusted."""


def warmup_gated_median(samples: list[float]) -> float | None:
    """Return median of `samples` when at least WARMUP_MIN_SAMPLES are present;
    otherwise return None (the documented warm-up default)."""
    if len(samples) < WARMUP_MIN_SAMPLES:
        return None
    return statistics.median(samples)


def warmup_gated_success_rate(outcomes: list[str], ok_label: str = "ok") -> float:
    """Return the fraction of `outcomes` equal to `ok_label` when at least
    WARMUP_MIN_SAMPLES are present; otherwise return 1.0 (the warm-up default —
    treat unknown actions as fully reliable to avoid starving the planner)."""
    if len(outcomes) < WARMUP_MIN_SAMPLES:
        return 1.0
    return sum(1 for o in outcomes if o == ok_label) / len(outcomes)
