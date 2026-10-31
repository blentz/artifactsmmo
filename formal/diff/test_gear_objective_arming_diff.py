"""Differential: the gear objective's two halves, bound to production (ruling C4-b).

`Formal/Liveness/GearTierLeveling.lean` restates the combat objective below the
cap over the gear objective `(L*, m*)`:

* `fight_armed_of_held` — `L*` held: the root is one more level and the grind
  target is `m*`;
* `no_xp_fight_of_not_held` — `L*` not held: no grind target;
* `piece_root_of_not_held` / `no_root_when_every_piece_declined` — `L*` not
  held: the root is the step of the FIRST missing piece the cycle serves, in
  `missing`'s order, or no root when every piece is declined;
* `whichPieceIsNext none … = none` — no objective is the wall.

The Lean `whichPieceIsNext` / `grindTarget` are re-evaluated here in Python over the
abstraction they state (`m*`, `held`, the missing piece codes, a `serves`
predicate), and compared with what the LIVE functions produce:
`attach_gear_objective` → `farm_target` for the grind target, and `resolve_root`
→ `WhichPieceIsNext` → `piece_step` for the root. `serves` is production's own
`RootWalk.serves` per piece (with `GearPiece.awaits_delivery` as a decline), so
nothing about which piece is served is re-derived.

The sweep is every bundle scenario with no monsters task held and no fleet piece
(the two inputs the Lean view abstracts away), plus each scenario's `L*` carried
in the bag (ruling Q: carrying holds `L*`), which is where the held half is
exercised. Both halves must be exercised, or the sweep proves nothing about one.

This replaces `test_perceive_arm_diff.py`, which bound the same perception step
to the deleted windowed picker (a property production no longer has).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.decisions import which_piece_is_next as wp
from artifactsmmo_cli.ai.decisions.root import RootWalk, resolve_root
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_objective_result import GearObjective
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ReachCharLevel, no_decline
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT
from tests.test_ai.shared_world import attached, shared_world

BUNDLE = (Path(__file__).resolve().parents[2] / "tests" / "test_ai" / "scenarios"
          / "fixtures" / "gamedata_bundle.json")


def _lean_grind_target(objective: GearObjective | None) -> str | None:
    """`GearTierLeveling.grindTarget` with no task held: `m*` while `L*` is held."""
    if objective is None:
        return None
    return objective.monster if objective.held else None


def _lean_root(objective: GearObjective | None, served: list[bool],
               at_cap: bool) -> tuple[str, int] | None:
    """`GearTierLeveling.whichPieceIsNext`: `("level", 0)`, `("piece", index into
    missing)` or None."""
    if objective is None:
        return None
    if objective.held:
        return None if at_cap else ("level", 0)
    for index, ok in enumerate(served):
        if ok:
            return ("piece", index)
    return None


def _cases() -> list[tuple[str, bool]]:
    return [(name, carried) for name in sorted(SCENARIOS) for carried in (False, True)]


def _world(name: str, carried: bool) -> tuple[WorldState, GameData, SelectionContext]:
    gd = shared_world(BUNDLE)
    state = scenario_state(SCENARIOS[name], gd)
    if carried:
        objective = attached(state, gd, TIMED_NO_PROFILE_CONTEXT, None).gear_objective
        if objective is not None:
            bag = Counter(state.inventory)
            bag.update(piece.code for piece in objective.missing)
            state = replace(state, inventory=dict(bag))
    return state, gd, attached(state, gd, TIMED_NO_PROFILE_CONTEXT, None)


def _in_scope(state: WorldState, ctx: SelectionContext) -> bool:
    """The Lean view has no task arm and no fleet pieces."""
    return not (state.task_type == "monsters" and state.task_code) and not ctx.fleet_pieces


@pytest.mark.parametrize(("name", "carried"), _cases())
def test_production_matches_the_lean_root_walk(name: str, carried: bool) -> None:
    state, gd, ctx = _world(name, carried)
    if not _in_scope(state, ctx):
        return
    objective = ctx.gear_objective
    sheet = CharacterObjective.from_game_data(gd)

    # The grind target: production's `farm_target` (through attach_gear_objective).
    assert ctx.combat_monster == _lean_grind_target(objective), (name, carried)

    # The root: production's `resolve_root` from `WhichPieceIsNext`.
    walk = RootWalk(step_decline=no_decline)
    served = ([not piece.awaits_delivery(state)
               and walk.serves(piece.slot, wp.piece_target(piece, sheet, state),
                               state, gd, ctx, None)
               for piece in objective.missing] if objective is not None else [])
    at_cap = wp.next_level(state, gd) is None
    expected = _lean_root(objective, served, at_cap)
    actual = resolve_root(state, gd, sheet, ctx, None, no_decline).root

    want: MetaGoal | None
    if expected is None:
        want = None
    elif expected[0] == "level":
        want = ReachCharLevel(level=state.level + 1)
    else:
        assert objective is not None
        piece = objective.missing[expected[1]]
        want = wp.piece_step(piece.slot, wp.piece_target(piece, sheet, state),
                             RootWalk(step_decline=no_decline), state, gd, ctx, None)
    assert actual == want, (name, carried, actual, want)


def test_both_halves_are_in_the_sweep() -> None:
    """A sweep that never meets a held objective below the cap, or never a
    missing piece the cycle serves, binds nothing on that half. Counted here,
    not from the parametrized cases, so it holds however the cases are split
    across workers."""
    seen: Counter[str] = Counter()
    for name, carried in _cases():
        state, gd, ctx = _world(name, carried)
        objective = ctx.gear_objective
        if not _in_scope(state, ctx) or objective is None:
            continue
        if objective.held:
            seen["held"] += wp.next_level(state, gd) is not None
            continue
        sheet = CharacterObjective.from_game_data(gd)
        walk = RootWalk(step_decline=no_decline)
        seen["piece"] += any(
            not piece.awaits_delivery(state)
            and walk.serves(piece.slot, wp.piece_target(piece, sheet, state), state, gd, ctx, None)
            for piece in objective.missing)
        if seen["held"] and seen["piece"]:
            return
    pytest.fail(f"a half is never exercised: {dict(seen)}")


def test_a_declined_first_piece_hands_the_root_to_the_next() -> None:
    """`find?` skips a declined piece (`piece_root_of_not_held`'s order): declining
    the first missing piece's step makes production's root the second piece's."""
    for name in sorted(SCENARIOS):
        state, gd, ctx = _world(name, False)
        objective = ctx.gear_objective
        if (not _in_scope(state, ctx) or objective is None or objective.held
                or len(objective.missing) < 2):
            continue
        sheet = CharacterObjective.from_game_data(gd)
        first = resolve_root(state, gd, sheet, ctx, None, no_decline).root
        if first is None:
            continue

        def decline_first(root: MetaGoal, first: MetaGoal = first) -> str | None:
            return "declined for the differential" if root == first else None

        walk = RootWalk(step_decline=decline_first)
        served = [not piece.awaits_delivery(state)
                  and walk.serves(piece.slot, wp.piece_target(piece, sheet, state),
                                  state, gd, ctx, None)
                  for piece in objective.missing]
        expected = _lean_root(objective, served, False)
        actual = resolve_root(state, gd, sheet, ctx, None, decline_first).root
        if expected is None:
            assert actual is None, name
        else:
            piece = objective.missing[expected[1]]
            assert actual == wp.piece_step(
                piece.slot, wp.piece_target(piece, sheet, state),
                RootWalk(step_decline=decline_first), state, gd, ctx, None), name
            assert actual != first, name
        return
    pytest.fail("no scenario has two missing pieces and a served root")
