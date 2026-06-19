# PLAN: faithfulness modeling — discharge BlockersQuiet faithfully (perfect-model effort)

## Goal
Make the Lean liveness model FAITHFUL to the running bot's chore/inventory
dynamics, so `BlockersQuietBelowCapInfinitelyOftenP` is PROVEN (not assumed and
not falsely in-model-discharged). The model currently abstracts inventory
composition into opaque Bools and assumes "chores never re-arm"; the real bot
re-arms chores (fight → items → inventory fills → chore fires again) and stays
live by chore-fast-transience. This plan models that transience and proves it.

Authoritative perimeter context: `docs/LEVEL_FIFTY_RESIDUALS.md`. This plan
attacks residual #3. Residual #2 (WinnableAcrossBand) is a SEPARATE,
data-gated workstream (see § Workstream B); residual #1 (LIV-001) is irreducible.

## Principle
A perfect model is not a maximally-detailed model — it is the COARSEST model
whose predictions are DIFFERENTIALLY EXACT against production. We do not guess the
abstraction level; we measure it (Phase 0), then prove at exactly that level.
This is the project's proven-core philosophy ([[feedback_filter_at_use_time]],
formal-development Phase 1).

## The target theorem (what "faithful discharge" means)
Replace the opaque `BlockersQuietBelowCapInfinitelyOftenP` HYPOTHESIS with a
THEOREM of a richer state, modulo a small precise runtime invariant `I`:

```
theorem blockersQuiet_of_invariant (s : State)
    (hI : RuntimeInvariant s)                 -- bank reachable ∧ capacity ≥ B ∧ task-quiet/cancellable
    (hfaithful : <perceive/apply faithfulness, differentially validated>) :
    BlockersQuietBelowCapInfinitelyOftenP s
```

The win: an opaque fairness assumption becomes `RuntimeInvariant` — a small,
checkable, differentiable predicate the bot maintains. Where `I` fails is exactly
where the bot livelocks ([[project_inventory_profiles]], [[project_skill_gated_self_lock]]),
so the proof DOUBLES as a livelock-precondition characterization.

## The combat-progress argument (the proof skeleton, fidelity-independent)
1. Define `chorePressure : State → Nat` — the faithful accumulator the chore
   thresholds read (inventory used-slots, plus per-category armed counters).
2. **Bounded growth:** `chorePressure (fightApply s) ≤ chorePressure s + B` for a
   constant `B` (max drops/gathers per action). Combat is the only riser.
3. **Chore non-increase:** every chore action (deposit/discard/sell/craft/gear/
   claim/taskCancel) has `chorePressure (act s) ≤ chorePressure s`, and CLEARS its
   own category (extends `BlockerQuieting.lean`'s one-step-clear to the faithful
   state). No chore re-arms another (deposits/discards/sells remove; craft consumes
   N→1; optimizeLoadout is count-neutral).
4. **Bounded chore bursts:** between two combat selections there are ≤ N chore
   cycles (N = number of chore categories), because each category fires ≤ once
   before clearing and only combat re-arms. ⇒ combat is selected ≥ once per (N+1)
   cycles ⇒ `objectiveStepBlockers` all quiet infinitely often.
5. Discharge `BlockersQuietBelowCapInfinitelyOftenP` from (4) + the perceptionRefresh
   arming (already proven, [[project_perception_refresh_extension]]).

Steps 2–4 need `RuntimeInvariant` (bank reachable so deposit CAN clear pressure;
capacity ≥ B so a fight can't overflow past recovery; task quiet/cancellable so the
3 task-blockers settle). That residue is `I`.

## Phases

### Phase 0 — Faithfulness probe (DATA-DRIVEN; lynchpin, do FIRST)
Do NOT model blind. Instrument production and record, per decision cycle, every
chore flag alongside the underlying state, to find the coarsest exact abstraction.
- Add a trace hook in the perceive/decide path (`player.py` decide →
  `StrategyArbiter.select`) logging: `hasOverstockItems`, `selectBankDepositsNonempty`,
  `sellableInventoryNonempty`, `gearReviewFires`, `craftReliefFires`,
  `pendingItemsNonempty`, plus `inventory_used`, `inventory_max`, per-category
  counts (depositable/sellable/discardable), gear-improvable?, craftable-step?,
  task phase. Use the existing trace infra; no new bot run semantics.
- Replay/collect over a representative leveling segment (or synthesize from
  `formal/sim/game_data_snapshot.json` + crafted WorldStates if a live run is out
  of scope).
