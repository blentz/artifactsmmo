# PLAN — C2 composed liveness: geared combat, honest chores, trace lockstep

**Status: Phase A COMPLETE (663f3673, 319f1b73); Phase B1 (trace characterization) COMPLETE this commit — findings in LEVEL_FIFTY_RESIDUALS.md (357/406 zero-xp fights confirms Phase-C gating as load-bearing; rest partial-heal gap found). B2 COMPLETE 94c5e746 + alignment fix (trace state is POST-action, player.py:740): open question RESOLVED as harness off-by-one; corrected lockstep = 709/762 decision agreement, rest dynamics exact 322/322, fights DO yield xp in-band (3-29). B1's zero-xp headline was the same artifact — residuals doc corrected. B3 DONE this commit: StrategyArbiter.last_fires snapshots the fired
guard/means kinds at selection time (recompute-at-emit would drift on
ctx-dependent flags) and _emit_trace rides them on every cycle record as
"fires". The lockstep harness gains the fired-vector comparison once enriched
traces accumulate (guarded on the key's presence). Next C1 / C0b / C2a-c. Multi-session epic.**

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
* **C0b: xp VALUE core. DONE.** `monster_catalog.xp_per_kill` REFACTORED to
  exact integer arithmetic (one rational num/den, round-half-even; old float
  differed at 12/17400 grid points, all ±1 at half-integer ties — exact is now
  canonical). Proven mirror `Formal.XpValue.xpPerKill` bit-identical
  (differential incl. enumerated band edges + a verified .5 tie; XP_VALUE
  mutation group 4/4 killed). Role theorems: roundHalfEven floor/ceil bounds,
  `xpPerKill_pos_iff_gate` (value positive ⟺ C0a gate, given 1 ≤ charLevel —
  ties the value core to the positivity core in-kernel),
  `xpPerKill_wisdom_mono`. LESSON: omega treats `d*(n/d)` with VARIABLE d as
  opaque nonlinear atoms — align both `Nat.div_add_mod` instances onto ONE
  atom (rw the quotient equality first) before omega.
* **C0c: trace corroboration. DONE** (`diff/xp_formula_replay.py`): 262/399
  exact at wisdom=0; all 137 residuals exactly +1 (wisdom signature); 0
  zero-band fights observed — the picker gate holds in practice.
* **C0d: liveness closure.** The E-tower fight row (C2b below) credits xp ONLY
  under `loadoutAdequate && xpPositiveGate` — the level_penalty=0 case becomes
  UNREACHABLE in the credited path instead of silently over-credited. The
  existing towers' arming already images xp-positive targets via the
  grounded witness table (`xpPosConcrete` ← production picks ← xp_per_kill>0),
  so their honesty note gains the citation, not a new hypothesis.

## The level-38 wall (C2 pre-design finding, 2026-07-04)

Probes over the acquirable pool (snapshot-pinned):

* Bands 34-37's acquirable witness farms death_knight (L28). At char 38 the
  10-band level_penalty ZEROES it (38 ≥ 28+10 — C0a's gate, exactly), and no
  monster in the xp-positive window (L29-40) is winnable with acquirable gear
  — not even with EVERY acquirable utility potion stocked (Phase-1.5 revival
  probed: potions do NOT close it). The next acquirable-winnable target
  (owlbear L30, band-39 row) needs L39 base stats. Combat is the only char-xp
  source (taskCompleteXpEstimate = 0, server-verified). Hence:

  **Acquirable-only progression hard-caps at level 38.** Crossing 38→39
  requires event/boss/NPC-class gear (the C1b frontier items). This is the
  game's actual progression design surfaced as a theorem-shaped fact.

* C2c therefore splits: `ai_reaches_thirtyeight_geared` (unconditional over
  acquirable gear) + `ai_reaches_fifty_geared` modulo ONE named, satisfiable
  hypothesis — a winnable xp-positive band-38 loadout is obtained (witnessed
  by the optimistic row 38; production path: event content per roadmap-4).
  The E-tower's gearGap descent uses `acquirableWitness` below 38 and above
  39, and the frontier hypothesis exactly at the wall.

## Phase C — the C2 composition (gaps 1+2)

The old Option-C scoping (`PLAN_winnable_across_band_discharge.md`) collapsed
because validating winnability needed per-level base stats. Task 4
(`WinnableGrounded`) broke that wall for TARGET EXISTENCE by kernel-deciding a
per-level witness table over production-projected scalars. C2 finishes the job
for ACQUISITION: prove the bot can OBTAIN a witness-adequate loadout at every
band, and gate the model's xp credit on it.

* **C1: acquirability data obligation (kernel, WinnableGrounded-style).**
  SURVEY FACTS (2026-07-04, session end): `WitnessRow` carries PROJECTED
  SCALARS only — no item codes in Lean; per-item `level ≤ L` is ALREADY
  asserted by `test_winnable_witness_diff.py` (module docstring line 31). So
  C1's real kernel obligation is the CRAFT-CLOSURE side, and it needs a new
  fixture export:
  - C1a: extend the witness generator (the script feeding
    `test_winnable_witness_diff.py` / `winnableWitness`) to ALSO emit the
    per-band loadout ITEM CODES into a Lean fixture
    (`WitnessLoadouts.lean`, generated — snapshot-regen discipline,
    `reference_snapshot_regen`).
  - C1b: kernel `decide` per band over `GameDataFixture`: every witness item
    either drops from a monster/resource gated ≤ L, or has a recipe whose
    RecipeClosure bottoms out in such leaves with craft-skill requirements
    reachable by the gather loop (reuse `RecipeChainClosure` +
    `SkillGapClosure` machinery). Honest frontier: bands needing event/boss
    drops get NAMED exceptions, not forced green.
  - C1c: differential re-pins the generated fixture against production
    (`pick_loadout` + recipe data) so the Lean table cannot drift.
  **C1 EXPERIMENT RESULT (2026-07-04, pivotal):** `obtainable_inventory_for_level`
  is DOCUMENTED-OPTIMISTIC (level ≤ L is its only filter; acquirability is the
  Task-3/corner-3 residual). Rebuilding the witness table with an
  acquirability-FILTERED pool (closure over gather ∪ live monster drops ∪
  task-exchange; 290/522 equippables close) shows: **47/49 bands stay winnable
  with provably-acquirable gear; bands 38-39 FAIL** — no winnable xp-positive
  target without ~10 closure-unreachable items (ancestral_talisman,
  ancient_jean, cursed_sceptre, dreadful_shield, gold_boots, life_crystal,
  lifesteal_rune, novice_guide, obsidian_helmet, ring_of_the_adept), whose
  sources are event/boss/NPC-class (npc stock empty outside events —
  event-merchant memory). This CONFIRMS roadmap-4 ("events gate lvl20-50
  gear") with a kernel-adjacent experiment, and TENSIONS the
  boss-not-level50-blocker memory (its criterion was gear-exists, not
  band-winnability). C1b's theorem therefore states the TRUE frontier: closure
  acquirability for 47 bands + the named 38-39 event-dependency. C1b kernel
  work: emit gatherableItems + monsterDropItems (+ task-exchange set) into the
  fixture (snapshot script gains monster_drops), certificate-style decide
  (python computes the acquirable set, kernel VERIFIES closure membership),
  rowAcquirable over loadoutCodes with the two exception bands named in the
  theorem statement. ORIGINAL SCOPE: Over
  the live `GameDataFixture`: for every band L ∈ [1,50), the witness loadout
  for L is OBTAINABLE at L — every piece has a craft recipe whose closure
  bottoms out in resources/drops gated ≤ L (or an NPC purchase with income
  proven by the task loop), with skill requirements reachable by the gather
  loop. Reuses RecipeClosure + skill-gap machinery; `decide`d per band, no
  native_decide. Deliverable: `WitnessAcquirable.lean` +
  `witness_acquirable_all_bands`. RISK: some band may genuinely need an event/
  boss drop — then the theorem records the TRUE frontier (band table with named
  exceptions), not a forced green.
* **C2a: adequacy predicate.** Discipline decision: `loadoutAdequate` enters
  the cycle State as an OPAQUE observed Bool (like every chore flag), pinned
  by a differential that recomputes it as production `is_winnable(current
  gear, band target)` — the full in-kernel derivation from `State.equipment`
  via the mirrored projection is a LATER strengthening (the pieces exist:
  LoadoutProjection + PredictWin), not a C2b blocker. A `gearGap : Nat`
  opaque counter (recipe-closure steps remaining toward the band's
  acquirable-witness loadout) rides with it, decremented by gear means —
  the A2 debt pattern at gear scale.
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
