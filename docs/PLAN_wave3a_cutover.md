# Wave 3a — the cutover: graph resolution replaces the ranking

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `decide_tree`'s argmax over a scored ranking with a resolution
walk over a root Decision graph, leaving every ranking module uncalled but
present.

**Architecture:** Waves 1-2 and 5 are merged: derived tier ladder, `Decision`
node type, six transcribed `ObtainItem` decisions, band-derived combat targets.
3a generalises `resolve_node` to any leaf type, adds a `ReachSkillLevel`
MetaGoal, structures `GearTarget.blocker`, builds the root graph, adds two
gate obligations, flips `decide_tree`, and trims the display. Nothing is deleted
— that is 3b.

**Tech Stack:** Python 3.13, `uv`, pytest, mypy strict, ruff, Lean 4.

**Spec:** `docs/superpowers/specs/2026-08-23-wave3-resolution-design.md`

**This plan deliberately does not restate the spec's code.** Section 5 of that
document contains the signatures and bodies; each task below names the section
it implements. Copying 400 lines into a second document would create two sources
of truth for one design, which is the failure mode this whole epic exists to
remove. Implementers are given BOTH paths and told the spec is authoritative on
content.

## Global Constraints

- Every Python command is prefixed `uv run` (CLAUDE.md). If `uv` is not on PATH,
  use `/home/blentz/.local/bin/uv`.
- One behavioural class per file. Pure data/schema/enum groups may share a module.
- No inline imports; no `if TYPE_CHECKING`; no triple-dot imports.
- Never catch `Exception`.
- No defaulting around missing API data.
- 0 errors, 0 warnings, 0 skipped, **100% coverage** (`--cov-fail-under=100`).
- Implementers run, ONE AT A TIME with nothing else active in the worktree:
  `uv run ruff check src/ tests/`, then
  `uv run mypy --strict src/artifactsmmo_cli`, then `bash scripts/run_tests.sh`.
  Never `--no-cov`. `formal/gate.sh` is the controller's job. Two concurrent
  processes corrupt the shared `.coverage` file and report a bogus ~45%.
- The pre-commit hook is NOT sufficient evidence: 5-rule ruff subset, `--no-cov`.
- Do not create a second implementation of anything.
- **Every task leaves `bash formal/gate.sh` green.** No module is deleted in 3a;
  the ranking machinery becomes *uncalled*, which the mutation gate will report
  as survivors. That is expected and is 3b's input — do not "fix" it by deleting.

## Test honesty — this epic's running cost

Ten decorative tests have been caught across waves 1-5, every one written by a
plan author, and five distinct mechanisms produced them:

1. a line executed but never asserted on
2. a test that dodges the branch it is named for
3. an assertion over a collection that is empty for unrelated reasons
4. a second mechanism coincidentally producing the same answer
5. a mock returning exactly what the real collaborator would return

For every test you write: name the one-line production change that makes it
fail, and RUN that mutation. Copy the file aside first — `git checkout` silently
does nothing on an untracked file. Quote the failure. A test that survives its
own mutation is not a test.

## Deletion discipline

Task 5.3 of the previous plan investigated three "obviously dead" sites and
found all three live, one feeding a live decision through a caller the plan
author had missed. The design doc's §6.2 lists what grep says must NOT be
deleted. Nothing in 3a deletes a module. If a task tempts you to, report it.

---

## Task 1: (3a.1) `resolve_node` becomes leaf-type-agnostic

**Files:**
- Modify: `src/artifactsmmo_cli/ai/decision.py`
- Modify: `src/artifactsmmo_cli/ai/decisions/obtain_item.py`
- Test: `tests/test_ai/test_decision.py`

**Spec section:** §5.1, the `Generic[Leaf]` change.

**Interfaces produced:** `Decision[Leaf]`, `resolve_node(node, ...) -> Leaf | None`.
The six existing decisions gain `Decision[Goal]` in their base clause and change
in no other way.

- [ ] **Step 1** — read §5.1 of the spec and `ai/decision.py` in full.
- [ ] **Step 2** — write the failing test: a `Decision[str]` chain resolving to a
      `str` leaf, which the current `isinstance(current, Goal)` termination
      cannot handle. Run it; confirm it fails for that reason.
- [ ] **Step 3** — implement §5.1. The termination condition flips from
      "is it a Goal" to "is it NOT a Decision".
- [ ] **Step 4** — confirm the existing 7 `test_decision.py` tests still pass
      unchanged. If any needs editing, that is a signal the change is not
      behaviour-preserving for `Decision[Goal]` — report it rather than editing.
- [ ] **Step 5** — mutation: revert the loop condition to
      `isinstance(current, Goal)`; your new test must fail. Quote it.
