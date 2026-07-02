"""Tests for the means bands (collect-reward + discretionary)."""

from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

import artifactsmmo_cli.ai.learning.projections as projections_mod
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.models import Session as SessionModel
from artifactsmmo_cli.ai.learning.projections import Yield
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.means import (
    COLLECT_REWARD_ORDER,
    DISCRETIONARY_ORDER,
    MeansKind,
    active_means,
)
from tests.test_ai.fixtures import make_state


def _ctx(**kw) -> SelectionContext:
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None)
    base.update(kw)
    return SelectionContext(**base)


def _seed_cycles(store: LearningStore, cycles: list[dict]) -> None:
    store.start_session()
    with Session(store._engine) as s:
        if not s.get(SessionModel, store._session_id):
            s.add(SessionModel(
                session_id=store._session_id,
                started_at="2026-05-18T00:00:00Z",
                character="hero",
            ))
        for kw in cycles:
            kw_with = dict(kw)
            kw_with["session_id"] = store._session_id
            s.add(Cycle(**kw_with))
        s.commit()


def _cycle(idx: int, goal: str, *, delta_xp: int = 0, delta_gold: int = 0,
           task_progress: int = 0) -> dict:
    return dict(
        ts=f"2026-05-18T00:{idx:02d}:00Z",
        cycle_index=idx,
        character="hero",
        selected_goal=goal,
        action_repr="X",
        action_class="X",
        outcome="ok",
        delta_xp=delta_xp,
        delta_gold=delta_gold,
        delta_hp=0,
        delta_inv_used=0,
        task_progress=task_progress,
        task_total=10,
    )


def test_complete_task_in_collect_reward_when_task_done():
    state = make_state(task_code="cyclops", task_type="monsters", task_total=5, task_progress=5)
    collect, _ = active_means(state, GameData(), None, _ctx())
    assert MeansKind.COMPLETE_TASK in collect


def test_accept_task_in_discretionary_when_no_task():
    state = make_state(task_code=None)
    _, discretionary = active_means(state, GameData(), None, _ctx())
    assert MeansKind.ACCEPT_TASK in discretionary


def test_accept_task_fires_when_target_gear_already_equipped():
    """Equipped target gear doesn't block AcceptTask — that gear slot needs no
    further work, so the deferral `continue`s past it."""
    state = make_state(task_code=None,
                       equipment={"weapon_slot": "copper_dagger"})
    _, discretionary = active_means(
        state, GameData(), None, _ctx(target_gear=frozenset({"copper_dagger"})))
    assert MeansKind.ACCEPT_TASK in discretionary


def test_accept_task_deferred_when_target_gear_owned_but_unequipped():
    """Target gear sitting in inventory unequipped defers AcceptTask so
    UpgradeEquipment can fire first (the trace 2026-06-06 regression)."""
    state = make_state(task_code=None, inventory={"copper_dagger": 1})
    _, discretionary = active_means(
        state, GameData(), None, _ctx(target_gear=frozenset({"copper_dagger"})))
    assert MeansKind.ACCEPT_TASK not in discretionary


def test_accept_task_deferred_when_target_gear_craftable_now():
    """Target gear that's craftable under current skills defers AcceptTask so
    the gear chain wins material contention."""
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1),
    }
    # weaponcrafting defaults to 1 in make_state → skill >= crafting_level.
    state = make_state(task_code=None)
    _, discretionary = active_means(
        state, gd, None, _ctx(target_gear=frozenset({"copper_dagger"})))
    assert MeansKind.ACCEPT_TASK not in discretionary


def test_accept_task_fires_when_target_gear_unknown_or_uncraftable():
    """Target gear with no stats (or no crafting_skill, or skill too low) does
    not defer AcceptTask — the loop falls through and the task is accepted."""
    gd = GameData()
    gd._item_stats = {
        # Skill too high to craft now (skill-gate path, line 133-134 false).
        "future_gear": ItemStats(
            code="future_gear", level=20, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=20),
        # No crafting_skill at all (line 132 continue path).
        "dropped_gear": ItemStats(
            code="dropped_gear", level=5, type_="weapon"),
    }
    state = make_state(task_code=None)
    _, discretionary = active_means(
        state, gd, None,
        _ctx(target_gear=frozenset({"future_gear", "dropped_gear"})))
    assert MeansKind.ACCEPT_TASK in discretionary


