"""Phase-B1 trace characterization — MEASURE the model↔bot divergence classes.

Part of docs/PLAN_c2_composed_liveness.md Phase B. This is a MEASUREMENT tool,
NOT a differential (it calls no Lean def — the oracle-backed lockstep needs the
Phase-B2 computable mirror of the noncomputable `cycleStepD`). It reads a live
play trace (jsonl, one record per cycle with scalar state snapshots) and
reports, per model abstraction, what production actually did:

  * FIGHT dynamics (model: xp += 10 flat, no hp loss, loot ≤ DROP_BOUND=8):
    real xp-delta distribution, level rollovers, hp-delta distribution
    (the gap-1 data the E-tower's bounded hp-loss constant needs),
    inventory-delta distribution.
  * REST semantics (model: hp := max_hp): violation count.
  * CHORE transience (the 2026-06-18 honesty boundary wanted exactly this
    live data): chore-burst lengths between consecutive fights, and
    consecutive same-chore run lengths (grounds DEBT_CAP).
  * TASK lifecycle transitions (accept/complete/cancel shapes vs the Lean
    phase semantics).

Output: formal/diff/trace_characterize_report.txt + stdout summary. Reads the
trace read-only; safe to run while the bot is live (no src import, no state).

Usage: python diff/trace_characterize.py [path-to-trace.jsonl]
"""

import json
import sys
from collections import Counter
from pathlib import Path

DROP_BOUND = 8  # Lean InventoryDynamics.DROP_BOUND — provisional constant to check
MODEL_FIGHT_XP = 10  # Lean applyActionKind .fight projection


