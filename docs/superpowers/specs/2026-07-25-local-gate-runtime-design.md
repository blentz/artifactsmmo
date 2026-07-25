# Local gate runtime: under 15 minutes, no loss of comprehensiveness

Status: design agreed 2026-07-25. Target: total local gate < 15 min.

## Problem

Merging a feature locally costs up to an hour. That latency has been shaping
development: work gets batched to avoid paying the gate, and the gate gets run
less often than it should be.

The requirement is a **total local testing runtime under 15 minutes with
minimal-to-no loss in test comprehensiveness**. No test may be deleted, no
Hypothesis example budget reduced, and the 100% coverage gate must still be
enforced.

## Measurements (2026-07-25, this machine)

All figures measured, not estimated.

| Stage | Command | Time |
|---|---|---|
| Full mutation execution | `mutate.py` (no flags) | ~36 min (documented dominator) |
| Differential, **single process** | `pytest formal/diff/ -q --no-cov` | 20:51 – 37:42 |
| Differential, **`-n auto`** | as `formal/gate.sh:23` runs it | **2:27** (755 tests) |
| Suite lane 2, default coverage core | census + scenarios | 5:34 |
| Suite lane 2, **`COVERAGE_CORE=sysmon`** | same | **1:14** |
| Suite lane 2, no coverage at all | same | 1:13 |
| Suite lane 1 | `-n auto`, 5651 tests | ~22s |
| Full suite, sysmon | `scripts/run_tests.sh` | **1:38.8**, 100% coverage |
| Mutation anchors | `mutate.py --check-anchors` | seconds |

Oracle process economics, measured directly:

| | cost |
|---|---|
| one spawn, batch of 1 | 107.03 ms |
| one spawn, batch of 400 | 111.07 ms (0.28 ms/example) |

Process startup dominates and is nearly independent of batch size. The diff
suite declares 48,090 Hypothesis examples across 82 `@settings` decorators, and
62 of 80 oracle-using files call `run_oracle` **inside** `@given` — one spawn per
example, batch size 1, against an interface that already accepts batches.

## Root causes

1. **`formal/gate.sh:24` runs full mutation execution locally.** CI moved
   mutation to the nightly `mutation-gate.yml` (documented in
   `formal-gate.yml:97-100`: ~36 min, was `continue-on-error`, peaks ~22GB). The
   local script never followed. This is the hour.

2. **Coverage uses the C trace core.** Lane 2 spends 4m20s of its 5m34s on
   coverage instrumentation — the census fixture fans 152 planner searches over a
   `ProcessPoolExecutor`, and tracing that is expensive. Python 3.13's
   `sys.monitoring` core costs almost nothing by comparison, and this project
   sets `branch = false` (`pyproject.toml:86`), the one case sysmon does not
   support.

3. **`formal/gate.sh` is not the whole gate.** It omits `scripts/run_tests.sh`
   entirely and (as of `b87079b9`) `check_audit_generated.sh`. Anyone wanting
   "run everything" must know to invoke several scripts in the right order, which
   is how ad-hoc invocations drift from what CI actually does.

### Correction to an earlier claim

An earlier draft of this analysis reported the differential suite at 21–38
minutes. That was measured with a **manual `pytest formal/diff/` invocation that
omitted `-n auto`**. `formal/gate.sh:23` has always passed `-n auto` and
`--ignore=formal/diff/test_game_data_fixture_diff.py`. The project's gate was
correct; the measurement was not. The real diff cost is 2:27.

## Design

### Part 1 — mutation execution leaves the local gate

Delete `formal/gate.sh:24`. Mutation execution runs nightly, as it already does
in CI. `--check-anchors` (line 22, seconds) stays, so anchor rot still fails on
the commit that causes it.

Comprehensiveness: unchanged locally versus CI — this makes the two agree. The
mutation sweep still runs every night against `main`.

### Part 2 — `COVERAGE_CORE=sysmon`

Export it in `scripts/run_tests.sh`, and in the CI workflows that run the suite
(`pytest.yml`). Guard on interpreter support so an older Python degrades to the
default core rather than failing:

```bash
# Python 3.12+ sys.monitoring coverage core: ~4.5x faster than the C trace
# function on lane 2, whose census fixture fans out over a ProcessPoolExecutor.
# Requires branch coverage OFF, which pyproject.toml already sets.
export COVERAGE_CORE="${COVERAGE_CORE:-sysmon}"
```

