"""Phase-B1 trace characterization — MEASURE the model↔bot divergence classes.

Part of docs/PLAN_c2_composed_liveness.md Phase B. This is a MEASUREMENT tool,
NOT a differential (it calls no Lean def — the oracle-backed lockstep needs the
Phase-B2 computable mirror of the noncomputable `cycleStepD`). It reports, per
model abstraction, what production actually did, for:

  * FIGHT dynamics (model: xp += 10 flat, no hp loss): real xp-delta
    distribution, the model-exact count, hp-delta distribution (the gap-1 data
    the E-tower's bounded hp-loss constant needs).
  * REST dynamics: observed hp-delta distribution (see SCOPE REDUCTION below
    for why this can no longer assert the "hp := max_hp" full-heal claim).

MIGRATION (2026-08-15, Task 4 of
docs/superpowers/plans/2026-08-15-harnesses-read-the-learning-store.md). This
file used to read `play-trace-*.jsonl` and recover per-cycle deltas by
DIFFERENCING CONSECUTIVE STATE SNAPSHOTS — `(prev, cur)` pairs built by
zipping adjacent trace records. It now reads
`formal/diff/store_records.load_cycles`, and every FIGHT/REST figure below is
a row's OWN `delta_xp` / `delta_hp` (see `store_records.py`'s module
docstring for why that distinction is load-bearing — it is what stopped an
earlier trace replay from crediting every craft with the FOLLOWING cycle's
result for three review rounds). There is no "prev/cur" pair anywhere in this
file any more; every figure below is computed from a single row.

SCOPE REDUCTION, and why each piece was cut rather than faked. `CycleRecord`
(`store_records.py`) exposes `character, cycle_index, action_repr,
action_class, outcome, level, xp, hp, delta_xp, delta_hp, delta_skill_xp,
skill_levels` — narrower than the full state snapshot a trace record carried.
Four sections this file used to report do not survive that narrowing, and are
REMOVED rather than computed on fabricated inputs:

  * REST full-heal violations (`post-hp == max_hp`). `max_hp` is a real
    `cycles` column but `CycleRecord` does not expose it, so this file can no
    longer tell "healed some" from "healed fully" — only the raw `delta_hp`
    distribution below, which needs no `max_hp`.
  * Inventory-delta distribution / the `DROP_BOUND` census. `inventory_used`
    is a real `cycles` column `CycleRecord` also does not expose.
  * LEVEL monotonicity (regression count) and CHORE transience (same-chore
    run lengths, non-fight burst lengths between fights). Both need TRUE
    CHRONOLOGICAL ADJACENCY between consecutive cycles, which the store
    cannot safely give: `load_cycles` orders rows by `(character,
    cycle_index)`, and `cycle_index` RESETS every session — one character in
    the live corpus has 61 distinct sessions sharing `cycle_index` values.
    Two rows that sort adjacently after that ordering can belong to sessions
    recorded weeks apart; treating them as "the next thing that happened"
    would silently manufacture bogus chore-runs and bursts across the seam.
    `CycleRecord` carries neither `ts` nor `session_id` to filter this
    safely, so both sections are dropped rather than computed unsound. (The
    write site's own `xp_gain.xp_gained` docstring notes the server-side
    invariant LEVEL monotonicity existed to police — "a level going down is
    not a thing the server does" — and the store already collapses a same-row
    decrease into the same `delta_xp = None` bucket as an ordinary
    multi-level jump, so even a single-row substitute could not tell the two
    apart.)
  * TASK lifecycle transitions — named in this file's original docstring as a
    planned section but never implemented in `main()` even before this
    migration; dropped from the docstring rather than carried forward as a
    stale promise.

A side effect of reading `delta_xp` instead of differencing `xp` across two
trace records: fights that leveled the character mid-fight, which the old
code diverted into a separate "rollover" bucket and DISCARDED from the xp-delta
distribution entirely, are now included with their correctly-attributed xp
gain (`Cycle.delta_xp` resolves a single-level-up pair via
`xp_gained`'s `(prev_max_xp - prev_xp) + new_xp` branch; see
`ai/learning/xp_gain.py`). Only a genuine multi-level jump — never observed in
the live corpus — still reads as unresolved.

Output: formal/diff/trace_characterize_report.txt + stdout summary.
Usage: uv run python formal/diff/trace_characterize.py [db_path]
"""