def test_claim_pending_fires_with_pending_items():
    state = make_state(pending_items=(("id1", "copper_ore"),))
    collect, _ = active_means(state, GameData(), None, _ctx())
    assert MeansKind.CLAIM_PENDING in collect


def test_sell_pressured_vs_idle_mutually_exclusive_on_bag():
    gd = GameData()
    gd._npc_sell_prices = {"merchant": {"copper_ore": 5}}
    gd._npc_locations = {"merchant": (1, 2)}  # reachable now (required by _has_sellable)
    pressured = make_state(inventory={"copper_ore": 18}, inventory_max=20, task_code="t",
                           task_total=1, task_progress=0)  # 0.90 fill; task held so ACCEPT_TASK off
    idle = make_state(inventory={"copper_ore": 2}, inventory_max=20, task_code="t",
                      task_total=1, task_progress=0)        # 0.10 fill
    pc, pd = active_means(pressured, gd, None, _ctx())
    ic, idd = active_means(idle, gd, None, _ctx())
    assert MeansKind.SELL_PRESSURED in pc
    assert MeansKind.SELL_IDLE not in pd          # exclusivity: not both at high fill
    assert MeansKind.SELL_IDLE in idd
    assert MeansKind.SELL_PRESSURED not in ic     # exclusivity: not both at low fill


def test_band_order_matches_declared_order():
    state = make_state(task_code=None, pending_items=(("id", "x"),))
    collect, discretionary = active_means(state, GameData(), None, _ctx())
    assert collect == [m for m in COLLECT_REWARD_ORDER if m in collect]
    assert discretionary == [m for m in DISCRETIONARY_ORDER if m in discretionary]


def test_task_exchange_fires_when_enough_coins():
    state = make_state(inventory={"tasks_coin": 5}, task_code="t", task_total=1, task_progress=0)
    _, discretionary = active_means(state, GameData(), None, _ctx(task_exchange_min_coins=3))
    assert MeansKind.TASK_EXCHANGE in discretionary


def test_low_yield_cancel_absent_when_no_history():
    state = make_state(task_code="x", task_total=20, task_progress=5)
    collect, _ = active_means(state, GameData(), None, _ctx())
    assert MeansKind.LOW_YIELD_CANCEL not in collect


def _gd_task_rewards() -> GameData:
    """GameData carrying API completion rewards for the low-yield task codes so
    the projection reads real payouts (never a hardcoded 150/3)."""
    gd = GameData()
    gd._task_gold_rewards = {"x": 150, "gudgeon": 150}
    gd._task_coin_rewards = {"x": 3, "gudgeon": 3}
    return gd


def test_low_yield_cancel_fires_with_seeded_history(tmp_path):
    """Zero-char-XP FarmItems + positive FarmMonster → fires immediately (no confidence gate)."""
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    cycles = [_cycle(i, "FarmItems", delta_xp=0, task_progress=i) for i in range(5)]
    cycles += [_cycle(5 + i, "FarmMonster(slime)", delta_xp=15) for i in range(3)]
    _seed_cycles(store, cycles)
    state = make_state(task_code="gudgeon", task_type="items", task_total=347, task_progress=5)
    collect, _ = active_means(state, _gd_task_rewards(), store, _ctx())
    assert MeansKind.LOW_YIELD_CANCEL in collect
    store.close()


def test_task_cancel_absent_when_no_history():
    """TASK_CANCEL requires history; absent when history is None."""
    state = make_state(task_code="small_health_potion", task_type="items",
                       task_total=5, task_progress=0,
                       skills={"alchemy": 1, "mining": 1, "woodcutting": 1,
                               "fishing": 1, "weaponcrafting": 1, "gearcrafting": 1,
                               "jewelrycrafting": 1, "cooking": 1})
    gd = GameData()
    gd._item_stats = {}
    gd._crafting_recipes = {}
    collect, _ = active_means(state, gd, None, _ctx())
    assert MeansKind.TASK_CANCEL not in collect


