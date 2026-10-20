"""The cycle's one gear objective in `SelectionContext` (spec 2026-10-18 §2.4,
§6.2): `GamePlayer._selection_context` computes `(L*, m*)` once and carries it,
and the grind target `combat_monster` is `m*` only while `L*` is held — no fight
is chosen for XP while a piece is missing — except a held monsters task's
monster, which keeps its precedence."""

import time
from dataclasses import replace
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import pytest

import artifactsmmo_cli.ai.gear_objective_context as ctx_mod
import artifactsmmo_cli.ai.player as player_mod
from artifactsmmo_cli.ai.bank_drain import bank_drain_excess
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_objective import gear_objective
from artifactsmmo_cli.ai.gear_objective_context import attach_gear_objective, gear_keep_for
from artifactsmmo_cli.ai.gear_objective_result import GearObjective, GearPiece
from artifactsmmo_cli.ai.inventory_keep import destroyable, keep_owned
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.recycle_surplus import recyclable_surplus
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.strategy import StrategyEngine
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT, make_state
from tests.test_ai.test_gear_objective import BUNDLE, CTX, _carrying_its_target, _robby

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
    player._offline_timing = committed_timing()
    player.state = make_state(task_code=None, task_total=0)
    player.game_data = GameData()
    monkeypatch.setattr(player, "_path_aligned_monster", _unasked)
    monkeypatch.setattr(player, "_pick_winnable_monster", _unasked)
    monkeypatch.setattr(player_mod, "pool_draw", lambda *a: (False, None))
    monkeypatch.setattr(ctx_mod, "secure_win", lambda *a: True)

    def objective_of(state, game_data, ctx, history):  # type: ignore[no-untyped-def]
        seen.append(ctx)
        return objective

    def loadout_of(state, game_data, ctx, history):  # type: ignore[no-untyped-def]
        seen.append(ctx)

    monkeypatch.setattr(ctx_mod, "gear_objective", objective_of)
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
    def keep(state, gd, history, monster, near_term):  # type: ignore[no-untyped-def]
        return {f"kept_for_{monster}": 1}
    monkeypatch.setattr(player_mod, "gear_keep_for", keep)
    monkeypatch.setattr(ctx_mod, "gear_keep_for", keep)
    # ...plus the `L*` pieces (ruling AM).
    assert player._selection_context().gear_keep == {"kept_for_wolf": 1, "iron_helm": 1}


