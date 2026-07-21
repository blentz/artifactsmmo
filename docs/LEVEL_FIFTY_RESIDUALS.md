# Level-50 reachability — the honest residual perimeter

**Status (2026-07-20, third pass): THREE hypothesis-free capstones.**

> `Formal.Liveness.UnconditionalDescent.ai_reaches_fifty_unconditional :`
> `∀ s, ∃ k, (cycleStepFN k s).level ≥ 50`
>
> `Formal.Liveness.DeferFaithful.ai_reaches_fifty_defer_faithful :`
> `∀ s, ∃ k, (cycleStepDN k s).level ≥ 50`
>
> `Formal.Liveness.GearedDescent.ai_reaches_fifty_geared :`
> `∀ s, ∃ k, (cycleStepEN k s).level ≥ 50`   ← **current best**

Each is strictly stronger than the last. The second (`cycleStepD`,
`docs/PLAN_residual_closure.md`) strengthens the first on two of the perimeter
rows below: the items-task defer-case is now MODELLED (arming gated on the
production-observed `itemsTaskDeferActive`; inside the window the cycle pursues
the items task and descends a `taskCycles` slot) instead of over-approximated,
and chore re-arming is WORST-CASED (every fight re-arms ALL 8 chore latches —
reach-50 still holds, because flags are lex-dominated by the fight's level/xp
descent). The third (`cycleStepE`) adds gear-adequacy gating — see "E-tower
LANDED" below.

**Superseded tower RETIRED 2026-07-20.** The ten modules of the older
`cycleStepN` fairness/Settled/FightReady cluster were deleted: their capstones
(`ai_reaches_level_fifty`, `…_from_spawn`, `…_config_positive`,
`…_from_fair_combat`, `…_from_persistent_combat`, `…_of_settled`,
`…_of_leveling`, `…_of_fightReady`, `…_from_spawn_warmup`,
`settledWitness_reaches_fifty`, `reach_fifty_of_eventually_settled`) all carried
UNDISCHARGED hypotheses (`GlobalInvariants`, `hfightFires`, `CombatPersistent`,
`BlockersQuietInfinitelyOften`, `Settled`) with NO satisfiability lemmas, and
nothing depended on them. They were not vacuous in the 2026-06-19 sense — they
lack the fatal `∧ level < 50` conjunct — but their NAMES read as the live
result, which is the citation hazard this document exists to prevent.

Kernel axioms: `{propext, Classical.choice, Quot.sound, xpToNextLevel}` — the
standard set plus LIV-001 only (`xpToNextLevel_pos` is no longer even consumed).
No `hquiet`, no `hspawn`, no fairness residual, no `GlobalInvariants` bundle.
Audited in `LivenessAudit.lean`; per-cycle engine and slot design in
`Formal/Liveness/FMeasure.lean`; per-means descent in `BlockerDescent.lean`;
case-analysis closure in `UnconditionalDescent.lean`; plan + design record in
`docs/PLAN_l50_unconditional_descent.md`.

## How the 2026-06-18 residuals were discharged (history)

The original perimeter (see git history of this file) named three residuals.
Their fates:

1. **LIV-001 (`xpToNextLevel`)** — RETAINED, unchanged. The server owns the xp
   curve; the measure is well-founded over it. The one accepted, openapi-cited
   server axiom (per-axiom signoff per the liveness axiom split).
2. **WinnableAcrossBand** — DISCHARGED 2026-06-20 (`WinnableGrounded.
   winnableAcrossBand_grounded`): kernel-`decide`d per-level witness table over
   the live catalog with production-projected scalars, differential-pinned by
   `formal/diff/test_winnable_witness_diff.py`.
3. **BlockersQuiet / `hquiet`** — DISCHARGED 2026-07-04 by the unconditional
   descent, WITHOUT the refused false-story. The 2026-06-18 refusal rejected
   proving "chores quiet forever" from the model's never-re-arm gap (the real
   bot re-arms chores; the in-model quiescence held for a reason false of the
   system). The descent argument makes no quiescence claim at all: every
   below-50-selectable means — chores included — strictly descends the 13-slot
   `FMeasure`, so the well-founded engine needs no scheduling assumption. The
   theorem is about the MODEL; the informal sketch of why the shape carries to
   the real bot (fight-loot re-arms ride slot-1/2 descents; multi-step deposits
   drain `bankPressure` with flags equal) has one disclosed counter-instance —
   a claim-minted item re-arming overstock on a pending-only descent cycle —
   where real chore-burst finiteness is covered only by the offline perimeter
   below, not by the kernel proof. `hspawn` (`1 ≤ level`) fell out too — the
   proof consumes only the refresh's set value, not the level-indexed witness
   table.

