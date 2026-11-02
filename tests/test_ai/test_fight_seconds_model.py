"""The learned fight-seconds model (spec 2026-10-18 §2.9, rulings CA, CC): fitted
to the fleet's recorded fights and a `/my/logs` bootstrap, refitted only when
either changes, and fitted offline from the committed live capture."""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest
from artifactsmmo_api_client.models.log_type import LogType

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.ge_fill_sell import GeFillSellOrderAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.actions.withdraw_gold import WithdrawGoldAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.fight_seconds_core import FightSecondsModel
from artifactsmmo_cli.ai.learning import fight_seconds_model as mod
from artifactsmmo_cli.ai.learning.fight_seconds_model import (
    BOOTSTRAP_FIGHTS,
    BOOTSTRAP_PAGE,
    PRICED_KINDS,
    STORE_KINDS,
    FleetBootstrap,
    committed_kind_seconds,
    fetch_fleet_bootstrap,
    fit_model,
    kind_seconds,
    learned_action_seconds,
    learned_kind_seconds,
    learned_model,
    log_fights,
    log_kind,
    store_kind_seconds,
    timing_of,
)
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.untimed_action_kind_error import UntimedActionKindError


def _store(tmp_path: Path) -> LearningStore:
    store = LearningStore(db_path=str(tmp_path / "fit.db"), character="hero")
    store.start_session()
    return store


def _fight(store: LearningStore, index: int, turns: int, haste: int, seconds: float) -> None:
    store.record_cycle(Cycle(ts=f"2026-10-19T00:00:{index:02d}+00:00", cycle_index=index,
                             outcome="ok", actual_cooldown_seconds=seconds,
                             fight_turns=turns, fight_haste=haste))


def test_the_model_prices_a_fight_from_its_turns_and_haste() -> None:
    model = FightSecondsModel(Fraction(2), Fraction(1, 100), Fraction(5), True, 3)
    assert model.seconds(Fraction(5), 8) == Fraction(46, 5)
    assert model.seconds(Fraction(1), 8) == 5


def test_one_haste_leaves_its_effect_unidentified() -> None:
    assert not fit_model([(5, 8, 9.0), (7, 8, 13.0), (4, 0, 0.0)]).haste_identified
    model = fit_model([(5, 0, 10.0), (5, 10, 9.0)])
    assert (model.haste_identified, model.samples) == (True, 2)


def test_log_fights_keep_the_fights_at_the_sheet_haste() -> None:
    assert log_fights(8, [("fight", 9, 5), ("gathering", 25, None)]) == [(5, 8, 9.0)]


def _entry(character: str, kind: LogType, cooldown: int, turns: int | None = None) -> SimpleNamespace:
    content = {"fight": {"turns": turns}} if kind == LogType.FIGHT else {}
    return SimpleNamespace(character=character, type_=kind, cooldown=cooldown, content=content)


class _Api:
    """`/my/logs` (the account's, `pages` pages) and `/my/logs/{name}`."""

    def __init__(self, pages: list[list[SimpleNamespace]],
                 own: list[SimpleNamespace] | None = None) -> None:
        self.pages = pages
        self.own = own or []
        self.calls: list[tuple[int, int]] = []

    def get_all_characters_logs(self, page: int, size: int) -> SimpleNamespace:
        self.calls.append((page, size))
        return SimpleNamespace(data=self.pages[page - 1], pages=len(self.pages))

    def get_character_logs(self, name: str, page: int, size: int) -> SimpleNamespace:
        return SimpleNamespace(data=[e for e in self.own if e.character == name], pages=1)


def _fights(character: str, n: int) -> list[SimpleNamespace]:
    return [_entry(character, LogType.FIGHT, 10, 5) for _ in range(n)]


