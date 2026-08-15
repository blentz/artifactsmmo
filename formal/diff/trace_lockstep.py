"""Phase-B2 trace lockstep — check production against the Lean model's stated
FIGHT/REST invariants.

Part of docs/PLAN_c2_composed_liveness.md Phase B.

MIGRATION (2026-08-15, Task 4 of
docs/superpowers/plans/2026-08-15-harnesses-read-the-learning-store.md) AND
THE CAPABILITY IT COST — READ THIS BEFORE TRUSTING THIS FILE'S OLD NUMBERS.

Before this migration, this file drove the LEAN MODEL ITSELF: each trace
cycle's full state snapshot was fed to the oracle's `cycle_step_d` entry,
which evaluated `CycleStepDC.cycleStepDC` — kernel-equal to the capstone's
`cycleStepD` at the axiom's value (`cycleStepDC_eq`) — with `xpNext` set to
the trace's recorded `max_xp` (the server's REAL xp curve for that cycle,
replacing the LIV-001 axiom with observed data). That produced the DECISION
comparison `docs/LEVEL_FIFTY_RESIDUALS.md` still cites: "709/762 agreement
(93%) on the scalars-visible rest/fight axis" — does the Lean production
ladder, fed the trace's real state, SELECT the same action class production
actually ran.

THAT DECISION COMPARISON CANNOT BE REPRODUCED FROM THE LEARNING STORE, and
this is a genuine capability loss, not a scope trim for convenience:

  * `xpNext` (the trace's `max_xp`) is not a `cycles` column at all — it was
    never persisted anywhere the store can be queried for. The oracle's
    fight-arm xp projection cannot be evaluated correctly without it; feeding
    a fabricated substitute (0, or the row's own `hp`) would silently corrupt
    the one figure this tool existed to make trustworthy — the REAL xp curve
    replacing the axiom. This project's data-honesty rule ("no defaulting to
    overcome missing data") applies here exactly as it does to the game API.
  * The production ladder's SELECTION also reads `bank_accessible`,
    `task_code`/`task_progress`/`task_total`, `gold`, `inventory_used`,
    `inventory_max` and a gear-adequacy flag. All but the gear flag ARE real
    `cycles` columns, but `CycleRecord` (`store_records.py`) does not expose
    any of them — only `character, cycle_index, action_repr, action_class,
    outcome, level, xp, hp, delta_xp, delta_hp, delta_skill_xp,
    skill_levels`. Zeroing them (the old script's own convention for the
    handful of opaque chore Bools the trace never recorded) is not an option
    here: those specific fields drive the FIGHT/REST branch of the ladder
    itself, not a side branch this tool already excluded as
    `flag-unobserved`, so quieting them would bias the ladder toward
    fight/rest regardless of what the real state was — a vacuous measurement
    dressed as a real one, exactly what this project's zero-vacuousness rule
    forbids.

So the oracle subprocess call is REMOVED. `docs/superpowers/specs/
2026-08-15-harnesses-read-the-learning-store-design.md`'s own field-need
table lists only `level, xp, hp` for this file — which is consistent with
this finding: whatever the design intended to survive migration was never the
oracle-backed decision comparison, only the FIGHT/REST invariant checks below,
which need nothing else.

WHAT SURVIVES, and why it is now sound. The Lean model's fight/rest arms make
two STATED, checkable claims independent of the ladder that selects them: a
fight pays flat `+10` xp and leaves hp untouched; a rest fully heals
(`hp := max_hp`). The first claim is checkable from `delta_xp` alone. The
second is NOT fully checkable — `max_hp` is not exposed by `CycleRecord`
either — so the REST section below reports only whether hp moved
(`delta_hp`), not whether it moved to `max_hp`; see `trace_characterize.py`'s
module docstring for the identical gap. Both are single-row reads of
`Cycle.delta_xp` / `Cycle.delta_hp` — the row's OWN attributed deltas, never a
difference against a neighboring row (see `store_records.py`'s module
docstring for why that distinction matters).

This file therefore now computes materially the same class of FIGHT/REST
observations as `trace_characterize.py`, reported as an explicit
agree/diverge verdict against each model claim rather than as a raw
distribution — the two files are NOT identical output, but they now draw on
the same corpus and the same fields, which they did not before. That
convergence is itself a finding to report, not a discrepancy to paper over.

Output: formal/diff/trace_lockstep_report.txt + stdout.
Usage: uv run python formal/diff/trace_lockstep.py [db_path]
"""