- OUTPUT: per-flag verdict — `count-threshold` (M1), `per-category-count` (M2), or
  `genuine-perceive-Bool` (M3, e.g. gearReview/craftRelief). This fixes the State
  fields Phases 1–2 add. Decision recorded in this plan before Phase 1.
- ALSO measure `B` (max per-action inventory delta) and confirm chore actions are
  pressure-non-increasing in the trace — the empirical basis for proof steps 2–3.

### Phase 0 — FINDINGS (2026-06-18, probe complete; abstraction DECIDED)

Two read-only probes mapped production's perceive + the winnability data path.
Result: the abstraction level is fixed, and far cheaper than full composition.

**A — chore-flag map (production fn → fidelity):**

| Flag | Production fn | Threshold gate | Fidelity NEEDED for transience |
|------|---------------|----------------|--------------------------------|
| hasOverstockItems | `inventory_caps.overstocked_items:417` | used/max ≥ 0.95 / 0.85 | **gate-direction only** (fires ⇒ ≥0.85) |
| selectBankDepositsNonempty | `bank_selection.select_bank_deposits:77` | used/max ≥ 0.90 | gate-direction only |
| sellableInventoryNonempty | `tiers/means._has_sellable:65` | used/max ≥ 0.85 | gate-direction only |
| craftReliefFires | `craft_relief.craft_relief_candidates:101` | used/max ≥ 0.70 | gate-direction only |
| gearReviewFires | `gear_latch.GearLatch.update:22` | NONE (level-change / fight-loss latch) | **latch model** (wrinkle 2) |
| pendingItemsNonempty | `means.py:88` `bool(state.pending_items)` | NONE | **count model** (wrinkle 1) |

**KEY SIMPLIFICATION:** the four threshold-gated flags need only the ONE-WAY
faithfulness fact `flagFires ⇒ used/max ≥ threshold` (production AND-gates the
composition test with the ratio). So below 0.70 used/max all four are provably
quiet WITHOUT modeling recipe closure / dominance / keep-sets. The faithful state
needs `inventoryUsed : Nat`, `inventoryMax : Nat` — NOT the item multiset. Phase 2
differential validates the gate direction, not full composition. This collapses
the feared "model all of inventory" into "model inventory PRESSURE + two latches".

**Inventory-pressure monotonicity (proof input, MEASURED):**
- Pressure-NON-increasing (proven-direction): deposit (`deposit_all.py:47`),
  discard (`delete.py:32`), sell (`npc_sell.py:47`), optimizeLoadout; craft
  strictly DEcreases (the `_net_relief_per_craft > 0` gate, `craft_relief.py:87`,
  rejects 1:1 recipes).
- Pressure-PRODUCERS: fight (loot), gather, AND **ClaimPending mints +1**
  (`claim.py:48`, slot-guarded at `claim.py:30/36/41`). So the transience claim is
  NOT "only combat raises pressure"; it is "raisers are {fight, gather, claim};
  claim's fuel `pending_items` is finite + claim-depleted ⇒ bounded bursts".

**WRINKLE 1 — ClaimPending:** model `pendingCount : Nat`; claim decrements it and
+1's `inventoryUsed`; refilled only by task/event rewards (bounded per window).
Bounds the claim burst.

**WRINKLE 2 — gearReview fight-loss re-arm:** the latch re-arms on
`last_outcome == "error:fight_lost"`. Losses are bounded only because the combat
veto fights at ≥0.9 win-rate ([[project_combat_veto_threshold]]) — a PROBABILISTIC
transience a deterministic model cannot express exactly. HONEST sub-residual:
either (a) carry "fights are won" as a `RuntimeInvariant` conjunct (couples to #2 /
WinnableAcrossBand — fine, both in scope), or (b) model a loss-budget. Decide in
Phase 3; lean (a) since it unifies with B.

**B — winnability data path (confirmed pure DATA dependency):**
- `is_winnable`/`predict_win` (`combat.py:81-192`) read projected `p.attack[e]`,
  `p.max_hp`, `p.resistance[e]`, `p.critical_strike`, `p.initiative`, `state.hp`;
  base components of these are server-totals-only (`projection.py:1-6`,
  `world_state.py:236-262`). No `base_hp`/`HP_PER_LEVEL`/formula anywhere in
  `src/` or `formal/` (grep-confirmed). Base `max_hp(L)` is the load-bearing gap.
