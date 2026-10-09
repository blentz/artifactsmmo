"""A fight's price carries its learned loss rate (`docs/PLAN_loss_risk.md`).

USER 2026-10-08, "Price the loss risk": a drop or grind fight's cost includes
its learned loss rate. Expected fights per win is `1/p`; each loss is charged
its death plus recovery. Proved core `Formal.LossRisk`."""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

import artifactsmmo_cli.ai.player as player_mod
import artifactsmmo_cli.ai.tiers.skill_grind_target as grind_mod
from artifactsmmo_cli.ai.acquisition_cost import _loss_surcharge, _priced, route_options
from artifactsmmo_cli.ai.combat import MIN_WIN_SAMPLES
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.fight_loop_cost import loss_cost
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.loss_risk_core import loss_surcharge
from artifactsmmo_cli.ai.obtain_sources import UNBOUNDED_CAPACITY, Source, SourceKind
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.skill_grind_target import _cache_key, build_selectable_grind_candidates
from tests.test_ai.fixtures import make_state

_BUNDLE = Path(__file__).resolve().parent / "scenarios" / "fixtures" / "gamedata_bundle.json"


@pytest.fixture(scope="module")
def game_data():  # type: ignore[no-untyped-def]
    return load_bundle_game_data(_BUNDLE)


@pytest.fixture(scope="module")
def state(game_data):  # type: ignore[no-untyped-def]
    return scenario_state(SCENARIOS["l12_deep_chain_grind"], game_data)


class TestCore:
    def test_the_expected_losses_per_win_times_a_loss(self) -> None:
        """R2D2 vs king_slime, 2026-10-08: 22 fights, 14 wins; 8/14 losses per win."""
        assert loss_surcharge(22, 14, 5, 130, 30) == Fraction(8, 14) * Fraction(130, 30)

    def test_no_evidence_and_no_loss_cost_nothing(self) -> None:
        assert loss_surcharge(4, 0, 5, 130, 30) == 0
        assert loss_surcharge(10, 10, 5, 130, 30) == 0

    def test_the_warmup_boundary_is_evidence(self) -> None:
        """Exactly `min_samples` fights is enough, the veto's own boundary."""
        assert loss_surcharge(5, 4, 5, 130, 30) == Fraction(1, 4) * Fraction(130, 30)

    def test_a_winless_record_charges_every_loss_against_one_win(self) -> None:
        """Behind the veto in production; total here."""
        assert loss_surcharge(6, 0, 5, 130, 30) == Fraction(6 * 130, 30)


def test_a_loss_is_the_fight_plus_a_full_bar_rest() -> None:
    """A loss leaves 1 hp: the Rest for `max_hp - 1` missing, 100 s, is 10/3
    fights; plus the lost Fight."""
    assert loss_cost(695) == Fraction(130, 30)


class TestTheDropPrice:
    def test_a_monster_lost_to_costs_more_per_unit(self, state, game_data) -> None:
        feather = Source(SourceKind.DROP, "chicken", 1, UNBOUNDED_CAPACITY)
        cold = _priced("feather", feather, state, game_data).actions_per_application
        lost = _priced("feather", feather, state, game_data, None,
                       (("chicken", 10, 5),)).actions_per_application
        assert lost > cold

    def test_another_monsters_record_or_no_evidence_changes_nothing(self, state, game_data) -> None:
        feather = Source(SourceKind.DROP, "chicken", 1, UNBOUNDED_CAPACITY)
        cold = _priced("feather", feather, state, game_data).actions_per_application
        assert _priced("feather", feather, state, game_data, None,
                       (("cow", 10, 5),)).actions_per_application == cold
        assert _priced("feather", feather, state, game_data, None,
                       (("chicken", MIN_WIN_SAMPLES - 1, 0),)).actions_per_application == cold

    def test_the_routes_read_the_records_off_the_context(self, state, game_data) -> None:
        def drop(ctx):  # type: ignore[no-untyped-def]
            return next(o.actions_per_application
                        for o in route_options("feather", state, game_data, ctx)
                        if o.kind == SourceKind.DROP.value and o.venue == "chicken")

        lost = replace(NO_PROFILE_CONTEXT, fight_records=(("chicken", 10, 5),))
        assert drop(lost) > drop(NO_PROFILE_CONTEXT)

    def test_the_surcharge_reads_the_named_monster(self) -> None:
        cost = loss_cost(695)
        assert _loss_surcharge("king_slime", 695, (("rat", 80, 45), ("king_slime", 16, 8))) \
            == float(Fraction(8, 8) * cost)
        assert _loss_surcharge("pig", 695, (("rat", 80, 45),)) == 0.0


class TestTheGrindRungs:
    def test_the_records_are_part_of_the_memo_key(self, state) -> None:
        assert _cache_key("cooking", state, ()) != _cache_key("cooking", state, (("rat", 9, 4),))

    def test_the_rung_prices_see_the_records(self, state, game_data, monkeypatch) -> None:
        seen = []

        def spy(code, qty, probe, gd, ctx, equip, policy):  # type: ignore[no-untyped-def]
            seen.append(ctx.fight_records)
            return 1

        monkeypatch.setattr(grind_mod, "acquisition_actions", spy)
        records = (("chicken", 9, 4),)
        ctx = replace(NO_PROFILE_CONTEXT, fight_records=records)
        build_selectable_grind_candidates("weaponcrafting", state, game_data, ctx)
        assert seen and set(seen) == {records}


class TestThePlayerContext:
    def _player(self, monkeypatch, history):  # type: ignore[no-untyped-def]
        player = GamePlayer(character="probe", history=history)
        player.state = make_state(task_code=None, task_total=0)
        player.game_data = GameData()
        monkeypatch.setattr(player, "_winnable_farm_target", lambda: None)
        player._draws_enabled = False
        return player

    def test_the_records_reach_the_selection_context(self, monkeypatch, tmp_path) -> None:
        records = (("rat", 80, 45),)
        monkeypatch.setattr(player_mod, "fight_records", lambda *a: records)
        store = LearningStore(db_path=str(tmp_path / "l.db"), character="probe")
        player = self._player(monkeypatch, store)
        monkeypatch.setattr(player_mod, "supply_shortfall", lambda *a: ())
        monkeypatch.setattr(player_mod, "xp_demand", lambda *a: (frozenset(), False))
        assert player._selection_context().fight_records == records
        store.close()

    def test_no_history_no_records(self, monkeypatch) -> None:
        player = self._player(monkeypatch, None)
        assert player._selection_context().fight_records == ()