def test_task_cancel_fires_when_pivot(tmp_path):
    """task_decision returns PIVOT for a combat-gated task → TASK_CANCEL fires."""
    store = LearningStore(db_path=str(tmp_path / "tc.db"), character="hero")
    gd = GameData()
    # combat-type task: task_requirement returns a combat req → PIVOT immediately
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._monster_level = {"cyclops": 20}
    # State: task is monsters type — task_requirement returns None (no skill gap) → PURSUE
    # To get PIVOT we need a skill-gated items task with no feasible path.
    # Use a task that requires alchemy level 5 but character only has level 1.
    gd._item_stats["small_health_potion"] = ItemStats(
        code="small_health_potion", level=1, type_="utility",
        crafting_skill="alchemy", crafting_level=5,
    )
    gd._crafting_recipes["small_health_potion"] = {"sunflower": 3}
    state = make_state(
        task_code="small_health_potion", task_type="items",
        task_total=29, task_progress=0,
        skills={"alchemy": 1, "mining": 1, "woodcutting": 1,
                "fishing": 1, "weaponcrafting": 1, "gearcrafting": 1,
                "jewelrycrafting": 1, "cooking": 1},
    )
    collect, _ = active_means(state, gd, store, _ctx())
    assert MeansKind.TASK_CANCEL in collect
    store.close()


def test_complete_task_not_in_collect_when_incomplete():
    state = make_state(task_code="cyclops", task_type="monsters", task_total=5, task_progress=3)
    collect, _ = active_means(state, GameData(), None, _ctx())
    assert MeansKind.COMPLETE_TASK not in collect


def test_accept_task_not_in_discretionary_when_task_held():
    state = make_state(task_code="cyclops", task_type="monsters", task_total=5, task_progress=3)
    _, discretionary = active_means(state, GameData(), None, _ctx())
    assert MeansKind.ACCEPT_TASK not in discretionary


def test_bank_expand_fires_when_conditions_met():
    gd = GameData()
    gd._bank_capacity = 20
    gd._next_expansion_cost = 10
    # 19/20 = 0.95 fill, gold >= cost, bank accessible
    state = make_state(bank_items={f"item{i}": 1 for i in range(19)}, gold=100)
    _, discretionary = active_means(state, gd, None, _ctx(bank_accessible=True))
    assert MeansKind.BANK_EXPAND in discretionary


def test_bank_expand_absent_when_bank_not_accessible():
    gd = GameData()
    gd._bank_capacity = 20
    gd._next_expansion_cost = 10
    state = make_state(bank_items={f"item{i}": 1 for i in range(19)}, gold=100)
    _, discretionary = active_means(state, gd, None, _ctx(bank_accessible=False))
    assert MeansKind.BANK_EXPAND not in discretionary


def test_bank_expand_absent_when_capacity_zero():
    gd = GameData()
    # _bank_capacity defaults to 0
    state = make_state(bank_items={"iron_ore": 1}, gold=100)
    _, discretionary = active_means(state, gd, None, _ctx(bank_accessible=True))
    assert MeansKind.BANK_EXPAND not in discretionary


def test_bank_expand_absent_when_fill_below_threshold():
    gd = GameData()
    gd._bank_capacity = 100
    gd._next_expansion_cost = 10
    # Only 5 items in a 100-slot bank → 5% fill, far below 95%
    state = make_state(bank_items={f"item{i}": 1 for i in range(5)}, gold=100)
    _, discretionary = active_means(state, gd, None, _ctx(bank_accessible=True))
    assert MeansKind.BANK_EXPAND not in discretionary


def test_bank_expand_absent_when_insufficient_gold():
    gd = GameData()
    gd._bank_capacity = 20
    gd._next_expansion_cost = 1000
    state = make_state(bank_items={f"item{i}": 1 for i in range(19)}, gold=5)
    _, discretionary = active_means(state, gd, None, _ctx(bank_accessible=True))
    assert MeansKind.BANK_EXPAND not in discretionary