def test_a_character_without_fights_bootstraps_from_the_account_log() -> None:
    """Ruling ZD (live 2026-10-20: R2D2's and C3P0's newest 100 entries held
    no fight, and their `plan` raised "no fight with a positive cooldown").
    The bootstrap is the account's log, each fight at its character's sheet
    haste; a gathering character fits on its siblings' fights."""
    own = [_entry("R2D2", LogType.GATHERING, 25)]
    account = [_entry("R2D2", LogType.GATHERING, 25), _entry("Robby", LogType.FIGHT, 9, 5),
               _entry("Lor", LogType.FIGHT, 0, 4), _entry("Lor", LogType.FIGHT, 20, 10)]
    api = _Api([account], own)
    calls: list[str] = []
    bootstrap = fetch_fleet_bootstrap(api, {"R2D2": 0, "Robby": 8, "Lor": 2},  # type: ignore[arg-type]
                                      lambda: calls.append("acquire"))
    assert bootstrap == FleetBootstrap(fights=((5, 8, 9.0), (10, 2, 20.0)),
                                       cooldowns=(25, 9, 0, 20),
                                       kinds=(("gathering", 25, None, 1), ("fight", 9, None, 1),
                                              ("fight", 0, None, 1), ("fight", 20, None, 1)))
    assert calls == ["acquire"] and api.calls == [(1, BOOTSTRAP_PAGE)]
    model, seconds = timing_of(None, bootstrap)
    assert (model.samples, model.haste_identified, seconds) == (2, True, 18)


def test_paging_stops_once_the_fit_has_enough_fights_at_two_hastes() -> None:
    first = _fights("Robby", BOOTSTRAP_FIGHTS)
    second = _fights("Lor", 1)
    api = _Api([first, second, _fights("Lor", 3)])
    bootstrap = fetch_fleet_bootstrap(api, {"Robby": 8, "Lor": 2}, lambda: None)  # type: ignore[arg-type]
    assert api.calls == [(1, BOOTSTRAP_PAGE), (2, BOOTSTRAP_PAGE)]
    assert len(bootstrap.fights) == BOOTSTRAP_FIGHTS + 1


def test_one_haste_in_the_fleet_needs_no_spread() -> None:
    api = _Api([_fights("Robby", BOOTSTRAP_FIGHTS), _fights("Lor", 1)])
    bootstrap = fetch_fleet_bootstrap(api, {"Robby": 8, "Lor": 8}, lambda: None)  # type: ignore[arg-type]
    assert api.calls == [(1, BOOTSTRAP_PAGE)]
    assert not fit_model(bootstrap.fights).haste_identified


def test_a_log_that_runs_out_first_is_all_the_bootstrap() -> None:
    api = _Api([_fights("Robby", 2), [_entry("Lor", LogType.GATHERING, 25)]])
    bootstrap = fetch_fleet_bootstrap(api, {"Robby": 8, "Lor": 2}, lambda: None)  # type: ignore[arg-type]
    assert api.calls == [(1, BOOTSTRAP_PAGE), (2, BOOTSTRAP_PAGE)]
    assert len(bootstrap.fights) == 2
    empty = fetch_fleet_bootstrap(_Api([[_entry("Lor", LogType.GATHERING, 25)]]),  # type: ignore[arg-type]
                                  {"Lor": 2}, lambda: None)
    with pytest.raises(ValueError, match="no fight with a positive cooldown"):
        timing_of(None, empty)


def test_a_character_off_the_roster_is_no_observation() -> None:
    """Review M-2: the account log can keep a deleted or renamed character's
    entries. It has no sheet, so no haste to put its fights at; its entries
    are left out rather than raise a KeyError at every fleet start."""
    api = _Api([[_entry("Ghost", LogType.FIGHT, 30, 15), _entry("Ghost", LogType.GATHERING, 40),
                 _entry("Robby", LogType.FIGHT, 9, 5)]])
    bootstrap = fetch_fleet_bootstrap(api, {"Robby": 8}, lambda: None)  # type: ignore[arg-type]
    assert bootstrap == FleetBootstrap(fights=((5, 8, 9.0),), cooldowns=(9,),
                                       kinds=(("fight", 9, None, 1),))


def test_a_bootstrap_round_trips_through_json() -> None:
    bootstrap = FleetBootstrap(fights=((5, 8, 9.0),), cooldowns=(9, 25),
                               kinds=(("crafting", 10, "copper_bar", 2), ("rest", 3, None, 1)))
    assert FleetBootstrap.from_json(bootstrap.to_json()) == bootstrap


