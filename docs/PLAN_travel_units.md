# PLAN: one travel unit — seconds

USER 2026-10-09, "One unit: seconds".

## Evidence (live, fleet restarted 2026-10-09 13:08Z on d3706cf4)

R2D2's rat grind (rat lives in the interior at (-3,12)): every ~25 s fight is
followed by a RestoreHP plan

    Transition(interior->overworld), Craft(cheese×1) at the workshop (1,1),
    UseConsumable ×2, Rest

that takes ~170 s of wall clock (two ~80 s walks: the transition + 15 tiles, and
the walk back the next goal pays), while `Rest` in place would take 47 s.
284 cycles, 955 XP in 2.6 h. Offline probe (same state, hp 384/720): the
planner prices that plan at 34 against Rest at 47.

## Cause

Every action prices its walk in a different unit:

| Action | Walk term |
|---|---|
| `MoveAction` | `5.0` per tile (seconds) |
| `Rest` | seconds (`rest_cooldown_seconds`) |
| 21 actions with a built-in walk (Craft, Recycle, Withdraw*, Deposit*, Npc*, Ge*, Task*, AcceptTask, CompleteTask, BankExpansion, Fight) | `1` per tile |
| `Transition` | `1` per tile (+3) |
| `Gather` | `(6 + dist) × gathers` — 1 per tile, charged once PER GATHER although `execute` walks once per batch |

So a walk folded into an action costs a fifth of the same walk as a Move, and
recovery that leaves the tile looks cheaper than resting.

## Design

1. One constant, `cost_core.MOVE_SECONDS_PER_TILE = 5` (int), and one helper
   `travel_seconds(src, dest) = MOVE_SECONDS_PER_TILE * manhattan`. `MoveAction`
   and every built-in walk use it. The proved cost cores
   (`distance_cost_pure`, `qty_cost_pure`, `Formal.ActionCostNonneg`,
   `Formal.PlannerAdmissibility`) already take the distance as an argument:
   they receive seconds, and their statements stand.
2. Gather charges its walk ONCE: `6 × gathers + travel + penalties` (the
   per-gather base, the banked and loadout penalties stay per gather). This
   changes `Formal.GatherCost.gatherCost`'s travel term from
   `(base + dist) * qty` to `base * qty + dist`; its theorems are restated only
   where the travel term appears (nonneg, monotone, one-is-base hold; the
   parity / neutrality statements are re-checked). The learned arm's per-gather
   `default` stays the per-gather figure without the walk.
3. Re-measure: the scenario census / matrices (craft MATRIX/BACKLOG, OPEN_RUNG,
   DROP_WALL, GRIND_CYCLE, liveness) and the offline R2D2 probe — RestoreHP at
   hp 384/720 in the interior must plan `[Rest]`.

## Residuals

- Every non-travel base constant (fight 10, craft 5/unit, gather 6/gather, ...)
  is still an ad hoc number, not a measured cooldown in seconds.
- The walk back a plan leaves for the next goal is not priced.

## Status (2026-10-09): built

As designed: `cost_core.MOVE_SECONDS_PER_TILE`/`travel_seconds` in 23 actions
plus Move; Gather walks once (`6*gathers + travel`); `Formal.GatherCost`
restated on the travel term only (`gather_cost_loadout_parity`,
`gather_cost_batch_parity`; batch = qty × (singleton − walk) + walk, the
singleton chain's shape). Every census byte-identical; no scenario plan pin
moved. Witness: the live R2D2 state now plans `[Transition, Rest]` (50) where
it planned the cheese detour (34, really ~170 s).

New residual: `RestAction` (and other location-free actions) inherit
`travel_region = "overworld"` (`actions/base.py`), so the planner cannot Rest
inside an interior — the witness's leading Transition is that region lock.

## Rest anywhere (2026-10-09, USER "Fix resting anywhere")

`actions/base.ANY_REGION` marks an action that folds in no movement (Rest,
UseConsumable, Equip, Unequip, OptimizeLoadout, Delete, Wait); `serves_region`
is the one predicate the planner, the decomposition's region bridge and the
region-edge admission ask. Live R2D2 had stepped out of the interior before
each of 92 rests; the witness now plans `[Rest]` (47) in the interior.