def test_low_yield_cancel_absent_when_no_alt_history(tmp_path):
    """FarmItems history present but no FarmMonster data → no fire."""
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    cycles = [_cycle(i, "FarmItems", delta_xp=1, task_progress=i) for i in range(5)]
    _seed_cycles(store, cycles)
    state = make_state(task_code="x", task_type="items", task_total=20, task_progress=5)
    collect, _ = active_means(state, GameData(), store, _ctx())
    assert MeansKind.LOW_YIELD_CANCEL not in collect
    store.close()


def test_low_yield_cancel_absent_when_no_farmitems_history(tmp_path):
    """FarmMonster history but no FarmItems samples → no fire."""
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    cycles = [_cycle(i, "FarmMonster(slime)", delta_xp=15) for i in range(3)]
    _seed_cycles(store, cycles)
    state = make_state(task_code="gudgeon", task_type="items", task_total=50, task_progress=5)
    collect, _ = active_means(state, GameData(), store, _ctx())
    assert MeansKind.LOW_YIELD_CANCEL not in collect
    store.close()


def test_low_yield_cancel_positive_path_fires_above_margin(tmp_path):
    """Both current and alt positive; alt >= current * 1.5; sufficient confidence."""
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    # FarmItems: 1 xp/cycle; FarmMonster: 5 xp/cycle → 5x > 1.5 margin.
    # Need enough cycles for confidence >= 0.5 (sample_count / (10*3) >= 0.5 → >= 15 samples).
    cycles = (
        [_cycle(i, "FarmItems", delta_xp=1, task_progress=i) for i in range(35)] +
        [_cycle(35 + i, "FarmMonster(chicken)", delta_xp=5) for i in range(35)]
    )
    _seed_cycles(store, cycles)
    state = make_state(task_code="x", task_type="items", task_total=50, task_progress=10)
    collect, _ = active_means(state, _gd_task_rewards(), store, _ctx())
    assert MeansKind.LOW_YIELD_CANCEL in collect
    store.close()


def test_low_yield_cancel_absent_below_confidence_threshold(tmp_path):
    """Few FarmItems cycles → confidence < 0.5; positive current → no fire on positive path."""
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    # 3 FarmItems cycles → confidence = 3/30 = 0.1 < 0.5
    cycles = (
        [_cycle(i, "FarmItems", delta_xp=1, task_progress=i) for i in range(3)] +
        [_cycle(3 + i, "FarmMonster(chicken)", delta_xp=5) for i in range(3)]
    )
    _seed_cycles(store, cycles)
    state = make_state(task_code="x", task_type="items", task_total=50, task_progress=3)
    collect, _ = active_means(state, _gd_task_rewards(), store, _ctx())
    assert MeansKind.LOW_YIELD_CANCEL not in collect
    store.close()


def test_low_yield_cancel_positive_path_no_fire_below_margin(tmp_path):
    """Alt slightly better (1.2x) but below margin (1.5x) → no fire."""
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    cycles = (
        [_cycle(i, "FarmItems", delta_xp=1, task_progress=i) for i in range(30)] +
        [_cycle(30 + i, "FarmMonster(chicken)", delta_xp=1) for i in range(30)] +
        [_cycle(60 + i, "FarmMonster(chicken)", delta_xp=2) for i in range(6)]
    )
    _seed_cycles(store, cycles)
    state = make_state(task_code="x", task_type="items", task_total=50, task_progress=10)
    collect, _ = active_means(state, _gd_task_rewards(), store, _ctx())
    assert MeansKind.LOW_YIELD_CANCEL not in collect
    store.close()


def test_best_alternative_repr_returns_none_on_sqla_error(tmp_path):
    """SQLAlchemyError inside Session context → returns None → no LOW_YIELD_CANCEL."""
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    cycles = [_cycle(i, "FarmItems", delta_xp=0, task_progress=i) for i in range(5)]
    _seed_cycles(store, cycles)
    state = make_state(task_code="gudgeon", task_type="items", task_total=50, task_progress=5)
    with patch("artifactsmmo_cli.ai.learning.projections.Session") as mock_session:
        mock_session.side_effect = SQLAlchemyError("db error")
        collect, _ = active_means(state, GameData(), store, _ctx())
        assert MeansKind.LOW_YIELD_CANCEL not in collect
    store.close()


