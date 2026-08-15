"""Phase-B1 trace characterization — MEASURE the model↔bot divergence classes.

Part of docs/PLAN_c2_composed_liveness.md Phase B. This is a MEASUREMENT tool,
NOT a differential (it calls no Lean def — the oracle-backed lockstep needs the
Phase-B2 computable mirror of the noncomputable `cycleStepD`). It reports, per
model abstraction, what production actually did, for:

  * FIGHT dynamics (model: xp += 10 flat, no hp loss, loot <= DROP_BOUND=8):
    real xp-delta distribution, the model-exact count, hp-delta distribution
    (the gap-1 data the E-tower's bounded hp-loss constant needs), and the
    inventory-delta / DROP_BOUND census.
  * REST dynamics (model: hp := max_hp): observed hp-delta distribution and
    the full-heal violation count.
  * LEVEL monotonicity (model: level never decreases).

MIGRATION (2026-08-15, Task 4 of
docs/superpowers/plans/2026-08-15-harnesses-read-the-learning-store.md). This
file used to read `play-trace-*.jsonl` and recover per-cycle deltas by
DIFFERENCING CONSECUTIVE STATE SNAPSHOTS — `(prev, cur)` pairs built by
zipping adjacent trace records. It now reads
`formal/diff/store_records.load_cycles`, and every FIGHT/REST figure below is
a row's OWN `delta_xp` / `delta_hp` (see `store_records.py`'s module
docstring for why that distinction is load-bearing — it is what stopped an
earlier trace replay from crediting every craft with the FOLLOWING cycle's
result for three review rounds). Every FIGHT and REST figure below is computed
from a single row; the ONE cross-row comparison left in the file is the LEVEL
monotonicity pass, which compares a character's consecutive rows in `ts` order
and is discussed as such below.

SCOPE, and the part of the earlier scope reduction that was SELF-INFLICTED
(corrected 2026-08-15 by the branch's final review). At migration this file
dropped four sections. One (TASK lifecycle) had never been implemented; the
other three were dropped on reasons that pointed at the wrong thing. Two said
"`CycleRecord` does not expose `max_hp` / `inventory_used`" — true, and the
wrong conclusion, since `cycles` carries both on every row and `CycleRecord` is
a dataclass THIS BRANCH wrote. The third said the adjacency it needed was
something "the store cannot safely give" — false about the store, which carries
`ts` AND `session_id`. Deleting a check because a field list a reviewer can
extend in five lines omits a column, while leaving the claim that check used to
police standing in `docs/LEVEL_FIFTY_RESIDUALS.md`, is the exact defect this
migration existed to remove. The field list was extended and the checks are
back:

  * REST full-heal (`hp == max_hp` on the Rest row). Sound from ONE row: the
    scalars `record_cycle` stores are POST-action (`new_state`), so the Rest
    row itself already carries the healed hp and the max it should have
    reached. No neighbor, no differencing.
  * Inventory-delta distribution / the `DROP_BOUND` census, from the row's own
    `delta_inv_used` — NOT from `inventory_used[i] - inventory_used[i-1]`,
    which is the differencing this module exists to avoid. `inventory_used`
    and `inventory_max` are read only to bound OBSERVABILITY: a fight that
    began with fewer than `DROP_BOUND` free slots could not have exhibited a
    violation, so a census that did not report that count could be reporting
    zero violations because the bags were full.
  * LEVEL monotonicity (regression count), over rows ordered by `(character,
    ts)`. This needs chronology, not session identity — a level is not
    supposed to fall between two sessions any more than within one — and `ts`
    is now on the record. Note `level` is post-action, so a decrease means the
    server showed a lower level later in wall-clock time.

Two sections stay dropped, for reasons that survive the correction:

  * CHORE transience (same-chore run lengths, non-fight burst lengths between
    fights) needs TRUE ADJACENCY WITHIN ONE SESSION — "the next thing that
    happened", not merely "the next row". `load_cycles` orders by `(character,
    cycle_index)` and `cycle_index` RESETS every session (one character in the
    live corpus has 61 distinct sessions sharing `cycle_index` values), and
    ordering by `ts` instead still splices the end of one session onto the
    start of the next, manufacturing runs and bursts across the seam.
    `CycleRecord` carries no `session_id` to cut those seams, so this section
    stays dropped rather than computed unsound — and that is again a FIELD
    LIST limit, not a store limit; `cycles.session_id` is right there for
    whoever wants the section back.
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
DROP_BOUND = 8  # Lean InventoryDynamics.DROP_BOUND — provisional constant to check


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
    fight_inv: Counter[int] = Counter()
    fight_unresolved = 0  # delta_xp is None: multi-level jump (never observed live) or unattributable
    fight_hp_loss_max = 0
    fight_inv_censored = 0  # began with < DROP_BOUND free slots: no violation was observable
    fight_inv_free_min: int | None = None
    rest_total = 0
    rest_hp: Counter[int] = Counter()
    rest_full_heal = 0
    rest_violations = 0   # hp != max_hp AFTER an ok Rest
    rest_unjudged = 0     # hp or max_hp absent on the row

    for rec in records:
        if _is_fight(rec):
            if rec.delta_xp is None:
                fight_unresolved += 1
            else:
                fight_xp[rec.delta_xp] += 1
            if rec.delta_hp is not None:
                fight_hp[rec.delta_hp] += 1
                fight_hp_loss_max = max(fight_hp_loss_max, -rec.delta_hp)
            if rec.delta_inv_used is not None:
                fight_inv[rec.delta_inv_used] += 1
                if rec.inventory_used is not None and rec.inventory_max is not None:
                    # Scalars are post-action, so the pre-fight fill is
                    # `inventory_used - delta_inv_used`.
                    free_before = rec.inventory_max - (rec.inventory_used - rec.delta_inv_used)
                    if free_before <= DROP_BOUND:
                        fight_inv_censored += 1
                    if fight_inv_free_min is None or free_before < fight_inv_free_min:
                        fight_inv_free_min = free_before
        elif _is_rest(rec):
            rest_total += 1
            if rec.delta_hp is not None:
                rest_hp[rec.delta_hp] += 1
            if rec.hp is None or rec.max_hp is None:
                rest_unjudged += 1
            elif rec.hp == rec.max_hp:
                rest_full_heal += 1
            else:
                rest_violations += 1

    total_fights = sum(fight_xp.values()) + fight_unresolved
    over_drop = sum(c for d, c in fight_inv.items() if d > DROP_BOUND)

    # LEVEL monotonicity, in WALL-CLOCK order per character — `load_cycles`
    # orders by `cycle_index`, which resets per session, so the level pass
    # re-sorts by `ts` rather than trusting the load order.
    level_rows = sorted(
        (r.character, r.ts, r.level) for r in records if r.level is not None
    )
    lvl_regressions = sum(
        1
        for (prev_char, _, prev_lvl), (cur_char, _, cur_lvl) in zip(level_rows, level_rows[1:])
        if prev_char == cur_char and cur_lvl < prev_lvl
    )
    ts_span = (min(r.ts for r in records), max(r.ts for r in records))

    out = []
    out.append(f"db={db_path}  rows={len(records)}")
    out.append(f"corpus spans {ts_span[0]} .. {ts_span[1]}  (row `ts`; every figure below is")
    out.append("as live as that range — this file states it so a later reader cannot cite a")
    out.append("dead corpus as a current measurement)")
    out.append("")
    out.append("== FIGHT dynamics (model: xp += 10 flat, hp untouched, loot <= DROP_BOUND=8) ==")
    out.append(f"fights={total_fights}  unresolved(multi-level-jump)={fight_unresolved}")
    out.append(f"xp-delta distribution (top 10): {fight_xp.most_common(10)}")
    xp10 = fight_xp.get(MODEL_FIGHT_XP, 0)
    checked_xp = sum(fight_xp.values())
    out.append(f"  model-exact (+{MODEL_FIGHT_XP}): {xp10}/{checked_xp}")
    out.append(f"hp-delta distribution (top 10): {fight_hp.most_common(10)}")
    out.append(f"  max hp LOSS in one fight: {fight_hp_loss_max}  (E-tower bounded-loss constant candidate)")
    out.append(f"inventory-delta distribution (top 10, row's own delta_inv_used): {fight_inv.most_common(10)}")
    out.append(f"  fights exceeding DROP_BOUND={DROP_BOUND}: {over_drop}/{sum(fight_inv.values())}")
    out.append(f"  of which UNOBSERVABLE (began with <= {DROP_BOUND} free slots, so no violation")
    out.append(f"  could have shown): {fight_inv_censored}   min free slots before a fight: {fight_inv_free_min}")
    out.append("")
    out.append("== REST dynamics (model: hp := max_hp) ==")
    out.append(f"rests={rest_total}")
    out.append(f"hp-delta distribution (top 10): {rest_hp.most_common(10)}")
    out.append(f"  post-hp == max_hp: {rest_full_heal}/{rest_full_heal + rest_violations}"
               f"   violations={rest_violations}   unjudged(hp or max_hp NULL)={rest_unjudged}")
    out.append("")
    out.append("== LEVEL monotonicity (model: level never decreases) ==")
    out.append(f"rows with a level={len(level_rows)}  regressions (per character, ordered by ts)={lvl_regressions}")
    out.append("")
    out.append("== DROPPED SECTIONS (see module docstring for why) ==")
    out.append("CHORE transience (same-chore runs / non-fight bursts) needs adjacency WITHIN a")
    out.append("session, and CycleRecord carries no session_id to cut the seams — a field-list")
    out.append("limit, not a store limit. TASK lifecycle transitions were never implemented.")
    out.append("")
    out.append("Divergence classes above feed docs/LEVEL_FIFTY_RESIDUALS.md — measured, not assumed.")

    report = "\n".join(out)
    REPORT.write_text(report + "\n")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
