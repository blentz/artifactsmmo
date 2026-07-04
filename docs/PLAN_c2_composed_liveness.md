# PLAN — C2 composed liveness: geared combat, honest chores, trace lockstep

**Status: Phase A COMPLETE (663f3673, 319f1b73); Phase B1 (trace characterization) COMPLETE this commit — findings in LEVEL_FIFTY_RESIDUALS.md (357/406 zero-xp fights confirms Phase-C gating as load-bearing; rest partial-heal gap found). B2 COMPLETE 94c5e746 + alignment fix (trace state is POST-action, player.py:740): open question RESOLVED as harness off-by-one; corrected lockstep = 709/762 decision agreement, rest dynamics exact 322/322, fights DO yield xp in-band (3-29). B1's zero-xp headline was the same artifact — residuals doc corrected. B3 (trace flag enrichment) queued; next C1. Multi-session epic.**

Successor to `docs/PLAN_residual_closure.md` (commit 96c339f6). User mandate:
fix unmodeled gaps 1 (combat outcomes), 2 (gear/skill economy), 4 (chore
corners), 5 (trajectory binding depth) and execute the C2 composition — the
reach-50 proof must stop CREDITING xp the real bot might not earn, and instead
prove the gear economy delivers a loadout that makes the credited fights
winnable, band by band.

## Phase A — chore-corner closure (gap 4) [THIS SESSION]

Rework the D-tower's flag dynamics so the two disclosed corners disappear:

* **A1: mint-driven cross-arm.** DMeasure v2 slot order: `pendingFlag` moves UP
  to slot 5 (directly under `taskCycles`), the other 7 chore flags become
  slots 6-12. New re-arm map `rearmOnMint` (replaces fight-only `rearmIfFight`):
  - fight dispatch → re-arm ALL flags incl. pending (dominated by slots 1/2);
  - `claimPending` → re-arm flags 6-12 (the mint can overstock the bag — the
    disclosed claim→overstock instance, now MODELLED; pending itself stays
    cleared, which is claim's own strict slot 5);
  - `completeTask` → re-arm pending + flags 6-12 (task rewards mint items;
    dominated by slots 1/3).
  Per-means proofs: claim row gets EASIER (strict at 5 needs only slots 1-4
  equal); other chore rows gain a pendingFlag-equality obligation (their
  applies don't touch it — rfl).
* **A2 (follow-up): partial clears.** Replace the Bool latches for
  deposit/sell/discard with bounded Nat DEBT counters (opaque, production =
  number of deposit/sell batches outstanding): chore apply decrements by ≥1,
  mint re-arms add a bounded amount. Same lex argument; kills the one-apply-
  clears-all conservatism. Needs State fields (defaulted) + fires predicates
  gated on debt > 0. DONE — `partialClear` layer in `cycleStepD`, 18-slot DMeasure (debt slot directly above its latch), all rows re-proved.

## Phase B — trace-lockstep differential (gap 5)

Multi-cycle model↔bot binding, offline, from recorded live traces:

* Oracle entry `cycle-step-d`: given a serialized State, return the Lean
  `cycleStepD` post-state projection (level, xp, phase, flags, inventoryUsed).
* Python harness `diff/test_trace_lockstep_diff.py`: fold
  `play-trace-Robby.jsonl` into per-cycle State snapshots (the trace already
  records selection + post-state); feed cycle k's snapshot to the oracle;
  compare the oracle's post-state against cycle k+1's snapshot.
* HONESTY: exact equality is impossible (opaque flags are re-observed, xp is
  the +10 projection, loot varies). The harness CHARACTERIZES: assert agreement
  on the DECISION layer (selected means, phase transitions, flag CLEAR events)
  and record/report divergence classes on the dynamics layer (xp delta, fill
  delta) rather than asserting them. Divergence classes become named rows in
  `docs/LEVEL_FIFTY_RESIDUALS.md` — measured, not assumed.

## Phase C0 — xp-formula / level_penalty core (NEW, user-flagged 2026-07-04)

Server xp formula is DOCUMENTED with a closed form
(https://docs.artifactsmmo.com/concepts/stats_and_fights/#xp-formula):

    XP = round((monster_level/player_level * 20 + monster_hp * 0.04)
               * level_penalty * monster_multiplier * wisdom_bonus)
    level_penalty: 1.0 (diff <= 4), 0.7 (5 <= diff <= 9), 0.0 (diff >= 10)
    where diff = char_level - monster_level

Production already implements it verbatim (`monster_catalog.xp_per_kill`,
doc-cited comment) and gates combat targeting on `xp_per_kill(code, lvl) > 0`
(player.py:1574 → combat_picker) plus FightAction's xpPositive applicability
(ActionApplicability.lean). The MODEL gap: the liveness towers' `.fight` apply
credits xp unconditionally — no level_penalty image.

Closure bricks:

* **C0a: integer decision core. DONE** (`Formal/XpPositive.lean` +
  oracle `xp_positive` + `test_xp_positive_diff.py` w/ deterministic band-edge
  sweep + XP_POSITIVE mutation group, 4/4 killed — random sampling alone let a
  `>= 11` mutant survive; edges must be enumerated). KEY FACT (makes the gate float-free): within
  the band (diff <= 9, monster_level >= 1) the formula's minimum value is
  ~1.4 (worst case plvl=10/mlvl=1/penalty=0.7), which rounds to >= 1; outside
  the band penalty = 0. Hence `xp_per_kill > 0 ⟺ char_level <
  monster_level + 10` EXACTLY — immune even to Python's banker's rounding.
  Ship `xpPositiveGate (charLevel monsterLevel : Nat) : Bool := decide
  (1 <= monsterLevel) && decide (charLevel < monsterLevel + 10)` as a proven
  core with the full pipeline (differential vs production `xp_per_kill(...) >
  0` over the live catalog x level grid; mutation group bound; Contracts pin).
  Server-doc citation on the constants per the axiom-split signoff discipline.
* **C0b: xp VALUE core (follow-up).** `unlock_boost.py` ranks by xp VALUE, not
  just positivity — an exact ℚ (or scaled-int) mirror of the full formula with
  round-half-even, differential bit-agreement vs the float implementation.
  Separate brick; only needed when a decision consumes the magnitude.
* **C0c: trace corroboration. DONE** (`diff/xp_formula_replay.py`): 262/399
  exact at wisdom=0; all 137 residuals exactly +1 (wisdom signature); 0
  zero-band fights observed — the picker gate holds in practice.
* **C0d: liveness closure.** The E-tower fight row (C2b below) credits xp ONLY
  under `loadoutAdequate && xpPositiveGate` — the level_penalty=0 case becomes
  UNREACHABLE in the credited path instead of silently over-credited. The
  existing towers' arming already images xp-positive targets via the
  grounded witness table (`xpPosConcrete` ← production picks ← xp_per_kill>0),
  so their honesty note gains the citation, not a new hypothesis.

## Phase C — the C2 composition (gaps 1+2)

The old Option-C scoping (`PLAN_winnable_across_band_discharge.md`) collapsed
because validating winnability needed per-level base stats. Task 4
(`WinnableGrounded`) broke that wall for TARGET EXISTENCE by kernel-deciding a
per-level witness table over production-projected scalars. C2 finishes the job
for ACQUISITION: prove the bot can OBTAIN a witness-adequate loadout at every
band, and gate the model's xp credit on it.

* **C1: acquirability data obligation (kernel, WinnableGrounded-style).** Over
  the live `GameDataFixture`: for every band L ∈ [1,50), the witness loadout
  for L is OBTAINABLE at L — every piece has a craft recipe whose closure
  bottoms out in resources/drops gated ≤ L (or an NPC purchase with income
  proven by the task loop), with skill requirements reachable by the gather
  loop. Reuses RecipeClosure + skill-gap machinery; `decide`d per band, no
  native_decide. Deliverable: `WitnessAcquirable.lean` +
  `witness_acquirable_all_bands`. RISK: some band may genuinely need an event/
  boss drop — then the theorem records the TRUE frontier (band table with named
  exceptions), not a forced green.
* **C2a: adequacy predicate.** `loadoutAdequate : State → Bool` — the equipped
  scalar totals (from `State.equipment`, via the proven equipment-scoring
  cores) meet the witness scalars for the current band. Differential-pinned
  against production's `pick_loadout`/projection (existing gear diff harness
  extends).
* **C2b: the E-tower (geared cycle).** `cycleStepE`:
  - fight row credits xp ONLY when `loadoutAdequate` (gap 1's sharpest edge:
    no more unconditional +10);
  - when inadequate, gear means become selectable below 50 (gather/craft/
    equip — the F/D towers' unreachable tail), each descending a new
    `gearGap` slot placed BETWEEN `levelDeficit` and `xpDeficit`:
    `gearGap := witnessNeed(band) - acquiredProgress` (recipe-closure steps
    remaining, from C1's per-band closure depth). Level-up RAISES gearGap
    (new band) — dominated by slot 1.
  - fight applies bounded hp LOSS (worst case from the witness table's damage
    race) + death→respawn as hp := maxHp, position reset (position not in
    measure) — rest/hpCritical row already absorbs recovery. Removes the
    "fights are free" abstraction.
* **C2c: capstone.** `ai_reaches_fifty_geared : ∀ s, ∃ k, level ≥ 50` from
  per-cycle E-descent, hypothesis-free modulo LIV-001 + the C1 data theorem.
  What STAYS abstract (disclose, do not hide): "adequate loadout ⟹ fight
  yields xp progress" remains the projected-dynamics bridge — the model now
  refuses to credit xp without adequacy, but the server's actual combat rolls
  are not derivable offline. That bridge is exactly what Phase B's lockstep
  harness measures (xp-delta divergence class on adequate fights).

## Phase D — docs, audit, gate, honesty review

Per phase: LivenessAudit `#print axioms` rows, Formal.lean imports,
`LEVEL_FIFTY_RESIDUALS.md` rewrite, full gate (serialized with the bot), and a
Phase-4 adversarial pass — special attention to: C1 not degenerating into a
hand-table (must be `decide` over the SAME fixture the differentials pin),
adequacy not inlining the formula (must call the proven scoring cores), and
the E-tower fight gate not being vacuous (a state with adequate loadout must be
REACHABLE in-model — the C2b gear means must provably produce one, which is the
gearGap descent's job).

## Sequencing

A1 (this session) → A2 → B → C1 → C2a → C2b → C2c → D rolls per phase.
B before C so the lockstep harness exists to measure C's new dynamics rows.
Each phase lands as its own commit with gates green.