Measured: lane 2 5:34 → 1:14, full suite ~6:00 → 1:38.8, 100% coverage still
reached. No test changes.

### Part 3 — one local gate entrypoint

`formal/gate.sh` becomes the single command that runs what CI runs:

* add `check_audit_generated.sh` alongside the other `gate/check_*.sh` calls
* add `scripts/run_tests.sh` as its own phase
* keep the existing ordering principle: cheapest failures first (orphan, sorry,
  axioms, manifest, index, extraction, anchors), then the two slow phases

This is the same structural move as deriving `Audit.lean` from `Manifest.lean`
(`b87079b9`): a single source of truth beats two lists that agree only by
discipline. Here the drift was between the local gate and CI.

### Projected total

| Stage | Now | After |
|---|---|---|
| mutation execution | ~36 min | 0 (nightly) |
| kernel build (warm) + 7 checks | ~2 min | ~2 min |
| anchors | seconds | seconds |
| differential (`-n auto`) | 2:27 | 2:27 |
| suite (both lanes) | ~6 min | 1:39 |
| **total** | **~45 min** | **~6 min** |

Under 15 minutes with every test, every Hypothesis example, and the 100%
coverage gate intact.

## Deferred: persistent oracle

Not required to hit the target, so it is out of scope for this work. Recorded
because the measurement is done and the option is real.

`Oracle.lean:3021` reads stdin to EOF, answers once, exits. A request loop (one
JSON array per line in, one response line out, flush, repeat) plus a
session-scoped process in `oracle_client` would cut per-call cost from 107ms to
pipe IPC, with **no test file changes** — `run_oracle` keeps its signature. The
diff suite burns 40m47s of user CPU to produce 2:27 wall-clock; most of that is
process startup.

Reasons to defer rather than do now:

* 2:27 already fits the budget; this optimises a stage that is no longer the
  bottleneck.
* It introduces a failure mode that does not exist today: a hung oracle becomes
  a stuck run instead of a clean per-call error. It would need a read timeout,
  fail-fast restart, and the current spawn-per-call path kept behind a flag as
  the parity oracle.

Revisit if the diff suite grows or if mutation execution is ever wanted locally
again — mutation runs the diff tests once per mutant, so it would benefit most.

## Non-goals

* Reducing `max_examples`, deleting tests, or lowering the coverage threshold.
  These would meet the number by giving up the thing the number exists to
  protect.
* Parallelising lane 2. Its serialisation is deliberate and documented
  (`run_tests.sh:4-11`): the census nests a `ProcessPoolExecutor`, and the
  scenario suite asserts against a wall-clock planner budget that busy workers
  would squeeze into spurious timeouts. After Part 2 it costs 1:14, of which
  62.22s is one honest fixture — there is little left to win.
* Changing the mutation runner. Its parallel mode already leases per-worker
  private copies of `src/artifactsmmo_cli` with `PYTHONPATH` shadowing
  (`mutate.py:2069-2077`, `_execute_parallel` at 2187); the production tree is
  never mutated.

## Risks

| Risk | Mitigation |
|---|---|
| `sysmon` reports different coverage than the C core | Acceptance criterion below requires the 100% gate to pass on the union of both lanes; verified once at 100.00% already |
| Dropping mutation locally lets a weak test reach `main` | Nightly mutation still runs; anchors still checked per-commit. This matches CI's existing posture, so it removes a divergence rather than creating one |
| `gate.sh` grows into something people skip | Keep the cheap-failures-first ordering so it fails fast; total ~6 min is short enough to run |

## Acceptance criteria

1. `bash formal/gate.sh` completes in **under 15 minutes** on this machine, from
   a warm Lean build.
2. It runs, at minimum: kernel build, orphan, sorry, axioms, manifest, proof
   index, extraction drift, audit drift, anchors, differential, full Python
   suite.
3. The Python suite still reports **100.00%** coverage and the same test count
   (5651 + 159).
4. The differential suite still runs all 755 offline tests with unchanged
   `max_examples`.
5. Full mutation execution no longer runs in `formal/gate.sh`; it still runs in
   the nightly workflow.
