"""Whether a held items task pays enough to defer the level step (spec
2026-10-14 items-task-pays §2)."""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlmodel import Session as SqlSession

import artifactsmmo_cli.ai.held_task_pays as pays_mod
import artifactsmmo_cli.ai.player as player_mod
from artifactsmmo_cli.ai.best_loadout import best_loadout
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.held_task_pays import held_task_pays
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.task_worth import task_worth_for
from artifactsmmo_cli.ai.task_worth_core import TaskWorth
from tests.test_ai.fixtures import make_state

_BUNDLE = Path(__file__).resolve().parent / "scenarios" / "fixtures" / "gamedata_bundle.json"

STATE = make_state(task_code="cooked_shrimp", task_type="items", task_total=200, task_progress=20)
CTX = replace(NO_PROFILE_CONTEXT, combat_monster="imp", skill_demand=frozenset({"cooking"}))
GRIND = Fraction(15, 31)   # HAL vs imp, live 2026-10-14


def _worth(monkeypatch: pytest.MonkeyPatch, worth: TaskWorth) -> list[tuple[object, ...]]:
    calls: list[tuple[object, ...]] = []

    def fake(*args: object) -> TaskWorth:
        calls.append(args)
        return worth
    monkeypatch.setattr(pays_mod, "task_worth_for", fake)
    return calls


def _grind(monkeypatch: pytest.MonkeyPatch, rate: Fraction = GRIND) -> list[str]:
    monsters: list[str] = []

    def fake(state: object, game_data: object, ctx: object, monster: str,
             store: object) -> SimpleNamespace:
        monsters.append(monster)
        return SimpleNamespace(rate=SimpleNamespace(xp_per_second=rate))
    monkeypatch.setattr(pays_mod, "best_loadout", fake)
    return monsters


def _store(monkeypatch: pytest.MonkeyPatch, own: float | None,
           fleet: float | None) -> LearningStore:
    store = LearningStore(db_path=":memory:", character="hero")
    monkeypatch.setattr(store, "task_work_xp_per_second", lambda code, skills: own)
    monkeypatch.setattr(store, "fleet_task_work_xp_per_second", lambda code, skills: fleet)
    return store


def _boom(*_: object, **__: object) -> None:
    raise AssertionError("must not be read")


def test_a_worthless_task_does_not_pay(monkeypatch: pytest.MonkeyPatch) -> None:
    _worth(monkeypatch, TaskWorth(xp=False, gold=False, drops=False))
    monkeypatch.setattr(pays_mod, "best_loadout", _boom)
    assert held_task_pays(STATE, GameData(), CTX, "imp", None) is False


@pytest.mark.parametrize("worth", [TaskWorth(xp=False, gold=True, drops=False),
                                   TaskWorth(xp=False, gold=False, drops=True)])
def test_a_gold_or_drop_verdict_pays(monkeypatch: pytest.MonkeyPatch, worth: TaskWorth) -> None:
    _worth(monkeypatch, worth)
    monkeypatch.setattr(pays_mod, "best_loadout", _boom)
    assert held_task_pays(STATE, GameData(), CTX, "imp", None) is True


def test_demanded_xp_faster_than_the_grind_pays(monkeypatch: pytest.MonkeyPatch) -> None:
    _worth(monkeypatch, TaskWorth(xp=True, gold=False, drops=False))
    monsters = _grind(monkeypatch)
    assert held_task_pays(STATE, GameData(), CTX, "wolf",
                          _store(monkeypatch, own=0.5, fleet=None)) is True
    assert monsters == ["wolf"]   # the argument, not ctx.combat_monster ("imp")


def test_demanded_xp_slower_than_the_grind_does_not_pay(monkeypatch: pytest.MonkeyPatch) -> None:
    _worth(monkeypatch, TaskWorth(xp=True, gold=False, drops=False))
    _grind(monkeypatch)
    assert held_task_pays(STATE, GameData(), CTX, "imp",
                          _store(monkeypatch, own=0.4, fleet=9.0)) is False


def test_an_equal_rate_does_not_pay(monkeypatch: pytest.MonkeyPatch) -> None:
    _worth(monkeypatch, TaskWorth(xp=True, gold=False, drops=False))
    _grind(monkeypatch, Fraction(1, 2))
    assert held_task_pays(STATE, GameData(), CTX, "imp",
                          _store(monkeypatch, own=0.5, fleet=None)) is False


def test_the_fleet_rate_stands_in_for_a_task_never_worked(monkeypatch: pytest.MonkeyPatch) -> None:
    _worth(monkeypatch, TaskWorth(xp=True, gold=False, drops=False))
    _grind(monkeypatch)
    assert held_task_pays(STATE, GameData(), CTX, "imp",
                          _store(monkeypatch, own=None, fleet=0.1)) is False
    assert held_task_pays(STATE, GameData(), CTX, "imp",
                          _store(monkeypatch, own=None, fleet=0.9)) is True


def test_no_rate_anywhere_defers_on_the_xp_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    """Spec ruling: without a learned rate the XP verdict alone decides, so a
    task never worked is worked once and measured (no absorbing state)."""
    _worth(monkeypatch, TaskWorth(xp=True, gold=False, drops=False))
    monkeypatch.setattr(pays_mod, "best_loadout", _boom)
    assert held_task_pays(STATE, GameData(), CTX, "imp",
                          _store(monkeypatch, own=None, fleet=None)) is True
    assert held_task_pays(STATE, GameData(), CTX, "imp", None) is True


