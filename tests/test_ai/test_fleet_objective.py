"""The fleet objective (Phase 5-2c-iv): fleet work the coordination tables name
for this character — a sibling's supply request this role serves, or a resolved
currency turn-in election — is a root alternative of its own
(`ReachFleetOutcome`), offered by `resolve_root` only while the context names
it, and served on its rotation turn. It was the SUPPLY_BANK and CURRENCY_TURNIN
collect rungs, above every root; these tests carry their properties onto the
new seam: the due predicates (`ai/fleet_work`), the offer (`_fleet_roots`), and
the step (`objective_step_goal` → `_fleet_step_goal`)."""

import dataclasses
from unittest.mock import patch

from artifactsmmo_cli.ai.currency_turnin import TurnIn
from artifactsmmo_cli.ai.decisions import root as root_mod
from artifactsmmo_cli.ai.decisions import route as route_mod
from artifactsmmo_cli.ai.decisions.route import route_price
from artifactsmmo_cli.ai.fleet_work import (
    FLEET_SUPPLY,
    FLEET_TURN_IN,
    SUPPLY_DEMAND_MIN,
    fleet_work_code,
    supply_due,
    turn_in_due,
)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.currency_turnin import CurrencyTurnInGoal
from artifactsmmo_cli.ai.goals.supply_bank import SupplyBankGoal
from artifactsmmo_cli.ai.goals.surrender_currency import SurrenderCurrencyGoal
from artifactsmmo_cli.ai.plan_tree import _label
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.strategy_driver import objective_step_goal
from artifactsmmo_cli.ai.tiers.meta_goal import (
    ObtainItem,
    ReachCharLevel,
    ReachFleetOutcome,
    ReachTaskOutcome,
)
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.prerequisite_graph import prerequisites
from artifactsmmo_cli.ai.tiers.strategy import root_category
from tests.test_ai import test_grey_farm
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_dual_role_fixtures import medal_game_data

TROPHY = TurnIn(item_code="lich_race_trophy", npc_code="archaeologist",
                price=10, currency="lich_race_medal",
                buyer="Robby", fleet_total=10)

SUPPLY = ReachFleetOutcome(FLEET_SUPPLY, "copper_ore")
TURN_IN = ReachFleetOutcome(FLEET_TURN_IN, "lich_race_trophy")


def _ctx(**kw) -> SelectionContext:  # type: ignore[no-untyped-def]
    return dataclasses.replace(NO_PROFILE_CONTEXT, **kw)


def _bulk() -> SelectionContext:
    return _ctx(supply_target=("copper_ore", 40, SUPPLY_DEMAND_MIN))


# ---------------------------------------------------------------------------
# supply_due — the bulk bar and the asymmetry arm (was `_fires(SUPPLY_BANK)`)
# ---------------------------------------------------------------------------

class TestSupplyDue:
    def test_no_supply_target_is_never_due(self) -> None:
        """Every single-character run: no target, so no fleet work — even with
        an asymmetric code on the board."""
        ctx = _ctx(supply_target=None, asymmetric_demand=frozenset({"copper_ore"}))
        assert supply_due(ctx) is False

    def test_due_at_exactly_the_threshold(self) -> None:
        assert supply_due(_ctx(supply_target=("iron_ore", 10, SUPPLY_DEMAND_MIN))) is True

    def test_not_due_one_unit_below_the_threshold(self) -> None:
        """The gate is a THRESHOLD, not a presence test: one unit short and the
        character keeps working its own chain."""
        assert supply_due(_ctx(supply_target=("iron_ore", 10, SUPPLY_DEMAND_MIN - 1))) is False

    def test_due_well_above_the_threshold(self) -> None:
        assert supply_due(_ctx(supply_target=("iron_ore", 80, 80))) is True

    def test_reads_unmet_demand_not_the_banked_target(self) -> None:
        """The third component (still-unmet demand), not the second (the
        absolute banked target, which counts stock the fleet already owns)."""
        assert supply_due(_ctx(supply_target=("iron_ore", 200, SUPPLY_DEMAND_MIN - 1))) is False

    def test_a_single_unit_request_the_asker_cannot_make_is_due(self) -> None:
        """The live case: every published row is quantity 1."""
        ctx = _ctx(supply_target=("greater_wooden_staff", 1, 1),
                   asymmetric_demand=frozenset({"greater_wooden_staff"}))
        assert supply_due(ctx) is True

    def test_a_small_request_the_asker_can_make_itself_is_not_due(self) -> None:
        ctx = _ctx(supply_target=("copper_ore", 3, 3),
                   asymmetric_demand=frozenset({"greater_wooden_staff"}))
        assert supply_due(ctx) is False


