"""A dual-role item is one the character can WEAR and also SPEND."""
from dataclasses import replace
from fractions import Fraction

from artifactsmmo_cli.ai.currency_grind_target import currency_grind_target_pure
from artifactsmmo_cli.ai.currency_turnin import TurnIn
from artifactsmmo_cli.ai.dual_role_currency import dual_role_holdings, fleet_pooled, is_dual_role
from artifactsmmo_cli.ai.gear_objective_result import GearObjective, GearPiece
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.obtain_item_routing import _equippable_goal, _passively_funded
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.source_kind import SourceKind
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_dual_role_fixtures import medal_game_data


def test_medal_is_dual_role_because_it_is_worn_and_spent():
    gd = medal_game_data()
    assert is_dual_role("lich_race_medal", gd) is True


def test_ticket_is_not_dual_role_because_it_cannot_be_worn():
    gd = medal_game_data()
    assert is_dual_role("event_ticket", gd) is False


def test_plain_artifact_is_not_dual_role_because_nothing_takes_it_as_payment():
    gd = medal_game_data()
    assert is_dual_role("novice_guide", gd) is False


def test_holdings_count_worn_and_carried_together():
    gd = medal_game_data()
    state = make_state(inventory={"lich_race_medal": 2, "event_ticket": 30},
                       equipment={"artifact1_slot": "lich_race_medal",
                                  "artifact2_slot": "novice_guide"})
    assert dual_role_holdings(state, gd) == {"lich_race_medal": 3}


def test_the_fleet_pools_worn_copies_and_every_sibling_s():
    gd = medal_game_data()
    state = make_state(inventory={"lich_race_medal": 2},
                       equipment={"artifact1_slot": "lich_race_medal"})
    # the bag and bank are the caller's own count; the pool is what lies beyond
    assert fleet_pooled("lich_race_medal", state, gd, {"lich_race_medal": 4}) == 5
    assert fleet_pooled("lich_race_medal", state, gd, {}) == 1
    # a code no turn-in pools pools nothing, whatever the siblings carry
    assert fleet_pooled("event_ticket", state, gd, {"event_ticket": 300}) == 0


def _trophy_world():  # type: ignore[no-untyped-def]
    gd = medal_game_data()
    gd.world.npc_tiles = {"archaeologist": (6, 13)}
    return gd


def test_a_trophy_the_fleet_already_holds_is_left_to_the_turn_in():
    """Live 2026-10-13: four characters each gathered toward their OWN medal
    shortfall while the fleet held all 10. The step is the election's then."""
    gd = _trophy_world()
    state = make_state(level=30, bank_items={"lich_race_medal": 3})
    ctx = replace(NO_PROFILE_CONTEXT, sibling_holdings={"lich_race_medal": 7})
    assert _equippable_goal("lich_race_trophy", "artifact1_slot", state, gd, ctx) is None


def test_a_fleet_short_of_the_price_gathers_only_the_fleet_s_shortfall():
    gd = _trophy_world()
    state = make_state(level=30, bank_items={"lich_race_medal": 3})
    # the fleet holds 3 + 2 = 5: the next batch milestone is 10, five more
    ctx = replace(NO_PROFILE_CONTEXT, sibling_holdings={"lich_race_medal": 2})
    goal = _equippable_goal("lich_race_trophy", "artifact1_slot", state, gd, ctx)
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal.needed == {"lich_race_medal": 3 + 5}
    # alone, the character's own count decides, as before
    alone = _equippable_goal("lich_race_trophy", "artifact1_slot", state, gd, NO_PROFILE_CONTEXT)
    assert isinstance(alone, GatherMaterialsGoal)
    assert alone.needed == {"lich_race_medal": currency_grind_target_pure(3, 10)}


def test_a_trophy_a_sibling_was_elected_to_buy_is_not_bought_here():
    """Live 2026-10-13 02:15Z: R2D2 withdrew the 10 surrendered medals for its
    own trophy step and the elected buyer's withdraw came back HTTP 404."""
    gd = _trophy_world()
    state = make_state(character="R2D2", level=30, bank_items={"lich_race_medal": 10})
    claim = TurnIn("lich_race_trophy", "archaeologist", 10, "lich_race_medal", "Robby", 10)
    ctx = replace(NO_PROFILE_CONTEXT, turn_in=claim)
    assert _equippable_goal("lich_race_trophy", "artifact1_slot", state, gd, ctx) is None
    # the buyer itself, and a claim on another item, plan the buy as before
    mine = replace(ctx, turn_in=replace(claim, buyer="R2D2"))
    assert _equippable_goal("lich_race_trophy", "artifact1_slot", state, gd, mine) is not None
    other = replace(ctx, turn_in=replace(claim, item_code="emerald_book"))
    assert _equippable_goal("lich_race_trophy", "artifact1_slot", state, gd, other) is not None


def _passive_tickets(gd, monkeypatch):  # type: ignore[no-untyped-def]
    """event_ticket drops from 56 of 58 live monsters; the fixture catalogue is
    too small to say so, so the predicate is pinned."""
    monkeypatch.setattr(gd, "currency_accrues_passively", lambda code: code == "event_ticket")
    return gd