- [ ] **Step 6** — add a mutation anchor for the loop condition in
      `formal/diff/mutate.py`, resolving to exactly one site. Verify with
      `uv run python formal/diff/mutate.py --check-anchors`.
- [ ] **Step 7** — ruff, mypy, `scripts/run_tests.sh`, one at a time. Commit.

---

## Task 2: (3a.2) `ReachSkillLevel` MetaGoal

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/meta_goal.py` (append)
- Modify: `src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py`
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py` (`root_category`)
- Test: `tests/test_ai/test_tiers_meta_goal.py`

**Spec section:** §5.1, the `meta_goal.py` append.

**Interfaces produced:** `ReachSkillLevel(skill: str, level: int)`.

Nothing constructs it yet, so this task changes no behaviour.

- [ ] **Step 1** — check whether `ai/goal_serialization.py` needs a round-trip
      arm. The spec says it serialises Goals, not MetaGoals — CONFIRM that by
      reading it before adding anything. Report what you found.
- [ ] **Step 2** — write the failing tests: construction, `repr`,
      `prerequisites` returning `[]`, and `root_category` returning `"skill"`.
- [ ] **Step 3** — implement per §5.1.
- [ ] **Step 4** — mutation: change `root_category`'s new arm to return
      something else; your test must fail. Quote it.
- [ ] **Step 5** — ruff, mypy, `scripts/run_tests.sh`. Commit.

---

