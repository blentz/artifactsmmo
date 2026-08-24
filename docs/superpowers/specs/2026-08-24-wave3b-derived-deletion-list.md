# Wave 3b — the deletion list, RE-DERIVED at execution time

**Status:** gating artifact for wave 3b. No production code was written and
nothing was deleted to produce this document. Every verdict below was derived
against the worktree `.worktrees/waves-3-6` at HEAD (`be966327`, branch
`waves-3-6`, identical to `main`), **after** wave 3a and its four fix rounds
landed.

**This document supersedes §6.1 of
`docs/superpowers/specs/2026-08-23-wave3-resolution-design.md`.** That table was
written at `1bffc75e`, before THE FLIP (`4539b9cb`) and before fix-rounds 1–3
(`6a4a1dcd`, `5de9669a`, `60e71243`) *reconnected* machinery the table assumes
died. Six of its sixteen rows are wrong at HEAD, and one of the wrong ones would
have deleted a kernel-checked liveness proof over a function the bot calls on
every aged cycle. §6.1 is cited elsewhere; **do not use it unamended.** Use §8 of
this document for the list of what it got wrong.

The lesson this repeats, in the words the wave-3c investigation used: *a deletion
list ages against the branch it was written on; re-derive it at execution time,
never trust it at authoring time.*

---

## 1. Method, and what counts as a consumer

For every row I separated three things that this epic has repeatedly seen
conflated:

* **production caller** — a real call or attribute read in `src/` or `scripts/`.
* **comment / docstring mention** — prose naming the symbol. Not a caller.
  Eleven times in this epic a corrected claim survived in the comment that
  justified it; §7 lists the current crop.
* **test reference** — `tests/` or `formal/diff/`. Not a caller, and in this
  epic **explicitly not evidence of liveness**: see §6.4 on why the mutation
  gate cannot discharge 3b's premise.

Two traps were specifically hunted:

1. **Consumers that never name the symbol.** The live consumers of
   `player._gear_focus` / `player._interleave_seats` do not import them and do
   not name the attributes: the dicts are handed to `SelectionContext` as
   *data* (`player.py:3762-3763`) and read off `ctx` two modules away
   (`decisions/root.py:347`, `:365`). A grep for `_gear_focus` inside
   `decisions/` returns nothing. This is exactly the shape that inverted a
   verdict in wave 3c.
2. **Callers-of-callers.** `achievability_core` and `role_alignment` each still
   have exactly one importer in `src/`, so a naive grep reads them as live. Both
   importers are *themselves* uncalled private helpers in `progression_tree.py`
   (`_achievability_map`, `_role_map`), orphaned by THE FLIP.

**Live-behaviour claims** rest on `~/.cache/artifactsmmo/learning.db` only
(78,800 cycles, latest `2026-08-24T03:50:26Z`), never on trace files.

---

## 2. The headline: wave 3a is live, and that is *why* half of §6.1 is wrong

`learning.db` shows `ReachSkill(...)` goals selected on 82 cycles up to
`2026-08-24T03:50:26Z` (`gearcrafting→10/11/16`, `jewelrycrafting→4/8/16`). Only
the wave-3a root walk can put a `ReachSkillLevel` in `chosen_step`
(`decisions/root.py`'s `IsThisTargetBlocked` skill arm → `strategy_driver.py`'s
`ReachSkillLevel` arm). So the walk is the live producer of the root.

The walk is *not* the ranking's replacement in the sense of using none of its
parts. Fix-round 1 (`6a4a1dcd`) deliberately **re-used** the ranking's
anti-starvation machinery inside `WhichSlotIsFurthestBehind`, threading the
player's focus ledger and d'Hondt seats through `SelectionContext` instead of
through `decide_tree` parameters. §6.1 was written before that happened and
still lists those parts as dead.

---

## 3. Per-row verdicts for §6.1

Counts are src/production callers at HEAD. **DELETE** = still dead. **KEEP** =
came back to life, or never was dead. **SPLIT** = part dead, part live.

