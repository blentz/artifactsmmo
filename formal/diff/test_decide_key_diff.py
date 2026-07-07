"""Differential test: the dispatcher repr maps must round-trip through every
enum variant — matching the Lean total-`match` exhaustiveness proof
(`formal/Formal/DecideKey.lean::goalReprOfGuard` / `goalReprOfMeans`).

These bind the LIVE `strategy_driver.py` dispatchers `map_guard` / `map_means`:
the repr of the Goal each enum variant dispatches to is a pure function of the
kind, extracted into `decide_key.py`, and the Lean compiler enforces total
coverage over the mirrored inductives at elaboration time.

(The flat scalar ranking's `decide_key` sort-tuple comparator that used to
share this harness was retired with the flat ranking in progression-tree
Phase 4b.)
"""
from artifactsmmo_cli.ai.tiers.decide_key import (
    goal_repr_of_guard,
    goal_repr_of_means,
)
from artifactsmmo_cli.ai.tiers.guards import GuardKind
from artifactsmmo_cli.ai.tiers.means import MeansKind
from formal.diff.oracle_client import run_oracle

# --- Dispatcher exhaustiveness ---------------------------------------------

# Order of the inductive cases in Lean's `goalReprOfGuard` (matches the indices
# the oracle uses, see Oracle.lean::runDecideKey).
_GUARD_INDEX = {
    GuardKind.HP_CRITICAL: 0,
    GuardKind.BANK_UNLOCK: 1,
    GuardKind.REACH_UNLOCK_LEVEL: 2,
    GuardKind.DISCARD_CRITICAL: 3,
    GuardKind.CRAFT_RELIEF: 4,
    GuardKind.DEPOSIT_FULL: 5,
    GuardKind.DISCARD_HIGH: 6,
    GuardKind.REST_FOR_COMBAT: 7,
    GuardKind.GEAR_REVIEW: 8,
    GuardKind.RECYCLE_RELIEF: 9,
    GuardKind.SELL_RELIEF: 10,
    GuardKind.CRAFT_POTIONS: 11,
}

_MEANS_INDEX = {
    MeansKind.CLAIM_PENDING: 0,
    MeansKind.COMPLETE_TASK: 1,
    MeansKind.SELL_PRESSURED: 2,
    MeansKind.LOW_YIELD_CANCEL: 3,
    MeansKind.TASK_CANCEL: 4,
    MeansKind.PURSUE_TASK: 5,
    MeansKind.ACCEPT_TASK: 6,
    MeansKind.TASK_EXCHANGE: 7,
    MeansKind.SELL_IDLE: 8,
    MeansKind.RECYCLE_SURPLUS: 9,  # 2026-06-14: proactive recycle surplus gear.
    MeansKind.BANK_EXPAND: 10,
    MeansKind.WAIT: 11,  # Phase 20e-v2 step 1: always-firing sentinel.
    MeansKind.MAINTAIN_CONSUMABLES: 12,  # PLAN #6a: cook/brew heals (combat-active).
    MeansKind.DRAIN_BANK_JUNK: 13,  # 2026-06-24: drain over-cap bank junk.
}


def test_every_guard_kind_dispatches_to_lean_repr() -> None:
    """Every `GuardKind` variant produces a non-empty repr from BOTH sides,
    and they match. This is the Prop-level read-back of the Lean total-match
    exhaustiveness guarantee — no `raise ValueError` fall-through is reachable
    on either side."""
    for kind, idx in _GUARD_INDEX.items():
        py = goal_repr_of_guard(kind)
        lean = run_oracle("decide_key", [[1, idx]])[0]["repr"]
        assert py == lean, f"{kind}: py={py} lean={lean}"
        assert py  # non-empty


def test_every_means_kind_dispatches_to_lean_repr() -> None:
    """Every `MeansKind` variant produces a non-empty repr from BOTH sides,
    and they match. Total dispatcher contract."""
    for kind, idx in _MEANS_INDEX.items():
        py = goal_repr_of_means(kind)
        lean = run_oracle("decide_key", [[2, idx]])[0]["repr"]
        assert py == lean, f"{kind}: py={py} lean={lean}"
        assert py  # non-empty


def test_enum_coverage_complete() -> None:
    """No GuardKind / MeansKind variant left out. If a new variant is added,
    this test fails immediately — the SAME static check the Lean compiler
    enforces on `goalReprOfGuard` / `goalReprOfMeans`."""
    assert set(_GUARD_INDEX.keys()) == set(GuardKind)
    assert set(_MEANS_INDEX.keys()) == set(MeansKind)
