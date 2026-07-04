# PLAN — Residual closure: defer-faithful + adversarially re-arming reach-50

**Status: COMPLETE 2026-07-04 — all bricks landed, gates green.**
Capstone `DeferFaithful.ai_reaches_fifty_defer_faithful` proven hypothesis-free
(axioms = standard + LIV-001). Design deltas vs plan below: `objectiveStepFlag`
went to slot 15 (LAST — below `hpDeficit`, since an arming-cycle rest would
otherwise break at a higher flag slot; safe because the placeholder cycle never
arms and, via `pressureDeltaD`, never loots), and DMeasure's lex order is
defined via the Mathlib embedding directly (equivalent, less boilerplate).
Residual disposition recorded in `docs/LEVEL_FIFTY_RESIDUALS.md`.

Follow-on to `docs/PLAN_l50_unconditional_descent.md` (capstone
`ai_reaches_fifty_unconditional`, commit 563efc7c). Goal: address the four
named gaps in `docs/LEVEL_FIFTY_RESIDUALS.md`.

## Disposition per residual

| # | Residual | Action |
|---|----------|--------|
| 1 | LIV-001 xp curve | IRREDUCIBLE (server-owned). No action possible beyond the existing per-axiom signoff + citation. |
| 2 | Opaque chore Bools | AUDIT existing differentials (O5.4 SELECT binds the ladder walk; flags are production-observed inputs). Document exactly which flags have harnesses and why deeper offline binding is impossible (the flags ARE the interface). |
| 3 | Items-task defer-case | CLOSE IN-MODEL: `cycleStepD` tower below. The refresh arms the combat objective ONLY outside the defer window; inside it the cycle pursues the items task, which descends a `taskCycles` slot. |
| 4 | One-shot chore semantics | SHARPEN IN-MODEL: `cycleStepD` includes worst-case chore re-arm — EVERY fight cycle re-arms ALL 8 chore latches — and reach-50 still holds. Remaining (disclosed, offline-only): claim→overstock cross-arm, multi-step chores. |

## The cycleStepD tower (closes 3, sharpens 4)

New, additive modules — the committed FMeasure/cycleStepF tower is untouched.

### perceptionRefreshD (defer-gated arming)

```
deferGate s := s.itemsTaskDeferActive           -- NEW opaque Bool, production:
                                                --   bootstrap_gap > 4 ∧ items-task active
               && pursueTaskFires s              -- phase ∈ {accepted, inProgress}
               && decide (s.taskProgress < s.taskTotal)
perceptionRefreshD s :=
  if s.level < 50 && !(deferGate s)
  then { s with objectiveStepFires := true, objectiveStepIsFight := true }
  else s
```

Production faithfulness: outside the defer window this is exactly
`perceptionRefresh` (grounded by `test_objectivestep_arming_diff.py`); inside it
production returns NO fight and pursues the items task — now mirrored instead of
over-approximated. `itemsTaskDeferActive` is a state-carried production
observation (same discipline as every other opaque Bool). The extra two
conjuncts make the gate self-certifying: they are exactly the facts the
pursueTask descent needs (phase active; progress < total).

### choreRearm (adversarial worst case)

After a cycle whose dispatched action is `.fight`, set ALL 8 chore latches to
`true` (`hasOverstockItems`, `selectBankDepositsNonempty`,
`sellableInventoryNonempty`, `recyclableSurplusNonempty`, `craftReliefFires`,
`craftPotionsFires`, `gearReviewFires`, `pendingItemsNonempty`). This
OVER-approximates production re-arming (loot cannot arm more than everything).
Fight cycles descend slots 1/2, which lex-dominate every flag, so descent
survives the worst case — killing the "flags never re-arm" objection for the
fight direction. NOT modelled (stays disclosed): chore-cycle cross-arming
(claim→overstock) and partial chore clears.

### cycleStepD