def test_the_worth_reads_the_remaining_units(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _worth(monkeypatch, TaskWorth(xp=False, gold=False, drops=False))
    held_task_pays(STATE, GameData(), CTX, "imp", None)
    code, task_type, remaining = calls[0][:3]
    assert (code, task_type, remaining) == ("cooked_shrimp", "items", 180)


def test_the_rate_reads_the_demanded_skills(monkeypatch: pytest.MonkeyPatch) -> None:
    _worth(monkeypatch, TaskWorth(xp=True, gold=False, drops=False))
    _grind(monkeypatch)
    store = LearningStore(db_path=":memory:", character="hero")
    seen: list[tuple[str, frozenset[str]]] = []

    def own(code: str, skills: frozenset[str]) -> float:
        seen.append((code, skills))
        return 1.0
    monkeypatch.setattr(store, "task_work_xp_per_second", own)
    assert held_task_pays(STATE, GameData(), CTX, "imp", store) is True
    assert seen == [("cooked_shrimp", frozenset({"cooking"}))]


class TestAgainstTheRealPrices:
    """No mock between the verdict and the numbers: the real `task_worth_for`,
    the real `best_loadout` grind rate and a real `LearningStore` of recorded
    task-work cycles, over the committed scenario world."""

    TASK = "cooked_beef"      # cooking level 5; the scenario character cooks at 10
    MONSTER = "pig"           # a monster with a positive modelled grind rate

    @pytest.fixture(scope="class")
    def game_data(self) -> GameData:
        return load_bundle_game_data(_BUNDLE)

    def _world(self, game_data: GameData):  # type: ignore[no-untyped-def]
        state = replace(scenario_state(SCENARIOS["l20_boost_stock"], game_data),
                        task_code=self.TASK, task_type="items",
                        task_total=100, task_progress=10)
        ctx = replace(NO_PROFILE_CONTEXT, combat_monster="chicken",
                      skill_demand=frozenset({"cooking"}))
        return state, ctx

    @staticmethod
    def _record(store: LearningStore, task: str, xp: int, seconds: float) -> None:
        with SqlSession(store._engine) as s:
            s.add(Cycle(ts="2026-10-14T00:00:00+00:00", session_id=store._session_id,
                        cycle_index=0, character="hero", outcome="ok", task_code=task,
                        selected_goal=f"PursueTask({task})",
                        actual_cooldown_seconds=seconds,
                        delta_skill_xp_json=f'{{"cooking": {xp}}}'))
            s.commit()

    def _store(self, tmp_path: Path, xp: int) -> LearningStore:
        store = LearningStore(db_path=str(tmp_path / "learning.db"), character="hero")
        store.start_session()
        self._record(store, self.TASK, xp, 100.0)
        return store

    def test_the_demanded_skill_makes_the_xp_verdict(self, game_data: GameData) -> None:
        state, ctx = self._world(game_data)
        assert task_worth_for(self.TASK, "items", 90, state, game_data, ctx, None).xp
        undemanded = replace(ctx, skill_demand=frozenset())
        assert held_task_pays(state, game_data, undemanded, self.MONSTER, None) is False

    def test_the_verdict_follows_the_recorded_rate_against_the_real_grind(
            self, game_data: GameData, tmp_path: Path) -> None:
        state, ctx = self._world(game_data)
        grind = best_loadout(state, game_data, ctx, self.MONSTER, None).rate.xp_per_second
        assert grind > 0
        above = int(grind * 100) + 20      # recorded over 100 s of work
        below = int(grind * 100) - 20
        assert below > 0
        assert held_task_pays(state, game_data, ctx, self.MONSTER,
                              self._store(tmp_path, above)) is True
        assert held_task_pays(state, game_data, ctx, self.MONSTER,
                              self._store(tmp_path, below)) is False


class TestPlayerPricesThePayOncePerCycle:
    """`GamePlayer._selection_context` reads the pay once and holds it."""

    def _player(self, monkeypatch: pytest.MonkeyPatch, state, pays: list[object]):  # type: ignore[no-untyped-def]
        player = GamePlayer(character="probe", history=None)
        player.state = state
        player.game_data = GameData()
        monkeypatch.setattr(player, "_winnable_farm_target", lambda: None)
        monkeypatch.setattr(player_mod, "pool_draw", lambda *a: (False, None))
        monkeypatch.setattr(player_mod, "fight_ahead_loadout", lambda *a: None)
        monkeypatch.setattr(player_mod, "secure_win", lambda *a: True)

        def fake(state_, game_data, ctx, monster, history):  # type: ignore[no-untyped-def]
            pays.append((monster, ctx.combat_monster))
            return True
        monkeypatch.setattr(player_mod, "held_task_pays", fake)
        return player

    def test_an_active_items_task_with_a_target_is_priced_once(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        pays: list[object] = []
        player = self._player(monkeypatch, STATE, pays)
        ctx = player._selection_context("imp")
        assert ctx.held_task_pays is True
        assert pays == [("imp", "imp")]

    def test_no_items_task_is_not_priced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        pays: list[object] = []
        monsters = replace(STATE, task_type="monsters")
        player = self._player(monkeypatch, monsters, pays)
        assert player._selection_context("imp").held_task_pays is False
        assert pays == []

    def test_no_combat_target_is_not_priced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        pays: list[object] = []
        player = self._player(monkeypatch, STATE, pays)
        assert player._selection_context().held_task_pays is False
        assert pays == []
