"""The cycle's one gear objective in `SelectionContext` (spec 2026-10-18 §2.4,
§6.2): `GamePlayer._selection_context` computes `(L*, m*)` once and carries it,
and the grind target `combat_monster` is `m*` only while `L*` is held — no fight
is chosen for XP while a piece is missing — except a held monsters task's
monster, which keeps its precedence."""

import time
from dataclasses import replace
from fractions import Fraction

import pytest

import artifactsmmo_cli.ai.player as player_mod
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_objective import gear_objective
from artifactsmmo_cli.ai.gear_objective_result import GearObjective, GearPiece
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import load_bundle_game_data
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_gear_objective import BUNDLE, CTX, _robby

PIECE = GearPiece("helmet_slot", "iron_helm", 0, Fraction(1), Fraction(10))
MISSING = GearObjective("wolf", {"helmet_slot": "iron_helm"}, Fraction(2), (PIECE,))
HELD = GearObjective("wolf", {"helmet_slot": "iron_helm"}, Fraction(2), ())


def _unasked(*_: object) -> None:
    raise AssertionError("the band / windowed pick is no longer consulted")


def _player(monkeypatch: pytest.MonkeyPatch, objective: GearObjective | None,
            seen: list[SelectionContext]) -> GamePlayer:
    """A player whose objective is `objective`; `seen` collects the context the
    objective was computed from, then the one the loadout was chosen against."""
    player = GamePlayer(character="probe", history=None)
    player.state = make_state(task_code=None, task_total=0)
    player.game_data = GameData()
    monkeypatch.setattr(player, "_path_aligned_monster", _unasked)
    monkeypatch.setattr(player, "_pick_winnable_monster", _unasked)
    monkeypatch.setattr(player_mod, "pool_draw", lambda *a: (False, None))
    monkeypatch.setattr(player_mod, "secure_win", lambda *a: True)

    def objective_of(state, game_data, ctx, history):  # type: ignore[no-untyped-def]
        seen.append(ctx)
        return objective

    def loadout_of(state, game_data, ctx, history):  # type: ignore[no-untyped-def]
        seen.append(ctx)

    monkeypatch.setattr(player_mod, "gear_objective", objective_of)
    monkeypatch.setattr(player_mod, "fight_ahead_loadout", loadout_of)
    return player


def test_the_context_carries_the_cycles_objective(monkeypatch: pytest.MonkeyPatch) -> None:
    """Computed once, from the cycle's own pricing context (bank access and the
    siblings' skills), before any grind target exists."""
    seen: list[SelectionContext] = []
    player = _player(monkeypatch, MISSING, seen)
    player._sibling_skills = {"gearcrafting": 30}
    ctx = player._selection_context()
    assert ctx.gear_objective is MISSING
    pricing, chosen = seen
    assert pricing.sibling_skills == {"gearcrafting": 30}
    assert pricing.bank_accessible is True
    assert pricing.combat_monster is None
    assert chosen.gear_objective is MISSING


def test_the_context_carries_no_objective_when_none_pays(
        monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _player(monkeypatch, None, [])._selection_context()
    assert ctx.gear_objective is None
    assert ctx.combat_monster is None


def test_no_xp_monster_while_a_piece_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """§6.2: no fight is chosen for XP while `L*` is missing."""
    seen: list[SelectionContext] = []
    ctx = _player(monkeypatch, MISSING, seen)._selection_context()
    assert ctx.combat_monster is None
    assert ctx.combat_risky is False and ctx.combat_propped is False
    assert seen[-1].combat_monster is None


def test_the_objectives_monster_once_held(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every consumer after the objective reads `m*`: the loadout chooser and
    the context it hands on."""
    seen: list[SelectionContext] = []
    ctx = _player(monkeypatch, HELD, seen)._selection_context()
    assert ctx.combat_monster == "wolf"
    assert seen[-1].combat_monster == "wolf"


def test_a_held_monsters_task_keeps_its_monster(monkeypatch: pytest.MonkeyPatch) -> None:
    """The task's monster outranks `m*`, held or not, and the objective is
    priced with it as the grind target (its gold rate prices a buy)."""
    for objective in (HELD, MISSING):
        seen: list[SelectionContext] = []
        player = _player(monkeypatch, objective, seen)
        monkeypatch.setattr(player, "_task_aligned_monster", lambda: "cow")
        ctx = player._selection_context()
        assert ctx.combat_monster == "cow"
        assert ctx.gear_objective is objective
        assert [c.combat_monster for c in seen] == ["cow", "cow"]


def test_the_gear_keep_follows_the_final_target(monkeypatch: pytest.MonkeyPatch) -> None:
    """The objective is priced keeping the task target's profile gear; the
    context the cycle hands on keeps the final target's."""
    player = _player(monkeypatch, HELD, [])
    monkeypatch.setattr(player, "_active_gear_keep",
                        lambda monster, near_term: {f"kept_for_{monster}": 1})
    assert player._selection_context().gear_keep == {"kept_for_wolf": 1}


def test_risk_is_judged_on_the_final_target(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[str] = []
    player = _player(monkeypatch, HELD, [])
    monkeypatch.setattr(player_mod, "secure_win",
                        lambda state, gd, monster: asked.append(monster) is not None)
    assert player._selection_context().combat_risky is True
    assert asked == ["wolf"]


def _timed(state: WorldState, gd: GameData) -> tuple[GearObjective | None, float, float]:
    """The objective and the (CPU, wall) seconds it took."""
    wall, cpu = time.perf_counter(), time.process_time()
    objective = gear_objective(state, gd, CTX, None)
    return objective, time.process_time() - cpu, time.perf_counter() - wall


def test_objective_cost_on_robbys_shape(capsys: pytest.CaptureFixture[str]) -> None:
    """Review Focus 5 (ruling P): the objective is computed every cycle, so on
    Robby's live shape a cycle's objective costs under 2 s of CPU (CPU, not
    wall: the suite runs under xdist load).

    A cycle's cost is the one a running process pays: the first objective in
    a process fills the fight-odds and loop memos, which every later cycle
    with the same fighters reuses. So the bound is asserted on a second cycle
    whose state differs (gold and bag, as a cycle's would) and the first is
    measured and printed beside it."""
    gd = load_bundle_game_data(BUNDLE)
    first, first_cpu, first_wall = _timed(_robby(), gd)
    cycle, cpu, wall = _timed(replace(_robby(), gold=1234, inventory={"copper_ore": 3}), gd)
    with capsys.disabled():
        print(f"\ngear_objective on Robby: first in process cpu {first_cpu:.3f} s, "
              f"wall {first_wall:.3f} s; a later cycle cpu {cpu:.3f} s, wall {wall:.3f} s")
    assert first is not None and cycle is not None
    assert cpu < 2.0