- Infra gaps to close (buildable offline, NO live data): (i) extend
  `snapshot_game_data.py:49-57` to serialize item combat stats
  (`attack`/`hp_bonus`/`resistance`/`dmg`/`critical_strike`/`initiative`/
  `lifesteal`/`antipoison`); (ii) new pure catalog-wide "argmax weapon attack with
  `item.level ≤ L`" (the existing `scoring.pick_loadout` only scans OWNED items).
- LIVE CAPTURE (user-run, real account/time): `GET /characters/{name}` with all 11
  slots empty, per level 1..49, record `max_hp`, `attack_{elem}`, `res_{elem}`,
  `critical_strike`, `initiative`. Fixture block `character_base_stats` keyed by
  level, sibling of `game_data_snapshot.json`. NOT a formula — needs ≥ the per-
  level rows. This is the `GameDataFixture`-class data obligation for #2.

**Phase-0 verdict:** A is fully buildable offline at the pressure+latch+count
abstraction (no live data). B is buildable-infra + one live-capture step the user
runs. Proceed: Phase 1 (A modeling) in parallel with B infra; B's sweep waits on
the capture fixture.

### Phase 1 — BRICK STATUS (Workstream A)
- **Brick 1 DONE (2026-06-19, commit 3d8a0dd)** — `InventoryPressure.lean`: the
  gate-direction lemmas. Phase-0 confirmed the 4 pressure-gated chores already
  AND-gate their used/max threshold INSIDE the `*Fires` defs, so `*Fires_imp_
  threshold` + `pressureGatedChores_quiet_of_low` (100·used < 85·max ⇒ all 4 quiet)
  are provable with NO State change. Axioms {propext, Quot.sound}. Foundation of
  the transience argument.
- **Brick 2 NEXT — the high-ripple core.** The model currently PRESERVES
  `inventoryUsed` across every action (Plan.lean:229/237/246 explicitly defer the
  decrement; `.fight` never raises it). Brick 2 wires the faithful dynamics:
  fight/gather +B (bounded), deposit→drop, discard/sell/craft reduce, claim +1
  (Phase-0 wrinkle 1). **KEY DESIGN TENSION (the crux of the whole effort):**
  making `.fight` RAISE pressure deliberately BREAKS `BlockerSettled.Settled_
  cycleStep` (which holds only because fight preserves the gated-chore quiet) — i.e.
  the easy `Settled` fixpoint is UNFAITHFUL (the real Settled isn't fight-invariant;
  fighting fills the bag). Brick 2+ must REPLACE the fixpoint with the real
  bounded-burst transience: fight raises pressure → a gated chore fires ≤ once per
  category → pressure drops → combat resumes, combat selected ≥ 1 per (N+1) cycles.
  This ripples into ~50 proofs (measure descent, Settled_cycleStep, the capstone)
  and needs a FULL gate run per brick + subagent-driven discipline. Its own focused
  session.

### Phase 1 — Faithful State extension + apply cores
- Extend `Measure.State` with the Phase-0-selected fields (e.g. `inventoryUsed`,
  `inventoryMax`, per-category counters). Keep additive — existing proofs must not
  break (the opaque Bools stay, now DERIVED in Phase 2).
- Model each action's effect on the new fields in `applyActionKind` faithfully:
  fight/gather add (bounded by B), deposit zeroes depositable, discard reduces
  discardable, sell reduces sellable, craft consumes→produces, etc.
- Extract pure cores (`inventory_apply_core.py`) and DIFFERENTIALLY validate each
  against production's real apply (`Oracle.lean` dispatch + `formal/diff/` harness +
  `mutate.py` anchors). NO field is added without a differential pin.

### Phase 2 — Faithful perceive (derive the flags)
- Replace each opaque flag with a DERIVED predicate at its Phase-0 fidelity:
  `hasOverstockItems := inventoryUsed * 100 ≥ OVERSTOCK_NUM * inventoryMax`, etc.
  For M3 genuine-perceive Bools (gearReview/craftRelief), model the acquisition-
  event semantics (fires on a new better-loadout / new craftable-step; cleared by
  the action; re-arms only on the corresponding acquisition).
- DIFFERENTIALLY validate the derived flag ⟺ production's `perceive` output over
  random faithful states. This is the heart of faithfulness — a mismatch here is a
  model lie. Mutation-enforce.

### Phase 3 — The transience proof
- `chorePressure`, bounded-growth (step 2), chore-non-increase + clear (step 3,
  extend `BlockerQuieting`), bounded-burst (step 4).
- `RuntimeInvariant` def + its preservation under cycleStepP.
- `blockersQuiet_of_invariant` (the target theorem). Kernel-checked, standard
  axioms + LIV-001 only.

