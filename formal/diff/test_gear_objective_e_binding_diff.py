"""Differential: bind the E-tower's gear fields to production's gear objective (ruling C4-R I3).

`Measure.State.loadoutAdequate` and `gearGap` drive the E-tower
(`CycleStepE.perceptionRefreshE`, `gearProgress`). Until now `loadoutAdequate` was bound
to "holds the band's witness loadout" (`test_loadout_adequate_diff.py`). Production's
gear decisions read the gear objective instead, so this file binds

    loadoutAdequate := gear_objective.held
    gearGap         := len(gear_objective.missing)

and checks the E-tower's definitions against production on the scenario bundle, both
polarities required:

* `gearProgress` restores adequacy EXACTLY at zero: `loadoutAdequate == (gearGap == 0)`
  at every bound state (production: `held = not missing`);
* `rearmE` re-arms the gap at `GEAR_CAP` (read from `CycleStepE.lean`), which is
  production's gear slot count (`len(gear_objective._GEAR_SLOTS)`, asserted equal):
  `missing` holds at most one piece per slot, so every bound gap is at most that;
* `perceptionRefreshE`: an adequate state passes through to the fight (production:
  root `ReachCharLevel`, grind target `m*`); an inadequate one arms a NON-fight
  objective step (production: no grind target, root not a level-up);
* `gearProgress` on one gear cycle: acquiring the first missing piece leaves the gap
  unchanged (an unproductive cycle, `gearCycleProductive = false`) or lowers it by
  exactly one (a productive one), never raises it, keeps `m*`, and adequacy follows
  the gap to zero. At least one productive cycle must be seen.

What it does NOT bind: `rearmE`'s reset on a level-up to a fresh `GEAR_CAP` gap.
Since `GEAR_CAP` is the gear slot count no `L*` misses more pieces, so the reset is a
true worst case for the gap; production recomputes `L*` and may hold it at once,
which a differential over single states cannot pin.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import replace
from pathlib import Path

from artifactsmmo_cli.ai.decisions.root import resolve_root
from artifactsmmo_cli.ai.gear_objective import _GEAR_SLOTS, gear_objective
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.tiers.meta_goal import ReachCharLevel, no_decline
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import WorldState
from formal.diff.test_gear_objective_arming_diff import BUNDLE
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT
from tests.test_ai.shared_world import attached, shared_world

CTX = TIMED_NO_PROFILE_CONTEXT
CYCLE_STEP_E = Path(__file__).resolve().parents[1] / "Formal" / "Liveness" / "CycleStepE.lean"


def _gear_cap() -> int:
    match = re.search(r"^def GEAR_CAP : Nat := (\d+)$", CYCLE_STEP_E.read_text(), re.MULTILINE)
    assert match, "GEAR_CAP not found in CycleStepE.lean"
    return int(match.group(1))


def _carry(state: WorldState, codes: list[str]) -> WorldState:
    bag = Counter(state.inventory)
    bag.update(codes)
    return replace(state, inventory=dict(bag))


def _bound_states() -> list[tuple[str, WorldState]]:
    """Every bundle scenario with a gear objective, plain and with its `L*` carried."""
    gd = shared_world(BUNDLE)
    out = []
    for name in sorted(SCENARIOS):
        state = scenario_state(SCENARIOS[name], gd)
        objective = gear_objective(state, gd, CTX, None)
        if objective is None:
            continue
        out.append((name, state))
        out.append((f"{name}+carried", _carry(state, [p.code for p in objective.missing])))
    return out


def test_gear_cap_is_the_gear_slot_count() -> None:
    """`GEAR_CAP` is production's gear slot count: the most pieces any `L*` can
    miss (one per slot), so the model's rollover reset is a true worst case."""
    assert _gear_cap() == len(_GEAR_SLOTS)


def test_the_bound_fields_satisfy_the_e_tower_invariants() -> None:
    gd = shared_world(BUNDLE)
    cap = _gear_cap()
    sheet = CharacterObjective.from_game_data(gd)
    seen: Counter[str] = Counter()
    for name, state in _bound_states():
        objective = gear_objective(state, gd, CTX, None)
        assert objective is not None, name
        adequate, gap = objective.held, len(objective.missing)
        assert adequate == (gap == 0), name
        assert gap <= cap, (name, gap, cap)
        assert len(objective.missing) <= len({piece.slot for piece in objective.missing}), name
        if state.task_type == "monsters" and state.task_code:
            continue
        ctx = attached(state, gd, CTX, None)
        if ctx.fleet_pieces:
            continue
        root = resolve_root(state, gd, sheet, ctx, None, no_decline).root
        if adequate:
            seen["adequate"] += 1
            # perceptionRefreshE passes an adequate state through to the fight.
            assert ctx.combat_monster == objective.monster, name
            assert root == ReachCharLevel(level=state.level + 1), (name, root)
        else:
            seen["inadequate"] += 1
            # perceptionRefreshE arms a NON-fight objective step.
            assert ctx.combat_monster is None, name
            assert not isinstance(root, ReachCharLevel), (name, root)
    assert seen["adequate"] >= 1 and seen["inadequate"] >= 1, seen


def test_one_gear_cycle_is_gear_progress() -> None:
    """Acquiring the first missing piece is one `gearProgress` step, at every
    scenario with an open gap; a productive step must be among them."""
    gd = shared_world(BUNDLE)
    steps: Counter[int] = Counter()
    for name in sorted(SCENARIOS):
        state = scenario_state(SCENARIOS[name], gd)
        objective = gear_objective(state, gd, CTX, None)
        if objective is None or objective.held:
            continue
        gap = len(objective.missing)
        after = gear_objective(_carry(state, [objective.missing[0].code]), gd, CTX, None)
        assert after is not None, name
        assert after.monster == objective.monster, name
        assert len(after.missing) in (gap, gap - 1), (name, gap, len(after.missing))
        assert after.held == (not after.missing), name
        steps[gap - len(after.missing)] += 1
    assert steps[1] >= 1, steps
