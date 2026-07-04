# PLAN — L50 capstone: unconditional per-cycle descent (discharge `hquiet`)

**Status: COMPLETE 2026-07-04 — all bricks landed, gates green.**
Capstone `UnconditionalDescent.ai_reaches_fifty_unconditional` proven with
axioms `{propext, Classical.choice, Quot.sound, xpToNextLevel}` (hspawn AND
xpToNextLevel_pos both dropped). Design deltas vs the plan below: slot 3 became
`phasePresent` (phase ≠ `.none`) because `taskCompleteXpEstimate = 0`
(server-verified — completeTask grants NO xp, so it cannot ride slots 1/2);
Brick 2 folded into Brick 3 (only two bridges needed:
`fMeasure_perceptionRefresh` invariance + `fires_of_ladder`). Brick 7
(faithful chore re-arm, `cycleStepR`) remains the tracked follow-up.
Authoritative perimeter statement: `docs/LEVEL_FIFTY_RESIDUALS.md`.

## Goal

Discharge the `hquiet` (blockers-quiet) residual of
`LevelingDescent.ai_reaches_fifty_grounded` (LevelingDescent.lean:189). Today the
capstone assumes every below-50 faithful cycle selects a FIGHT means. This plan
replaces that assumption with a proof: **every below-50 `cycleStepF` cycle strictly
descends a new lex measure (`FMeasure`), whatever means the ladder selects.** Target:

```
theorem ai_reaches_fifty_unconditional (s : State) :
    ∃ k, (cycleStepFN k s).level ≥ 50
-- axioms ⊆ {propext, Classical.choice, Quot.sound, LIV-001}; NO hquiet, NO hspawn
```

Supersedes the stale "bounded-fuel ×4 (claimPending/gearReview/acceptTask/completeTask)"
framing in memory `project_levelfifty_vacuity`: `acceptTask`/`taskExchange`/`bankExpand`
sit AFTER `.objectiveStep` in `allInLadderOrder` (MeansKind.lean:102-110), and below 50
`perceptionRefresh` arms `objectiveStepFires` every cycle, so the ladder can never reach
them — no fuel needed. `completeTask` now grants xp+rollover in-model (Plan.lean
`.completeTask`, Phase 21c/23c-3b) so it descends like a fight.

## The case analysis (all 18 selectable means below 50)

Ladder prefix before `.objectiveStep` (17 means) + `.objectiveStep` itself. Discretionary
tail (`pursueTask, acceptTask, taskExchange, maintainConsumables, sellIdle,
recycleSurplus, bankExpand, drainBankJunk, wait`) unreachable below 50 (objectiveStep
armed and earlier in list). `none`-case impossible below 50 (objectiveStep fires).

| Means | Action | Descends | Why strict |
|---|---|---|---|
| bankUnlock, reachUnlockLevel, objectiveStep | .fight | slot 1/2 (level/xpDeficit) | existing `cycleStepF_fight_descends`; arming gives IsFight |
| completeTask | .completeTask | slot 1/2 | xp+10 rollover, same split as fight |
| taskCancel, lowYieldCancel | .taskCancel | slot 3 phaseActive | fires needs phase∈{accepted,inProgress} (=1); apply sets phase .none (=0) |
| discardCritical, discardHigh | .discard | slot 4 overstockFlag | fires needs `hasOverstockItems`; apply clears |
| depositFull | .depositAll | slot 5 selectBankDepositsFlag | fires needs flag; apply clears |
| sellPressured, sellRelief | .npcSell | slot 6 sellableFlag | fires needs flag; apply clears |
| recycleRelief | .recycle | slot 7 recyclableFlag | fires needs flag; apply clears |
| craftRelief | .craft | slot 8 craftReliefFlag | fires needs flag; apply clears |
| craftPotions | .craft | slot 9 craftPotionsFlag | fires needs flag; apply clears (Plan.lean:410) |
| gearReview | .optimizeLoadout | slot 10 gearReviewFlag | fires needs flag; apply clears (Plan.lean:449) |
| claimPending | .claimPendingItem | slot 11 pendingFlag | fires needs `pendingItemsNonempty`; apply clears; pressureDelta +1 hits slot 12 (below) |
| hpCritical, restForCombat | .rest | slot 13 hpDeficit | hpCritical: maxHp>0 ∧ hp·DEN<NUM·maxHp ⟹ hp<maxHp; restForCombat: explicit `hp < maxHp` conjunct; apply hp:=maxHp |