def test_the_learned_model_refits_only_when_its_observations_change(tmp_path: Path) -> None:
    store = _store(tmp_path)
    try:
        _fight(store, 0, 5, 0, 10.0)
        first = learned_model(store, [(10, 0, 20.0)])
        assert first.s_turn == 2
        assert learned_model(store, [(10, 0, 20.0)]) is first
        _fight(store, 1, 5, 0, 15.0)
        assert learned_model(store, [(10, 0, 20.0)]).s_turn == Fraction(10 * 5 + 15 * 5 + 200, 150)
        assert learned_model(store, []).s_turn == Fraction(5, 2)
    finally:
        store.close()


def test_the_cache_holds_its_store(tmp_path: Path) -> None:
    """A second store with the same counts is a different key: the cache pins
    the store object, never its id."""
    first, second = _store(tmp_path / "a"), _store(tmp_path / "b")
    try:
        _fight(first, 0, 5, 0, 10.0)
        _fight(second, 0, 5, 0, 15.0)
        assert learned_model(first, []).s_turn == 2
        assert learned_model(second, []).s_turn == 3
        assert mod._LEARNED[0][0] is second
    finally:
        first.close()
        second.close()


def test_no_fight_anywhere_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    try:
        with pytest.raises(ValueError, match="no fight with a positive cooldown"):
            learned_model(store, [])
    finally:
        store.close()


def test_the_action_seconds_are_learned_then_bootstrapped_or_raise(tmp_path: Path) -> None:
    """The store's mean once it has one; the bootstrap's (positive cooldowns
    only) until then; neither raises."""
    store = _store(tmp_path)
    try:
        with pytest.raises(ValueError, match="the bootstrap has: no action with a cooldown"):
            learned_action_seconds(store, [0])
        assert learned_action_seconds(store, [9, 0, 25]) == 17
        _fight(store, 0, 5, 0, 10.0)
        store.record_cycle(Cycle(ts="2026-10-19T00:01:00+00:00", cycle_index=1, outcome="ok",
                                 actual_cooldown_seconds=30.0))
        assert learned_action_seconds(store, [9, 25]) == 20
    finally:
        store.close()


def test_timing_without_a_store_fits_the_bootstrap_alone(tmp_path: Path) -> None:
    bootstrap = FleetBootstrap(fights=((5, 0, 10.0), (10, 0, 20.0)), cooldowns=(10, 20, 30), kinds=())
    model, seconds = timing_of(None, bootstrap)
    assert (model.s_turn, model.samples, seconds) == (Fraction(2), 2, Fraction(20))
    with pytest.raises(ValueError, match="the /my/logs bootstrap: no action with a cooldown"):
        timing_of(None, FleetBootstrap(fights=(), cooldowns=(0, 0), kinds=()))


def test_timing_with_a_store_pools_the_fleet_and_the_bootstrap(tmp_path: Path) -> None:
    store = _store(tmp_path)
    try:
        _fight(store, 0, 5, 0, 15.0)
        model, seconds = timing_of(store, FleetBootstrap(fights=((5, 0, 10.0),), cooldowns=(10,), kinds=()))
        assert (model.s_turn, model.samples, seconds) == (Fraction(5, 2), 2, Fraction(15))
    finally:
        store.close()


def _cold(store: LearningStore, bootstrap: list[tuple[int, int, float]]) -> FightSecondsModel:
    """The fit read and summed afresh from every recorded fight."""
    return fit_model([*store.fleet_fight_samples(0, store.last_cycle_id()), *bootstrap])


def test_the_held_fit_equals_a_cold_refit_after_every_recorded_fight(tmp_path: Path) -> None:
    """Plan B Task 14c (M-5): fights recorded one at a time, among cycles that
    are no fight and a fight of no cooldown, at three hastes; after each the
    held model equals a cold fit of the same history, and the read covers only
    the cycles recorded since the last one."""
    store = _store(tmp_path)
    reads: list[tuple[int, int]] = []
    read = store.fleet_fight_samples

    def spy(after_id: int, through_id: int) -> list[tuple[int, int, float]]:
        reads.append((after_id, through_id))
        return read(after_id, through_id)

    bootstrap = [(10, 0, 20.0), (8, 4, 15.0)]
    rows = [(5, 0, 10.0), None, (7, 4, 13.0), (6, 4, 0.0), (9, 12, 14.0), None, (3, 8, 5.5)]
    try:
        store.fleet_fight_samples = spy  # type: ignore[method-assign]
        for index, row in enumerate(rows):
            if row is None:
                store.record_cycle(Cycle(ts=f"2026-10-19T00:01:{index:02d}+00:00",
                                         cycle_index=index, outcome="ok",
                                         actual_cooldown_seconds=25.0))
            else:
                _fight(store, index, *row)
            before = len(reads)
            held = learned_model(store, bootstrap)
            assert reads[before:] == [(index, index + 1)]
            assert held == fit_model([*read(0, store.last_cycle_id()), *bootstrap])
            assert learned_model(store, bootstrap) is held
            assert len(reads) == before + 1
        assert held.samples == 4 + len(bootstrap)  # the 0 s fight is no observation
    finally:
        store.close()


