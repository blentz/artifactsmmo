# Sub-15-Minute Local Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring `bash formal/gate.sh` from ~45 minutes to under 15 minutes without deleting a test, reducing a Hypothesis example budget, or lowering the coverage threshold.

**Architecture:** Three independent changes, each landing on its own. (1) Full mutation execution leaves the local gate, matching what CI already does. (2) Coverage switches to Python 3.13's `sys.monitoring` core, which costs ~4.5× less on the census lane. (3) `formal/gate.sh` becomes the single entrypoint that runs everything CI runs, so ad-hoc invocations stop drifting from the real gate.

**Tech Stack:** bash, pytest, pytest-xdist 3.8.0, coverage.py 7.10.6, Python 3.13, Lean 4 / lake, `uv`.

## Global Constraints

- Every Python command is prefixed `uv run` (project rule).
- No test may be deleted, no `max_examples` reduced, no coverage threshold lowered.
- The Python suite must still report **100.00%** coverage over the union of both lanes.
- Test counts must not change: **5651** (lane 1) + **159** (lane 2) + **755** (offline differential).
- Never run gate commands concurrently with anything else importing `src` — serialize.
- `formal/diff/test_game_data_fixture_diff.py` stays excluded from the offline gate: it hits the live API.
- Source spec: `docs/superpowers/specs/2026-07-25-local-gate-runtime-design.md`.

---

### Task 1: Remove full mutation execution from the local gate

The local gate runs `mutate.py` with no flags (~36 min, the dominator). CI moved
mutation to the nightly `mutation-gate.yml`; the local script never followed.
`--check-anchors` at line 22 stays — it is the seconds-long check that catches
anchor rot on the commit that causes it.

**Files:**
- Modify: `formal/gate.sh:24`

**Interfaces:**
- Consumes: nothing.
- Produces: a `formal/gate.sh` with no `mutate.py` invocation other than
  `--check-anchors`. Task 3 appends further phases to this same file.

- [ ] **Step 1: Confirm the current line is present**

Run: `grep -n 'mutate.py' formal/gate.sh`

Expected, exactly two hits:
```
22:echo "== (b'''') mutation anchors =="; ( cd "$ROOT" && uv run python formal/diff/mutate.py --check-anchors )
24:echo "== (c) mutation =="; ( cd "$ROOT" && uv run python formal/diff/mutate.py )
```

- [ ] **Step 2: Replace line 24 with a comment recording why it is gone**

Delete this line:
```bash
echo "== (c) mutation =="; ( cd "$ROOT" && uv run python formal/diff/mutate.py )
```

Put this in its place:
```bash
# Full mutation EXECUTION is deliberately not here. It runs nightly in
# mutation-gate.yml, where CI moved it: ~36 min, peaks ~22GB, and it was the
# dominator of this script. Anchor resolution (phase b'''' above) is the part
# worth paying per-commit — it is seconds, runs no tests, and catches the stale
# or ambiguous anchor on the commit that caused it rather than 14h later.
# To run the sweep by hand: `uv run python formal/diff/mutate.py`.
```

- [ ] **Step 3: Verify only the anchor check remains**

Run: `grep -n 'mutate.py' formal/gate.sh`

Expected: one executable hit (line 22, `--check-anchors`) plus the comment's
mention inside the replacement block. No bare `mutate.py )` invocation.

- [ ] **Step 4: Verify the script still parses**

Run: `bash -n formal/gate.sh`
Expected: no output, exit 0.

- [ ] **Step 5: Commit**

```bash
git add formal/gate.sh
git commit -m "perf(gate): drop full mutation execution from the local gate

It ran ~36 min on every local gate run and was the dominator. CI already
defers mutation to the nightly mutation-gate.yml workflow (formal-gate.yml:97-100
records why: ~36 min, continue-on-error so it never blocked, peaks ~22GB against
a 16GB runner). The local script never followed, so local and CI disagreed about
what the gate is.

--check-anchors stays: seconds, runs no tests, and fails on the commit that
breaks an anchor instead of at the end of the nightly run."
```

---

### Task 2: Switch coverage to the `sys.monitoring` core

Lane 2 spends 4m20s of its 5m34s inside coverage's C trace function, because the
census fixture fans 152 planner searches over a `ProcessPoolExecutor` and every
one is traced. Python 3.12+ ships a `sys.monitoring` core that is far cheaper.
It does not support branch coverage — and this project sets `branch = false`
(`pyproject.toml:86`), so it is a drop-in.

Measured: lane 2 5:34 → 1:14; full suite ~6:00 → 1:38.8; coverage still 100.00%.

**Files:**
- Modify: `scripts/run_tests.sh` (after the `unset FORCE_COLOR NO_COLOR` block, before `rm -f .coverage`)
- Modify: `.github/workflows/pytest.yml:32-36` (the job `env:` block)

**Interfaces:**
- Consumes: nothing.
- Produces: `COVERAGE_CORE=sysmon` in the environment for both lanes. No Python
  API changes; nothing else reads this variable.