## FMeasure — the new lex tuple (13 slots)

```
(1) levelDeficit  (2) xpDeficit  (3) phaseActive  (4) overstockFlag
(5) selectBankDepositsFlag  (6) sellableFlag  (7) recyclableFlag
(8) craftReliefFlag  (9) craftPotionsFlag  (10) gearReviewFlag
(11) pendingFlag  (12) bankPressure(=inventoryUsed)  (13) hpDeficit
```

Ordering rationale (each raiser is lex-dominated by what that step descends):
* fight raises bankPressure(12) [+DROP_BOUND] — dominated by 1/2.
* claim raises bankPressure(12) [+1] — dominated by pendingFlag(11).
* completeTask raises nothing in-tuple except phase .complete→.none (phaseActive
  .complete = 0 → 0, unchanged) and gold (not in tuple) — descends 1/2 anyway.
* acceptTask (only phaseActive raiser) unreachable below 50; above 50 unconstrained.
* reducers set inventoryUsed→0 (never raise); rest touches hp only.
* `perceptionRefresh` mutates ONLY `objectiveStepFires`/`objectiveStepIsFight` —
  deliberately NOT in the tuple, so refresh is FMeasure-invariant.
* Old measure slots 3-4 (taskCycles, skillXpDeficit) dropped — no selectable below-50
  means needs them; taskCycles would be RAISED by acceptTask and can't be placed.

## Bricks

1. **FMeasure module** (`Formal/Liveness/FMeasure.lean`): structure, `fMeasure : State
   → FMeasure`, `fMeasureLt` (13-way lex disjunction), WF via `toLex13` embedding into
   `Nat ×ₗ …` (mirror CumulativeProgress.toLex15 pattern), helper `fLt_of_slotK_dec`
   lemmas, and the generic engine `exists_level_ge_of_fdescent` (mirror
   MeasureDescent.exists_level_ge_of_descent; needs levelDeficit=50-level so
   below-50 guard works — reuse `no_infinite_descent` shape).
2. **Refresh/pressure invariance bridges**: `perceptionRefresh` preserves every
   FMeasure field (rfl-ish); `pressureDelta k` preserves every field except
   `inventoryUsed` (exists: `pressureDelta_*`); `cycleStepF` field bridges (exist for
   level/xp/hp; add flag/phase bridges as needed).
3. **Per-means descent lemmas** (`Formal/Liveness/BlockerDescent.lean`): one lemma per
   row of the table over `cycleStepF` at below-50 states. Fight rows: lift
   `cycleStepF_fight_descends` to FMeasure (same rollover/accumulate split).
   Chore rows: fires⟹slot=1, apply⟹slot=0, higher slots preserved (case-by-case
   `{s with …}` rfl), pressureDelta case per means.
   VERIFY per case in Plan.lean that the apply really clears the fired flag and sets
   `taskLifecyclePhase` (taskCancel must set phase := .none — confirm, else fix model
   faithfully against production task_cancel.py).