def test_a_replaced_table_is_read_afresh(tmp_path: Path) -> None:
    """A newest id below the one last read is a table pruned under the store:
    the held sums are dropped, never folded into."""
    store = _store(tmp_path)
    try:
        _fight(store, 0, 5, 0, 10.0)
        _fight(store, 1, 5, 0, 20.0)
        assert learned_model(store, []).s_turn == 3
        with store._engine.begin() as conn:
            conn.exec_driver_sql("DELETE FROM cycles")
        _fight(store, 2, 5, 0, 25.0)
        assert store.last_cycle_id() == 1
        assert learned_model(store, []) == _cold(store, [])
        assert learned_model(store, []).s_turn == 5
    finally:
        store.close()


def test_the_action_mean_is_read_once_per_recorded_cycle(tmp_path: Path) -> None:
    """Plan B Task 14c (M-5): the fleet's mean action seconds are read again
    only when a cycle has been recorded since, and held against their store."""
    store, other = _store(tmp_path / "a"), _store(tmp_path / "b")
    reads: list[int] = []
    read = store.fleet_mean_action_seconds

    def spy() -> float | None:
        reads.append(1)
        return read()

    try:
        store.fleet_mean_action_seconds = spy  # type: ignore[method-assign]
        _fight(store, 0, 5, 0, 10.0)
        other.record_cycle(Cycle(ts="2026-10-19T00:00:00+00:00", cycle_index=0, outcome="ok",
                                 actual_cooldown_seconds=40.0))
        assert learned_action_seconds(store, ()) == 10
        assert learned_action_seconds(store, ()) == 10
        assert len(reads) == 1
        assert learned_action_seconds(other, ()) == 40
        assert mod._MEAN[0][0] is other
        store.record_cycle(Cycle(ts="2026-10-19T00:01:00+00:00", cycle_index=1, outcome="ok",
                                 actual_cooldown_seconds=30.0))
        assert learned_action_seconds(store, ()) == 20
        assert len(reads) == 2
    finally:
        store.close()
        other.close()


def test_each_log_kind_is_timed_by_its_mean_positive_cooldown() -> None:
    """`kind_seconds` (ruling "seconds inside", 2026-10-31): the measured
    seconds of one action of each log kind, its entries' positive cooldowns
    over the actions they ran; a kind never timed (only zero cooldowns) is
    absent."""
    assert kind_seconds([("gathering", 30, None, 1), ("gathering", 40, None, 1),
                         ("fight", 0, None, 1), ("crafting", 13, "copper_bar", 1)],
                        lambda _item: 1) == (
        ("crafting", Fraction(13)), ("gathering", Fraction(35)))
    assert dict(committed_kind_seconds())["gathering"] > dict(committed_kind_seconds())["crafting"]


def test_a_logged_craft_or_recycle_is_timed_per_action() -> None:
    """Review I3, settled on the account's 5,000 newest `/my/logs` entries
    (2026-10-31): a craft request's cooldown is 5 s per craft run, its log
    quantity the units made (hardwood plank x6: 30 s; cheese, 2 a run, logs
    2 made at 5 s); a recycle's is 3 s a unit; a withdraw is one action
    whatever it carries. A batched entry is its cooldown over the runs."""
    entries = [("crafting", 30, "hardwood_plank", 6), ("crafting", 5, "cheese", 2),
               ("recycling", 6, "skeleton_helmet", 2), ("withdraw_item", 3, None, 1)]
    yields = {"hardwood_plank": 1, "cheese": 2}
    assert kind_seconds(entries, yields.__getitem__) == (
        ("crafting", Fraction(5)), ("recycling", Fraction(3)), ("withdraw_item", Fraction(3)))
    entry = SimpleNamespace(character="Lor", type_=LogType.CRAFTING, cooldown=10,
                            content={"item": "cheese", "quantity": 4})
    assert log_kind(entry) == ("crafting", 10, "cheese", 4)  # type: ignore[arg-type]
    assert log_kind(_entry("Lor", LogType.GATHERING, 25)) == ("gathering", 25, None, 1)  # type: ignore[arg-type]


