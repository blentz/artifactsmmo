# PLAN: Kill alphabetical tiebreaks in the strategy decision path

## Origin

Trace diagnosis (`play-trace-Robby.jsonl`, 2026-06-21): bot ran 369 cycles / 3.5h,
level **1→3**, never obtained its committed root `copper_boots` (267/375 cycles
committed; `Craft(copper_boots)` count = **0**; `gearcrafting` skill stayed **0**).

Root cause = **cross-root cannibalization**: `copper_boots` needs 8 `copper_bar`;
`copper_ring` needs 6. The arbiter oscillated chosen_root copper_boots↔copper_ring↔
wooden_shield; ring upgrades (equipped c77, c145) drained the bars boots needed, so
boots' `ObtainItem(copper_bar)` prereq never reached 8 simultaneously → `actionable_step`
never returned `copper_boots` → never crafted. Then the bot abandoned gear for chicken
grind where ~50% of cycles are RestoreHP.

**Recipe facts (live API, verified):** copper_boots = gearcrafting **L1**, {copper_bar:8};
copper_ring = jewelrycrafting L1, {copper_bar:6}; copper_bar = mining L1, {copper_ore:10};
wooden_shield = gearcrafting L1, {ash_plank:6}. Skills start at L1, so the gearcrafting
gate was **satisfied** — the skill node was NOT the blocker (corrects the earlier
"gate=5" guess). The blocker is shared-input contention + unstable root commitment.

User directive: **"alphabetical sort is almost always wrong. we should never be
resorting to it ever."** Two alphabetical sites in the decision path. User-confirmed
scope: replace BOTH + strengthen sticky to not drop a work-in-progress root.

## The two alphabetical sites

| # | Site | What alphabet decides | Severity |
|---|------|----------------------|----------|
| A | `tiers/strategy.py:204` `sorted(unmet, key=repr)` in `actionable_step` | which prereq branch becomes `chosen_step` (ObtainItem beats ReachSkillLevel by `'O'<'R'`; copper_bar beats copper_ore by spelling) | **live offender** — picks the step every cycle on no semantic basis |
| B | `tiers/decide_key.py:34` 4th field `root_repr` (`strategy.py:620`) | final tiebreak among ranked roots | **guarded backstop** — docstring (line 57-59) claims distinct roots never tie on leading fields, so it "never decides". Unproven assumption about production inputs. |

## Decisions (user-confirmed)

1. **Site A** → order siblings by **nearest-completion**: `sorted(unmet, key=lambda p:
   unmet_closure_size(p, state, game_data))`. Finish the branch closest to done first;
   drains work-in-progress, fights cannibalization.
2. **Site B** → replace `root_repr` final field with **`-owned_inputs`** (more recipe
   inputs already owned sorts first), repr demoted to an even-later genuine-uniqueness
   field if still needed.
3. **Sticky** → `sticky_choose` must **not drop a root that has work-in-progress inputs
   owned** even when a sibling dominates by ratio — so a half-built gear root is
   finished, not abandoned mid-build.

## ⚠️ Open risk to validate BEFORE the DecideKey proof churn

Site B may be **functionally inert**: if boots/ring/shield never tie on
(final, effort, protection) — they have different effort (`unmet_closure_size`) and
protection (`equip_value` gain) — then the repr field never actually fires, and adding
`owned_inputs` before it changes nothing. In that case the cannibalization is driven by
the **leading fields shifting as inventory changes** + the sticky ratio (3/2) breaking,
and the **load-bearing fix is the StickySelect WIP-retention (decision 3), not DecideKey
(decision 2)**.