## The remaining faithfulness perimeter (named, differential where possible)

These are NOT Lean hypotheses — the theorem has none. They are the points where
the model's fidelity to production is established offline rather than in-kernel:

| # | Gap | Where established | 2nd-pass status |
|---|-----|-------------------|-----------------|
| 1 | LIV-001 server xp curve | accepted axiom, openapi-cited (`Measure.lean`) | IRREDUCIBLE by design — the server owns the number; no offline data reproduces the curve. |
| 2 | Opaque chore Bools (`hasOverstockItems`, `selectBankDepositsNonempty`, `sellableInventoryNonempty`, `gearReviewFires`, `craftReliefFires`, `craftPotionsFires`, `recyclableSurplusNonempty`, `pendingItemsNonempty`, and now `itemsTaskDeferActive`) carry production's observed answers | AUDITED 2026-07-04: the O5.4 SELECT differential (`test_ladder_fires_diff.py`) DRIVES the production predicates behind the computable flags (overstock, deposit selection, sellable, pending, gear-review latch) against the oracle ladder, and pins the walk itself 23-slots-wide, mutation-enforced. The flags whose production computation reads live game data (`craftReliefFires`, `craftPotionsFires`, `itemsTaskDeferActive`) are observed inputs BY DESIGN — that is the model's interface, not a gap to close offline. |
| 3 | Items-task defer-case | `test_perceive_arm_diff.py` / `test_objectivestep_arming_diff.py` characterize | CLOSED IN-MODEL by `cycleStepD`: arming is gated on the defer window; inside it the cycle pursues the items task (`pursueTask` descends `taskCycles`; `acceptTask` remains unreachable — the gate implies an active phase, contradicting `acceptTaskFires`). |
| 4 | One-shot chore semantics | disclosure | SHARPENED twice: fight-direction re-arming WORST-CASED (`choreRearm`: every fight re-arms everything) AND mint-direction cross-arm MODELLED (Phase A1, `rearmOnMint`: the claim mint re-arms the 7 flags below `pendingFlag`, the completeTask reward mint re-arms everything — the formerly disclosed claim→overstock instance is now a theorem case, not a disclosure). Partial clears MODELLED too (Phase A2, `partialClear`): the three multi-batch chores (discard/deposit/sell) carry opaque DEBT counters — one apply either clears the latch (debt exhausted) or re-arms it and strictly decrements the debt, so production needing debt+1 batches is stepped through in-model; mints restore worst-case `DEBT_CAP`. Residual on this row is now only the OPAQUE debt/flag VALUES themselves (row 2's interface discipline) — no structural conservatism left. |

If any of these is wrong (e.g. a production chore that neither clears its latch
nor drains inventory, or an unbounded chore burst between fights), the model and
the real trajectory diverge at that point and the reach-50 guarantee does not
transfer — that divergence, observable as a live stall the model calls
impossible, is exactly the falsifiable surface this proof exposes.

## Measured divergence classes (Phases B1+B2, corrected 2026-07-04)

**Correction:** the first replay mis-read the trace — `_emit_trace`
(player.py:740) runs AFTER `action.execute`, so record k's `state` is that
action's POST-state. The initial "357/406 zero-xp fights", "131/355 rest
violations", and the lockstep's "(fight,rest)×354 open question" were all
one-action misattributions from feeding post-states as selection states. Both
tools now align `prev.state → cur.action → cur.state`; corrected findings
(5822 pairs, single character, early band):

| Model abstraction | Measured reality (corrected) | Consequence |
|---|---|---|
| fight: `xp += 10` flat | real per-fight xp 3-29 (mode 19-23), 6 rollovers; +10 within range, never exact | projection direction sound in-band; Phase-C gate (adequate + xp-positive target) still the principled fix for OUT-of-band fights the trace does not exercise |
| fight: hp untouched | every fight LOSES hp (-24…-270); max loss 270 | E-tower bounded hp-loss constant ≥ 270 |
| fight loot ≤ `DROP_BOUND = 8` | max fight inventory delta 3 | safe |
| rest: `hp := max_hp` | **EXACT — 0/357 violations; lockstep post-hp 322/322** | Rest apply is faithful; no partial-heal debt needed |
| chores fast-transient | max same-chore run 1; chore bursts short | CONFIRMED; `DEBT_CAP = 8` generous |
| non-fight bursts | up to 689 cycles (gather/grind phases) | the gap-2 economy the E-tower models as gear means |

**Lockstep decision layer** (`trace_lockstep.py`, oracle `cycle_step_d` →
`cycleStepDC`, kernel-equal to `cycleStepD` at the axiom's value, `xpNext` =
each cycle's recorded server `max_xp`): **709/762 agreement (93%)** on the
scalars-visible rest/fight axis; 5060 pairs `flag-unobserved` (opaque Bools not
in the trace — Phase B3 enrichment queued). Residual mismatch tails, both
small and named: (rest, fight)×35 — production rested ABOVE the 75% gate
(`restForCombatReady`, unobserved opaque); (fight, rest)×18 — production
fought slightly below the gate (sticky-commitment/timing tail; real but
bounded, revisit with B3 flags). Level-rollover agreement 383/387.

## XP formula corroboration (Phase C0c, 2026-07-04 — `formal/diff/xp_formula_replay.py`)

The documented server xp formula (stats_and_fights#xp-formula: level_penalty
1.0 / 0.7@diff≥5 / 0@diff≥10, type multiplier, wisdom bonus) replayed against
399 observed ok-fights with fixture monster level/hp: **262/399 exact at
wisdom = 0, and all 137 remaining deltas are exactly +1 xp** — the wisdom-bonus
signature (uniform, tips the round). **0 zero-band fights observed**: the
combat picker's `xp_per_kill > 0` gate keeps the bot off level_penalty = 0
targets in practice. This is the server-axiom-signoff evidence for the C0a
`xpPositiveGate` core (`docs/PLAN_c2_composed_liveness.md` §C0).

## The level-38 wall — RAISED, then DISSOLVED (2026-07-04)

History: with the PRIMARY-drop closure, acquirable progression hard-capped at
level 38 (bands 34-37 farm death_knight L28; the 10-band level_penalty zeroes
it at 38 — `xpPositiveGate` exactly; no L29-40 monster winnable, potions
included; owlbear L30 needs L39 stats; combat is the only char-xp source).
Root cause (engagement-expansion P1): every sourcing decision consumed the
primary-drop map while resources MULTI-drop — gem stones at 1/100-1/200 from
ordinary rocks — walling the jewelry/obsidian/gold recipe families. With the
full-drop closure the acquirable-witness FRONTIER IS EMPTY: 49/49 bands carry
a provably-obtainable winning loadout (`acquirableFrontier_empty`, kernel).
The E-tower capstone no longer needs a band-38 event-gear hypothesis; event/
raid/currency content (P3-P6) widens gear breadth (309→496 equippables) and
remains valuable, but is NOT progression-critical.

**E-tower LANDED:** `ai_reaches_fifty_geared` (GearedDescent.lean) — fight xp
credited only behind adequate gear, gear progress grounded by the empty
acquirable frontier, fight hp-loss (270, B1-measured) with death→respawn,
rollovers adversarially re-arming gear + every chore latch/debt. Axioms:
std + xpToNextLevel (LIV-001). The combat-outcome gap family (gap 1) is now
CLOSED in-model; the residual is the opaque-Bool faithfulness of
`loadoutAdequate`/`gearGap` (pinned per-band by the acquirable-witness
differential; per-cycle latency measured, not asserted).

## What this does NOT prove

* Nothing about wall-clock time or xp RATE — only eventual reachability under
  the model's cycle semantics.
* Nothing about levels beyond 50, boss content, or achievements.
* The `.fight` apply's `xp += 10` is the deliberate abstract projection
  (FakeServer + Lean lockstep) — see `feedback_combat_xp_projection_is_abstract`.