def _priced(store: LearningStore, index: int, action_class: str, action_repr: str,
            seconds: float, outcome: str = "ok") -> None:
    store.record_cycle(Cycle(ts=f"2026-10-19T00:01:{index:02d}+00:00", cycle_index=index,
                             outcome=outcome, actual_cooldown_seconds=seconds,
                             action_class=action_class, action_repr=action_repr))


def test_the_store_times_each_priced_kind_per_action_run(tmp_path: Path) -> None:
    """The user's I2 ruling (2026-10-31, "learning DB, then raise") and review
    I3: a priced kind is timed by the learning store's recorded server
    cooldowns of its action class, each over the runs its repr records (a
    craft's runs, a recycle's units); a failed cycle, a zero cooldown and an
    unpriced class are not observations. A kind it never recorded raises
    where it is priced, by name."""
    store = _store(tmp_path)
    try:
        _priced(store, 1, "CraftAction", "Craft(cheese×3)", 15.0)
        _priced(store, 2, "CraftAction", "Craft(copper_bar×1)", 5.0)
        _priced(store, 3, "CraftAction", "Craft(copper_bar×1)", 99.0, "error:cooldown")
        _priced(store, 4, "RecycleAction", "Recycle(iron_dagger×2)", 6.0)
        _priced(store, 5, "GatherAction", "Gather(ash_tree)", 30.0)
        _priced(store, 6, "GatherAction", "Gather(ash_tree)", 0.0)
        _priced(store, 7, "RestAction", "Rest", 12.0)
        rows = store.fleet_action_cooldowns(frozenset(STORE_KINDS), 0, store.last_cycle_id())
        assert sorted(rows) == [("CraftAction", "Craft(cheese×3)", 15.0, 1),
                                ("CraftAction", "Craft(copper_bar×1)", 5.0, 1),
                                ("GatherAction", "Gather(ash_tree)", 30.0, 1),
                                ("RecycleAction", "Recycle(iron_dagger×2)", 6.0, 1)]
        timed = store_kind_seconds(rows)
        assert timed == (("crafting", Fraction(5)), ("gathering", Fraction(30)),
                         ("recycling", Fraction(3)))
        ctx = replace(NO_PROFILE_CONTEXT, kind_seconds=timed)
        assert ctx.seconds_of(LogType.CRAFTING) == 5
        with pytest.raises(UntimedActionKindError) as untimed:
            ctx.seconds_of(LogType.WITHDRAW_GOLD)
        assert untimed.value.kind == "withdraw_gold"
        # a context carrying no kind seconds at all refuses every kind
        assert NO_PROFILE_CONTEXT.kind_seconds is None
        with pytest.raises(ValueError, match="no learned action-kind seconds"):
            NO_PROFILE_CONTEXT.seconds_of(LogType.CRAFTING)
    finally:
        store.close()
    with pytest.raises(ValueError, match="no quantity"):
        store_kind_seconds([("CraftAction", "Craft(cheese)", 5.0, 1)])


def test_a_fresh_install_times_its_kinds_from_the_account_log(tmp_path: Path) -> None:
    """The user's I2 ruling: `/my/logs` stays the bootstrap for a store that
    has recorded no priced action, or no store at all."""
    bootstrap = FleetBootstrap((), (), (("withdraw_gold", 3, None, 1),
                                        ("crafting", 10, "cheese", 4)))
    expected = (("crafting", Fraction(5)), ("withdraw_gold", Fraction(3)))
    assert learned_kind_seconds(None, bootstrap, {"cheese": 2}.__getitem__) == expected
    store = _store(tmp_path)
    try:
        assert learned_kind_seconds(store, bootstrap, {"cheese": 2}.__getitem__) == expected
    finally:
        store.close()