```
cycleStepD s := match productionLadder (perceptionRefreshD s) with
  | some k => rearmIfFight k (pressureDelta k (cycleStep (perceptionRefreshD s)))
  | none   => cycleStep (perceptionRefreshD s)
```
where `rearmIfFight k st` applies `choreRearm` iff `planFor k` leads with
`.fight` (bankUnlock / reachUnlockLevel / armed objectiveStep).

### DMeasure (15 slots)

```
(1) levelDeficit (2) xpDeficit (3) phasePresent (4) taskCycles
(5..12) the 8 chore flags (order as FMeasure)
(13) objectiveStepFlag (14) bankPressure (15) hpDeficit
```

New vs FMeasure: `taskCycles` (slot 4) — descended by pursueTask/taskTrade;
never raised below 50 (acceptTask unreachable: under the gate `pursueTaskFires`
holds, so `acceptTaskFires` (phase = .none) is false; outside the gate the armed
objectiveStep precedes it). `objectiveStepFlag` (slot 13) — a STALE-true
`objectiveStepFires` inside the defer window with `objectiveStepIsFight = false`
selects the synthetic placeholder, whose apply clears the Bool; the slot books
that descent (raised only by the refresh on arming cycles, which then fight —
dominated by 1/2).

### Case analysis (every below-50-selectable means descends DMeasure)

* 17 blocker-prefix rows: same slots/args as `BlockerDescent` (re-proved over
  `cycleStepD`; rearm never applies — not fights).
* objectiveStep, `isFight = true` (armed or stale-true): `.fight` — slots 1/2;
  rearm + pressure + flag churn all dominated.
* objectiveStep, `isFight = false` (stale-true Bool inside defer window):
  placeholder — slot 13.
* pursueTask (reachable ONLY inside the gate): `.taskTrade` — slot 4, strict
  from the gate's `taskProgress < taskTotal` conjunct; phase stays active or
  goes `.complete` (slot 3 unchanged at 1... `.complete` also counts present).
* none-case: outside the gate the arm fires objectiveStep; inside the gate
  `pursueTaskFires` holds — either way `findSome?` cannot be none.
* Discretionary tail after pursueTask: unreachable (pursueTask fires whenever
  the gate holds; objectiveStep armed whenever it doesn't).

### Capstone

`ai_reaches_fifty_defer_faithful : ∀ s, ∃ k, (cycleStepDN k s).level ≥ 50` —
hypothesis-free, axioms = standard + LIV-001, same engine shape as FMeasure's.

## Bricks

1. `DMeasure.lean` — structure/extraction/lex/WF/helpers/engine (FMeasure
   pattern, 15 slots).
2. `CycleStepD.lean` — `itemsTaskDeferActive` State field (NEW — State extension,
   mechanically preserved by `{s with …}` applies), `deferGate`,
   `perceptionRefreshD`, `choreRearm`, `cycleStepD`, iteration + field bridges.
   NOTE: adding a State field ripples NOTHING (existing applies use record
   update), but the Lean fixture generator may need the field — check
   `snapshot_game_data.py` / `generate_lean_fixture.py` drift rule
   (`reference_snapshot_regen`).
3. `BlockerDescentD.lean` — per-means descent over `cycleStepD` (17 + placeholder
   + pursueTask + fight).
4. `DeferFaithful.lean` — prefix argument (reuse shape), none-case, total
   descent, capstone.
5. Audit + docs: LivenessAudit entries; Formal.lean imports;
   LEVEL_FIFTY_RESIDUALS.md update (residual 3 closed in-model, 4 sharpened,
   2 audited, 1 noted); gate green.
6. Phase-4 adversarial pass: no quiescence claim, gate conjuncts honest
   (production defer ⟹ items-task active ⟹ phase+progress facts), placeholder
   descent not a vacuous slot, worst-case re-arm actually worst-case.

## Residual-2 audit checklist (Brick 5)

For each opaque Bool: does a differential exist that pins the PRODUCTION
predicate the Bool abstracts (not the Bool itself — that's an input)? Roster
from ProductionLadder docstring + formal/diff/. Outcome recorded in
LEVEL_FIFTY_RESIDUALS.md table row 2, per-flag.
