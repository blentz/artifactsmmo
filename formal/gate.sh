#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ROOT="$(cd "$HERE/.." && pwd)"
# RUNTIME BUDGET: this script must stay under 15 minutes from a warm Lean build.
# Measured integrated run 2026-07-25 (docs/superpowers/specs/2026-07-25-local-gate-runtime-design.md):
#   kernel build + 8 Lean/audit cheap checks (cache/build/orphans/sorry/
#     axioms/manifest/proof-concept index/extraction/audit-drift/anchors) ~29s
#   differential (-n auto)                                               0:07   <- was 1:59 before the persistent oracle (see below);
#                                                                               NEVER drop -n auto; single-process is 20-38 min
#   python suite (run_tests.sh)                                          1:36   <- needs COVERAGE_CORE=sysmon; ctrace core is ~6 min
#   PRIOR END-TO-END TOTAL (the three phases above, actually run together
#     2026-07-25): 4:03.6
# Added 2026-07-25 (final-review finding: gate.sh claimed to be "the whole
# local gate" while silently skipping ruff/mypy/openapi/census; timed
# standalone, not yet re-measured as one end-to-end run):
#   ruff + mypy + openapi conformance (strict)                          ~1s    <- 0.04s + 0.36s + 0.06s standalone
#   census --check x5 (inventory/recycle/craft/obtain-parity/req-parity) 2:39   <- 0:56 + 0:01 + 1:39 + 0:01 + 0:01 standalone
#   PROJECTED NEW TOTAL: ~6:43 (4:03.6 prior + ~2:40 added) -- still ~8 min
#   of headroom under the 15-minute ceiling.
# The differential phase dropped 1:59 -> 0:07 when the Lean oracle gained a
# `--serve` request loop (formal/diff/oracle_server.py): spawning that binary
# costs ~107ms regardless of batch size, and the suite calls it once per
# Hypothesis example, so it was paying startup ~48,000 times. One process per
# xdist worker now. `ARTIFACTSMMO_ORACLE_MODE=spawn` restores the old
# spawn-per-call transport as a parity oracle — both give 762 passed.
# Full mutation execution is nightly (mutation-gate.yml) and must not return here.
# SCOPE (accuracy matters here -- this claims to be "the whole local gate"):
# this script now runs everything CI runs across formal-gate.yml, lint-gate.yml,
# type-gate.yml, and census-gate.yml, with exactly two deliberate exclusions:
#   1. Full mutation EXECUTION (formal/diff/mutate.py's sweep, not the
#      anchor-only check below) -- stays in the nightly mutation-gate.yml:
#      ~36 min, peaks ~22GB, was this script's own dominator before it was
#      moved out (see phase (d) below for detail).
#   2. formal/diff/test_game_data_fixture_diff.py -- needs a live network
#      call to the game API to diff against the pinned snapshot; excluded
#      from the differential phase below via --ignore, exactly as
#      formal-gate.yml excludes it. Not a local/CI divergence, just a test
#      that cannot run offline.
. "$HOME/.elan/env" 2>/dev/null || true
# Pull Mathlib's hosted prebuilt cache before compiling. Saves ~30 min
# of cold Lean+Mathlib compile per CI run. `|| true` because the command
# fails benignly when cache.lean isn't built yet (first invocation) —
# subsequent `lake build` still recompiles what's missing.
echo "== (pre) mathlib cache =="
( cd "$HERE" && lake exe cache get 2>&1 | tail -3 || echo "cache get skipped" )
echo "== (a) kernel build =="; ( cd "$HERE" && lake build )
echo "== (a') orphan modules =="; bash "$HERE/gate/check_no_orphan_modules.sh"
echo "== (a'') no sorry/admit =="; bash "$HERE/gate/check_no_sorry.sh"
echo "== (b) axiom lint =="; bash "$HERE/gate/check_axioms.sh"
echo "== (b') role manifest =="; ( cd "$HERE" && lake env lean Formal/Manifest.lean >/dev/null && echo "manifest OK" )
echo "== (b'') proof-concept index =="; bash "$HERE/gate/check_proof_concept_index.sh"
echo "== (b''') extraction drift =="; bash "$HERE/gate/check_extraction.sh"
echo "== (b'''a) audit list derived from manifest =="; bash "$HERE/gate/check_audit_generated.sh"
echo "== (b'''b) proof citations =="; bash "$HERE/gate/check_proof_citations.sh"
# Anchor resolution runs here, before the two slow phases, because it is the
# cheapest possible failure: seconds against ~580 anchors, no tests executed. A
# stale or ambiguous anchor used to surface only at the END of the hour-long
# mutation run, long after the commit that caused it.
echo "== (b'''') mutation anchors =="; ( cd "$ROOT" && uv run python formal/diff/mutate.py --check-anchors )
# ruff/mypy/openapi conformance: three more sub-second CI gates
# (lint-gate.yml, type-gate.yml, formal-gate.yml's OpenAPI conformance step)
# that were missing from this script despite it claiming to be "the whole
# local gate". Same commands the workflows run, so a local pass means the
# CI job passes too.
# `formal/` joined the ruff scope 2026-08-25. It had been EXECUTED by this
# script (anchors, openapi conformance, 850 differential tests) but never
# LINTED: `ruff check formal/` reported 177 errors, among them 14 unused
# locals / unpacked variables / loop variables. In a differential harness that
# class is not cosmetic — an unused `lean_*` binding means both sides were
# computed and only one compared. Two of the 14 were real (a missing
# criticality comparison and a never-asserted current-item score); the rest
# were leftovers, now `_`-prefixed so an UNPREFIXED unused binding stays a
# signal. Keep the three paths in one command so local and lint-gate.yml agree.
echo "== (c) ruff =="; ( cd "$ROOT" && uv run ruff check src/ tests/ formal/ )
echo "== (c') mypy strict =="; ( cd "$ROOT" && uv run mypy src/ )
echo "== (c'') openapi conformance (strict) =="; ( cd "$ROOT" && uv run python formal/diff/openapi_conformance.py --strict )
# census-gate.yml's six --check scripts. Measured standalone 2026-07-25:
# inventory 56s, recycle 1s, craft 99s, obtain-parity 1s, requirement-parity
# 1s (~2:39 total) -- comfortably inside the gate's headroom, so they run
# here rather than being deferred like full mutation execution below. Placed
# before the differential phase per the same cheapest-real-failure-first
# principle: these are Python-only census scripts, no Lean oracle build
# needed, so they can fail before differential pays for `lake build oracle`.
# shed-reachability added 2026-08-05 (disposal-unification part 2), measured
# standalone at 2s: four `StrategyArbiter.select` drives plus one pure catalog
# sweep.
# liveness added 2026-08-18 and placed FIRST because it is the cheapest of
# the seven (<1s: one source scan plus, where a learning DB exists, two GROUP
# BYs). It is the only census that asks whether the planner ever DID a thing
# rather than whether it CAN -- the gap that hid 18 dead goals, 17 dead
# actions, a task subsystem that never once ran, and the unified objective `J`
# itself. It needs NO learning DB: the roster comes from the source, so CI
# still fails on a Goal or Action added without a liveness decision.
# open-rung added 2026-08-23 (wave-3 resolution design, obligation O1),
# measured standalone at 2.1s: 240 catalogue cells plus one `resolve_root`
# drive per scenario. Placed beside shed for the same reason -- it is a
# catalogue sweep, not a planner drive. It is the acceptance gate for "the bot
# cannot raise this skill and cannot say why": wave 3 puts ReachSkillLevel on
# the ONLY path from a skill-gated gear target to work, so a root the graph
# routes to and the planner cannot serve is a silent stall, not a low score.
# reachability-claims added 2026-08-24, measured standalone at 0.7s: `ast` over
# src/ and nothing else, so it runs FIRST, ahead of even the liveness scan. It
# verifies every comment that asserts a named thing has no caller, because the
# wave-3b deletion pass found three that asserted LIVE code was dead -- the
# worst on `ai/obtain_sources`, which ELEVEN production modules import and both
# plan producers run through. Those comments were true when written and were
# never revisited, which is what makes it a class rather than two incidents.
echo "== (c''') census (--check x11) =="
( cd "$ROOT" \
  && uv run python scripts/gen_reachability_claims.py --check \
  && uv run python scripts/gen_liveness.py --check \
  && uv run python scripts/gen_open_rung.py --check \
  && uv run python scripts/gen_shed_reachability.py --check \
  && uv run python scripts/gen_inventory_completeness.py --check \
  && uv run python scripts/gen_recycle_source_completeness.py --check \
  && uv run python scripts/gen_craft_completeness.py --check \
  && uv run python scripts/gen_obtain_parity.py --check \
  && uv run python scripts/gen_requirement_parity.py --check \
  && uv run python scripts/gen_one_cost_model.py --check \
  && uv run python scripts/gen_currency_wall.py --check \
  && uv run python scripts/gen_drop_wall.py --check )
