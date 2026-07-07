"""Pure core for the strategy driver's dispatcher routing.

`goal_repr_of_guard` / `goal_repr_of_means`: the `repr` strings the driver's
`map_guard` / `map_means` dispatchers produce per enum variant. Pulled out
for two reasons:

* the Lean exhaustiveness proof (`formal/Formal/DecideKey.lean`) matches
  every `GuardKind` / `MeansKind` variant against a total `goalReprOfGuard`
  / `goalReprOfMeans` function, and the compiler enforces total coverage at
  compile time (NO `raise ValueError` fall-through is possible), and
* `tests/test_ai/test_decide_key.py` round-trips every enum variant to a
  non-empty repr (matches the Lean total-match guarantee).

The Python `map_guard` / `map_means` in `strategy_driver.py` cannot delegate
their FULL behavior here (they construct parameterized `Goal` instances that
depend on `GameData` / `WorldState` / `SelectionContext`), but the repr of the
resulting Goal — the IDENTITY the strategy commits to — is a pure function of
the enum kind, captured here.

(Historical note: this module also carried `decide_key`, the sort-key tuple of
the retired flat scalar ranking's `StrategyEngine.decide`. That comparator was
deleted with the flat ranking in progression-tree Phase 4b; the dispatcher
tables below bind the LIVE arbiter dispatchers and stay.)
"""
from artifactsmmo_cli.ai.tiers.guards import GuardKind
from artifactsmmo_cli.ai.tiers.means import MeansKind

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
    GuardKind.CRAFT_POTIONS: "CraftPotions",
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
    MeansKind.DRAIN_BANK_JUNK: "DrainBankJunk",
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