# ---------------------------------------------------------------------------
# turn_in_due and fleet_work_code (was `_fires(CURRENCY_TURNIN)`)
# ---------------------------------------------------------------------------

class TestTurnInDue:
    def test_due_for_the_elected_buyer(self) -> None:
        assert turn_in_due(_ctx(turn_in=TROPHY)) is True

    def test_due_for_a_holder_asked_to_surrender(self) -> None:
        assert turn_in_due(_ctx(recall=("lich_race_medal", 2))) is True

    def test_not_due_for_an_uninvolved_character(self) -> None:
        assert turn_in_due(_ctx()) is False


class TestFleetWorkCode:
    def test_supply_names_the_requested_material(self) -> None:
        assert fleet_work_code(FLEET_SUPPLY, _bulk()) == "copper_ore"

    def test_turn_in_names_the_turn_in_item(self) -> None:
        ctx = _ctx(turn_in=TROPHY, recall=("lich_race_medal", 2))
        assert fleet_work_code(FLEET_TURN_IN, ctx) == "lich_race_trophy"

    def test_a_holder_with_no_turn_in_in_view_names_the_recalled_currency(self) -> None:
        assert fleet_work_code(FLEET_TURN_IN, _ctx(recall=("lich_race_medal", 2))) == "lich_race_medal"


# ---------------------------------------------------------------------------
# The offer: `_fleet_roots` and its place in `resolve_root`
# ---------------------------------------------------------------------------

class TestFleetRoots:
    def test_nothing_named_offers_nothing(self) -> None:
        assert root_mod._fleet_roots(_ctx()) == []

    def test_a_sub_threshold_request_is_not_offered(self) -> None:
        ctx = _ctx(supply_target=("copper_ore", 9, SUPPLY_DEMAND_MIN - 1))
        assert root_mod._fleet_roots(ctx) == []

    def test_each_kind_is_offered_alone(self) -> None:
        assert root_mod._fleet_roots(_bulk()) == [SUPPLY]
        assert root_mod._fleet_roots(_ctx(turn_in=TROPHY)) == [TURN_IN]
        assert root_mod._fleet_roots(_ctx(recall=("lich_race_medal", 2))) == [
            ReachFleetOutcome(FLEET_TURN_IN, "lich_race_medal")]

    def test_the_turn_in_is_offered_before_the_supply_run(self) -> None:
        ctx = dataclasses.replace(_bulk(), turn_in=TROPHY)
        assert root_mod._fleet_roots(ctx) == [TURN_IN, SUPPLY]

    def _offered(self, ctx: SelectionContext) -> list[object]:
        gd = test_grey_farm._gd()
        state = test_grey_farm.make_state(level=12)
        with patch.object(root_mod, "_task_root", return_value=ReachTaskOutcome("chicken")):
            resolution = root_mod.resolve_root(state, gd, CharacterObjective.from_game_data(gd),
                                               ctx, None)
        return [resolution.root, *resolution.alternatives]

    def test_the_walk_offers_it_after_the_task_objective(self) -> None:
        offered = self._offered(dataclasses.replace(_bulk(), turn_in=TROPHY))
        task = offered.index(ReachTaskOutcome("chicken"))
        assert offered[task + 1:task + 3] == [TURN_IN, SUPPLY]
        trunk = next(i for i, a in enumerate(offered) if isinstance(a, ReachCharLevel))
        assert trunk < task

    def test_the_walk_offers_it_only_while_the_work_is_due(self) -> None:
        offered = self._offered(_ctx(supply_target=("copper_ore", 9, SUPPLY_DEMAND_MIN - 1)))
        assert not any(isinstance(a, ReachFleetOutcome) for a in offered)


# ---------------------------------------------------------------------------
# The node's own arms: satisfaction, prerequisites, category, label, price
# ---------------------------------------------------------------------------

