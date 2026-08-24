# Wave 3b — the deletion

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the ranking machinery wave 3a made uncalled — Python, then Lean,
then the harness — leaving the gate green at every step.

**Architecture:** Wave 3a replaced a scored argmax with a resolution walk over
five named `Decision` nodes. It is merged and LIVE: `ReachSkill` fires on all
five characters, which it never did in 63,310 prior cycles. What the ranking left
behind is now deletable — but only the parts that are actually dead.

**Tech Stack:** Python 3.13, `uv`, pytest, mypy strict, ruff, Lean 4.

**Spec:** `docs/superpowers/specs/2026-08-24-wave3b-derived-deletion-list.md`

## THE LIST IS THE SPEC, AND THE OLD LIST IS WRONG

The wave-3 design's §6.1 "safe to delete" table is **stale and must not be
used**. Re-derivation against HEAD found **7 of its 16 rows wrong**: 9 DELETE,
6 KEEP, 1 SPLIT. Wave 3a's own fix rounds resurrected machinery §6.1 assumes
died. Two errors would have been unrecoverable:

- §6.1 marks `falloff` / `dhondt_step` / `FOCUS_FLAT` deletable together with
  **`InterleaveNoStarvation.lean` as a whole file**. All three are live
  (`decisions/root.py:55-57`, used `:348`, `:363`, `:365`), so that file is a
  kernel-checked no-starvation proof over a function the bot calls on every aged
  cycle. **A deleted proof is not recovered by a revert.**
- 3b.3's split line is **exactly inverted**. It says delete "the falloff/d'Hondt
  half of `ProgressionTree.lean`" — that is the LIVE half.

**Every deletion in this plan comes from the re-derived list, not from §6.1.**
If the two disagree, the re-derived list wins. If you find a THIRD answer, stop
and report — do not average them.

## User rulings folded in

- **The `objective` CLI is RETIRED in this wave** (user, 2026-08-24). It ran the
  retired ranking behind a LEGACY banner and contradicted the live decision.
  This flips rows 10, 11 and 12 from KEEP to DELETE and takes
  `Formal/ProgressionChoice.lean` and its whole downstream with them.
- **`scripts/measure_means_suppression.py` retires with it.** It is increment 0
  of `docs/PLAN_band_unification.md`, marked ✅ DONE with its verdict recorded in
  that document; it is not gate-wired or CI-wired. Its only remaining role is
  keeping three dead modules importable.

## Global Constraints

- Every Python command is prefixed `uv run` (CLAUDE.md). If `uv` is not on PATH,
  use `/home/blentz/.local/bin/uv`.
- One behavioural class per file. No inline imports; no `if TYPE_CHECKING`; no
  triple-dot imports. Never catch `Exception`. No defaulting around missing API
  data. No second implementation of anything.
- 0 errors, 0 warnings, 0 skipped, **100% coverage**.
- Implementers run, ONE AT A TIME with nothing else active in the worktree:
  `uv run ruff check src/ tests/`, then `uv run mypy --strict src/artifactsmmo_cli`,
  then `bash scripts/run_tests.sh`. Never `--no-cov`.
- **This wave deletes Lean. `bash formal/gate.sh` is MANDATORY before every
  commit from task 5 onward**, not just the controller's job. The pre-commit hook
  does NOT build Lean — that gap already put this branch red once, when a
  `BAND_RAID` renumber left eight Lean sites stale and every Python check passed.
  Redirect gate output to a file and check the exit code directly; a pipeline
  reports the tail's status, so a visible `GATE FAIL` can return rc=0.
- Commit in the background with a **≥600000 ms** timeout and verify HEAD moved
  with `git log --oneline -1`. A tool timeout that kills the ~5-minute pre-commit
  pytest pass leaves the tree STAGED AND SILENTLY UNCOMMITTED. This has already
  cost two commits on this branch.
- `mutate.py --check-anchors` uses `git diff --quiet` and ABORTS on unstaged
  edits to a tracked target — `git add` first.

## Deleting is not the same as the other waves

Every earlier wave could be reverted. This one removes ~1,650 lines of Lean and
several thousand lines of test; reverting it is a merge conflict. So:

- **Delete only what the re-derived list names.** A symbol that "looks dead"
  and is not on the list is a REPORT, not a deletion.
- **When a deletion orphans something else, say so and stop.** §5 of the list
  already names six helpers, nine `progression_tree_core` symbols and four
  schema fields that the flip orphaned and §6.1 never listed. If you find a
  seventh, report it rather than widening your task.
