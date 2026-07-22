"""Differential: bind the model's opaque `loadoutAdequate` Bool to production.

`Measure.State.loadoutAdequate` carries production's verdict that the character's
gear beats the band's acquirable-witness target. It gates the E-tower's arming
(`CycleStepE.perceptionRefreshE`) and therefore the whole `ai_reaches_fifty_geared`
capstone — and until this file it was ASSERTED and never checked. Opened as
`docs/PLAN_c2_composed_liveness.md:238-241`; the adversarial review of 2026-07-20
flagged the E layer as having zero production binding.

WHAT THIS PINS, AND WHAT IT CANNOT
-----------------------------------
It pins that the predicate is SATISFIABLE and DISCRIMINATING in production:

* positive polarity — for every band row the witness loadout genuinely wins,
  so `loadoutAdequate := true` names a reachable state rather than a fiction;
* negative polarity — stripped gear genuinely loses at some bands, so the
  predicate is not a constant-true dressed up as an observation. Without this
  the positive half would prove nothing.

It does NOT pin the model's DYNAMICS. `loadoutAdequate` is never computed by the
model: `Measure.lean` defaults it false and `CycleStepE.gearProgress` flips it
from `gearGap`. The gap→adequate transition is a lockstep divergence class the
C2 plan already declines to assert, not something a differential can close.

THE SEMANTIC GAP THIS FILE EXPOSES
-----------------------------------
`Measure.lean:409-412` documents `loadoutAdequate` as the verdict for the CURRENT
equipment. **Production has no such predicate, and cannot have one.**

`is_winnable` -> `predict_win` calls `pick_loadout_cached` over inventory +
equipped and projects the best on-hand loadout (`combat.py:152-156`; the
docstring says "best on-hand"). And `project_loadout_stats` is a DELTA against
`state.equipment` (`projection.py:45-46` skips unchanged slots), because a live
`WorldState`'s `attack`/`critical_strike`/... already carry worn gear — the API
reports totals. So a state that is already WEARING its loadout projects a ZERO
gear contribution.

That is not a hypothetical. The first version of this file built exactly that
state (equipment = witness loadout, empty inventory) expecting it to isolate
"worn gear", and every one of the 49 bands lost: the gear had become invisible.
"Worn beats target" and "best on-hand beats target" are not separable predicates
in this codebase.

The construction below is therefore the FAITHFUL one, matching how the witness
rows were generated (`winnable_witness.py:210-212`): base stats, loadout in
inventory, nothing equipped, so `pick_loadout` selects it and the projection adds
its full contribution. What this pins is "a character holding the band's witness
loadout beats the band's target" — which is what `loadoutAdequate` means
operationally, and the `Measure.lean` docstring should be read that way.

`history=None` throughout: the learned-loss veto and the monotonic-win inference
(`combat.py:383-408`) would let a recorded win against any higher-level monster
force `True`, which would make the positive half vacuous.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.world_state import WorldState
from formal.diff.test_winnable_across_band_diff import (
    BASE_STATS_PATH,
    SNAPSHOT_PATH,
    _game_data_from_snapshot,
    _item_stats_from_snapshot,
    _snapshot_has_combat_fields,
)

FIXTURE = Path(__file__).resolve().parents[1] / "Formal/Liveness/GameDataFixture.lean"

_ROW_RE = re.compile(
    r"\{ level := (\d+), monsterCode := \"([^\"]+)\", monsterLevel := \d+\s*"
    r"loadoutCodes := \[([^\]]*)\]",
    re.S,
)


def _witness_rows() -> list[tuple[int, str, list[str]]]:
    """(band level, target monster, loadout codes) from the emitted fixture.

    Parsed rather than recomputed on purpose: the point is to bind the table the
    KERNEL reasons about, not a fresh computation that might drift from it.
    `test_witness_acquirable_diff.py` already pins the table against an
    independent recompute, so parsing here is not a second source of truth.
    """
    src = FIXTURE.read_text()
    body = src[src.index("def acquirableWitness"):]
    rows = []
    for level, monster, codes in _ROW_RE.findall(body):
        rows.append((int(level), monster, re.findall(r'"([^"]+)"', codes)))
    return rows


def _holding_state(level: int, base_row: dict[str, Any],
                   loadout: list[str], stats_by_code: dict[str, Any]) -> WorldState:
    """A state HOLDING `loadout` in inventory with nothing equipped.

    This is the faithful construction (see the module docstring): the projection
    is a delta against `state.equipment`, so gear must arrive via `pick_loadout`
    to contribute at all. Mirrors `_base_world_state` in the across-band diff and
    `winnable_witness.py:210-212`, which is how the rows being pinned were built.

    `hp` is set to `base.max_hp + Σ hp_bonus(loadout)` so the verdict runs at full
    projected health — `predict_win` reads `state.hp`, not `max_hp`
    (`combat.py:146-151`).
    """
    hp_bonus = sum(
        (stats_by_code[c].hp_bonus for c in loadout if c in stats_by_code), 0
    )
    return WorldState(
        character="adequacy", level=level, xp=0, max_xp=999999,
        hp=base_row["max_hp"] + hp_bonus, max_hp=base_row["max_hp"],
        gold=0, skills={}, x=0, y=0,
        inventory={c: 1 for c in loadout}, inventory_max=100,
        inventory_slots_max=100,
        equipment={}, cooldown_expires=None,
        task_code=None, task_type=None, task_progress=0, task_total=0,
        bank_items=None, bank_gold=None, pending_items=None,
        attack={e: v for e, v in base_row["attack"].items() if v != 0},
        resistance={e: v for e, v in base_row["resistance"].items() if v != 0},
        critical_strike=base_row["critical_strike"],
        initiative=base_row["initiative"],
    )


def _setup():
    snapshot = json.loads(Path(SNAPSHOT_PATH).read_text())
    if not _snapshot_has_combat_fields(snapshot):
        pytest.skip("snapshot predates the combat-field capture")
    stats = _item_stats_from_snapshot(snapshot)
    gd = _game_data_from_snapshot(snapshot, stats)
    base = json.loads(Path(BASE_STATS_PATH).read_text())
    return snapshot, stats, gd, base


def _base_row(base: Any, level: int) -> dict[str, Any] | None:
    """`character_base_stats.json` is `{"base_stats": {"<level>": row}, ...}`."""
    return base["base_stats"].get(str(level))


def test_witness_loadout_is_adequate_at_every_band() -> None:
    """POSITIVE polarity: wearing the band's witness loadout beats its target.

    `acquirableFrontier` is empty, so this covers every band 1..49. If it fails,
    `loadoutAdequate := true` is a state the E-tower assumes but production never
    reaches — the capstone would be assuming something false.
    """
    _snapshot, stats, gd, base = _setup()
    rows = _witness_rows()
    assert rows, "no acquirableWitness rows parsed from the fixture"

    losses, covered = [], 0
    for level, monster, codes in rows:
        br = _base_row(base, level)
        assert br is not None, f"no base stats for band {level}"
        covered += 1
        state = _holding_state(level, br, codes, stats)
        if not is_winnable(state, gd, monster, None):
            losses.append((level, monster))
    assert covered == len(rows) == 49, f"expected 49 bands, swept {covered}"
    assert not losses, f"witness loadout NOT adequate at: {losses}"


def test_stripped_gear_is_inadequate_somewhere() -> None:
    """NEGATIVE polarity: the predicate discriminates.

    Without this the positive test is compatible with `is_winnable` being
    constant-true, and the binding would be worthless. Asserted as a sweep
    ("fails at SOME band") rather than at a fixed level, because bare base stats
    still beat the earliest bands — the discrimination only bites once monster
    scaling outruns them.
    """
    _snapshot, stats, gd, base = _setup()
    rows = _witness_rows()

    inadequate = []
    for level, monster, _codes in rows:
        br = _base_row(base, level)
        if br is None:
            continue
        bare = _holding_state(level, br, [], stats)
        if not is_winnable(bare, gd, monster, None):
            inadequate.append(level)
    assert len(inadequate) == len(rows) == 49, (
        f"bare base stats should lose EVERY band; lost only {len(inadequate)} "
        f"of {len(rows)}. If this loosens, gear has stopped being load-bearing "
        f"somewhere and the positive test is weaker than it looks."
    )


def test_bare_character_loses_where_the_witness_wins() -> None:
    """The gear is what makes the difference, at the SAME band and target.

    Stronger than the sweep above: it holds level and monster fixed and varies
    only the loadout, so a passing positive test cannot be explained by the band
    being easy. At least one band must flip win->lose when the gear is removed.
    """
    _snapshot, stats, gd, base = _setup()
    flipped = []
    for level, monster, codes in _witness_rows():
        br = _base_row(base, level)
        if br is None:
            continue
        with_gear = _holding_state(level, br, codes, stats)
        without = _holding_state(level, br, [], stats)
        if is_winnable(with_gear, gd, monster, None) and not is_winnable(
                without, gd, monster, None):
            flipped.append(level)
    assert len(flipped) == 49, (
        f"expected the witness loadout to be decisive at all 49 bands, got "
        f"{len(flipped)}. Every band flips lose->win on the gear alone, so any "
        f"shortfall means a band's witness stopped mattering."
    )