## Task 3: (3a.3) `GearTarget.blocker` becomes structured

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/objective.py`
- Test: `tests/test_ai/test_max_gear_for_level.py`

**Spec section:** §7, task 3a.3.

**Why:** `IsThisTargetBlocked` must not parse a formatted string back into a
decision. Replace `blocker=f"skill:{skill}:{level}"` with typed fields.

**Interfaces produced:** `GearTarget` with structured blocking fields; the exact
shape is the spec's — read it rather than inventing one.

- [ ] **Step 1** — read the spec's §7 3a.3 and `tiers/objective.py:294-300,
      415-447`.
- [ ] **Step 2** — write the failing tests. Five existing assertions in
      `test_max_gear_for_level.py` read `blocker` as a string; they move with the
      change. For each, state why the new expectation is right.
- [ ] **Step 3** — implement.
- [ ] **Step 4** — mutation: swap the skill and material arms; a test must fail.
      Quote it.
- [ ] **Step 5** — ruff, mypy, `scripts/run_tests.sh`. Commit.

**Note:** `gear_targets_with_blockers` currently has ZERO production callers
(controller-confirmed by grep). It is wave-3 groundwork whose consumer arrives
in 3a.6. Do not delete it and do not wire it early.

---

## Task 4: (3a.4) the root graph

**Files:**
- Create: `src/artifactsmmo_cli/ai/decisions/root.py`
- Create: `tests/test_ai/test_decisions_root.py`
- Create: the O2 DAG test (same commit — see below)

**Spec sections:** §5.1 and §5.3.

**Interfaces produced:** six `Decision[MetaGoal]` classes, `resolve_root`,
`RootResolution`.

Nothing calls it yet.

- [ ] **Step 1** — read §5.1 and §5.3 in full before writing anything.
- [ ] **Step 2** — write the failing tests for each decision's branches.
- [ ] **Step 3** — implement per the spec.
- [ ] **Step 4** — **the O2 DAG test, in this same commit** (spec §3.5): a
      reflection sweep over `ai/decisions/` asserting the static return-type
      edge relation is acyclic. This is a new gate obligation, not optional.
- [ ] **Step 5** — mutation: introduce a deliberate cycle in a test-local
      subclass; the DAG test must fail. Quote it. Then remove it.
- [ ] **Step 6** — ruff, mypy, `scripts/run_tests.sh`. Commit.

---

## Task 5: (3a.5) the O1 open-rung census

**Files:**
- Create: a sweep under `src/artifactsmmo_cli/audit/`
- Create: `scripts/gen_*.py --check` entry point matching the six existing ones
- Modify: `formal/gate.sh` census phase
- Test: `tests/test_audit/`

**Spec section:** §3.5, obligation O1.

**What it asserts:** for every `(skill, level)` reachable across the scenario
set, `ReachSkillLevel(S, C+1)` has an open, XP-positive rung, or the graph emits
a named wall.

- [ ] **Step 1** — read §3.5 and one existing census
      (`scripts/gen_shed_reachability.py` is the smallest) to match the
      established `--check` shape.
- [ ] **Step 2** — write the census and its test.
- [ ] **Step 3** — confirm it actually FAILS when given a skill/level with no
      open rung. A census that cannot report a wall is decorative.
- [ ] **Step 4** — wire into `formal/gate.sh` beside the existing seven
      `--check` scripts. Runtime should be seconds — it is a catalogue sweep. If
      it costs more than ~10s, report that rather than wiring a slow check into
      the gate.
- [ ] **Step 5** — ruff, mypy, `scripts/run_tests.sh`. Commit.

---

## Task 6: (3a.6) THE FLIP

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/progression_tree.py` (`decide_tree`)
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py` (`StrategyEngine.decide`)
- Modify: `src/artifactsmmo_cli/ai/player.py:727-737` and `:1040-1047`

**Spec section:** §5.2.

**This is the one reviewable behaviour change in 3a and it must be its own
commit.**

Parameters `band_adequate`, `focus`, `seats`, `committed_root_code`,
`enable_synergy` and `store` are removed from `decide_tree` and
`StrategyEngine.decide`; `history` replaces `store`.

- [ ] **Step 1 — CAPTURE THE BASELINE FIRST, before any edit.** Read from
      `~/.cache/artifactsmmo/learning.db` only, never trace files. Record
      `avg(planner_nodes)` and `max(planner_nodes)` per character over the
      cycles since 2026-08-20, and the current `weaponcrafting` per character.
      The design doc quotes 774.3 / 113,595 — do NOT use those numbers, capture
      your own, and report both so any drift is visible.
- [ ] **Step 2** — read §5.2 in full.
- [ ] **Step 3** — write the failing tests for the new `decide_tree` contract.
- [ ] **Step 4** — implement §5.2.
- [ ] **Step 5** — expect scenario and golden expectations to move. For EACH
      one, state in your report why the new value is correct. Do NOT weaken an
      assertion to make it pass. If a test's intent conflicts with the flip,
      report it rather than editing it into agreement.
- [ ] **Step 6** — mutation anchors in this same commit, each resolving to
      exactly one site: the `IsMyGearBehindMyTier` predicate, the
      `IsThisTargetBlocked` skill arm, and the `RootResolution.alternatives`
      construction. Verify with `--check-anchors`.
- [ ] **Step 7** — ruff, mypy, `scripts/run_tests.sh`. Commit.
- [ ] **Step 8** — runtime check, not just green tests:
      `uv run artifactsmmo plan Robby --learn` and the same for `Lor`. Record
      the actual `chosen_root`, `chosen_step`, selected goal and first action.

---

## Task 7: (3a.7) display

**Files:**
- Modify: `src/artifactsmmo_cli/ai/plan_tree.py` (`_resolution_rows`,
  `rank_detail`)
- Modify: `src/artifactsmmo_cli/commands/plan.py:76-82`

**Spec sections:** §1.3, §1.4, §7 3a.7.

`rank_detail`'s first two arms (the `j` and `reachable_level` cases) are
deleted. `RootScore.j` and `.reachable_level` become unused but are **NOT**
removed here — that is 3b, so the schema change lands as one commit.

- [ ] **Step 1** — read §1.4 before proposing any display deletion. It exists
      because a previous reader deleted display the TUI depended on.
- [ ] **Step 2** — write/adjust tests for the new rendering.
- [ ] **Step 3** — implement.
- [ ] **Step 4** — ruff, mypy, `scripts/run_tests.sh`. Commit.

---

## Verification

Every task ends gate-green. The controller runs `bash formal/gate.sh` between
tasks and `uv run python formal/diff/mutate.py --check-anchors` after any task
that adds an anchor.

**Live acceptance for 3a**, from `~/.cache/artifactsmmo/learning.db` only:

1. `avg(planner_nodes)` and `max(planner_nodes)` both FALL against the baseline
   captured in 3a.6 step 1.
2. `weaponcrafting` exceeds 10 on at least one character.

Both require a fleet restart onto this branch plus runtime. Until then 3a is
verified but NOT activated, and that distinction must be stated plainly rather
than rounded up.

## Self-review

**Spec coverage.** Design §7's 3a.1-3a.7 map one-to-one onto tasks 3a.1-3a.7.
§3.5's two new obligations are folded into task 4 (O2) and task 5 (O1) rather than
given their own tasks, because each belongs in the commit that creates the thing
it constrains.

**Deliberate omission.** No task restates the spec's code. Each names its
section. Implementers receive both paths and the spec is authoritative on
content — the alternative is two documents that can disagree about one design.

**Known soft spot.** Task 6 removes six parameters from two public-ish functions.
The blast radius is whatever calls them; the plan names the two `player.py` call
sites the design found, and the implementer must grep for others rather than
trusting that list — the same discipline task 5.3 vindicated.