**Action:** before paying the DecideKey proof cost, replay the boots/ring/shield cycles
via `artifactsmmo plan Robby` (plan CLI) instrumented to print per-root
(final, effort, protection, owned_inputs) and confirm whether two gear roots ever tie on
the leading three fields. If they never tie, descope decision 2 (or keep it as a cheap
correctness hardening but don't claim it fixes the stall). Update this plan with the
finding.

## Formal-gate cost per change

- **Site A (actionable_step order)** — LOW. `Formal/StrategyTraversal.lean` explicitly
  declares the DFS pick-order **implementation-defined** (lines 51, 538-539, 556, 921);
  `actStep_sound`, `actStep_some_reach`, `actStep_complete_min`,
  `actionable_step_sound/reach` are order-agnostic and DO NOT break. `unmetClosureSize`
  already modeled (line 499) with `unmetClosureSize_ge_one`, `_eq_count`. Work: confirm
  the differential harness for actStep doesn't pin a repr order; if it pre-sorts inputs
  by repr to match Python, update it to sort by closure size. No new theorem needed.
- **Site B (decide_key field)** — MEDIUM, only if not descoped. `Formal/DecideKey.lean`:
  add field to `Key` struct (line 65), extend `decideCmp` (line 75), re-prove
  `decideCmp_trichotomy/_swap/_lt_trans` (strict total order), add
  `decideCmp_eq_imp_negOwnedInputs` role theorem, keep `decideCmp_ne_of_repr_ne`.
  Update `Formal/Manifest.lean` roster + `Formal/Contracts.lean` exact-statement pin.
  Python: `decide_key` → 5-tuple; `strategy.py:620` passes `-owned_inputs`. Oracle JSON
  shape + `diff/test_decide_key_diff.py` + refresh `diff/mutate.py` anchors.
- **Site C / Sticky WIP-retention** — HIGH (liveness-sensitive).
  `Formal/Liveness/StickySelect.lean` carries kernel-proved **no-zombie liveness**
  (`sticky_requires_progress`, `no_infinite_sticky_hold`). Adding WIP-retention RISKS
  REINTRODUCING an infinite hold (hold forever because WIP never drains). The retention
  MUST stay bounded — hold only while the root is *progressing toward draining its WIP*,
  else release (couples to `next_last`/progress gate). Re-prove `no_infinite_sticky_hold`
  under the new rule or it's a regression. `sticky_select_core.py` `StickyCand` gains a
  `wip`/`owned_inputs` field; `sticky_choose` modified. Manifest + Contracts + Oracle +
  `diff/test_sticky_select_diff.py` + mutate anchors in lockstep.

## P0 RESULTS (2026-06-21, `scripts/p0_tiebreak_probe.py`) — reshapes the fix

Live Robby ranking (current state, 2 rings already equipped → copper_ring filtered out):

```
root            final  effort  protect  owned_in
copper_boots    2.50     3      10000      6     <- #1
wooden_shield   2.50     3       8000      4     <- #2 (TIES boots on final+effort)
...
weaponcrafting@5 1.53    4         0       0  } TIE on all 3 leading fields
gearcrafting@5   1.53    4         0       0  } -> repr DOES fire here
```

**Finding 1 — Site B (decide_key repr field) is INERT for the gear contest.**
copper_boots wins #1 over wooden_shield by **`protection`** (10000 > 8000), NOT repr.
`owned_inputs` agrees (6 > 4) → swapping repr→owned_inputs changes nothing at the top.
repr only fires among tied NON-gear skill-bootstrap roots (gearcrafting vs weaponcrafting
at 1.53/4/0) — low value, not the stall. **→ DESCOPE Site B / decision 2.** Keep only as
optional principle-cleanup per [[feedback_no_alphabetical_tiebreak]], NOT as the fix.

**Finding 2 — the cannibalization is NOT a tiebreak; it's the sticky PROGRESS GATE
releasing the boots anchor during long ore-gather stretches.**
`root_progress.py::_obtain_progress` already counts WIP — but only **DIRECT recipe inputs
in INVENTORY** (`state.inventory.get(mat)` over `recipe`), blind to (a) **transitive**
inputs (copper_ore, which boots needs via copper_bar) and (b) the **bank**. In the trace,
`GatherMaterials(copper_bar)` ran **55 cycles gathering copper_ore**; during that stretch
the direct copper_bar count is ~flat (bars only appear on smelt), so boots shows **no
progress** → `next_last` releases the anchor every cycle → a tied same-tier gear root
(copper_ring, when still unsatisfied) is free to win and consume the shared copper_bar.
Boots' bar pool never reaches 8 → never crafts. This is the precise mechanism behind
[[project_overgather_cannibalization]] + [[project_zombie_progress_gate]].

**Finding 3 — refined load-bearing fix: deepen the progress witness.**
Make `_obtain_progress` count the **transitive recipe closure + bank**, weighted by
`raw_material_units` (already in `recipe_closure.py:124`) so crafting conversions are
**non-decreasing**: 10 copper_ore (raw=1 each =10) → 1 copper_bar (raw=10) = 10, equal;
new gathers strictly increase it. Then boots registers progress through the whole
ore→bar→craft chain → anchor holds → no cannibalization. This is the
`hprogFaithful` production witness (`Formal/Liveness/ZombieFreedom.lean`); the Lean
no-zombie theorems assume `progressed` faithfully witnesses strict measure descent —
deepening the witness MUST preserve monotonicity (the raw-unit weighting is exactly what
guarantees it). No theorem STATEMENT changes; the trust boundary is the thing being
hardened. Differential/diff lock on `root_progress_value` (if any) must be updated.

**Revised scope:** Site A (nearest-completion sibling order) = keep as cheap
defense-in-depth. **Finding-3 progress-witness deepening = the real fix.** Site B / Sticky
WIP-retention via `stickyChoose` (original decision 2/3) = **descoped** — the progress gate
already holds tied roots once the witness sees through the gather stretch.

## Phases (TodoWrite-tracked; gate green between each)

- [x] **P0** DONE — `scripts/p0_tiebreak_probe.py`. Site B INERT; real fix = deepen the
      progress witness (Finding 2/3). See P0 RESULTS above.
- [x] **P1 (load-bearing)** DONE — `root_progress.py::_obtain_progress` deepened to the
      transitive recipe closure (`closure_demand`) + bank, weighted by `raw_material_units`.
      Live-verified monotone: gather ore ⇒ strict ↑, smelt 10 ore→1 bar ⇒ equal (non-↓),
      craft 8 bar→1 boots ⇒ equal, bank+inv additive, equipped dominates. Unit tests
      updated/added in `tests/test_ai/test_sticky_select_core.py`
      (`test_obtain_transitive_closure_raw_weighted` + fake extended); 28 tests green.
  - [x] **PROOF EXTENSION (user: "close the gap")** — new
        `formal/Formal/Liveness/ObtainProgress.lean` models the deepened witness as a
        computable `obtainProgress` def and PROVES its faithfulness (the `hprogFaithful`
        obligation `ZombieFreedom.lean` hand-waved to the differential for gear roots):
        `obtainProgress_gather_strict` (gather ⇒ strict ↑, kills the false-flat that
        released the anchor), `obtainProgress_mono` (owned ↑ ⇒ witness ↑),
        `obtainProgress_consume` (exact −delta), `obtainProgress_craft_invariant`
        (single-intermediate craft ⇒ witness UNCHANGED, via `rawUnits_top_eq_cost`
        conservation — covers the boots←bar←ore chain exactly). Built on existing proved
        `RecipeClosure.rawUnits`. Axioms = {propext, Quot.sound}. Wired: import into
        `Formal.lean`, roster in `Manifest.lean` (3 #checks), anti-weakening pins in
        `Contracts.lean`. `lake build` green for ObtainProgress + Contracts + Manifest.
  - [x] DIFFERENTIAL — `formal/diff/test_obtain_progress_diff.py` + oracle command
        `obtain_progress` (`Oracle.lean::runObtainProgress`) bridge the LIVE Python
        `_obtain_progress` to the Lean `obtainProgress` def over 250 random recipe graphs
        (acyclic+cyclic). Green. Node set computed independently of the function under test.
  - [x] MUTATION — `mutate.py` group `root_progress` (3 mutants: drop-bank, drop-weight,
        skip-closure) all KILLED by the differential; "mutation gate OK". `ROOT_PROGRESS_SRC`
        added to `_ALL_SRCS` + `run_group` wired.
  - [x] PHASE-4 adversarial review — theorems non-vacuous (boots/bar/ore witnesses);
        Contracts pins bind the strong statements via `@thm`; differential binds the live
        function; mutation confirms teeth. HONEST LIMITS: `craft_invariant` is
        single-intermediate only (gather_strict/mono cover all node counts); the proof
        closes witness FAITHFULNESS (no false-flat / no false-regression), NOT the full
        `hprogFaithful → reach-50 measureLt` link in ZombieFreedom (gear progress ≠ leveling
        axis) — that remains a hypothesis, not overclaimed.
  - [ ] REMAINING (optional): full `formal/gate.sh` run; ZombieFreedom hookup consuming the
        faithfulness theorems for gear roots; trace replay of the cannibalization window
        (needs live bot run or crafted-state sim) to behaviorally confirm boots holds its
        anchor through the ore-gather stretch and crafts.
- [ ] **P2 (defense-in-depth)** Site A: `actionable_step` sibling order repr→
      `unmet_closure_size`. Low formal cost (StrategyTraversal order impl-defined). Unit
      test pinning nearest-completion choice.
- [ ] **P3 (optional principle-cleanup)** Site B decide_key repr→owned_inputs ONLY if we
      want to honor the never-alphabet directive on the tied skill-bootstrap roots; pure
      formal churn, no behavior fix. Default: skip unless user wants it.
- [ ] **P4** Adversarial proof review: confirm deepened witness stays monotone (no false
      progress that would let a TRUE zombie hold), and `ZombieFreedom` story still honest.
- [ ] **P5** Full `formal/gate.sh` green + unit coverage gate; replay the trace scenario
      with rings UNsatisfied (the cannibalization window) and confirm boots now holds its
      anchor through the ore-gather stretch and crafts.

## Related memory

`[[project_zombie_commitment_livelock]]`, `[[project_zombie_progress_gate]]`,
`[[project_overgather_cannibalization]]`, `[[project_skill_grind_committed_item]]`
(cross-skill cannibalization "known residual"), `[[project_protection_tiebreak]]`
(precedent: replaced an alphabetical tiebreak with computed value), `[[project_plan_cli]]`
(the replay vehicle), `[[project_o54_select_differential]]` (sticky firing bound to
production).