4. **Total descent + capstone** (`Formal/Liveness/UnconditionalDescent.lean`):
   `cycleStepF_descends_below_fifty : ∀ s, s.level < 50 → fMeasureLt (fMeasure
   (cycleStepF s)) (fMeasure s)` by cases on `productionLadder (perceptionRefresh s)`
   over `allInLadderOrder` (prefix-selection lemma: firing means before objectiveStep,
   none-case contradiction via armed objectiveStepFires). Then
   `ai_reaches_fifty_unconditional` via the Brick-1 engine. Non-vacuity: trivially
   satisfiable (no hypotheses) — state the ≥50-witness anyway for the audit pattern.
5. **Audit + docs**: `LivenessAudit.lean` `#print axioms` entries (expect
   {propext, Classical.choice, Quot.sound, LIV-001}); rewrite
   `docs/LEVEL_FIFTY_RESIDUALS.md` (hquiet DISCHARGED; new perimeter below);
   update `LevelingDescent` module docstring (grounded capstone superseded but kept).
6. **Adversarial review (Phase 4)** — specifically against the honesty boundary that
   REFUSED the old Settled discharge (`feedback_proofs_tell_false_stories`):
   see "Honesty analysis" below; confirm the disclosures land in module docstrings.
7. *(Optional, follow-up)* **Faithful chore re-arm**: additive `cycleStepR :=
   choreRearm ∘ cycleStepF` where fight cycles may re-arm the one-shot flags
   (production loot re-arms overstock/sellable). Descent survives verbatim: flag
   raises on fight cycles are dominated by slot 1/2. Kills the last structural
   objection; do only after Brick 5 lands green.

## Honesty analysis (why this is NOT the refused false-story)

The 2026-06-18 refusal (`LEVEL_FIFTY_RESIDUALS.md` §3) rejected proving
"chores quiet forever" from the model's never-re-arm gap: the in-model theorem held
for a reason FALSE of the bot (chores absent vs chores fast-transient). The descent
argument does not claim chores are absent or quiet — it allows a chore at ANY step and
shows each chore strictly descends. On the REAL trajectory, flag re-arms ride cycles
that strictly descend higher slots (loot arrives on fights → slot 1/2 down; a partial
production deposit that leaves the flag armed still drains inventory → slot 12 down
with flags equal). So the real system satisfies the same descent shape for the same
structural reason — the model's one-shot-flag conservatism narrows WHICH slot descends,
not WHETHER. Named residual faithfulness gaps (disclose, differential where possible):
1. LIV-001 (unchanged, server xp curve).
2. Opaque-Bool fidelity: flags carry production's observed answers (existing O5.4
   SELECT differential pins the ladder; per-flag diff harnesses already noted in
   ProductionLadder docstring).
3. Items-task defer-case over-approximation of unconditional arming (unchanged,
   `test_objectivestep_arming_diff.py`).
4. Single-action chore semantics (model clears a flag in one apply; production may
   need several — real multi-step chores descend via bankPressure instead; note only).
Brick 7 removes the sharpest edge of (2) structurally.

## Gate

Liveness namespace (Mathlib allowed; axiom split per `project_liveness_axiom_split` —
no new axioms expected, LIV-001 inherited only). `lake build` + LivenessAudit axiom
lines + orphan-module check (import new modules into the audit). No production code
change → no differential/mutation delta; gate.sh must stay green. Never run gate.sh
concurrent with the bot (`feedback_serialize_gate_runs`).

## Risks / verify-first per brick

* taskCancel apply may not set `taskLifecyclePhase := .none` (Brick 3 blocker; fix
  model against task_cancel.py if so — production cancel clears the task).
* `.craft` apply may clear only ONE of {craftReliefFires, craftPotionsFires}; if a
  single apply clears both flags that's fine (both descend); if it clears NEITHER for
  the other's selection path, split needed.
* completeTask accumulate-branch strictness needs `xpToNextLevel_pos` (LIV-001) same
  as fight — fine.
* `sellRelief`→`.npcSell` mapping and `recycleRelief`→`.recycle` mapping assumed —
  confirm in Plan.lean meansToPlan.
* `restForCombat`→`.rest` mapping assumed — confirm.