class TestTheNode:
    def test_it_is_never_satisfied_itself(self) -> None:
        assert SUPPLY.is_satisfied(make_state(), GameData()) is False

    def test_it_has_no_prerequisites_and_is_a_fleet_root(self) -> None:
        assert prerequisites(SUPPLY, make_state(), GameData()) == []
        assert root_category(TURN_IN) == "fleet"
        assert _label(SUPPLY) == ("fleet supply copper_ore", "fleet")

    def test_a_supply_run_costs_obtaining_the_unmet_demand(self) -> None:
        state, gd = make_state(), GameData()
        ctx = _ctx(supply_target=("copper_ore", 40, 12))
        real = route_mod.route_price

        def priced(goal, *args, **kw):  # type: ignore[no-untyped-def]
            return 42 if isinstance(goal, ObtainItem) else real(goal, *args, **kw)

        with patch.object(route_mod, "route_price", side_effect=priced) as inner:
            assert real(SUPPLY, state, gd, ctx, None) == 42
        assert inner.call_args.args[0] == ObtainItem("copper_ore", 12)

    def test_a_supply_run_the_context_no_longer_names_is_one_booking(self) -> None:
        state, gd = make_state(), GameData()
        assert route_price(SUPPLY, state, gd, _ctx(), None) == 1
        other = _ctx(supply_target=("iron_ore", 40, 12))
        assert route_price(SUPPLY, state, gd, other, None) == 1

    def test_a_turn_in_is_one_booking(self) -> None:
        ctx = _ctx(turn_in=TROPHY, supply_target=("lich_race_trophy", 40, 12))
        assert route_price(TURN_IN, make_state(), GameData(), ctx, None) == 1


# ---------------------------------------------------------------------------
# The step (`_fleet_step_goal`, was the rungs' `map_means` arms)
# ---------------------------------------------------------------------------

class TestSupplyStep:
    def test_the_step_banks_the_requested_material(self) -> None:
        goal = objective_step_goal(SUPPLY, make_state(), GameData(),
                                   _ctx(supply_target=("copper_ore", 40, 12)))
        assert isinstance(goal, SupplyBankGoal)
        assert repr(goal) == "SupplyBank(copper_orex40)"
        assert goal._demand == 12

    def test_no_step_once_the_request_is_no_longer_due(self) -> None:
        state, gd = make_state(), GameData()
        assert objective_step_goal(SUPPLY, state, gd, _ctx()) is None
        small = _ctx(supply_target=("copper_ore", 9, SUPPLY_DEMAND_MIN - 1))
        assert objective_step_goal(SUPPLY, state, gd, small) is None

    def test_no_step_when_the_context_names_another_material(self) -> None:
        ctx = _ctx(supply_target=("iron_ore", 40, 12))
        assert objective_step_goal(SUPPLY, make_state(), GameData(), ctx) is None

    def test_no_step_once_the_bank_holds_the_target(self) -> None:
        ctx = _ctx(supply_target=("copper_ore", 40, 12))
        state = make_state(bank_items={"copper_ore": 40})
        assert objective_step_goal(SUPPLY, state, GameData(), ctx) is None


class TestTurnInStep:
    def test_the_named_buyer_gets_the_buyer_goal(self) -> None:
        goal = objective_step_goal(TURN_IN, make_state(character="Robby", level=27),
                                   medal_game_data(), _ctx(turn_in=TROPHY))
        assert isinstance(goal, CurrencyTurnInGoal)

    def test_a_non_buyer_with_no_recall_has_no_step(self) -> None:
        """CRITICAL (fix-round-3): a SECOND buyer must be impossible.

        `_resolve_turn_in` sets `recall` only when the loser actually HOLDS
        units, so a level-20+ character that qualified, lost the claim, and
        holds ZERO units ends its cycle with `turn_in` set and `recall` None.
        Keying on "recall is None ⇒ I am the buyer" would hand it the buyer
        goal and a double-spend; identity is the only key. With nothing to
        surrender it has no fleet step at all (it was a zero-unit surrender,
        already satisfied, before Phase 5-2c-iv)."""
        goal = objective_step_goal(TURN_IN, make_state(character="HAL", level=27),
                                   medal_game_data(), _ctx(turn_in=TROPHY))
        assert goal is None

    def test_a_recalled_holder_surrenders_its_holding(self) -> None:
        state = make_state(character="C3P0", level=17, inventory={"lich_race_medal": 2})
        ctx = _ctx(turn_in=TROPHY, recall=("lich_race_medal", 2))
        goal = objective_step_goal(TURN_IN, state, medal_game_data(), ctx)
        assert isinstance(goal, SurrenderCurrencyGoal)
        assert repr(goal) == "SurrenderCurrency(lich_race_medalx2)"

    def test_a_holder_that_already_surrendered_has_no_step(self) -> None:
        ctx = _ctx(turn_in=TROPHY, recall=("lich_race_medal", 2))
        state = make_state(character="C3P0", level=17)
        assert objective_step_goal(TURN_IN, state, medal_game_data(), ctx) is None

    def test_no_step_once_the_election_no_longer_names_this_character(self) -> None:
        state = make_state(character="Robby", level=27)
        assert objective_step_goal(TURN_IN, state, medal_game_data(), _ctx()) is None