def test_every_priced_kind_is_a_recorded_action_class_and_the_capture_times_it() -> None:
    """The user's I2 ruling: each priced kind maps to the executed action class
    the store records it under, and the committed store capture
    (`STORE_COOLDOWNS`) times every one, so no offline world prices an
    untimed kind."""
    classes = {GatherAction, CraftAction, RecycleAction, WithdrawItemAction, WithdrawGoldAction,
               NpcSellAction, NpcBuyAction, GeFillSellOrderAction}
    assert set(STORE_KINDS) == {cls.__name__ for cls in classes}
    assert set(STORE_KINDS.values()) == PRICED_KINDS
    assert {kind.value for kind in PRICED_KINDS} == set(dict(committed_kind_seconds()))


def test_each_kind_is_the_store_s_and_otherwise_the_account_log_s(tmp_path: Path) -> None:
    """The user's ruling (fix round 3, re-review N1): the per-kind seconds
    merge per kind, real data only. A fresh install whose store has recorded
    one gather still prices its craft from the `/my/logs` bootstrap, which a
    whole-store cutover dropped (the craft then raised forever, and was never
    recorded). A kind the store has timed is the store's; a kind neither
    timed is absent and raises where it is priced."""
    store = _store(tmp_path)
    try:
        _priced(store, 1, "GatherAction", "Gather(ash_tree)", 30.0)
        bootstrap = FleetBootstrap((), (), (("crafting", 10, "cheese", 4),
                                            ("gathering", 50, None, 1)))
        merged = learned_kind_seconds(store, bootstrap, {"cheese": 2}.__getitem__)
        assert merged == (("crafting", Fraction(5)), ("gathering", Fraction(30)))
        with pytest.raises(UntimedActionKindError):
            replace(NO_PROFILE_CONTEXT, kind_seconds=merged).seconds_of(LogType.SELL_NPC)
    finally:
        store.close()


def test_the_store_sums_are_read_incrementally(tmp_path: Path) -> None:
    """Re-review: the cycles table is append-only, so the held per-kind sums
    take only the rows past the last id read, and equal a full scan after
    every append; a store whose newest id dropped (replaced) reads afresh."""
    store = _store(tmp_path)
    classes = frozenset(STORE_KINDS)
    try:
        _priced(store, 1, "CraftAction", "Craft(cheese×3)", 15.0)
        _priced(store, 2, "GatherAction", "Gather(ash_tree)", 30.0)
        boot = FleetBootstrap((), (), ())

        def full() -> tuple[tuple[str, Fraction], ...]:
            return store_kind_seconds(store.fleet_action_cooldowns(classes, 0,
                                                                   store.last_cycle_id()))

        assert learned_kind_seconds(store, boot, lambda _item: 1) == full()
        # nothing appended since the last read: the held sums, no query at all
        reads: list[tuple[int, int]] = []
        query = store.fleet_action_cooldowns

        def counted(kinds, after, through):  # type: ignore[no-untyped-def]
            reads.append((after, through))
            return query(kinds, after, through)

        store.fleet_action_cooldowns = counted  # type: ignore[method-assign]
        assert learned_kind_seconds(store, boot, lambda _item: 1) == full()
        assert reads == [(0, store.last_cycle_id())]  # `full()`'s own scan, none of the sums'
        _priced(store, 3, "CraftAction", "Craft(cheese×1)", 7.0)
        _priced(store, 4, "GatherAction", "Gather(ash_tree)", 34.0)
        assert learned_kind_seconds(store, boot, lambda _item: 1) == full() == (
            ("crafting", Fraction(22, 4)), ("gathering", Fraction(32)))
        mod._KIND_SUMS[:] = [(store, store.last_cycle_id() + 5, {})]
        assert learned_kind_seconds(store, boot, lambda _item: 1) == full()
    finally:
        store.close()


def test_a_recorded_craft_or_recycle_repr_parses_to_its_runs() -> None:
    """Re-review I3: the store's only quantity is the action's repr, so the
    parse is tied to `CraftAction.__repr__` and `RecycleAction.__repr__`."""
    craft = CraftAction(code="cheese", workshop_location=(1, 1), quantity=3)
    recycle = RecycleAction(code="iron_dagger", workshop_location=(1, 1), quantity=2)
    assert mod._store_runs(LogType.CRAFTING, repr(craft)) == 3
    assert mod._store_runs(LogType.RECYCLING, repr(recycle)) == 2
    assert mod._store_runs(LogType.GATHERING, repr(craft)) == 1
