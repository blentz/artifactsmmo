"""Pure cores for the strategy decision layer's sort and dispatcher routing.

Two related extractions:

1. `decide_key`: the tuple Python `decide` (in `strategy.py`) sorts candidates
   by — `(-final, effort, root_repr)`. The lexicographic comparator over this
   tuple is the property we lock with `formal/Formal/DecideKey.lean`. Distinct
   candidate roots have distinct reprs, so the comparator is a strict total
   order on production inputs (the third field is the final tiebreak).

2. `goal_repr_of_guard` / `goal_repr_of_means`: the `repr` strings the driver's
   `map_guard` / `map_means` dispatchers produce per enum variant. Pulled out
   for two reasons:

   * the Lean exhaustiveness proof matches every `GuardKind` / `MeansKind`
     variant against a total `goalReprOfGuard` / `goalReprOfMeans` function,
     and the compiler enforces total coverage at compile time (NO `raise
     ValueError` fall-through is possible), and
   * a small `tests/test_decide_dispatch.py` round-trip pins every enum
     variant to a non-empty repr (matches the Lean total-match guarantee).

The Python `map_guard` / `map_means` in `strategy_driver.py` cannot delegate
their FULL behavior here (they construct parameterized `Goal` instances that
depend on `GameData` / `WorldState` / `SelectionContext`), but the repr of the
resulting Goal — the IDENTITY the strategy commits to — is a pure function of
the enum kind, captured here.
"""
from fractions import Fraction

from artifactsmmo_cli.ai.tiers.guards import GuardKind
from artifactsmmo_cli.ai.tiers.means import MeansKind


def decide_key(neg_final: Fraction, effort: int, neg_protection: int,
               root_repr: str) -> tuple[Fraction, int, int, str]:
    """The sort key tuple `decide` builds: `(-final, effort, -protection,
    root_repr)`.

    Lower tuple sorts FIRST: smaller `-final` (= higher `final`) wins, ties
    break by lower `effort`, then by smaller `-protection` (= HIGHER computed
    gear value), then by string-ordered `root_repr`. The tuple is the SAME
    shape as Python's tuple lexicographic comparison and Lean's
    `compareLex`/`compareOn` composition over the four fields.

    `protection = max(0, strategic_value(item) - strategic_value(current_in_slot))`
    is the exact-int efficiency-weighted gain (`tiers/strategic_value.py`, #16);
    `decide` passes its negation. This breaks the `EMPTY_SLOT_URGENCY` saturation
    tie — where every empty combat slot flattens to the same `final` score — by
    COMPUTED protection, so body armor (large hp_bonus) outranks an amulet on its
    actual stats instead of on an alphabetical accident. Combat stats carry the
    dominant SCALE weight so combat-slot ordering is unchanged vs the old
    equip_value tiebreak; non-combat efficiency stats add their own weight. Either
    way `decide_key` is AGNOSTIC to the source — it receives an abstract int.
    Non-gear / stats-unknown roots contribute `0`, leaving them ordered by the
    leading fields and the repr.

    The fourth field is the GENUINE last tiebreak: in production every distinct
    candidate root has a distinct `repr` (different MetaGoal types/codes), so
    no two candidates with distinct roots can tie under the full lex key.

    P4a: `neg_final` is an exact `Fraction` and `neg_protection` an exact `int`
    (strategy scores / equip values are exact rationals/ints) — lexicographic
    comparison is exact, no float near-ties.
    """
    return (neg_final, effort, neg_protection, root_repr)


# --- guard/means dispatcher repr maps --------------------------------------
# These mirror the strings the parameterized Goal instances `map_guard`/
# `map_means` build in `strategy_driver.py`. The Goal class names ARE the
# repr (see each Goal class's `__repr__`/`__str__`, or rely on the default
# class repr stripping arguments — for the dispatch property we only need
# uniqueness across enum variants, not the exact runtime repr).

_GUARD_REPR: dict[GuardKind, str] = {
    GuardKind.HP_CRITICAL: "RestoreHP",
    GuardKind.REST_FOR_COMBAT: "RestoreHP",
    GuardKind.DISCARD_CRITICAL: "DiscardOverstock",
    GuardKind.DISCARD_HIGH: "DiscardOverstock",
    GuardKind.BANK_UNLOCK: "UnlockBank",
    GuardKind.REACH_UNLOCK_LEVEL: "ReachUnlockLevel",
    GuardKind.DEPOSIT_FULL: "DepositInventory",
    # CRAFT_RELIEF's runtime repr is CraftRelief({target_item}) — the
    # target is state-dependent. The static prefix below satisfies
    # exhaustiveness for callers that only want the goal family.
    GuardKind.CRAFT_RELIEF: "CraftRelief",
    GuardKind.RECYCLE_RELIEF: "RecycleSurplus",
    GuardKind.SELL_RELIEF: "SellInventory",
    # GEAR_REVIEW maps to UpgradeEquipment or GatherMaterials depending on
    # material availability — the static prefix covers exhaustiveness.
    GuardKind.GEAR_REVIEW: "UpgradeEquipment",
}

_MEANS_REPR: dict[MeansKind, str] = {
    MeansKind.CLAIM_PENDING: "ClaimPending",
    MeansKind.COMPLETE_TASK: "CompleteTask",
    MeansKind.SELL_PRESSURED: "SellInventory",
    MeansKind.SELL_IDLE: "SellInventory",
    MeansKind.RECYCLE_SURPLUS: "RecycleSurplus",
    MeansKind.LOW_YIELD_CANCEL: "LowYieldCancel",
    MeansKind.TASK_CANCEL: "TaskCancel",
    MeansKind.PURSUE_TASK: "PursueTask",
    MeansKind.ACCEPT_TASK: "AcceptTask",
    MeansKind.TASK_EXCHANGE: "TaskExchange",
    MeansKind.BANK_EXPAND: "ExpandBank",
    MeansKind.WAIT: "Wait",
    MeansKind.MAINTAIN_CONSUMABLES: "MaintainConsumables",
}


def goal_repr_of_guard(kind: GuardKind) -> str:
    """Total dispatcher: every `GuardKind` variant maps to a non-empty repr.

    The Lean `DecideKey.goalReprOfGuard` mirror is a total `match` over the
    `GuardKind` inductive, so the Lean compiler enforces full coverage at
    elaboration time — no fall-through path is reachable. Python upholds the
    same totality here: the table covers every enum member; a NEW variant
    added without a table entry raises `KeyError` immediately (caught by the
    parametrized test). NO `raise ValueError` fall-through.
    """
    return _GUARD_REPR[kind]


def goal_repr_of_means(kind: MeansKind) -> str:
    """Total dispatcher: every `MeansKind` variant maps to a non-empty repr.

    See `goal_repr_of_guard` for the totality argument; the Lean
    `MeansKind` mirror is similarly exhaustive.
    """
    return _MEANS_REPR[kind]