- The mutation gate **cannot** be this wave's evidence and the plan that said it
  could was wrong: `focus_aging_pick`, `_synergy_map`, `_role_map` are called
  DIRECTLY by unit tests, so their mutants are killed and never surface as
  survivors. **Caller analysis is the evidence**, and it is already done.

## Test honesty

This epic has caught ten decorative tests, from five mechanisms: a line executed
but never asserted on; a test dodging the branch it names; an assertion over a
collection empty for unrelated reasons; a second mechanism coincidentally giving
the same answer; a mock returning what the real collaborator would return.

Deletion has its own version: **a test deleted because it covered deleted code,
when it actually covered something that survived.** For every test file you
remove, name what it pinned and confirm that subject is gone. If a test covers
both a deleted and a surviving symbol, split it — do not delete it whole.

---

## Task 1: Retire the `objective` CLI and the spent probe

**Files:**
- Delete: `src/artifactsmmo_cli/commands/objective.py`
- Delete: `scripts/measure_means_suppression.py`
- Modify: `src/artifactsmmo_cli/main.py:17,63-66` (command registration)
- Modify/delete: the CLI's tests

**Why first:** it is the single largest KEEP-to-DELETE flip, and until it lands
rows 10-12 cannot be touched.

- [ ] **Step 1** — read §3 rows 10, 11, 12 of the re-derived list.
- [ ] **Step 2** — delete both files and unregister the command.
- [ ] **Step 3** — record in `docs/PLAN_band_unification.md` that its increment-0
      probe has been retired, so a reader does not go looking for it.
- [ ] **Step 4** — ruff, mypy, `scripts/run_tests.sh`. Commit.

---

## Task 2: The zero-reader `RootScore` / `StrategyDecision` fields

**Files:** `src/artifactsmmo_cli/ai/tiers/strategy.py`,
`src/artifactsmmo_cli/ai/tiers/progression_tree.py`, and the FIVE
`StrategyDecision` construction sites named in row 5.

Rows 1, 2, 3, 5, 7 of the re-derived list: `RootScore.cost`, `.contribution`,
`.instrumental`, `StrategyDecision.desired_state`, `.j_ranking`.

**`StrategyDecision.aged_pick` is KEPT (row 6) — it is reconnected and live.**
It does not "die with the seat ledger"; it *gates* it.

- [ ] **Step 1** — read rows 1, 2, 3, 5, 6, 7. Note that row 5 has **five**
      production construction sites (`progression_tree.py:531` plus four
      censuses), not one, and the field is a required positional.
- [ ] **Step 2** — delete the five fields and fix every construction site.
- [ ] **Step 3** — row 7 also requires stripping `to_trace`'s `j_ranking` block
      and `strategy.py`'s `finite_j` / `ProgressionCandidate` imports. That is
      what removes `tiers/strategy`'s dependency on `branch_objective` — task 4
      depends on it.
- [ ] **Step 4** — ruff, mypy, `scripts/run_tests.sh`. Commit.

---

## Task 3: `objective_step_goal`'s dead parameter

**Files:** `src/artifactsmmo_cli/ai/strategy_driver.py`, `src/artifactsmmo_cli/ai/player.py`

Row 4. The parameter is declared at `strategy_driver.py:610` and never read.
There are **FIVE** call sites, not the four §6.1 lists: `strategy_driver.py:1116`,
`:1124`, `:1132`, `:1368`, and **`player.py:2921`**, inside `_step_servable`'s
`servable` closure — which §6.1 missed.

- [ ] **Step 1** — grep for a sixth before editing. Do not trust either list.
- [ ] **Step 2** — remove the parameter and all call-site arguments.
- [ ] **Step 3** — ruff, mypy, `scripts/run_tests.sh`. Commit.

---

## Task 4: The dead ranking modules

**Files:** delete `src/artifactsmmo_cli/ai/tiers/achievability_core.py`,
`src/artifactsmmo_cli/ai/role_alignment.py`,
`src/artifactsmmo_cli/ai/tiers/branch_objective.py`,
`src/artifactsmmo_cli/ai/tiers/progression_choice.py`,
`src/artifactsmmo_cli/ai/tiers/horizon_contribution.py`, and the
`progression_tree` functions that die with them.

Rows 8, 9, 10, 11, 12, 16 plus §5's newly-dead items.

