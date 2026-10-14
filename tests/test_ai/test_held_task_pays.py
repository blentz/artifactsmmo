"""Whether a held items task pays enough to defer the level step (spec
2026-10-14 items-task-pays §2)."""

from dataclasses import replace
from fractions import Fraction
from types import SimpleNamespace

import pytest

import artifactsmmo_cli.ai.held_task_pays as pays_mod
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.held_task_pays import held_task_pays
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.task_worth_core import TaskWorth
from tests.test_ai.fixtures import make_state

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
    assert held_task_pays(STATE, GameData(), CTX, "imp",
                          _store(monkeypatch, own=0.5, fleet=None)) is True
    assert monsters == ["imp"]


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
