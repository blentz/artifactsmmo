"""Phase-B2 trace lockstep — replay a live trace through the Lean cycle mirror.

Part of docs/PLAN_c2_composed_liveness.md Phase B. Unlike trace_characterize.py
(pure measurement), this drives the LEAN MODEL: each trace cycle's scalar
snapshot is fed to the oracle's `cycle_step_d` entry, which evaluates
`CycleStepDC.cycleStepDC` — kernel-equal to the capstone's `cycleStepD` at the
axiom's value (`cycleStepDC_eq`), with `xpNext` = the trace's recorded `max_xp`
(the server's REAL xp curve, replacing LIV-001 with observed data per cycle).

HONESTY — what this can and cannot lock:
* The trace records scalars only; the opaque chore flags / debts / defer Bool
  are NOT recorded, so they are fed as quiet (0). Model selections that depend
  on them (deposit/sell/discard/claim/...) are therefore NOT comparable — those
  pairs are counted under `flag-unobserved`, and full decision lockstep awaits
  trace enrichment (tracked as Phase B3 in the plan).
* What IS comparable from scalars alone: the rest-vs-fight axis (hpCritical
  reads hp/maxHp) and the fight path's post-state projection. Dynamics
  divergences (xp projection vs real, rest partial heal) are REPORTED as
  classes, not asserted — they are the measured gap the Phase-C E-tower closes.

Output: formal/diff/trace_lockstep_report.txt + stdout. Read-only on the trace;
safe beside the live bot.

Usage: python diff/trace_lockstep.py [trace.jsonl] [oracle-binary]
"""

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

CHUNK = 500


def derive_phase(st: dict) -> int:
    code = st.get("task_code")
    prog = st.get("task_progress") or 0
    total = st.get("task_total") or 0
    if not code:
        return 0
    if total > 0 and prog >= total:
        return 3
    if prog > 0:
        return 2
    return 1


def vector(st: dict) -> list:
    return [
        st["hp"], st["max_hp"], st["level"], st["xp"],
        0,   # initialXp
        0,   # bankRequiredLevel
        0,   # unlockMonsterLevel
        st["inventory_used"], st["inventory_max"],
        0, 0, 0,  # taskCoinsTotal, taskExchangeMinCoins, actionsAttempted
        st.get("gold", 0),
        0, 1, 0,  # bankItemsCount, bankCapacity, nextExpansionCost
        derive_phase(st),
        1 if st.get("bank_accessible") else 0,
        0,  # bankUnlockMonsterPresent
        0, 0, 0, 0,  # overstock, selectBankDeposits, pending, sellable
        0, 1, 0,  # recyclable, taskFeasibleProjected, restForCombatReady=0? (opaque; quiet)
        0, 0, 0, 0, 1, 0, 0,  # gearReview, craftRelief, objectiveStepFires, maintainConsumables, bankItemsKnown, bankJunk, craftPotions
        st.get("max_xp", 0),  # [33] xpNext — the server's real curve value
        0,  # itemsTaskDeferActive
        0, 0, 0,  # debts
    ]


def action_class(action: str) -> str:
    head = (action or "").split("(", 1)[0]
    return {
        "Fight": "fight", "Rest": "rest",
    }.get(head, "other:" + head)


FLAG_DEPENDENT = {
    "claimPending", "completeTask", "sellPressured", "sellRelief",
    "depositFull", "discardCritical", "discardHigh", "gearReview",
    "craftPotions", "craftRelief", "recycleRelief", "drainBankJunk",
    "taskCancel", "lowYieldCancel", "pursueTask",
}