- [ ] **Step 1: Record the baseline so the win is measured, not assumed**

Run: `time bash scripts/run_tests.sh 2>&1 | tail -3`

Expected: both lanes pass, `Total coverage: 100.00%`, wall clock ~6 minutes.
Write the number down; Step 5 compares against it.

- [ ] **Step 2: Add the export to the runner**

In `scripts/run_tests.sh`, immediately after the line `unset FORCE_COLOR NO_COLOR`,
add:

```bash
# Coverage measurement core. Python 3.12+ implements coverage via sys.monitoring
# instead of a C trace function, which is ~4.5x cheaper on lane 2: the census
# fixture fans 152 planner searches over a ProcessPoolExecutor and tracing all of
# them dominated the lane (5:34 -> 1:14; whole suite ~6:00 -> 1:38.8). sysmon does
# not support BRANCH coverage, which is why this is safe here: pyproject.toml sets
# `branch = false`. Overridable so a bisect can pin the old core:
# `COVERAGE_CORE=ctrace bash scripts/run_tests.sh`.
export COVERAGE_CORE="${COVERAGE_CORE:-sysmon}"
```

- [ ] **Step 3: Add the same variable to CI**

In `.github/workflows/pytest.yml`, inside the existing `env:` block that already
holds `PYTHONDONTWRITEBYTECODE` and `ARTIFACTSMMO_TOKEN`, add:

```yaml
      # sys.monitoring coverage core (Python 3.12+): ~4.5x cheaper than the C
      # trace function on the census lane. Safe because pyproject.toml sets
      # branch = false, the one mode sysmon does not support.
      COVERAGE_CORE: sysmon
```

- [ ] **Step 4: Verify the script still parses**

Run: `bash -n scripts/run_tests.sh`
Expected: no output, exit 0.

- [ ] **Step 5: Run the suite and compare against the baseline**

Run: `time bash scripts/run_tests.sh 2>&1 | tail -5`

Expected, all of which must hold:
- `5651 passed` in lane 1
- `159 passed` in lane 2
- `Required test coverage of 100% reached. Total coverage: 100.00%`
- wall clock **under 2 minutes** (measured 1:38.8), versus the Step 1 baseline

If coverage comes back below 100%, do NOT lower the threshold. Stop: it means
sysmon is measuring something the C core did not, and that difference needs
understanding first.

- [ ] **Step 6: Commit**

```bash
git add scripts/run_tests.sh .github/workflows/pytest.yml
git commit -m "perf(tests): measure coverage via sys.monitoring

Lane 2 spent 4m20s of its 5m34s inside coverage's C trace function: the census
fixture fans 152 planner searches over a ProcessPoolExecutor and every one was
traced. Python 3.12+ implements coverage on sys.monitoring instead, which does
not support branch coverage — and pyproject.toml sets branch = false, so this is
a drop-in.

Measured: lane 2 5:34 -> 1:14, full suite ~6:00 -> 1:38.8, still 5651 + 159
passed at 100.00% coverage. No test changed."
```

---

### Task 3: Make `formal/gate.sh` the whole local gate

`formal/gate.sh` omits the Python suite entirely, and (since `b87079b9`) the
audit-drift check. Anyone wanting "run everything" has to know several commands
in the right order — which is exactly how a manual `pytest formal/diff/` without
`-n auto` turned a 2:27 stage into a 38-minute one.

Ordering principle to preserve: cheapest failures first, so the gate fails fast.

**Files:**
- Modify: `formal/gate.sh` (add audit-drift check after extraction drift; add the Python suite as a final phase)

**Interfaces:**
- Consumes: `formal/gate.sh` as left by Task 1 (no mutation execution);
  `scripts/run_tests.sh` as left by Task 2 (exports `COVERAGE_CORE`).
- Produces: a single command, `bash formal/gate.sh`, that runs every gate CI runs.

- [ ] **Step 1: Add the audit-drift check next to the other cheap checks**

In `formal/gate.sh`, immediately after the extraction-drift line
(`echo "== (b''') extraction drift =="; ...`), add:

```bash
echo "== (b'''a) audit list derived from manifest =="; bash "$HERE/gate/check_audit_generated.sh"
```

- [ ] **Step 2: Add the Python suite as the final phase**

At the end of `formal/gate.sh`, replace the final line
`echo "ALL GATE PARTS PASSED"` with:

```bash
# The Python suite runs LAST: it is the second-slowest phase, and every check
# above fails in seconds. run_tests.sh owns its own two-lane split and the 100%
# coverage gate; it is invoked rather than inlined so local and CI run the same
# script (.github/workflows/pytest.yml calls exactly this).
echo "== (e) python suite =="; ( cd "$ROOT" && bash scripts/run_tests.sh )
echo "ALL GATE PARTS PASSED"
```

- [ ] **Step 3: Verify the script still parses**