# The craft census's `--check` deliberately rewrites MATRIX/BACKLOG (see
# gen_craft_completeness.py:17-19) and its cell verdicts are wall-clock
# nondeterministic (~16% of cells hit the 10s budget), so a passing local run
# would otherwise leave the tree dirty with churn — one `git commit -a` away
# from being committed. Restore them, so the local gate VERIFIES without
# mutating; census-gate.yml remains the authoritative regeneration.
# This line is deliberately AFTER the &&-chain: under `set -euo pipefail` a real
# PLANNER_BUG failure aborts before it, leaving the regenerated docs on disk for
# diagnosis exactly as that script's docstring intends.
# LIVENESS_MATRIX.md is restored for a DIFFERENT reason: its `observed` column
# is environment-dependent BY DESIGN. A developer with a learning DB gets live
# counts; CI and a fresh clone get "unknown". The COMMITTED copy is the no-DB
# one, so the file in git is reproducible anywhere; a local run overwrites it
# with the richer view and this restores it. The gate VERDICT is identical
# either way -- the undeclared/orphan arms read the source, not the store.
( cd "$ROOT" && git checkout -- docs/craft_completeness/MATRIX.md docs/craft_completeness/BACKLOG.md \
                                docs/behavioral_completeness/LIVENESS_MATRIX.md )
echo "== (d) differential =="; ( cd "$HERE" && lake build oracle ); ( cd "$ROOT" && uv run pytest formal/diff/ -q --no-cov -n auto --ignore=formal/diff/test_game_data_fixture_diff.py )
# Full mutation EXECUTION is deliberately not here. It runs nightly in
# mutation-gate.yml, where CI moved it: ~36 min, peaks ~22GB, and it was the
# dominator of this script. Anchor resolution (phase b'''' above) is the part
# worth paying per-commit — it is seconds, runs no tests, and catches the stale
# or ambiguous anchor on the commit that caused it rather than 14h later.
# To run the sweep by hand: `uv run python formal/diff/mutate.py`.
# The Python suite runs LAST: it is the second-slowest phase, and every check
# above fails in seconds. run_tests.sh owns its own two-lane split and the 100%
# coverage gate; it is invoked rather than inlined so local and CI run the same
# script (.github/workflows/pytest.yml calls exactly this).
echo "== (e) python suite =="; ( cd "$ROOT" && bash scripts/run_tests.sh )
echo "ALL GATE PARTS PASSED"
