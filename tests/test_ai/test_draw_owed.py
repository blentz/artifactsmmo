"""A task draw is owed by the master's POOL WORTH (Phase 5-2c-iii-c-2 #5,
increment 3; USER 2026-10-07, `docs/PLAN_task_value.md` §8).

It used to be owed only when the chosen root changed (S-051 + the
no-immediate-redraw rule): after a turn-in or a cancel the next draw waited for
an unrelated root change — C3P0 5h+, R2D2 after its 13:28 turn-in. The brake
on an accept/cancel spin is now the economics: a pool is drawn from only while
the coins expected to be spent rerolling its worthless draws are at most what a
completion pays (`task_worth_core.draw_due`)."""

from types import SimpleNamespace

import pytest

import artifactsmmo_cli.ai.player as player_mod
import artifactsmmo_cli.ai.task_worth as mod
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.task_worth import pool_draw
from artifactsmmo_cli.ai.task_worth_core import WORTHLESS, TaskWorth
from tests.test_ai.fixtures import make_state

_WORTHY = TaskWorth(xp=True, gold=False, drops=False)


def _task(code: str, master: str, level: int = 1):  # type: ignore[no-untyped-def]
    return SimpleNamespace(code=code, type_=master, level=level, min_quantity=10, max_quantity=20)


def _gd(pools: dict[str, list[str]]) -> GameData:
    gd = GameData()
    gd.world.taskmaster_tiles = {master: (i, 0) for i, master in enumerate(pools)}
    gd._tasks = [_task(code, master) for master, codes in pools.items() for code in codes]
    gd._task_coin_rewards = {"any": 4}
    return gd


@pytest.fixture
def worthy(monkeypatch):  # type: ignore[no-untyped-def]
    """Worth by code: a code in the returned set is worthy, any other worthless."""
    codes: set[str] = set()
    seen: list[tuple[str, str, int]] = []

    def fake(code, task_type, remaining, *rest):  # type: ignore[no-untyped-def]
        seen.append((code, task_type, remaining))
        return _WORTHY if code in codes else WORTHLESS

    monkeypatch.setattr(mod, "task_worth_for", fake)
    return SimpleNamespace(codes=codes, seen=seen)


def test_nothing_is_due_while_a_task_is_held(worthy) -> None:
    worthy.codes.add("wolf")
    held = make_state(level=30, task_code="pig", task_type="monsters", task_total=5)
    assert pool_draw(held, _gd({"monsters": ["wolf"]}), NO_PROFILE_CONTEXT, None) == (False, None)


def test_a_pool_whose_rerolls_pay_is_due(worthy) -> None:
    """Live 2026-10-07: 9 of 21 worthy, 4 coins a completion — 12 ≤ 36."""
    worthy.codes.update(f"w{i}" for i in range(9))
    pool = [f"w{i}" for i in range(9)] + [f"g{i}" for i in range(12)]
    assert pool_draw(make_state(level=30), _gd({"monsters": pool}), NO_PROFILE_CONTEXT, None) \
        == (True, "monsters")
    assert ("w0", "monsters", 15) in worthy.seen  # each task at its mean quantity


def test_a_pool_too_poor_for_its_rerolls_is_not_due(worthy) -> None:
    """4 of 21: 17 rerolls cost more than 4 coins x 4 worthy draws pay."""
    worthy.codes.update(f"w{i}" for i in range(4))
    pool = [f"w{i}" for i in range(4)] + [f"g{i}" for i in range(17)]
    assert pool_draw(make_state(level=30), _gd({"monsters": pool}), NO_PROFILE_CONTEXT, None) \
        == (False, None)


def test_the_master_with_the_higher_worthy_share(worthy) -> None:
    worthy.codes.update({"wolf", "copper", "iron"})
    gd = _gd({"monsters": ["wolf", "sheep"], "items": ["copper", "iron", "tin"]})
    assert pool_draw(make_state(level=30), gd, NO_PROFILE_CONTEXT, None) == (True, "items")


def test_a_tie_leaves_the_master_to_the_synergy_choice(worthy) -> None:
    worthy.codes.update({"wolf", "copper"})
    gd = _gd({"monsters": ["wolf", "sheep"], "items": ["copper", "tin"]})
    assert pool_draw(make_state(level=30), gd, NO_PROFILE_CONTEXT, None) == (True, None)


def test_an_empty_or_out_of_level_pool_is_never_drawn(worthy) -> None:
    gd = _gd({"monsters": []})
    assert pool_draw(make_state(level=30), gd, NO_PROFILE_CONTEXT, None) == (False, None)
    worthy.codes.add("lich")
    gd = _gd({"monsters": []})
    gd._tasks = [_task("lich", "monsters", level=40)]
    assert pool_draw(make_state(level=30), gd, NO_PROFILE_CONTEXT, None) == (False, None)


class TestPlayerContext:
    def _player(self, monkeypatch) -> GamePlayer:  # type: ignore[no-untyped-def]
        player = GamePlayer(character="probe", history=None)
        player.state = make_state(task_code=None, task_total=0)
        player.game_data = GameData()
        monkeypatch.setattr(player, "_winnable_farm_target", lambda: None)
        return player

    def test_the_pool_verdict_reaches_the_selection_context(self, monkeypatch) -> None:
        player = self._player(monkeypatch)
        monkeypatch.setattr(player_mod, "pool_draw", lambda *a: (True, "items"))
        ctx = player._selection_context()
        assert ctx.draw_owed is True and ctx.draw_master == "items"
        monkeypatch.setattr(player_mod, "pool_draw", lambda *a: (False, None))
        ctx = player._selection_context()
        assert ctx.draw_owed is False and ctx.draw_master is None

    def test_an_offline_scenario_draws_nothing(self, monkeypatch) -> None:
        player = self._player(monkeypatch)
        monkeypatch.setattr(player_mod, "pool_draw", lambda *a: (True, "items"))
        player._draws_enabled = False
        ctx = player._selection_context()
        assert ctx.draw_owed is False and ctx.draw_master is None

    def test_the_dag_xp_demand_reaches_the_selection_context(self, monkeypatch) -> None:
        """c-2 #5 increment 4: the pool scan reads which XP the DAG demands."""
        player = self._player(monkeypatch)
        monkeypatch.setattr(player_mod, "xp_demand", lambda *a: (frozenset({"mining"}), True))
        seen = {}

        def draw(state, gd, ctx, history):  # type: ignore[no-untyped-def]
            seen.update(skills=ctx.skill_demand, level=ctx.level_demanded)
            return False, None

        monkeypatch.setattr(player_mod, "pool_draw", draw)
        ctx = player._selection_context()
        assert ctx.skill_demand == {"mining"} and ctx.level_demanded is True
        assert seen == {"skills": {"mining"}, "level": True}