- [ ] **Step 1** — read rows 8, 9, 16 and **§5 in full**. §5 lists what the flip
      orphaned that §6.1 never mentions — including `_effort_for`,
      `_skill_gate_levels`, `_synergy_map`, `_achievability_map`, `_role_map`.
- [ ] **Step 2** — note the trap in row 9: §6.1 says *"`ctx.role_skills` stays"*
      and that is **wrong at HEAD**. `_role_map` was its only reader, so
      `role_skills`, its producer `player._role_owned_skills` and the wiring at
      `player.py:3751` all become zero-reader. Same channel ≠ same field.
- [ ] **Step 3** — `tiers/synergy_core.py` **STAYS** (§6.2): `taskmaster_choice.py:26`
      and `means_worth.py:16` are live non-ranking consumers.
- [ ] **Step 4** — delete, in dependency order, and fix importers.
- [ ] **Step 5** — for every test file removed, name what it pinned and confirm
      that subject is gone. Split rather than delete any test that also covers a
      survivor.
- [ ] **Step 6** — ruff, mypy, `scripts/run_tests.sh`. Commit.

---

## Task 5: `progression_tree_core` — the SPLIT

**Files:** `src/artifactsmmo_cli/ai/tiers/progression_tree_core.py`

Row 13, detailed in §4. Of the six symbols §6.1 names:

| symbol | verdict |
|---|---|
| `falloff` | **KEEP — LIVE** (`root.py:57`, called `:363`) |
| `dhondt_step` | **KEEP — LIVE** (`root.py:56`, called `:365`) |
| `FOCUS_FLAT` | **KEEP — LIVE** (`root.py:55`, guard at `:348`) |
| `focus_aging_pick` | DELETE — `def` plus comments only |
| `focus_aging_order` | DELETE — `def` plus comments only |
| `bump_seats` | **does not exist as a Python symbol** — the referent is Lean's live `bumpSeats` |

- [ ] **Step 1** — read §4. Delete only the two that are dead.
- [ ] **Step 2** — §5 names nine further `progression_tree_core` symbols the flip
      orphaned. Read it and handle them here.
- [ ] **Step 3** — ruff, mypy, `scripts/run_tests.sh`, **and `bash formal/gate.sh`**. Commit.

---

## Task 6: Lean — `Achievability.lean` and the `ProgressionTree.lean` split

**Files:** delete `formal/Formal/Achievability.lean`; edit
`formal/Formal/ProgressionTree.lean`; one line of `formal/Formal.lean`.

**`InterleaveNoStarvation.lean` is KEPT.** §6.1 is wrong about it. Its subject
`dhondtStep`/`bumpSeats`/`interleaveDue` is live, and its hypothesis — all
weights strictly positive — is discharged by the live caller, which builds
`Fraction(max(1, tier_gap)) * falloff(level)` at `root.py:361-364`, where the
`max(1, …)` exists precisely so no weight is zero. `Formal.lean:121` stays.

**The `ProgressionTree.lean` split, in the correct direction** (§6.2 of the list):

- **KEEP:** `trunkCap`/`band`/`milestonePure` (`:62-108`), `potionWeight` + its 2
  theorems (`:140-160`), `focusFlat`/`focusSpan`/`focusFloor`/`falloffT`/`falloff`
  + all `falloff_*` (`:255-390`), `bumpSeats`/`dhondtQuot`/`selBeats`/`selectMax`/
  `dhondtStep`/`dhondtStepKey`/`interleaveDue` + `selectMax_quot_max`/
  `dhondtStepKey_quot_max` (`:419-573`).
- **DELETE:** `branchPick` + `branchPick_table`/`branchPick_gear_iff` (`:110-127`);
  `GearCand`/`better`/`pickFold`/`gearTargetPick` + `gearTargetPick_*` (`:162-253`);
  `lookupFocus`/`focusLevelOf`/`synergyOf`/`achievabilityOf`/`roleOf`/
  `scaledWeights`/`focusAgingPick` + `focusAgingPick_unaged_eq_argmax` (`:575-660`).

- [ ] **Step 1** — read §6 of the list in full before touching Lean.
- [ ] **Step 2** — confirm `Achievability.lean` is not a dependency of
      `InterleaveNoStarvation.lean`. The list says it is not (that file imports
      only `Mathlib` and `Formal.ProgressionTree`), and that `Manifest.lean:1365`'s
      "feeds `interleaveDue_reaches`" is a relevance note, not a Lean dependency.
      **Verify this yourself — it is the difference between a clean delete and a
      broken build.**
