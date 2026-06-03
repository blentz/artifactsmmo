# Item 2a — GlobalInvariants hypothesis classification

## Current shape (post-Item-1g cascade)

`Formal.Liveness.LevelFiftyReachable.GlobalInvariants` bundles 5 fields:

```
structure GlobalInvariants (s : State) : Prop where
  hnowait : ∀ k, productionLadder (cycleStepN k s) ≠ some .wait
  hex : ∀ k, productionLadder (cycleStepN k s) = some .taskExchange →
              (cycleStepN k s).taskExchangeMinCoins > 0
  hbe : ∀ k, productionLadder (cycleStepN k s) = some .bankExpand →
              (cycleStepN k s).nextExpansionCost > 0
  hperc : ∀ k k', productionLadder (cycleStepN k s) = some k' →
                    (k' = .bankUnlock ∨ k' = .reachUnlockLevel) →
                    (cycleStepN k s).xp < xpToNextLevel (cycleStepN k s).level
                    ∧ (cycleStepN k s).level < 50
  hfightFires : ∀ N, ∃ k ≥ N,
                  productionLadder (cycleStepN k s) = some .bankUnlock
                  ∨ productionLadder (cycleStepN k s) = some .reachUnlockLevel
```

## Classification

### Category A: Structural / game-data invariants (can establish from production state)

- **hex** — `taskExchange` fires only when `taskExchangeMinCoins > 0`.
  - Production: `_tasks_coin_total(state) ≥ task_exchange_min_coins`.
  - `_min_coins` is non-zero by `game_data.task_master.task_min_coins`
    (OpenAPI: items endpoint). Field is always > 0 in production.
  - Runtime check: assert `task_master.task_min_coins > 0`.

- **hbe** — `bankExpand` fires only when `nextExpansionCost > 0`.
  - Production: `game_data._next_expansion_cost`. Server returns positive
    integer for every level (openapi `bank.next_expansion_cost: int >= 0`,
    but in practice always > 0).
  - Runtime check: assert `game_data._next_expansion_cost > 0` before
    each `BankExpand` evaluation.

- **hperc** — perception invariant under `bankUnlock`/`reachUnlockLevel`.
  - Production: bot tracks `s.xp`, `s.level` against game_data's level
    curve. The Lean `xpToNextLevel` matches the openapi-exposed curve.
  - `xp < xpToNextLevel level` follows from server's character schema
    (xp resets to 0 on level-up; bot never reaches threshold mid-cycle).
  - `level < 50` is the goal-condition itself.
  - Runtime check: assert `s.xp < xpToNextLevel(s.level) ∧ s.level < 50`
    in perceive layer.

### Category B: Trajectory / liveness invariants (runtime-monitored)

- **hnowait** — `productionLadder` never picks `.wait` along trajectory.
  - Production: `.wait` is the last-resort fallback. Fires ONLY when no
    other means available — implies bot stuck.
  - NOT structurally provable: any state with all means disabled would
    fire `.wait`.
  - Runtime check: assert at each cycle that ladder choice ≠ `.wait`.
    If `.wait` selected → escalation event (stuck detector triggers).

- **hfightFires** — `.bankUnlock` or `.reachUnlockLevel` fires infinitely
  often along trajectory.
  - Production: bot is configured with bank-unlock objective until
    bank accessible; reach-unlock-level objective until bank_required_level
    reached. Both fire `.fight` via ladder.
  - NOT structurally provable: depends on goal selection.
  - Runtime check: monitor that fight-driving means fires within
    bounded window. Stuck-detector escalation if not.

## Sub-phase mapping

- **2b** — prove cycleStep preserves Category A (`hex`/`hbe`/`hperc`).
  Each is a state predicate that depends on game data + perception
  fields preserved by all cycleStep transitions EXCEPT those that
  modify the relevant field. Per ActionKind preservation table:
  - `taskExchangeMinCoins`: only `.taskExchange` modifies (Nat sub
    saturates → still ≥ 0; but threshold > 0 holds vacuously if
    operation succeeded).
  - `nextExpansionCost`: NO ActionKind modifies it. Trivially preserved.
  - `xp`, `level`: modified by `.fight` and `.completeTask`. Preservation
    requires showing post-state still satisfies `xp < threshold ∧
    level < 50` IF mean fires under the new state. Tractable case
    analysis.

- **2c** — Category B requires runtime monitoring (StuckDetector
  already does this on the safety side). Lean side cannot prove
  hfightFires without classical assumption about goal selection.

- **2d** — Python differential: assert that
  `_fetch_world_state` output establishes Category A at every observation;
  monitor Category B via StuckDetector escalation.

## Estimate

- 2b proof: 3 lemmas (hex/hbe/hperc preservation), ~150 LOC, 1 session.
- 2c documentation + StuckDetector cross-reference: ~50 LOC, < 1 session.
- 2d Python harness: ~300 LOC test + state-shape verification, 1 session.

Total Item 2 remaining: 2-3 sessions.

## Honest disclosure

Category B (hnowait, hfightFires) CANNOT be proven structurally. They
are runtime-monitored production assumptions; the safety-side
StuckDetector flags violations. This is consistent with the perimeter
plan Item 2's "production invariants established by perceive layer"
framing.