| # | §6.1 item | verdict | evidence at HEAD |
|---|---|---|---|
| 1 | `RootScore.cost` | **DELETE** | 0 readers. Now **1** writer, not 2 — the only `RootScore(...)` construction in `src/` is `tiers/progression_tree.py:462-465`, which pins `cost=0`. Serialised by `asdict` at `tiers/strategy.py:255-260`; `RootScoreView` (`ai/cycle_snapshot.py:8-14`) has no such field. |
| 2 | `RootScore.contribution` | **DELETE** | 0 readers. Same single writer, pinned `Fraction(1)` (`progression_tree.py:464`); floated at `strategy.py:259`. |
| 3 | `RootScore.instrumental` | **DELETE** | 0 readers **and now 0 writers** — `_resolution_rows` does not pass it (`progression_tree.py:462-465`), so it is the dataclass default at `strategy.py:225`. Pinned always-False by `tests/test_ai/test_tiers_strategy.py`. |
| 4 | `objective_step_goal(committed_root=…)` | **DELETE** | Declared `ai/strategy_driver.py:610`; `awk` over the whole function body finds the identifier exactly once — the parameter line. **Five** call sites, not four: `strategy_driver.py:1116`, `:1124`, `:1132`, `:1368`, and **`ai/player.py:2921`** (inside `_step_servable`'s `servable` closure), which §6.1 missed. |
| 5 | `StrategyDecision.desired_state` | **DELETE** | 1 reader, `to_trace` (`strategy.py:321`), always `{}`. But **five** production construction sites must be edited, not one: `progression_tree.py:531` plus four censuses — `audit/recycle_source_completeness.py:353`, `audit/shed_reachability_completeness.py:360`, `audit/inventory_completeness.py:499`, `audit/obtain_parity_completeness.py:383`. §6.1 counted none of the four. The field is a required positional, so removing it is not source-compatible. |
| 6 | `StrategyDecision.aged_pick` | **KEEP** | **Reconnected and live.** Produced by `RootResolution.aged` (`decisions/root.py:87-92`, set at `:367`), copied on at `progression_tree.py:539`, and read every cycle by `GamePlayer._bump_focus` → `_charge_focus` (`player.py:584`, `:590`, `:592`, `:612`). Also mirrored into the trace (`player.py:2305-2306`) and the snapshot (`player.py:2721-2722`, `cycle_snapshot.py:182`). It does **not** "die with the seat ledger" — it *gates* the seat ledger. |
| 7 | `StrategyDecision.j_ranking` | **DELETE**, with §6.1's reasoning corrected | §6.1 says "2 src consumers". At HEAD it has **zero producers** — nothing in `src/` assigns it, so it is permanently `[]` — and **one reader**, `to_trace` (`strategy.py:329-333`), which iterates the empty list and calls `finite_j`. Deleting it must also strip that `to_trace` block and `strategy.py`'s `finite_j` / `ProgressionCandidate` imports (`:14`, `:29`), which is what removes `tiers/strategy`'s dependency on `branch_objective`. |
| 8 | `tiers/achievability_core.py` | **DELETE** | Sole `src` importer is `progression_tree.py:30` (`achievability_pure`), used only inside `_achievability_map` (`progression_tree.py:383-392`) — and `_achievability_map` has **zero callers**: the only occurrence of the name in `src/` is its own `def`. Dies with it: `progression_tree._effort_for` (`:293-329`) and `_skill_gate_levels` (`:266-291`), whose only reachable caller is `_achievability_map:390`. |
| 9 | `ai/role_alignment.py` | **DELETE** | Sole `src` importer is `progression_tree.py:27` (`role_alignment_pure`), used only inside `_role_map` (`progression_tree.py:395-431`) — **zero callers**, only its own `def`. ⚠️ §6.1's note *"`ctx.role_skills` stays — `supply_target` uses the same channel"* is **wrong at HEAD**: `_role_map` was the *only* reader of `SelectionContext.role_skills` (`selection_context.py:119`), so once it goes, `role_skills`, its producer `player._role_owned_skills` (`player.py:3785-3811`) and the wiring at `player.py:3751` are all zero-reader. Same channel ≠ same field. See §5 — this is one of the items §6.1 does not list at all. |
| 10 | `tiers/horizon_contribution.py` | **KEEP** | Two production consumers, neither in the ranking: `tiers/branch_objective.py:82` imports `horizon_outcome`, called at `:143`; `scripts/measure_means_suppression.py:41` imports `cycles_to_horizon`, called at `:278`. It also re-exports `TARGET_LEVEL` from `progression_choice` (`horizon_contribution.py:44`). Row 12 keeps `branch_objective` alive, so this row is dead only if the `objective` CLI is retired, which wave 3 does not do. |
| 11 | `tiers/progression_choice.py` | **KEEP** | Four production importers: `commands/objective.py:40-42` (`TARGET_LEVEL`, `ProgressionCandidate`, `candidate_band`), `branch_objective.py:83-89`, `horizon_contribution.py:44`, `strategy.py:29`. `commands/objective.py` is a **registered CLI command** (`main.py:17`, `:63-66`), i.e. shipped production surface. `progression_tree.py:206-209` says this in the source already: the legacy `objective` CLI "still runs the retired ranking on its own and is explicitly out of this wave's scope." Deleting `progression_choice` therefore means deleting the `objective` command — a scope change, not a dead-code removal. |
| 12 | `tiers/branch_objective.py` | **KEEP** | `commands/objective.py:39` imports `branch_ranking` and `finite_j` (used `:112`, `:155`, `:264`); `scripts/measure_means_suppression.py:39` imports `TRUNK_IDENTITY`, `branch_ranking` (`:334`); `strategy.py:14` imports `finite_j`. §6.1 listed this row inside a table headed "safe to delete" while its own note says it is "the live pivot, not dead code" — the note is right and the placement is wrong. |
| 13 | `progression_tree_core`: `falloff`, `focus_aging_pick`, `focus_aging_order`, `dhondt_step`, `FOCUS_FLAT`, `bump_seats` | **SPLIT** | See §4. Three of the six are **live**, two are dead, and one **does not exist**. |
| 14 | `player._gear_focus` | **KEEP** | Mutated at `player.py:597` (`_charge_focus`), pruned at `:663-664` and `:693-695`, mirrored to trace `:2302` and snapshot `:2719`, and — the load-bearing one — handed to the walk as `ctx.gear_focus` at `player.py:3762`, read at `decisions/root.py:347` (`ctx.gear_focus.get(key, 0)`) to decide the flat-window fast path at `:348`. |
| 15 | `player._interleave_seats` | **KEEP** | Mutated at `player.py:614`, pruned `:667-668`, `:697-698`, mirrored `:2304`, `:2725`, handed over at `player.py:3763`, and consumed at `decisions/root.py:365` — `dhondt_step(weighted, ctx.interleave_seats)`. |
| 16 | `_synergy_map` (the call in `decide_tree`) | **DELETE**, and wider than §6.1 says | The *call* is already gone (3a). The **function** `progression_tree._synergy_map` (`:331-380`) now has zero callers, so the whole function goes, not just a call. `tiers/synergy_core.py` still **STAYS** (§6.2 holds): `tiers/taskmaster_choice.py:26` and `tiers/means_worth.py:16` are live non-ranking consumers. |

**Counts: 9 DELETE, 6 KEEP, 1 SPLIT.**

---

## 4. Row 13 in detail — `progression_tree_core`

This is the row that matters most, because §6.1 gets the split backwards and the
consequence is a deleted proof.

| symbol | verdict | evidence |
|---|---|---|
| `falloff` (`:79`) | **KEEP — LIVE** | Imported `decisions/root.py:57`, called `:363` inside `WhichSlotIsFurthestBehind._aged_head`. |
| `dhondt_step` (`:97`) | **KEEP — LIVE** | Imported `decisions/root.py:56`, called `:365`. |
| `FOCUS_FLAT` (`:56`) | **KEEP — LIVE** | Imported `decisions/root.py:55`, the flat-window guard at `:348`. |
| `focus_aging_pick` (`:257`) | **DELETE** | No production caller; name occurs in `src/` only in its own `def` and in five comments (`progression_tree.py:537`, `strategy.py:287`, `selection_context.py:221`, `:237`, `root.py:119`, `:272`). |
| `focus_aging_order` (`:307`) | **DELETE** | Same — `def` plus comments at `progression_tree.py:63`, `:146`, `selection_context.py:222`. |
| `bump_seats` | **DOES NOT EXIST** | There is no `bump_seats` anywhere in `src/`, `scripts/`, `tests/` or `formal/`. The only occurrence in the repository is §6.1's own row. The real symbol is the **Lean** `Formal.ProgressionTree.bumpSeats` (`formal/Formal/ProgressionTree.lean:419`), whose Python counterpart is the inline increment `player.py:614`. Both are live. |

Two more corrections inside this row's "**stay**" list. `milestone_pure`,
`Branch`, `GearCandidate` and `potion_type_weight` do stay — `milestone_pure`
`decisions/root.py:190`, `:486`, `:509` + `commands/objective.py:356` +
`scripts/measure_means_suppression.py:277`, `:366`; `Branch`/`GearCandidate`
`branch_objective.py:91`; `potion_type_weight` `progression_tree.py:159`. But
**`branch_pick_pure` (`:28`) does not stay** — it has zero production callers
(only prose at `skill_grind_cost_core.py:21`, `progression_choice.py:7`, `:26`,
`branch_objective.py:5`, `:7`, `:304`), and was already superseded by
`branch_from_ranking`.

---

## 5. Newly dead since §6.1 was written — items the list does not contain

THE FLIP orphaned more than §6.1 knew about. A 3b agent working only from §6.1
will leave all of this behind. Each has **zero production callers** at HEAD;
each was verified by grepping `src/` and `scripts/` for the bare name and
finding only the definition plus prose.

**In `tiers/progression_tree.py`:**

| symbol | line | note |
|---|---|---|
| `_j_by_identity` | `:213-229` | Orphaned when `decide_tree` stopped ranking. Its `finite_j` import (`:32`) and `ProgressionCandidate` import (`:36`) go with it. |
| `_synergy_map` | `:331-380` | Row 16; the `_NO_SYNERGY` (`:38`) and `synergy_pure` (`:43`) imports go with it. |
| `_achievability_map` | `:383-392` | Row 8; `achievability_pure` import `:30`. |
| `_role_map` | `:395-431` | Row 9; `role_alignment_pure` import `:27`. |
| `_effort_for` | `:293-329` | Reachable only from `_achievability_map:390`. |
| `_skill_gate_levels` | `:266-291` | Reachable only from `_effort_for:316`. |

**Public schema fields, zero-reader after 3a.7 (`76e64ad4`) deleted
`plan_tree.rank_detail`:** `RootScore.j` (`strategy.py:226`),
`RootScore.reachable_level` (`strategy.py:240`), and `RootScore.score`
(`strategy.py:222`, frozen to `Fraction(1)` at `progression_tree.py:464`). The
source says so itself at `progression_tree.py:190-196`. Note `RootScoreView.score`
(`cycle_snapshot.py:13`) is a *separate* required float — that is 3b.2's
snapshot-schema question, and `commands/plan.py:79` and `plan_tree.py:52-54`
both record that it is kept only for the schema pin.

**In `tiers/progression_tree_core.py`** — dead alongside `focus_aging_pick`:
`interleave_due` (`:122`), `gear_target_pick` (`:196`), `_gear_pref_key`
(`:166`), `_scaled_pref_key` (`:178`), `_scaled_weights` (`:233`), `_NO_SYNERGY`
(`:203`), `_NO_ACHIEVABILITY` (`:214`), `_NO_ROLE` (`:224`), `branch_pick_pure`
(`:28`). `gear_target_pick` and `_gear_pref_key` carry kernel-checked proofs
(§6); deleting a proved-but-uncalled helper is what
`feedback_proof_over_an_uncalled_helper` says to do, but it must be a deliberate
decision, made together with the manifest rows in §6.

**In `ai/selection_context.py` and `ai/player.py`:**
`SelectionContext.role_skills` (`selection_context.py:119`), its producer
`GamePlayer._role_owned_skills` (`player.py:3785-3811`) and the wiring at
`player.py:3751`. Zero readers once `_role_map` goes. §6.1 asserts the opposite;
see row 9.

**3b.2, restated:** `CycleSnapshot.gear_focus` / `.interleave_seats`
(`cycle_snapshot.py:176-189`) are the snapshot mirror of a **live** ledger, not
the residue of a dead one. My recommendation is **KEEP** both: deleting them
removes the only per-cycle visibility into the anti-starvation mechanism that
fix-round 1 was written to restore. If they are deleted anyway, that is a
diagnostics regression to be argued on its own merits, not a dead-code removal.
`CycleSnapshot.aged_pick` (`:182`) is likewise live.

---

## 6. The Lean and manifest side (3b.3 / 3b.4)

**The governing rule, and §6.1 breaks it:** *a Lean file whose Python subject is
still live must not be deleted.* Deleting a proof is not undone by a revert —
the proof has to be re-found.

| Lean artifact | verdict | evidence |
|---|---|---|
| `Formal/Liveness/InterleaveNoStarvation.lean` (404 lines) | **KEEP — §6.1 is wrong** | The file's subject is `dhondtStep` / `bumpSeats` / `interleaveDue` (`:42-55`, `:128-136`, `:158-...`), and `interleaveDue_reaches` is the bounded no-starvation result for the d'Hondt schedule. `dhondt_step` is called live at `decisions/root.py:365`. The theorem's own stated hypothesis — *"all weights strictly positive (the scaled selection weights `gain * falloff` are positive)"* (`:20-27`) — is discharged by the live caller, which builds `Fraction(max(1, tier_gap)) * falloff(level)` at `root.py:361-364`; the `max(1, …)` exists precisely so no weight is zero (`root.py:356-360`). The file is **not** inert. `Formal.lean:121` import stays. |
| `Formal/ProgressionTree.lean` (726 lines) | **SPLIT — and 3b.3's split line is INVERTED** | 3b.3 says delete "the falloff/d'Hondt half". That half is the **live** half. **KEEP:** `trunkCap`/`band`/`milestonePure` + `milestone_*` (`:62-108`), `potionWeight` + 2 theorems (`:140-160`), `focusFlat`/`focusSpan`/`focusFloor`/`falloffT`/`falloff` + all `falloff_*` (`:255-390`), `bumpSeats`/`dhondtQuot`/`selBeats`/`selectMax`/`dhondtStep`/`dhondtStepKey`/`interleaveDue` + `selectMax_quot_max`/`dhondtStepKey_quot_max` (`:419-573`). **DELETE:** `branchPick` + `branchPick_table`/`branchPick_gear_iff` (`:110-127`); `GearCand`/`better`/`pickFold`/`gearTargetPick` + `gearTargetPick_*` (`:162-253`); `lookupFocus`/`focusLevelOf`/`synergyOf`/`achievabilityOf`/`roleOf`/`scaledWeights`/`focusAgingPick` + `focusAgingPick_unaged_eq_argmax` (`:575-660`). |
| `Formal/Achievability.lean` (164 lines) | **DELETE** | Subject `tiers/achievability_core.py` is dead (row 8). Verified it is **not** a dependency of `InterleaveNoStarvation.lean` — that file imports only `Mathlib` and `Formal.ProgressionTree` (`:30-31`) and contains no occurrence of `Achievability`/`achievability`. `Manifest.lean:1365`'s "feeds `interleaveDue_reaches`" is a relevance note, not a Lean dependency. |
| `Formal/ProgressionChoice.lean` (214 lines) | **KEEP — §6.1 is wrong** | Subject `tiers/progression_choice.py` is live (row 11). Everything downstream stays with it: `Formal/Extracted/ProgressionChoice.lean`, `Formal.lean:78` and `:172`, `Manifest.lean:118-127` (9 rows), `Audit.lean:83-91`, `Contracts.lean:14`, `:478-...`, `Oracle.lean:2946-2955` + `:3189` (`runProgressionChoice`), `formal/diff/test_progression_choice_diff.py`, `scripts/extract_lean.py:443-448`, `mutate.py:1285-1332`. |
| `Formal/Synergy.lean` | **KEEP** | Per §6.2; `synergy_core` is live at `taskmaster_choice.py:26`, `means_worth.py:16`. |
| `Formal/Contracts.lean` | **NO CHANGE** | Its only reference in this set is `ProgressionChoice` (`:14`, `:478-...`), which stays. 3b.4 lists it needlessly. |
| `Oracle.lean` | **NO CHANGE** | Its only reference in this set is `runProgressionChoice`. 3b.4 lists it needlessly. |
| `Formal.lean` | one line | Remove **only** `:223 import Formal.Achievability`. Keep `:78`, `:121`, `:172`, `:222`, `:224`. |
| `Formal/Manifest.lean` | **5 + 6 rows, not 9 + 5 + 12** | Delete `:1338-1339` (`branchPick_*`), `:1342-1343` (`gearTargetPick_*`), `:1351` (`focusAgingPick_unaged_eq_argmax`), and `:1360-1366` (the Achievability header + 6 rows). Keep `:1334-1337`, `:1340-1341`, `:1344-1350` (milestone, potionWeight, falloff ×5, `selectMax_quot_max`, `dhondtStepKey_quot_max`), all of `:1352-1359` (Synergy) and all of `:118-127` (ProgressionChoice). |
| `Formal/Audit.lean` | **regenerate, do not hand-edit** | `formal/gate/check_audit_generated.sh` runs `uv run python scripts/gen_audit.py --check`; Audit.lean is derived from Manifest.lean. The rows that will disappear are `:1031-1032`, `:1035-1036`, `:1044`, `:1052-1057`. |
| `docs/behavioral_completeness/PROOF_CONCEPT_INDEX.md` | 1 row | Drop `:11` (`Achievability`). `ProgressionChoice` `:86`, `ProgressionTree` `:88`, `Synergy` `:101` stay. Re-run `scripts/gen_proof_concept_index.py --check`. |
| `formal/diff/test_progression_choice_diff.py` | **KEEP** | 3b.4 lists it for deletion. Its subject `sort_key` is live; it is the only pointwise pin of the shipped band literals (`branch_objective.py:111-115` cites it by name). |

### 6.4 `formal/diff/mutate.py` — and why its survivors cannot be 3b's evidence

**Group to SPLIT:** `PROGRESSION_TREE_MUTATIONS` (`:3645-3746`, run at
`:7657-7658` against `tests/test_ai/test_progression_tree_core.py`) mixes live
and dead subjects. **Keep** the two `falloff` mutants (`:3671-3678`) and the
three `dhondt_step` mutants (`:3679-3693`) — they now guard
`decisions/root.py`'s live call. **Delete** the four `focus_aging_pick` mutants
(`:3694-3723`) and the four `_scaled_weights` mutants (`:3724-3746`).

**Groups to DELETE:** `SYNERGY_ASSEMBLY_MUTATIONS` (`_synergy_map`; `:3827-…`,
run `:7661-7662`), `ACHIEVABILITY_CORE_MUTATIONS` (`ACHIEVABILITY_CORE_SRC` at
`:170`, list `:3960-3982`, run `:7687-7688`), `ROLE_ALIGNMENT_MUTATIONS`
(`ROLE_ALIGNMENT_SRC` at `:171`, list `:3987-4016`, run `:7689-7690`),
`ROLE_MAP_MUTATIONS` (`:4018-4040`, run `:7691-7692`).

**Groups to KEEP:** `PROGRESSION_CHOICE_MUTATIONS` (`PROGRESSION_CHOICE_SRC`
`:1289`, list `:1291-1332`, run `:7253-7254`), `TREE_OCCUPANCY_MUTATIONS`
(`:1131-…`, run `:7669`), and `ROOT_DECISION_MUTATIONS` (`ROOT_DECISION_SRC`
`:359`, list `:2841-…`), which already mutates the new flat-farm-window guard at
`:2964`.

**Methodological warning, and it contradicts plan 3b's stated gate.** §7.4 says
3b's evidence is "3a's mutation survivors". **It cannot be**, for the items in
this document. `focus_aging_pick`, `focus_aging_order`, `gear_target_pick`,
`_synergy_map`, `_role_map` and `achievability_pure` are all called **directly by
unit tests** — e.g. `tests/test_ai/test_role_alignment.py:82-113` calls
`focus_aging_pick`/`focus_aging_order` directly, `tests/test_ai/test_synergy_assembly.py:60-285`
calls `_synergy_map` sixteen times. A mutant of an uncalled function that a unit
test invokes directly is still **killed**, so it never appears as a survivor.
The re-derived caller analysis in §3–§5 is the evidence; the mutation gate is
only a regression guard afterwards.

---

## 7. Stale prose found in this sweep — **11 instances**

Not fixed here (that is the implementation task). Every one asserts something is
dead, uncalled, inert or produced by a mechanism that no longer produces it, and
my re-derivation shows otherwise.

1. **`src/artifactsmmo_cli/ai/selection_context.py:221-222`** — *"`decide_tree`
   was the only production caller of `focus_aging_pick` / `focus_aging_order` /
   `dhondt_step`"*. True for the first two; **false for `dhondt_step`**, called
   at `decisions/root.py:365`. This is the eleventh recurrence of the
   corrected-claim-survives-in-its-own-comment defect, and it sits in the very
   comment that documents the fix that made it false.
2. **`selection_context.py:223`** — *"left `falloff` and the d'Hondt scheduler
   with zero callers"*. Both have a caller: `root.py:363`, `:365`.
3. **`selection_context.py:224-225`** — *"left
   `Formal.ProgressionTree.interleaveDue_reaches` … INERT over a function
   nothing calls"*. The proof is not inert; see §6.
4. **`selection_context.py:224`** — the same citation names the **wrong module**:
   `interleaveDue_reaches` is declared in `Formal.Liveness.InterleaveNoStarvation`,
   not `Formal.ProgressionTree`. It passes `check_proof_citations.sh` only
   because that script resolves on the **leaf name** across all of
   `formal/Formal` (`check_proof_citations.sh:70-79`), so a wrong namespace is
   invisible to the gate.
5. **`tiers/progression_tree.py:491-492`** — *"`StrategyDecision.aged_pick` and
   `.j_ranking` now take their field defaults"*. False for `aged_pick`: it is set
   from `resolution.aged` 48 lines below, in the same function
   (`progression_tree.py:539`). The same docstring's own §"What SURVIVES" list
   does not mention it.
6. **`tiers/strategy.py:283-292`** — the `aged_pick` field comment describes its
   producer as *"the negation of `focus_aging_pick`'s fast-path condition, over
   the SAME candidates"*. At HEAD the producer is
   `WhichSlotIsFurthestBehind._aged_head` (`root.py:347-367`) over gear
   **targets**, and `focus_aging_pick` is uncalled.
7. **`tiers/progression_tree.py:402-403`** — `_role_map`'s docstring: *"the
   caller (`decide_tree`, off `ctx.role_skills`) already has them"*. `decide_tree`
   no longer calls `_role_map`, and nothing reads `ctx.role_skills`.
8. **`tiers/progression_tree.py:398-399`** — `_role_map` described as *"the FIFTH
   selection factor"* of a product (`_scaled_weights`) that nothing computes.
9. **`ai/selection_context.py:111-118`** — *"`progression_tree._role_map` turn
   this straight into the per-candidate role-fit multiplier"* and *"`_role_map`
   returns `{}` for it, the inert four-factor product"*: describes a live path
   through a function with zero callers. This is the comment that makes
   `role_skills` *look* live.
10. **`formal/diff/mutate.py:3793-3796`** — *"`_synergy_map` (progression_tree.py)
    — the impure B-assembly … decide_tree's GEAR-branch fallback ORDER"*.
    `decide_tree` does not call it.
11. **`formal/diff/mutate.py:4006-4008`** — *"`_role_map` … the impure assembly
    that ACTIVATES the … `decide_tree`"*. Same.

Borderline, recorded but not counted: `ai/cycle_snapshot.py:181` ("the interleave
… rather than the plain argmax" — the argmax no longer exists) and
`tiers/progression_tree.py:4-5` ("Consumes the same helpers the flat ranking
used" — half true, and the half that is true is exactly the half §6.1 wants
deleted).

---

## 8. What §6.1 got WRONG — the amendment list

§6.1 is cited from other wave documents. A future reader must not trust it
unamended. These are its errors, in descending order of danger.

1. **It marks `falloff`, `dhondt_step`, `FOCUS_FLAT` and
   `InterleaveNoStarvation.lean` (whole file) for deletion.** All are live
   (`decisions/root.py:55-57`, `:348`, `:363`, `:365`). **This is the most
   dangerous item on the list**: deleting the Lean file destroys
   `interleaveDue_reaches`, the bounded no-starvation proof for the exact
   mechanism that fix-round 1 reconnected to cure the ring2 starvation livelock,
   and a deleted proof is not recovered by `git revert` in any meaningful sense
   — it has to be re-proved.
2. **3b.3 says "the falloff/d'Hondt half of `ProgressionTree.lean`" is the part
   to delete.** It is exactly backwards: that is the live half. The dead half is
   `branchPick` + the `GearCand`/`gearTargetPick` argmax + the
   `scaledWeights`/`focusAgingPick` block.
3. **It marks `player._gear_focus`, `player._interleave_seats` and the
   `CycleSnapshot` fields for deletion.** Both dicts are read live through
   `SelectionContext` (`player.py:3762-3763` → `root.py:347`, `:365`). Neither
   is named anywhere in `decisions/`, which is why a name-based grep misses them.
4. **It marks `StrategyDecision.aged_pick` "dies with the seat ledger".** It
   gates the seat ledger (`root.py:367` → `progression_tree.py:539` →
   `player.py:612`).
5. **It names `bump_seats` as a Python symbol.** No such symbol exists anywhere
   in the repository. The referent is Lean's `bumpSeats`
   (`ProgressionTree.lean:419`), which is live.
6. **It lists `branch_pick_pure` among the symbols that "stay".** It has zero
   production callers and is deletable.
7. **It claims "`ctx.role_skills` stays — `supply_target` uses the same
   channel".** Same *channel*, different *field*: `role_skills` is read only by
   the now-uncalled `_role_map` and is zero-reader at HEAD.
8. **It puts `tiers/branch_objective.py`, `tiers/progression_choice.py` and
   `tiers/horizon_contribution.py` in a table headed "safe to delete (zero
   non-ranking consumers)"** when all three are reachable from the registered
   `objective` CLI command (`main.py:63-66`), which wave 3 does not retire.
9. **Its consumer counts are stale in both directions.** `objective_step_goal`
   has 5 call sites, not 4 (`player.py:2921` missed). `StrategyDecision.desired_state`
   has 5 production construction sites, not 1 (four censuses missed).
   `StrategyDecision.j_ranking` has 0 producers, not "2 src consumers".
   `RootScore.cost`/`.contribution` have 1 writer, not 2.
10. **It is incomplete.** THE FLIP orphaned six private helpers in
    `progression_tree.py`, nine symbols in `progression_tree_core.py`, three
    `RootScore` fields and a `SelectionContext` field that §6.1 does not mention
    at all (§5).
11. **3b.4 lists `Contracts.lean`, `Oracle.lean` and
    `formal/diff/test_progression_choice_diff.py` as needing edits.** None do —
    their only subject in this set is `ProgressionChoice`, which stays.
12. **3b.5 asks whether `scripts/measure_means_suppression.py` should be updated
    or retired.** **Neither.** Everything it imports survives:
    `cycles_to_horizon` (`:41`, row 10), `TRUNK_IDENTITY`/`branch_ranking`
    (`:39`, row 12), `milestone_pure` (`:45`, §4). No action.

---

## 9. Deletion ORDER — confirmed, with one refinement

The design's ordering is **Python → Lean → manifest/audit/index**, and it is
still correct on my re-derived list. I read both gate scripts to check the
stated reasons rather than take them on trust.

* **`formal/gate/check_proof_citations.sh`** scans `src/` and `formal/diff/`
  for `Formal.<Ns>.<name>` citations and fails when the leaf name resolves to no
  declaration or module under `formal/Formal` (`:50-99`). So deleting Lean
  *first* leaves a dangling citation and fails the gate. Concretely for this
  list: `progression_tree_core.py:172` cites `Formal.ProgressionTree.better` and
  `focusAgingPick_unaged_eq_argmax` — both in §6's DELETE column — so that
  Python comment must be gone before the Lean declarations are.
  **Python first is right.**
* **`formal/gate/check_no_orphan_modules.sh`** requires every `.lean` under
  `Formal/` to be imported by `Formal.lean` (`:30-60`). So a deleted import with
  the file still present is an orphan and fails.

**Refinement the design does not state, and it matters:** the third step is not
freely deferrable. `Manifest.lean` and `Audit.lean` are *compiled* by the gate
and name declarations directly (`Audit.lean:1031-1057`, `Manifest.lean:1334-1366`).
A commit that deletes `focusAgingPick` while `Manifest.lean:1351` still `#check`s
it does not merely drift — it **fails to elaborate**. So:

1. **Commit A (Python).** All §3 DELETEs plus all §5 additions, including every
   comment that cites a Lean name being removed. Gate is fully green here; no
   Lean file has changed.
2. **Commit B (Lean, atomic).** The `Achievability.lean` deletion **together
   with** `Formal.lean:223`, **together with** the `Manifest.lean` row removals
   from §6, **together with** the `ProgressionTree.lean` intra-file deletions,
   **together with** a regenerated `Audit.lean` (`uv run python
   scripts/gen_audit.py`). These four cannot be split across commits without a
   red intermediate: orphan check, citation check, manifest elaboration and
   `check_audit_generated.sh` each fence a different pair of them.
3. **Commit C (harness + index).** `mutate.py` group split and anchor refresh
   (anchors must resolve to exactly one site, and refreshing them belongs in the
   same commit as the edit per `project_mutation_anchor_hardening`), plus
   `scripts/gen_proof_concept_index.py --check`.
4. **Commit D (schema), only if taken.** `CycleSnapshot` changes with a schema
   version bump — and per §5 my recommendation is that this commit is **empty**,
   because the snapshot fields mirror live state.

Run `bash formal/gate.sh` (≈5 min, one command) after B and after C. Redirect to
a file or read `${PIPESTATUS[0]}` — piping it to `tail` reports the tail's exit
code and has already turned a visible `GATE FAIL` into `rc=0` once in this repo.

---

## 10. What I could not determine

* **Whether the `objective` CLI command should survive wave 3 at all.** Rows
  10–12 are KEEP *because* it exists. If a later wave retires it, all three
  modules plus `ProgressionChoice.lean` and its nine manifest rows become
  deletable in one stroke. That is a scope decision, not a fact I can derive
  from the code, and `progression_tree.py:206-209` says it is out of this wave's
  scope.
* **Whether the `WhichSlotIsFurthestBehind` d'Hondt arm has actually fired in
  production.** `learning.db`'s `cycles` table records no `aged_pick` column, so
  the live-firing question cannot be settled from the only admissible source.
  What is settled: the code path is reachable and imported, and `ReachSkill`
  goals prove the walk itself runs. The KEEP verdicts on rows 6, 13, 14, 15 rest
  on the call graph, which is sufficient — an uncalled arm of a called function
  is still a caller for deletion purposes.
* **Test-line accounting.** §7.4's "~3,770 lines of test" is not re-derived here;
  the per-symbol test-module map is in the evidence but I did not re-measure the
  total, and several modules (`test_ring2_starvation_repro.py`,
  `test_decisions_root.py`, `test_progression_tree_core.py`) now cover the LIVE
  falloff/d'Hondt path and must be preserved rather than deleted wholesale.

---

## 11. Amendments after task 4 executed (2026-08-24)

Task 4 deleted the five ranking modules. Its review found four corrections to
this document. Recorded here rather than in a task report, because tasks 6 and 7
act on this catalogue and a task report is not where they will look.

### 11.1 `Contracts.lean:478-521` holds SEVEN bridge examples, not nine

The task-4 orphan catalogue said nine. **It is seven** — `:484, :489, :494,
:499, :505, :513, :519`, every one over
`Extracted.ProgressionChoice.ProgressionCandidate`. Nine is the `#check` count
at `Manifest.lean:118-127`, conflated.

**This matters and is not a tidying note.** The line range `:478-521` is
correct, so an agent deleting that range wholesale is safe. An agent *counting
to nine* over-reaches into `:530+`, which is `SkillXpPositive` — a LIVE
contract with live `Extracted.SkillXpPositive` bridges. Deleting two of those
would remove proofs of code the bot runs.

### 11.2 `_utility_candidates` is orphaned too, and §5 omits it

`tiers/progression_tree.py:120`. Its only remaining reachability is through
`objective_candidates` (`:174-175`), which task 4 reported as zero-caller and
correctly left alone as off-list. Its sibling `_structural_candidates` survives
independently via `has_structural_upgrade` -> `player.py:794`;
`_utility_candidates` does NOT.

This is the callers-of-callers shape §1 warns about. Whichever wave rules on
`objective_candidates` must rule on `_utility_candidates` in the same breath, or
it will under-scope by one function. Delete them together or keep them together.

### 11.3 Horizon-monotonicity is a KNOWINGLY DROPPED property

Task 4 deleted `reached_spread` and `tests/.../test_band_edge_horizon.py`
together. The reasoning is sound and the review confirmed it: the helper's
parameter type (`ProgressionCandidate`) and its only producer (`branch_ranking`)
are both deleted, and re-homing it would require the candidate projection loop
(`_outcome` -> `horizon_outcome`), also deleted — i.e. a reimplementation of a
deleted model.

The property it measured — **horizon-monotonicity of the objective's benefit
term** — is therefore not merely untested but currently UNSTATABLE: the
surviving `cheapest_path_to_level` is the benefit term, but nothing computes the
spread over candidates. Recorded here so it is a decision with a name rather
than a silent loss.

### 11.4 `Extracted/ProgressionChoice.lean` has stale provenance and has left the drift gate

Its header still reads `GENERATED from
src/artifactsmmo_cli/ai/tiers/progression_choice.py (sha256: d077ceff...)` for a
file that no longer exists, and removing its `ModuleSpec` from
`scripts/extract_lean.py` means `--check` no longer covers it — 24 modules now,
silently one fewer.

Task 6/7 must delete this file in the SAME commit as `Formal.lean:78` and
`Contracts.lean:14`. If that slips, add a one-line "provenance retired, pending
deletion" note to the header rather than leaving a file asserting a provenance
it cannot have.

## 12. Amendments after tasks 5, 6 and 7 executed (2026-08-24)

Five more errors in this document, found by executing it. Recorded because the
whole point of §11 and §12 is that a deletion list ages against its branch —
and this one aged against the very tasks it was written to drive.

### 12.1 A DELETE range that ends inside a KEEP declaration

§6.2 gives `ProgressionTree.lean:110-127` for `branchPick` and its two theorems.
**That range ends inside `inductive PotionFamily`, which is a KEEP item.**
Deleting it wholesale breaks the build. Task 6 deleted by DECLARATION NAME
(`:106-122` as the file then stood) rather than by the stated range.

Every other line range in §6.2 should be read as indicative, not executable.
Line numbers in this document were taken before tasks 1-5 shifted the files.

### 12.2 `Oracle.lean` and `Contracts.lean` DID need changes

§6.3 lists both as "no change". That was true only while row 11 was a KEEP.
Once the user retired the `objective` CLI and row 11 flipped to DELETE, both
had to change. Also: the path is `formal/Oracle.lean`, NOT `formal/Formal/`;
`runProgressionChoice` starts at `:2943`, not `:2946`; and its dispatch arm is
two lines.

### 12.3 §6's ProgressionChoice downstream was already partly gone

It lists `test_progression_choice_diff.py`, `extract_lean.py`'s `ModuleSpec` and
`PROGRESSION_CHOICE_MUTATIONS` as still to remove. Task 4 had already removed
them.

### 12.4 §6.4's mutant count is wrong in both directions

Task 5 found it naming 8 where the group held 19, with three more anchoring on
deleted code — retiring only the named 8 would have failed `--check-anchors` at
gate phase (b'''') before a single test ran. Task 6/7 then found **zero** left to
retire, because tasks 4 and 5 had already taken every group and mutant §6.4
names. The section is not a reliable count in either direction; count them
against `mutate.py` at execution time.

### 12.5 `inductive Branch` — RESOLVED, deleted 2026-08-24

Neither §4 nor §6 names it. Task 5 reported the Python `Branch` enum as newly
zero-consumer and left it (§4 lists it under "stay", on evidence that cites
`branch_objective.py:91` — a file task 1 deleted). Task 6/7 deleted the Python
mirror and reported the Lean `inductive Branch` for the same reason.

Controller ruling: **both deleted.** Verified zero Python consumers repo-wide and
zero real Lean references — `Oracle.lean:1905`'s "Branch 4" is a numbered
dispatch arm in `runActionCostNonneg`, not this type. The Python enum went with
`branchPick`'s mirror in task 6/7; the Lean inductive followed immediately, so
neither was left mirroring nothing. Gate rc=0 after.

Both implementers were RIGHT to report rather than delete off-list. The
discipline held; the ruling is the controller's job, and this is it.