### Phase 4 — Re-wire the capstone
- Drop `hfightFiresP`'s reliance on the BlockersQuiet HYPOTHESIS: feed
  `blockersQuiet_of_invariant` into `FightFairnessP.hfightFiresP_of_blockers_quiet`.
- New `GlobalInvariantsP` carries `RuntimeInvariant` instead of `hfightFiresP`.
- `ai_reaches_level_fiftyP` now rests on {LIV-001, WinnableAcrossBand,
  RuntimeInvariant}. If Phase 3 proves `RuntimeInvariant` preserved-from-spawn,
  it collapses to a spawn condition; else it is the new, MINIMAL, PRECISE residual
  (vastly smaller than opaque BlockersQuiet, and differentially grounded).

### Phase 5 — Gate + adversarial review
- Full `formal/gate.sh` green (build, no-sorry, axiom-lint, manifest, contracts,
  differential, mutation). Serialize per [[feedback_serialize_gate_runs]].
- Phase-4 adversarial review: does the faithful perceive model tell the truth about
  reachable bot states? Hunt the dishonest-proof patterns ([[feedback_proofs_tell_false_stories]]).

## SCOPE DECISION (2026-06-18): A + B, both in scope. Build Phase 0 now.
Workstream B is committed (not deferred). Phase 0 probes BOTH: the chore-flag
perceive map (A) and the winnability/loadout/base-stat data path (B), to scope
exactly what live capture B needs.

## Workstream B — WinnableAcrossBand (#2), data-gated, SEPARATE
Faithful discharge of #2 is blocked on DATA, not modeling: the server exposes only
total stats, never per-level base stats, and attack is gear-derived (no-gear char
does zero damage). Two honest paths, neither pure modeling:
- **B-data:** capture per-level base-stat + best-craftable-loadout from a live
  character leveling 1→50 (a `GameDataFixture`-style data obligation), then a
  sweep differential validates a winnable in-band target ∀L. Real data-capture
  infrastructure + a live run.
- **B-axiom:** accept WinnableAcrossBand as a documented server-data axiom beside
  LIV-001 (needs per-axiom signoff + openapi citation, [[project_liveness_axiom_split]]).
Recommend B is deferred behind Workstream A — A is the "perfect model" core (the
bot's own dynamics); B depends on external data the model cannot conjure.

## Honest risk
`BlockersQuiet` may turn out CONDITIONALLY true — provable only modulo a
`RuntimeInvariant` the bot does not always maintain (the historical livelocks are
evidence). That is a SUCCESS, not a failure: it converts a hidden assumption into
a precise, enforceable runtime contract, and may surface a real bot bug. The plan
must report `I` honestly even if `I` is non-trivial.

## Status
- 2026-06-18: drafted. Phase 0 (faithfulness probe) is the lynchpin and gates all
  modeling detail — its output fixes the State fields and the abstraction level.
  Awaiting scope decision (Workstream A only vs A+B) before Phase 0 build.
- 2026-06-18: scope = A+B, Phase 0 COMPLETE (abstraction decided, see Phase-0
  FINDINGS above).
- 2026-06-19: **Workstream B Phase-1 infra COMPLETE** (commits 6a05d5c, 3aaed18,
  8afdb43). Built: (1) `snapshot_game_data.py` serializes item combat stats; (2)
  `capture_base_stats.py` — user-run live tool, strips all 16 equip slots to read
  per-level BASE stats, resumable merge, try/finally restore, 5 mocked tests; (3)
  `best_weapon_for_level` catalog proxy (100% cov, 7 tests); (4)
  `formal/diff/test_winnable_across_band_diff.py` — per-level sweep with REAL
  `is_winnable`, faithful base+weapon WorldState, optimistic-weapon proxy
  documented, SKIPS until fixtures captured (2 synthetic tests green).
  **USER ACTION (the long pole):** (a) re-run `snapshot_game_data.py` against live
  API (combat fields); (b) run `capture_base_stats.py <char>` once per level 1..49
  over a real session. Then the real sweep validates WinnableAcrossBand.
- NEXT: **Workstream A Phase 1** — the perfect-model core (faithful inventory-
  pressure State extension + apply cores). Offline, no data dependency. Delicate:
  extends `Measure.State` (additive; ripples into Oracle 31-int layout + diff
  harnesses; ~50 dependent proofs must not break) → its own gated, subagent-driven
  multi-brick effort. Per [[feedback_serialize_gate_runs]] serialize the gate.
```