- [ ] **Step 3** — delete `Achievability.lean`, remove **only**
      `Formal.lean:223 import Formal.Achievability`, and apply the split above.
- [ ] **Step 4** — **`bash formal/gate.sh` must be green before you commit.**
      Confirm no theorem became VACUOUS: a hypothesis that can no longer be
      satisfied leaves a theorem true and worthless, and this repo has a
      zero-vacuousness rule for `formal/`.
- [ ] **Step 5** — Commit. Note: task 7 may have to land in this same commit; see
      its ordering constraint.

---

## Task 7: The Lean harness — manifest, audit, index, mutants

**Files:** `formal/Formal/Manifest.lean`, `formal/Formal/Audit.lean`,
`formal/diff/mutate.py`, and whatever `scripts/gen_proof_concept_index.py --check`
requires.

**ORDERING CONSTRAINT, confirmed by the re-derivation:** `Manifest.lean` row
removal, the `Formal.lean` import, the Lean file deletion and the `Audit.lean`
regeneration **cannot be split across commits** — four different gate scripts
fence pairs of them. If that means merging task 6 and task 7 into one commit, do
that and say so.

**Manifest rows: 5 + 6, not §6.1's 9 + 5 + 12.**
Delete `:1338-1339` (`branchPick_*`), `:1342-1343` (`gearTargetPick_*`), `:1351`
(`focusAgingPick_unaged_eq_argmax`), and `:1360-1366` (the Achievability header
plus 6 rows). **Keep** `:1334-1337`, `:1340-1341`, `:1344-1350`, all of
`:1352-1359` (Synergy), and all of `:118-127` (ProgressionChoice — unless task 1
retired it, in which case those go too; check).

**`formal/diff/test_progression_choice_diff.py`:** 3b.4 lists it for deletion.
**Do not delete it** unless task 1's CLI retirement removed its subject — its
`sort_key` is the only pointwise pin of the shipped band literals, cited by name
at `branch_objective.py:111-115`. If `branch_objective` went in task 4, re-derive
this one and say what you found.

- [ ] **Step 1** — read §6.3 and §6.4 of the list.
- [ ] **Step 2** — apply the manifest/audit/index/mutant edits.
- [ ] **Step 3** — `uv run python formal/diff/mutate.py --check-anchors` (git add
      first) and `bash formal/gate.sh`, both green.
- [ ] **Step 4** — Commit.

---

## Task 8: The eleven stale-prose instances

**Files:** per §7 of the re-derived list.

A corrected claim surviving in the comment that justified it has recurred
**eleven** times in this epic — §7 lists all of them with file:line. The
best-known: `selection_context.py:221-222` says *"decide_tree was the only
production caller of focus_aging_pick / focus_aging_order / dhondt_step"*, which
is true for the first two and false for `dhondt_step`.

- [ ] **Step 1** — read §7 and fix all eleven (plus the 2 borderline, with a
      judgement on each).
- [ ] **Step 2** — then sweep the hunks YOU touched in tasks 1-7 for a twelfth.
      That instruction is what found the fifth and the eleventh.
- [ ] **Step 3** — ruff, mypy, `scripts/run_tests.sh`, `bash formal/gate.sh`. Commit.

---

## Verification

Every task ends with the gate green. From task 5 onward that means
`bash formal/gate.sh`, not just the Python checks.

**No live acceptance criterion.** Deleting uncalled code should change no live
behaviour at all — that is the claim. The evidence is the gate plus the caller
analysis, and the live check is negative: after this branch merges and the fleet
restarts, `ReachSkill` must still fire and the walk must still choose the same
roots. If any live behaviour changes, something on the list was not dead.

## Self-review

**Spec coverage.** The re-derived list's rows 1-16, §4, §5, §6 and §7 map onto
tasks 1-8. The user's two rulings (retire the CLI, retire the probe) are folded
into task 1 and cascade into task 4.

**Deliberate omission.** No task restates the list's evidence. Each names its
rows; the list is authoritative on content. The alternative is two documents
that can disagree about which of sixteen rows is right — which is exactly the
failure this wave exists to correct.

**Known soft spot.** Task 6/7's ordering constraint may force one large commit
spanning Lean deletion, manifest, and audit regeneration. That is a worse review
surface than the rest of the plan, and it is unavoidable — four gate scripts
fence the pairs. The mitigation is that task 6 lists the exact keep/delete line
ranges, so the diff can be checked against the list rather than read cold.