import sys
from collections import Counter
from pathlib import Path

from store_records import CycleRecord, EmptyCorpusError, load_cycles

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT = REPO_ROOT / "formal" / "diff" / "trace_characterize_report.txt"
DEFAULT_DB = Path.home() / ".cache" / "artifactsmmo" / "learning.db"

MODEL_FIGHT_XP = 10  # Lean applyActionKind .fight projection


def _is_fight(rec: CycleRecord) -> bool:
    return bool((rec.action_repr or "").startswith("Fight(") and rec.outcome == "ok")


def _is_rest(rec: CycleRecord) -> bool:
    return bool(rec.action_repr == "Rest" and rec.outcome == "ok")


def main() -> int:
    db_path = sys.argv[1] if len(sys.argv) > 1 else str(DEFAULT_DB)
    try:
        records = load_cycles(db_path)
    except EmptyCorpusError as exc:
        print(f"trace_characterize: {exc}", file=sys.stderr)
        return 1

    fight_xp: Counter[int] = Counter()
    fight_hp: Counter[int] = Counter()
    fight_unresolved = 0  # delta_xp is None: multi-level jump (never observed live) or unattributable
    fight_hp_loss_max = 0
    rest_total = 0
    rest_hp: Counter[int] = Counter()

    for rec in records:
        if _is_fight(rec):
            if rec.delta_xp is None:
                fight_unresolved += 1
            else:
                fight_xp[rec.delta_xp] += 1
            if rec.delta_hp is not None:
                fight_hp[rec.delta_hp] += 1
                fight_hp_loss_max = max(fight_hp_loss_max, -rec.delta_hp)
        elif _is_rest(rec):
            rest_total += 1
            if rec.delta_hp is not None:
                rest_hp[rec.delta_hp] += 1

    total_fights = sum(fight_xp.values()) + fight_unresolved

    out = []
    out.append(f"db={db_path}  rows={len(records)}")
    out.append("")
    out.append("== FIGHT dynamics (model: xp += 10 flat, hp untouched) ==")
    out.append(f"fights={total_fights}  unresolved(multi-level-jump)={fight_unresolved}")
    out.append(f"xp-delta distribution (top 10): {fight_xp.most_common(10)}")
    xp10 = fight_xp.get(MODEL_FIGHT_XP, 0)
    checked_xp = sum(fight_xp.values())
    out.append(f"  model-exact (+{MODEL_FIGHT_XP}): {xp10}/{checked_xp}")
    out.append(f"hp-delta distribution (top 10): {fight_hp.most_common(10)}")
    out.append(f"  max hp LOSS in one fight: {fight_hp_loss_max}  (E-tower bounded-loss constant candidate)")
    out.append("  inventory-delta / DROP_BOUND census: UNAVAILABLE — inventory_used is not")
    out.append("  exposed by CycleRecord (see module docstring, SCOPE REDUCTION).")
    out.append("")
    out.append("== REST dynamics (model: hp := max_hp) ==")
    out.append(f"rests={rest_total}")
    out.append(f"hp-delta distribution (top 10): {rest_hp.most_common(10)}")
    out.append("  full-heal violation count: UNAVAILABLE — max_hp is not exposed by")
    out.append("  CycleRecord, so 'healed some' cannot be distinguished from 'healed fully'.")
    out.append("")
    out.append("== DROPPED SECTIONS (see module docstring for why) ==")
    out.append("LEVEL monotonicity, CHORE transience (same-chore runs / non-fight bursts),")
    out.append("TASK lifecycle transitions — all needed either true chronological adjacency")
    out.append("the store's (character, cycle_index) ordering cannot safely provide across")
    out.append("session boundaries, or fields CycleRecord does not expose.")
    out.append("")
    out.append("Divergence classes above feed docs/LEVEL_FIFTY_RESIDUALS.md — measured, not assumed.")

    report = "\n".join(out)
    REPORT.write_text(report + "\n")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