def test_risk_is_judged_on_the_final_target(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[str] = []
    player = _player(monkeypatch, HELD, [])
    monkeypatch.setattr(ctx_mod, "secure_win",
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


def test_a_carried_piece_is_equipped_before_m_star_is_fought() -> None:
    """Ruling Q: carrying every `L*` piece holds the objective, so `m*` is the
    grind target, and the piece is not left in the bag: the plan arms it
    (`OptimizeLoadout`, the fight-loadout gate's equip) before the fight."""
    gd = load_bundle_game_data(BUNDLE)
    carrying, before = _carrying_its_target("l10_bag_pursuit", gd)
    player = GamePlayer(character="l10_bag_pursuit", history=None)
    player._offline_timing = committed_timing()
    player.seed_offline(carrying, gd)
    report = player.plan_from_state()
    assert player._last_ctx is not None and player._last_ctx.gear_objective is not None
    assert player._last_ctx.gear_objective.held
    assert player._last_ctx.combat_monster == before.monster
    assert [repr(a) for a in report.plan[:2]] == [f"OptimizeLoadout({before.monster})",
                                                   f"Fight({before.monster})"]


def test_a_new_targets_keep_carries_the_in_flight_upgrades(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The shared step (ruling W) on its own: a target the objective names
    replaces the task keep it arrived with by one built for that target, and
    the in-flight upgrades (`ctx.near_term_targets`) stay kept at one spare."""
    monkeypatch.setattr(ctx_mod, "gear_objective", lambda *a: HELD)
    monkeypatch.setattr(ctx_mod, "secure_win", lambda *a: True)
    ctx = replace(CTX, gear_keep={"task_gear": 1}, near_term_targets=frozenset({"iron_boots"}))
    out = ctx_mod.attach_gear_objective(make_state(task_code=None, task_total=0), GameData(),
                                        ctx, None)
    assert out.gear_objective is HELD
    assert out.combat_monster == "wolf"
    # The in-flight upgrade, plus `L*`'s own iron_helm (ruling AM).
    assert out.gear_keep == {"iron_boots": 1, "iron_helm": 1}
    assert out.combat_risky is False


def _gearing_store(tmp_path: Path) -> LearningStore:
    """A learning store whose last cycle ground `chicken` in the scenario's
    copper loadout: the live shape of a character between acquisition steps,
    whose active combat profile names every armour slot."""
    store = LearningStore(db_path=str(tmp_path / "keep.db"), character="l10_copper_adequate")
    store.start_session()
    worn = scenario_state(SCENARIOS["l10_copper_adequate"], load_bundle_game_data(BUNDLE))
    store.record_loadout_profile(
        "combat:chicken", {slot: code for slot, code in worn.equipment.items() if code})
    store.record_cycle(Cycle(
        ts=datetime.now(tz=timezone.utc).isoformat(), session_id="t", cycle_index=0,
        character="l10_copper_adequate", selected_goal="GrindCharacterXP(chicken)",
        action_repr="<none>", action_class="NoPlan", outcome="ok"))
    return store


@pytest.mark.parametrize("where", ["bank", "bag"])
def test_an_owned_l_star_piece_is_never_destroyable(tmp_path: Path, where: str) -> None:
    """Ruling AM (final review F6), on a scenario: `l10_copper_adequate`
    owns one `leather_armor`, an `L*` piece (the `iron_armor` until spec
    2026-10-18 §2.9 re-derived `L*` by kill speed), while its last fight's combat
    profile (copper, every armour slot named) is active. The profile switches
    the blanket equippable keep off for the slots it names, so before the fix
    the armour kept 0 copies: banked, `bank_drain_excess` drained it; carried
    (where it counts as held), `recyclable_surplus` recycled it. The keep map
    now carries every `L*` code, so the piece is kept, missing or held."""
    gd = load_bundle_game_data(BUNDLE)
    store = _gearing_store(tmp_path)
    base = scenario_state(SCENARIOS["l10_copper_adequate"], gd)
    state = (replace(base, bank_items={**(base.bank_items or {}), "leather_armor": 1})
             if where == "bank" else replace(base, inventory={**base.inventory, "leather_armor": 1}))
    arrived = replace(TIMED_NO_PROFILE_CONTEXT,
                      gear_keep=gear_keep_for(state, gd, store, None, frozenset()))
    ctx = attach_gear_objective(state, gd, arrived, store)
    assert ctx.gear_objective is not None
    assert ctx.gear_objective.loadout["body_armor_slot"] == "leather_armor"
    assert "copper_armor" in ctx.gear_keep
    assert keep_owned("leather_armor", state, gd, ctx) == 1
    assert destroyable("leather_armor", state, gd, ctx) == 0
    assert "leather_armor" not in bank_drain_excess(state, gd, ctx)
    assert "leather_armor" not in recyclable_surplus(state, gd, ctx)


def test_the_keep_carries_l_star_at_its_worn_count() -> None:
    """Ruling AM: every `L*` code at the copies `L*` wears, never lowering a
    larger demand already in the keep; no objective leaves the keep as is."""
    rings = GearObjective("wolf", {"ring1_slot": "iron_ring", "ring2_slot": "iron_ring",
                                   "helmet_slot": "iron_helm"}, Fraction(1), ())
    keep = ctx_mod.with_objective_keep({"iron_helm": 3, "copper_ring": 1}, rings)
    assert keep == {"iron_helm": 3, "copper_ring": 1, "iron_ring": 2}
    assert ctx_mod.with_objective_keep({"copper_ring": 1}, None) == {"copper_ring": 1}


def test_the_objective_line_names_the_target_and_the_first_missing_piece() -> None:
    """Final review F8: one line per decided cycle names `m*` and the first
    missing `L*` piece, so a 24 h witness can count flips of either."""
    assert ctx_mod.gear_objective_line(MISSING) == (
        "Gear objective: target wolf; first missing iron_helm (helmet_slot); 1 missing")
    assert ctx_mod.gear_objective_line(HELD) == "Gear objective: target wolf; L* held"
    assert ctx_mod.gear_objective_line(None) == "Gear objective: none (no loadout pays XP)"


def test_every_decided_cycle_logs_its_objective(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """The line is printed where the cycle's context is built (`_decide_band`),
    before the decision, so it is there even when the decision raises."""
    player = _player(monkeypatch, MISSING, [])

    class _Stop(Exception):
        pass

    def stop(*_: object, **__: object) -> None:
        raise _Stop

    player._strategy = StrategyEngine(objective=CharacterObjective.from_game_data(GameData()))
    monkeypatch.setattr(StrategyEngine, "decide", stop)
    with pytest.raises(_Stop):
        player._decide_band(player.state, player.game_data, [])
    assert "Gear objective: target wolf; first missing iron_helm (helmet_slot); 1 missing" \
        in capsys.readouterr().out