def test_best_alternative_repr_returns_none_when_all_goals_none(tmp_path):
    """All selected_goal rows are None → counts dict empty → returns None → no fire."""

    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    cycles = [_cycle(i, "FarmItems", delta_xp=0, task_progress=i) for i in range(5)]
    _seed_cycles(store, cycles)
    state = make_state(task_code="gudgeon", task_type="items", task_total=50, task_progress=5)

    class FakeSession:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def exec(self, stmt):
            return iter([None, None])

    with patch("artifactsmmo_cli.ai.learning.projections.Session", FakeSession):
        collect, _ = active_means(state, GameData(), store, _ctx())
        assert MeansKind.LOW_YIELD_CANCEL not in collect
    store.close()


class TestPursueTask:
    def test_in_discretionary_order(self):
        assert MeansKind.PURSUE_TASK in DISCRETIONARY_ORDER

    def test_fires_for_items_task_on_pursue(self):
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=0)
        store = LearningStore(db_path=":memory:", character="hero")
        with patch("artifactsmmo_cli.ai.tiers.means.task_decision", return_value="pursue"):
            _, discretionary = active_means(state, GameData(), store, _ctx())
        assert MeansKind.PURSUE_TASK in discretionary

    def test_does_not_fire_for_monster_task(self):
        state = make_state(task_code="chicken", task_type="monsters",
                           task_total=20, task_progress=0)
        store = LearningStore(db_path=":memory:", character="hero")
        with patch("artifactsmmo_cli.ai.tiers.means.task_decision", return_value="pursue"):
            _, discretionary = active_means(state, GameData(), store, _ctx())
        assert MeansKind.PURSUE_TASK not in discretionary

    def test_does_not_fire_on_pivot(self):
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=0)
        store = LearningStore(db_path=":memory:", character="hero")
        with patch("artifactsmmo_cli.ai.tiers.means.task_decision", return_value="pivot"):
            _, discretionary = active_means(state, GameData(), store, _ctx())
        assert MeansKind.PURSUE_TASK not in discretionary

    def test_does_not_fire_when_full(self):
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=20)
        store = LearningStore(db_path=":memory:", character="hero")
        with patch("artifactsmmo_cli.ai.tiers.means.task_decision", return_value="pursue"):
            _, discretionary = active_means(state, GameData(), store, _ctx())
        assert MeansKind.PURSUE_TASK not in discretionary

    def test_does_not_fire_without_history(self):
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=0)
        _, discretionary = active_means(state, GameData(), None, _ctx())
        assert MeansKind.PURSUE_TASK not in discretionary


def test_low_yield_cancel_absent_when_alt_repr_found_but_no_yield(tmp_path):
    """alt_repr is found but expected_yield_per_cycle returns 0 samples for it → no fire."""
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    cycles = [_cycle(i, "FarmItems", delta_xp=0, task_progress=i) for i in range(5)]
    _seed_cycles(store, cycles)
    state = make_state(task_code="gudgeon", task_type="items", task_total=50, task_progress=5)

    def fake_best_alt(history: LearningStore) -> str | None:
        return "FarmMonster(ghost)"

    def fake_yield(goal_repr: str, history: LearningStore, window: int = 100) -> Yield:
        if goal_repr == "FarmMonster(ghost)":
            return Yield(sample_count=0)
        return Yield(sample_count=5, char_xp=0.0)

    with patch.object(projections_mod, "_best_alternative_repr", fake_best_alt):
        with patch("artifactsmmo_cli.ai.learning.projections.expected_yield_per_cycle", fake_yield):
            collect, _ = active_means(state, GameData(), store, _ctx())
            assert MeansKind.LOW_YIELD_CANCEL not in collect
    store.close()