def test_a_medal_step_buys_only_what_the_held_tickets_pay_for(monkeypatch):
    """Live 2026-10-13: 472 ticket gathers for 4 tickets (1 in 200). Medals are
    bought with tickets already held, never farmed for."""
    gd = _passive_tickets(_trophy_world(), monkeypatch)
    state = make_state(level=30, bank_items={"lich_race_medal": 3, "event_ticket": 150})
    goal = _equippable_goal("lich_race_trophy", "artifact1_slot", state, gd, NO_PROFILE_CONTEXT)
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal.needed == {"lich_race_medal": 3 + 1}  # 150 tickets pay for 1
    # under one medal's price: nothing to do, the character levels instead
    poor = make_state(level=30, bank_items={"lich_race_medal": 3, "event_ticket": 99})
    assert _equippable_goal("lich_race_trophy", "artifact1_slot", poor, gd, NO_PROFILE_CONTEXT) is None
    # plenty: the batch milestone, as before
    rich = make_state(level=30, bank_items={"lich_race_medal": 3, "event_ticket": 900})
    goal = _equippable_goal("lich_race_trophy", "artifact1_slot", rich, gd, NO_PROFILE_CONTEXT)
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal.needed == {"lich_race_medal": currency_grind_target_pure(3, 10)}


def test_only_a_currency_bought_with_a_passive_one_is_capped(monkeypatch):
    gd = _passive_tickets(_trophy_world(), monkeypatch)
    state = make_state(inventory={"event_ticket": 30}, bank_items={"event_ticket": 220})
    assert _passively_funded("lich_race_medal", state, gd) == 2
    # a medal with any other source is not capped
    monkeypatch.setattr(gd, "gatherable_drop_items", lambda: frozenset({"lich_race_medal"}))
    assert _passively_funded("lich_race_medal", state, gd) is None
    # nor one bought with a currency that is not passive
    plain = _trophy_world()
    assert _passively_funded("lich_race_medal", state, plain) is None


def test_a_medal_worn_for_itself_is_bought_only_with_tickets_held(monkeypatch):
    """Live 2026-10-13 (after 9559cc91): HAL and Lor rooted on the MEDAL as an
    artifact and ran 163 `Gather(...->event_ticket)` for it. The passive rule
    filtered the ticket price out, so the step fell through to a plain
    GatherMaterials(medal) whose currency injection farmed the tickets."""
    gd = _passive_tickets(_trophy_world(), monkeypatch)
    poor = make_state(level=30, inventory={"event_ticket": 20}, bank_items={"event_ticket": 79})
    assert _equippable_goal("lich_race_medal", "artifact2_slot", poor, gd, NO_PROFILE_CONTEXT) is None
    paid = make_state(level=30, inventory={"event_ticket": 20}, bank_items={"event_ticket": 80})
    goal = _equippable_goal("lich_race_medal", "artifact2_slot", paid, gd, NO_PROFILE_CONTEXT)
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal.needed == {"lich_race_medal": 1}


def _piece_ctx(code: str, slot: str):  # type: ignore[no-untyped-def]
    """A context whose gear objective names `code` as a missing `L*` piece."""
    piece = GearPiece(slot, code, 0, Fraction(1), Fraction(10), SourceKind.BUY)
    return replace(NO_PROFILE_CONTEXT,
                   gear_objective=GearObjective("wolf", {slot: code}, Fraction(1), (piece,)))


def test_an_l_star_trophy_farms_the_tickets_its_medals_cost(monkeypatch):
    """Ruling T14a-B (spec 2026-10-18 §2.1, §6.1, §6.2): an `L*` piece paid
    for in a currency bought with a passive one is pursued by farming that
    currency, never left to levelling. Live HAL/C3P0/Robby 2026-10-25:
    `lich_race_trophy` declined `no_step_goal` 100-200 cycles a day each. The
    cost is answered by its price ordering it (ruling T14a-B'), not refused."""
    gd = _passive_tickets(_trophy_world(), monkeypatch)
    poor = make_state(level=30, bank_items={"lich_race_medal": 3, "event_ticket": 99})
    ctx = _piece_ctx("lich_race_trophy", "artifact1_slot")
    goal = _equippable_goal("lich_race_trophy", "artifact1_slot", poor, gd, ctx)
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal.needed == {"lich_race_medal": currency_grind_target_pure(3, 10)}
    # Not an `L*` piece: the passive rule stands (a medal step's tickets held).
    assert _equippable_goal("lich_race_trophy", "artifact1_slot", poor, gd,
                            NO_PROFILE_CONTEXT) is None


def test_an_l_star_medal_worn_for_itself_farms_its_tickets(monkeypatch):
    gd = _passive_tickets(_trophy_world(), monkeypatch)
    poor = make_state(level=30, inventory={"event_ticket": 20}, bank_items={"event_ticket": 79})
    ctx = _piece_ctx("lich_race_medal", "artifact2_slot")
    goal = _equippable_goal("lich_race_medal", "artifact2_slot", poor, gd, ctx)
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal.needed == {"lich_race_medal": 1}
    assert goal.fight_gold is True
    assert _equippable_goal("lich_race_medal", "artifact2_slot", poor, gd,
                            NO_PROFILE_CONTEXT) is None
