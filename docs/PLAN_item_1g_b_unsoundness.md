# Item 1g-B — UNSOUNDNESS FINDING (post-XP=0 fix)

## Concrete counter-state to `lifecycle_progress_from_bounds`

Under user commit 7ad19e5 (`taskCompleteXpEstimate = 0`), the axiom
admits a concrete counter-example state `s`:

- `bankUnlockMonsterPresent := false`     → bankUnlockFires impossible.
- `bankRequiredLevel := 0`                → reachUnlockLevelFires impossible.
- `hasOverstockItems := false`            → discardCritical/discardHigh off.
- `selectBankDepositsNonempty := false`   → depositFull off.
- `pendingItemsNonempty := false`         → claimPending off.
- `sellableInventoryNonempty := false`    → sellPressured/sellIdle off.
- `taskCancelFires := false`, `lowYieldCancelFires := false` → cancels off.
- `hp := maxHp` (no hpCritical).
- `bankAccessible := false`, `bankItemsKnown := false` → bankExpand off.

In this state, productionLadder cycles through {.completeTask,
.pursueTask, .acceptTask, .objectiveStep, .wait}. With `hnowait`,
.wait never fires. With XP=0, none of the remaining means advance
level. ∀k, level(cycleStepN k s) = s.level. The axiom's `∃ k,
level > s.level` is **FALSE**.

`hex`, `hbe`, `hperc` are vacuously true (those means never fire).
The axiom is unsound under current hypothesis set.

## Recommended fix (user-approved Option A)

Add hypothesis to `lifecycle_progress_from_bounds`:
```
(hfightFires : ∀ N, ∃ k ≥ N,
    productionLadder (cycleStepN k s) = some .bankUnlock
    ∨ productionLadder (cycleStepN k s) = some .reachUnlockLevel)
```

Cascade:
1. `lifecycle_progress_from_bounds` axiom signature in
   `LIV003Decomposition.lean:516` — add new hypothesis.
2. `GlobalInvariants` struct in `LevelFiftyReachable.lean:38` —
   add new field `hfightFires`.
3. `cumulative_progress_under_no_wait` in `CumulativeProgress.lean:1201`
   — add new hypothesis parameter; thread through to
   `lifecycle_progress_from_bounds` call site at line 1216.
4. `level_advances_once` in `LevelFiftyReachable.lean:114` —
   thread `h.hfightFires`.
5. `forward_GlobalInvariants` lemma (line ~80) — re-establish
   `hfightFires` across cycleStep iteration. Subtle: requires
   showing that fight-firing positions are preserved under
   cycleStep prefix-stripping.
6. GameDataFixture's GlobalInvariants instances — populate the
   new field from production observation.

## Discharge sketch (next sub-item: 1g-B2)

With `hfightFires`, prove `lifecycle_progress_from_bounds_proven`:
1. Use `hfightFires 0` to get k₀ with .fight firing.
2. cycleStep at k₀ applies .fight (via planFor [.fight]).
3. .fight either advances level (done) or grants xp+=10.
4. If just xp, well-founded induction on Phase 19's
   `fight_decreases_measure` — measure strictly decreases.
5. `hfightFires k₀+1` gives next .fight; repeat until level
   advances. Finite by well-foundedness.

## Estimate
- Cascade work (steps 1-6): 1 session, ~150 LOC scattered changes.
- Discharge (1g-B2): 1-2 sessions, ~200 LOC trajectory induction.
- Drop axioms + allow-list (1g-C): <1 session.

Total remaining for Item 1g: 3-4 sessions.

## STATUS: AWAITING USER APPROVAL for the cascade

The hypothesis change affects level-50 reachability and
GlobalInvariants — load-bearing infrastructure. User confirmation
needed before executing.