import sys
from collections import Counter
from pathlib import Path

from store_records import CycleRecord, EmptyCorpusError, load_cycles

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT = REPO_ROOT / "formal" / "diff" / "trace_lockstep_report.txt"
DEFAULT_DB = Path.home() / ".cache" / "artifactsmmo" / "learning.db"

MODEL_FIGHT_XP = 10  # Lean applyActionKind .fight projection — restated, not
# imported: this is a corroboration harness, and a harness that reads the
# constant under test cannot falsify it (matches xp_formula_replay.py).


def _is_fight(rec: CycleRecord) -> bool:
    return bool((rec.action_repr or "").startswith("Fight(") and rec.outcome == "ok")


def _is_rest(rec: CycleRecord) -> bool:
    return bool(rec.action_repr == "Rest" and rec.outcome == "ok")


def main() -> int:
    db_path = sys.argv[1] if len(sys.argv) > 1 else str(DEFAULT_DB)
    try:
        records = load_cycles(db_path)
    except EmptyCorpusError as exc:
        print(f"trace_lockstep: {exc}", file=sys.stderr)
        return 1

    fight_xp_agree = 0
    fight_xp_diverge = 0
    fight_xp_unresolved = 0  # delta_xp is None: multi-level jump, can't judge
    fight_xp_mismatch: Counter[tuple[int, int]] = Counter()  # (model=10, real) -> count
    fight_hp_agree = 0    # model claims hp untouched: delta_hp == 0
    fight_hp_diverge = 0
    rest_total = 0
    rest_healed = 0       # delta_hp > 0 (model claims full heal; this only checks "moved up")
    rest_hp: Counter[int] = Counter()

    for rec in records:
        if _is_fight(rec):
            if rec.delta_xp is None:
                fight_xp_unresolved += 1
            elif rec.delta_xp == MODEL_FIGHT_XP:
                fight_xp_agree += 1
            else:
                fight_xp_diverge += 1
                fight_xp_mismatch[(MODEL_FIGHT_XP, rec.delta_xp)] += 1
            if rec.delta_hp is not None:
                if rec.delta_hp == 0:
                    fight_hp_agree += 1
                else:
                    fight_hp_diverge += 1
        elif _is_rest(rec):
            rest_total += 1
            if rec.delta_hp is not None:
                rest_hp[rec.delta_hp] += 1
                if rec.delta_hp > 0:
                    rest_healed += 1

    out = []
    out.append(f"db={db_path}  rows={len(records)}")
    out.append("(oracle-backed decision differential REMOVED this migration — see module")
    out.append(" docstring; this now checks the model's FIGHT/REST invariants directly)")
    out.append("")
    out.append(f"== FIGHT xp lockstep (model claim: xp += {MODEL_FIGHT_XP} flat) ==")
    fight_xp_checked = fight_xp_agree + fight_xp_diverge
    out.append(f"checked={fight_xp_checked}  agree={fight_xp_agree}  diverge={fight_xp_diverge}  "
               f"unresolved(multi-level-jump)={fight_xp_unresolved}")
    out.append(f"mismatch classes (model, real) -> count, top 12: {fight_xp_mismatch.most_common(12)}")
    out.append("")
    out.append("== FIGHT hp lockstep (model claim: hp untouched) ==")
    fight_hp_checked = fight_hp_agree + fight_hp_diverge
    out.append(f"checked={fight_hp_checked}  agree={fight_hp_agree}  diverge={fight_hp_diverge}")
    out.append("")
    out.append("== REST hp lockstep (model claim: hp := max_hp) ==")
    out.append(f"rests={rest_total}  hp-increased={rest_healed}")
    out.append(f"hp-delta distribution (top 10): {rest_hp.most_common(10)}")
    out.append("  FULL-heal verdict UNAVAILABLE — max_hp is not exposed by CycleRecord, so")
    out.append("  'hp increased' cannot be distinguished from 'hp reached max_hp' (see")
    out.append("  module docstring).")
    out.append("")
    out.append("Decision-layer lockstep (production ladder selection vs the Lean model,")
    out.append("previously '709/762 agreement (93%)' per docs/LEVEL_FIFTY_RESIDUALS.md) is")
    out.append("HISTORICAL as of this migration and cannot be re-derived from the learning")
    out.append("store — see module docstring for exactly which fields are missing.")

    report = "\n".join(out)
    REPORT.write_text(report + "\n")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