def main() -> int:
    trace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../play-trace-Robby.jsonl")
    oracle = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".lake/build/bin/oracle")
    if not trace.exists() or not oracle.exists():
        print(f"missing input: trace={trace} oracle={oracle}")
        return 1

    records = []
    with trace.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # TRACE SEMANTICS (player.py:740): _emit_trace runs AFTER action.execute —
    # record k's `state` is that action's POST-state. The selection state for
    # record k's action is record k-1's state. (First replay fed post-states as
    # pre-states, producing a phantom (fight,rest)x354 "divergence": hp 21/165
    # was post-fight damage, not the selection state — resolved 2026-07-04.)
    pairs = [
        (prev, cur) for prev, cur in zip(records, records[1:])
        if cur.get("cycle") == prev.get("cycle", -2) + 1
        and prev.get("state") and cur.get("state") and cur.get("outcome") == "ok"
    ]

    replies = []
    for i in range(0, len(pairs), CHUNK):
        batch = [{"kind": "cycle_step_d", "args": vector(prev["state"])} for prev, _ in pairs[i:i + CHUNK]]
        out = subprocess.run(
            [str(oracle)], input=json.dumps(batch), capture_output=True, text=True, check=True,
        )
        replies.extend(json.loads(out.stdout))

    decision = Counter()
    fight_xp_model_vs_real = Counter()
    fight_level_agree = 0
    fight_level_diverge = 0
    rest_hp_agree = 0
    rest_hp_diverge = 0

    for (prev, cur), r in zip(pairs, replies):
        sa, sb = prev["state"], cur["state"]
        tcls = action_class(cur.get("action") or "")
        sel = r.get("selected")
        if sel in FLAG_DEPENDENT or tcls.startswith("other:"):
            decision[("flag-unobserved", tcls, sel)] += 1
            continue
        model_cls = "fight" if sel in ("bankUnlock", "reachUnlockLevel", "objectiveStep") else \
                    "rest" if sel in ("hpCritical", "restForCombat") else str(sel)
        decision[("cmp", tcls, model_cls)] += 1
        if tcls == "fight" and model_cls == "fight":
            model_dxp = r["xp"] - sa["xp"] if r["level"] == sa["level"] else "rollover"
            real_dxp = sb["xp"] - sa["xp"] if sb["level"] == sa["level"] else "rollover"
            fight_xp_model_vs_real[(model_dxp, real_dxp)] += 1
            if (r["level"] > sa["level"]) == (sb["level"] > sa["level"]):
                fight_level_agree += 1
            else:
                fight_level_diverge += 1
        if tcls == "rest" and model_cls == "rest":
            if r["hp"] == sb["hp"]:
                rest_hp_agree += 1
            else:
                rest_hp_diverge += 1

    out = []
    out.append(f"trace={trace} pairs-replayed={len(pairs)} (oracle: cycle_step_d → cycleStepDC, kernel-equal to cycleStepD)")
    out.append("")
    out.append("== DECISION layer (scalars-only visibility) ==")
    agree = sum(c for (k, t, m), c in decision.items() if k == "cmp" and t == m)
    cmp_total = sum(c for (k, _, _), c in decision.items() if k == "cmp")
    unobs = sum(c for (k, _, _), c in decision.items() if k == "flag-unobserved")
    out.append(f"comparable={cmp_total} agree={agree} flag-unobserved(skipped)={unobs}")
    mism = [(t, m, c) for (k, t, m), c in decision.most_common() if k == "cmp" and t != m]
    out.append(f"mismatches (trace-action, model-selected, count): {mism[:12]}")
    out.append("")
    out.append("== FIGHT dynamics: model xp projection vs real (top 12) ==")
    out.append(f"{fight_xp_model_vs_real.most_common(12)}")
    out.append(f"level-rollover agreement: agree={fight_level_agree} diverge={fight_level_diverge}")
    out.append("")
    out.append("== REST dynamics: model hp:=max_hp vs real next hp ==")
    out.append(f"agree={rest_hp_agree} diverge={rest_hp_diverge}")
    out.append("")
    out.append("Divergence classes feed docs/LEVEL_FIFTY_RESIDUALS.md; decision lockstep")
    out.append("beyond the rest/fight axis awaits trace flag enrichment (Phase B3).")

    report = "\n".join(out)
    (Path(__file__).parent / "trace_lockstep_report.txt").write_text(report + "\n")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