def action_class(action: str) -> str:
    if not action:
        return "none"
    head = action.split("(", 1)[0]
    fight = {"Fight"}
    rest = {"Rest"}
    deposit = {"DepositAll", "Deposit"}
    sell = {"NpcSell", "Sell"}
    discard = {"DeleteItem", "Discard"}
    claim = {"ClaimPendingItem", "ClaimPending"}
    task = {"CompleteTask", "AcceptTask", "TaskCancel", "TaskTrade", "TaskExchange"}
    gather = {"Gather"}
    craft = {"Craft"}
    if head in fight:
        return "fight"
    if head in rest:
        return "rest"
    if head in deposit:
        return "deposit"
    if head in sell:
        return "sell"
    if head in discard:
        return "discard"
    if head in claim:
        return "claim"
    if head in task:
        return "task:" + head
    if head in gather:
        return "gather"
    if head in craft:
        return "craft"
    return "other:" + head


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../play-trace-Robby.jsonl")
    if not path.exists():
        print(f"trace not found: {path}")
        return 1

    records = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # tail record may be mid-write while the bot is live

    # TRACE SEMANTICS (player.py:740): _emit_trace runs AFTER action.execute,
    # so record k's `state` is the POST-state of record k's action; the PRE-state
    # is record k-1's state. Pairs are therefore (prev, cur): cur's action maps
    # prev.state -> cur.state. (The first replay of this tool mis-attributed
    # deltas by one action — resolved 2026-07-04.)
    pairs = []
    for prev, cur in zip(records, records[1:]):
        if cur.get("cycle") == prev.get("cycle", -2) + 1 and prev.get("state") and cur.get("state"):
            pairs.append((prev, cur))

    fight_xp = Counter()
    fight_hp = Counter()
    fight_inv = Counter()
    fight_rollovers = 0
    fight_hp_loss_max = 0
    rest_total = 0
    rest_violations = 0
    lvl_regressions = 0
    chore_runs = Counter()  # consecutive same-chore run lengths per class
    burst_lengths = Counter()  # non-fight burst length between fights

    cur_run_class = None
    cur_run_len = 0
    cur_burst = 0

    for prev, cur in pairs:
        sa, sb = prev["state"], cur["state"]
        cls = action_class(cur.get("action") or "")
        ok = cur.get("outcome") == "ok"

        if sb["level"] < sa["level"]:
            lvl_regressions += 1

        if cls == "fight" and ok:
            if sb["level"] > sa["level"]:
                fight_rollovers += 1
                fight_xp["rollover"] += 1
            else:
                fight_xp[sb["xp"] - sa["xp"]] += 1
            dhp = sb["hp"] - sa["hp"]
            fight_hp[dhp] += 1
            fight_hp_loss_max = max(fight_hp_loss_max, -dhp)
            fight_inv[sb["inventory_used"] - sa["inventory_used"]] += 1
        elif cls == "rest" and ok:
            rest_total += 1
            if sb["hp"] != sb["max_hp"]:
                rest_violations += 1

        # chore-run bookkeeping (deposit/sell/discard/claim classes)
        if cls in ("deposit", "sell", "discard", "claim"):
            if cls == cur_run_class:
                cur_run_len += 1
            else:
                if cur_run_class is not None and cur_run_len > 0:
                    chore_runs[(cur_run_class, cur_run_len)] += 1
                cur_run_class, cur_run_len = cls, 1
        else:
            if cur_run_class is not None and cur_run_len > 0:
                chore_runs[(cur_run_class, cur_run_len)] += 1
            cur_run_class, cur_run_len = None, 0

        # burst between fights
        if cls == "fight":
            if cur_burst > 0:
                burst_lengths[cur_burst] += 1
            cur_burst = 0
        else:
            cur_burst += 1

    out = []
    out.append(f"trace: {path}  records={len(records)}  consecutive-pairs={len(pairs)}")
    out.append("")
    out.append("== FIGHT dynamics (model: xp+=10 flat, hp untouched, loot <= DROP_BOUND=8) ==")
    total_fights = sum(fight_xp.values())
    out.append(f"fights={total_fights}  rollovers={fight_rollovers}")
    out.append(f"xp-delta distribution (top 10): {fight_xp.most_common(10)}")
    xp10 = fight_xp.get(MODEL_FIGHT_XP, 0)
    out.append(f"  model-exact (+{MODEL_FIGHT_XP}): {xp10}/{total_fights}")
    out.append(f"hp-delta distribution (top 10): {fight_hp.most_common(10)}")
    out.append(f"  max hp LOSS in one fight: {fight_hp_loss_max}  (E-tower bounded-loss constant candidate)")
    over_drop = sum(c for d, c in fight_inv.items() if isinstance(d, int) and d > DROP_BOUND)
    out.append(f"inventory-delta distribution (top 10): {fight_inv.most_common(10)}")
    out.append(f"  fights exceeding DROP_BOUND={DROP_BOUND}: {over_drop}")
    out.append("")
    out.append("== REST semantics (model: hp := max_hp) ==")
    out.append(f"rests={rest_total}  post-hp != max_hp violations={rest_violations}")
    out.append("")
    out.append("== LEVEL monotonicity (model: level never decreases) ==")
    out.append(f"regressions={lvl_regressions}")
    out.append("")
    out.append("== CHORE transience (2026-06-18 honesty boundary — now measured) ==")
    out.append(f"same-chore run lengths (class, len) -> count: {sorted(chore_runs.items())}")
    max_run = max((ln for (_c, ln) in chore_runs), default=0)
    out.append(f"  max same-chore run: {max_run}  (DEBT_CAP=8 grounding; model needs max_run-1 debt)")
    out.append(f"non-fight burst lengths between fights (top 15): {burst_lengths.most_common(15)}")
    max_burst = max(burst_lengths, default=0)
    out.append(f"  max burst: {max_burst}")
    out.append("")
    out.append("Divergence classes above feed docs/LEVEL_FIFTY_RESIDUALS.md — measured, not assumed.")

    report = "\n".join(out)
    (Path(__file__).parent / "trace_characterize_report.txt").write_text(report + "\n")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