Run: `bash -n formal/gate.sh`
Expected: no output, exit 0.

- [ ] **Step 4: Verify every expected phase is present and ordered**

Run: `grep -n '^echo "== ' formal/gate.sh`

Expected phases, in this order: `(pre) mathlib cache`, `(a) kernel build`,
`(a') orphan modules`, `(a'') no sorry/admit`, `(b) axiom lint`,
`(b') role manifest`, `(b'') proof-concept index`, `(b''') extraction drift`,
`(b'''a) audit list derived from manifest`, `(b'''') mutation anchors`,
`(d) differential`, `(e) python suite`.

There must be no `(c) mutation` phase.

- [ ] **Step 5: Run the whole gate and time it**

Run: `time bash formal/gate.sh 2>&1 | tail -20`

Expected:
- ends with `ALL GATE PARTS PASSED`
- `755 passed` from the differential phase
- `5651 passed` and `159 passed` from the suite phase
- `Total coverage: 100.00%`
- wall clock **under 15 minutes** (projected ~6) from a warm Lean build

- [ ] **Step 6: Commit**

```bash
git add formal/gate.sh
git commit -m "feat(gate): make formal/gate.sh the whole local gate

It omitted the Python suite entirely and, since b87079b9, the audit-drift check,
so 'run everything locally' meant knowing several commands in the right order.
That is how a manual \`pytest formal/diff/\` missing -n auto turned a 2:27 stage
into a 38-minute one and made the gate look like an hour's work.

Both are added, keeping the cheapest-failures-first ordering: the audit-drift
check joins the other seconds-long checks, and the suite runs last as the
second-slowest phase. run_tests.sh is invoked rather than inlined so local and
CI run the same script."
```

---

### Task 4: Record the runtime contract in the gate script

A future change can silently reintroduce a slow phase. The measured budget
belongs next to the code it constrains, not only in a spec file.

**Files:**
- Modify: `formal/gate.sh` (header comment block, after the `set -euo pipefail` line)

**Interfaces:**
- Consumes: the phase list as left by Task 3.
- Produces: nothing executable — documentation only.

- [ ] **Step 1: Add the budget header**

In `formal/gate.sh`, after line 3 (the `HERE=`/`ROOT=` line), add:

```bash
# RUNTIME BUDGET: this script must stay under 15 minutes from a warm Lean build.
# Measured 2026-07-25 (docs/superpowers/specs/2026-07-25-local-gate-runtime-design.md):
#   kernel build + 8 cheap checks  ~2 min
#   differential (-n auto)          2:27   <- NEVER drop -n auto; single-process is 20-38 min
#   python suite (run_tests.sh)     1:39   <- needs COVERAGE_CORE=sysmon; ctrace core is ~6 min
#   TOTAL                          ~6 min
# Full mutation execution is nightly (mutation-gate.yml) and must not return here.
```

- [ ] **Step 2: Verify the script still parses**

Run: `bash -n formal/gate.sh`
Expected: no output, exit 0.

- [ ] **Step 3: Confirm the two load-bearing flags are still present**

Run: `grep -c 'n auto' formal/gate.sh` → expected `1`
Run: `grep -c 'COVERAGE_CORE' scripts/run_tests.sh` → expected `1`

- [ ] **Step 4: Commit**

```bash
git add formal/gate.sh
git commit -m "docs(gate): pin the 15-minute runtime budget in the script

The measured per-phase costs live next to the phases they constrain, including
the two flags that are load-bearing for the budget: -n auto on the differential
suite (single-process is 20-38 min) and COVERAGE_CORE=sysmon on the Python suite
(the C trace core is ~6 min). Without the note, either is an easy silent revert."
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| Part 1 — mutation leaves the local gate | Task 1 |
| Part 2 — `COVERAGE_CORE=sysmon` | Task 2 |
| Part 3 — one local gate entrypoint | Task 3 |
| Acceptance criterion 1 (< 15 min) | Task 3 Step 5, Task 4 Step 1 |
| Acceptance criterion 2 (phase list) | Task 3 Step 4 |
| Acceptance criterion 3 (100%, 5651 + 159) | Task 2 Step 5, Task 3 Step 5 |
| Acceptance criterion 4 (755 offline diff tests) | Task 3 Step 5 |
| Acceptance criterion 5 (no local mutation) | Task 1 Step 3, Task 3 Step 4 |
| Deferred persistent oracle | intentionally no task — out of scope per spec |

**Placeholder scan:** none. Every step names an exact file, an exact command,
and the exact expected output.

**Type consistency:** no new Python or Lean symbols are introduced. The only
new identifier is the environment variable `COVERAGE_CORE`, spelled identically
in `scripts/run_tests.sh`, `.github/workflows/pytest.yml`, and Task 4's grep.
Phase labels in Task 3 Step 4 match the strings added in Task 3 Steps 1-2.

**Ordering dependency:** Task 3 Step 5 measures the whole gate and depends on
Task 2's export existing; run the tasks in order.
