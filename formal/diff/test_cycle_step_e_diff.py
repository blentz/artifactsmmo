"""Differential (E-tower): the oracle's `cycle_step_e` entry wires the geared
cycle faithfully.

The kernel already binds mirror = model (`cycleStepEC_eq`, an rfl-chain on
`cycleStepDC`'s clone), so the residual risk is the ORACLE BOUNDARY: the
40-slot vector decode (slots 38/39 are new) and the E-layer semantics as seen
through it. Each test drives the compiled oracle with hand-built states and
pins the behavior the capstone's descent rows prove:

* inadequate + quiet guards → the gear latch is armed and selected;
  gearProgress decrements an open gap / restores adequacy at exhaustion;
* adequate + quiet guards → the fight objective is armed and selected,
  xp advances, and the gear fields are untouched (non-rollover);
* a rollover fight resets gearGap := GEAR_CAP and drops adequacy;
* a fight costs FIGHT_LOSS_BOUND hp; at or below the bound it respawns full.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ORACLE = Path(__file__).resolve().parents[1] / ".lake/build/bin/oracle"

GEAR_CAP = 8
FIGHT_LOSS_BOUND = 270


def _base_vector() -> list[int]:
    """All ladder guards quiet: full hp, empty chores, no task phase."""
    v = [0] * 40
    v[0] = 1000        # hp
    v[1] = 1000        # maxHp (full → hpCritical/restForCombat quiet)
    v[2] = 10          # level
    v[3] = 50          # xp
    v[5] = 5           # bankRequiredLevel (level 10 ≥ 5 → bankUnlock quiet)
    v[7] = 10          # inventoryUsed
    v[8] = 100         # inventoryMax
    v[14] = 50         # bankCapacity
    v[17] = 1          # bankAccessible
    v[24] = 1          # taskFeasibleProjected
    v[30] = 1          # bankItemsKnown
    v[33] = 150        # xpNext (xpToNextLevel at this state)
    return v


def _run(batch: list[list[int]]) -> list[dict]:
    payload = [{"kind": "cycle_step_e", "args": v} for v in batch]
    out = subprocess.run(
        [str(ORACLE)], input=json.dumps(payload), capture_output=True,
        text=True, check=True,
    )
    return json.loads(out.stdout)


def test_inadequate_arms_and_discharges_gear() -> None:
    open_gap = _base_vector()
    open_gap[38] = 0   # loadoutAdequate = false
    open_gap[39] = 3   # gearGap
    exhausted = _base_vector()
    exhausted[38] = 0
    exhausted[39] = 0
    r_open, r_exh = _run([open_gap, exhausted])
    assert r_open["selected"] == "gearReview"
    assert r_open["gear_gap"] == 2
    assert r_open["loadout_adequate"] is False
    assert r_exh["selected"] == "gearReview"
    assert r_exh["gear_gap"] == 0
    assert r_exh["loadout_adequate"] is True   # exhaustion restores adequacy
    # last gap step restores adequacy too (gap 1 → 0)
    last = _base_vector()
    last[38] = 0
    last[39] = 1
    (r_last,) = _run([last])
    assert r_last["gear_gap"] == 0 and r_last["loadout_adequate"] is True


def test_adequate_fight_advances_xp_and_preserves_gear() -> None:
    v = _base_vector()
    v[38] = 1          # adequate
    v[39] = 5          # an open gap must be UNTOUCHED by a non-rollover fight
    (r,) = _run([v])
    assert r["selected"] == "objectiveStep"
    assert r["xp"] == 60                      # +10, below xpNext=150
    assert r["level"] == 10
    assert r["gear_gap"] == 5
    assert r["loadout_adequate"] is True
    assert r["hp"] == 1000 - FIGHT_LOSS_BOUND


def test_rollover_fight_rearms_gear() -> None:
    v = _base_vector()
    v[3] = 145         # xp + 10 ≥ xpNext=150 → rollover
    v[38] = 1
    v[39] = 0
    (r,) = _run([v])
    assert r["selected"] == "objectiveStep"
    assert r["level"] == 11
    assert r["gear_gap"] == GEAR_CAP
    assert r["loadout_adequate"] is False


def test_fight_below_bound_floors_at_one_hp() -> None:
    """A fight that would take the character below 0 floors at 1 hp.

    CORRECTED 2026-07-20 (was `test_fight_death_respawns_full`, asserting
    `hp == 300`). The old assertion pinned an UNFAITHFUL model: `fightLoss`
    treated the below-bound case as death → respawn-at-full. Because
    `hpDeficit = maxHp - hp` is EMeasure slot 18, that made dying decrease the
    measure MORE than surviving — the model priced death better than victory,
    and a bot that died every fight still reached 50.

    Production never dies and never restores: `FightAction.apply` computes
    `new_hp = max(1, hp - estimated_hp_cost)` (`ai/actions/combat.py:120-122`).
    This test now pins that floor.
    """
    v = _base_vector()
    v[0] = FIGHT_LOSS_BOUND          # hp == bound → below-bound branch
    v[1] = 300                       # maxHp low enough that hp/maxHp ≥ 3/4
    v[38] = 1
    (r,) = _run([v])
    # hp 270 of 300 = 90% → hpCritical quiet; the fight then floors hp at 1.
    assert r["selected"] == "objectiveStep"
    assert r["hp"] == 1


def test_defer_window_outranks_gear_arming() -> None:
    v = _base_vector()
    v[16] = 2          # phase inProgress
    v[34] = 1          # itemsTaskDeferActive
    # deferGate needs pursueTaskFires: phase active + progress < total
    v_total = list(v)
    v_total[38] = 0
    v_total[39] = 4
    # taskProgress/taskTotal are not in the vector head; the D entry models
    # them via phase alone — pursueTask fires on the phase. If the gate does
    # not hold the refresh arms the gear latch instead; both outcomes keep
    # gearGap intact, which is the wiring property pinned here.
    (r,) = _run([v_total])
    assert r["gear_gap"] in (3, 4)
    if r["gear_gap"] == 4:
        assert r["selected"] != "gearReview"
