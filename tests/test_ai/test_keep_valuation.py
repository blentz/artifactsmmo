"""keep_valuation: the ONE quantity-typed "worth keeping" valuation.

Three layers are covered here:

1. the pure cores (`bank_surplus_pure` / `drain_licensed_pure` /
   `bank_under_cap_pure`) — differentially pinned against Lean in
   formal/diff/test_keep_valuation_diff.py, so the unit tests here cover the
   branches and the boundary;
2. `worth_keeping` and its requirement-graph reachability term;
3. THE INVARIANT, at the adapter level over the live bank: no code is ever both
   drained by `ai/bank_drain` and routed to DEPOSIT by `ai/disposal_route`.

The live-bank fixture reproduces R2D2's eight bank piles and the catalog facts
behind them, probed read-only on 2026-08-05 (character level 11; alchemy 3,
cooking 1, gearcrafting 7, jewelrycrafting 2, mining 11, weaponcrafting 5,
woodcutting 11). It is the case this epic exists for: the old boolean
`_future_value` was True for every one of these, so `disposal_route` deposited
what `bank_drain` was licensing for withdrawal.
"""

import pytest

from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.deposit_item import DepositItemAction
from artifactsmmo_cli.ai.bank_drain import bank_drain_excess
from artifactsmmo_cli.ai.disposal_route import overstock_disposal
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.keep_valuation import (
    MAX_ATTAINABLE_SKILL_LEVEL,
    bank_quantity,
    bank_surplus_pure,
    bank_under_cap_pure,
    consumer_reachable,
    drain_licensed_pure,
    reachable_consumer_demand,
    worth_keeping,
)
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from tests.test_ai.fixtures import make_state

BANK_LOC = (4, 1)

# --------------------------------------------------------------------------- #
# The pure cores.
# --------------------------------------------------------------------------- #


def test_bank_surplus_is_bank_stock_minus_the_keep_quantity():
    assert bank_surplus_pure(1, 704) == 703
    assert bank_surplus_pure(400, 130) == -270


def test_exactly_at_cap_is_neither_surplus_nor_room():
    """The boundary that carries the invariant: at cap the drain licenses
    nothing AND the deposit gate is shut. A `<= 0` gate would hoard forever;
    a `>= 0` drain bound would withdraw a copy it is keeping."""
    assert bank_surplus_pure(7, 7) == 0
    assert drain_licensed_pure(99, 7, 7) == 0
    assert bank_under_cap_pure(7, 7) is False


def test_drain_is_bounded_by_the_ownership_licence():
    """18 banked axes, keep 0 — all surplus, but `destroyable` says 17 may leave."""
    assert drain_licensed_pure(17, 0, 18) == 17
    # …and by the surplus when THAT is the smaller of the two.
    assert drain_licensed_pure(999, 1, 704) == 703


def test_bank_under_cap_is_the_strict_room_test():
    assert bank_under_cap_pure(400, 130) is True
    assert bank_under_cap_pure(1, 704) is False


def test_bank_quantity_reads_an_unvisited_bank_as_empty():
    """`bank_items is None` means "never visited this session" — an unknown bank
    is not a full one, and it must not read as banked stock."""
    assert bank_quantity("sap", make_state(bank_items=None)) == 0
    assert bank_quantity("sap", make_state(bank_items={"sap": 9})) == 9
    assert bank_quantity("sap", make_state(bank_items={"other": 9})) == 0


# --------------------------------------------------------------------------- #
# Reachable-consumer demand: the requirement-graph term.
# --------------------------------------------------------------------------- #


def _reach_gd(*, consumer_level: int) -> GameData:
    gd = GameData()
    gd._item_stats = {
        "ore": ItemStats(code="ore", level=20, type_="resource"),
        "bar": ItemStats(code="bar", level=20, type_="resource",
                         crafting_skill="mining", crafting_level=consumer_level),
        # A second recipe that does NOT consume `ore`, so the consumer scan has
        # a non-consumer to skip.
        "plank": ItemStats(code="plank", level=1, type_="resource",
                           crafting_skill="woodcutting", crafting_level=1),
    }
    gd._crafting_recipes = {"bar": {"ore": 8}, "plank": {"wood": 2}}
    return gd


def test_demand_survives_when_a_consumer_is_reachable():
    gd = _reach_gd(consumer_level=MAX_ATTAINABLE_SKILL_LEVEL)
    assert reachable_consumer_demand("ore", gd) == 8


def test_demand_is_zero_when_every_consumer_is_off_the_progression_ladder():
    """A recipe gated ABOVE the API's documented progression cap can never be
    crafted by any character, so the material it consumes has no reachable
    consumer at all. This is the question `level_distance_keep_ceiling` could
    not ask: it only knew how far the ITEM's level sat from the character's."""
    gd = _reach_gd(consumer_level=MAX_ATTAINABLE_SKILL_LEVEL + 1)
    assert reachable_consumer_demand("ore", gd) == 0


def test_demand_is_zero_when_no_recipe_consumes_the_item_at_all():
    gd = _reach_gd(consumer_level=1)
    assert reachable_consumer_demand("bar", gd) == 0


def test_an_ungated_recipe_is_always_a_reachable_consumer():
    """A recipe with no crafting-skill gate has nothing to be walled behind."""
    gd = GameData()
    gd._item_stats = {"ore": ItemStats(code="ore", level=1, type_="resource")}
    gd._crafting_recipes = {"trinket": {"ore": 3}}
    graph = gd.requirement_graph.graph()
    assert consumer_reachable("trinket", graph) is True
    assert reachable_consumer_demand("ore", gd) == 3


# --------------------------------------------------------------------------- #
# worth_keeping: the max of the near-term cap and the eventual demand.
# --------------------------------------------------------------------------- #


def test_worth_keeping_takes_the_eventual_demand_when_it_is_larger():
    """The far-skill-gated case the bank exists for: the NEAR-term cap is 0
    precisely because the recipe is gated, so only the eventual demand keeps a
    banked gemstone out of the withdraw->discard pipeline."""
    gd = _reach_gd(consumer_level=MAX_ATTAINABLE_SKILL_LEVEL)
    state = make_state(level=5, skills={"mining": 5}, bank_items={"ore": 50})
    assert worth_keeping("ore", state, gd, NO_PROFILE_CONTEXT) == 8


def test_worth_keeping_takes_the_near_term_cap_when_it_is_larger():
    """An in-band material whose recipe the character can craft NOW: the
    near-term cap (demand x batch buffer) exceeds the bare eventual demand."""
    gd = _reach_gd(consumer_level=5)
    state = make_state(level=20, skills={"mining": 20}, bank_items={"ore": 50})
    assert worth_keeping("ore", state, gd, NO_PROFILE_CONTEXT) == 40


# --------------------------------------------------------------------------- #
# The live bank: eight piles, one valuation, one verdict each.
# --------------------------------------------------------------------------- #

LIVE_BANK = {
    "sap": 704,
    "raw_wolf_meat": 510,
    "raw_chicken": 277,
    "raw_beef": 162,
    "gudgeon": 148,
    "iron_ore": 130,
    "wolf_hair": 129,
    "raw_porkchop": 104,
}

LIVE_SKILLS = {"alchemy": 3, "cooking": 1, "fishing": 1, "gearcrafting": 7,
               "jewelrycrafting": 2, "mining": 11, "weaponcrafting": 5,
               "woodcutting": 11}


def _live_gd() -> GameData:
    """R2D2's catalog neighbourhood, probed live 2026-08-05: for each pile, the
    recipes that consume it and the crafting level each is gated behind."""
    gd = GameData()
    gd._item_stats = {
        "sap": ItemStats(code="sap", level=30, type_="resource"),
        "raw_wolf_meat": ItemStats(code="raw_wolf_meat", level=15, type_="resource"),
        "raw_chicken": ItemStats(code="raw_chicken", level=1, type_="resource"),
        "raw_beef": ItemStats(code="raw_beef", level=5, type_="resource"),
        "gudgeon": ItemStats(code="gudgeon", level=1, type_="resource"),
        "iron_ore": ItemStats(code="iron_ore", level=10, type_="resource"),
        "wolf_hair": ItemStats(code="wolf_hair", level=15, type_="resource"),
        "raw_porkchop": ItemStats(code="raw_porkchop", level=19, type_="resource"),
        # consumers
        "small_antidote": ItemStats(code="small_antidote", level=20, type_="consumable",
                                    crafting_skill="alchemy", crafting_level=20),
        "cooked_wolf_meat": ItemStats(code="cooked_wolf_meat", level=15, type_="consumable",
                                      crafting_skill="cooking", crafting_level=15),
        "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_="consumable",
                                    crafting_skill="cooking", crafting_level=1),
        "cooked_beef": ItemStats(code="cooked_beef", level=5, type_="consumable",
                                 crafting_skill="cooking", crafting_level=5),
        "cooked_gudgeon": ItemStats(code="cooked_gudgeon", level=1, type_="consumable",
                                    crafting_skill="cooking", crafting_level=1),
        "cooked_porkchop": ItemStats(code="cooked_porkchop", level=19, type_="consumable",
                                     crafting_skill="cooking", crafting_level=20),
        "iron_bar": ItemStats(code="iron_bar", level=10, type_="resource",
                              crafting_skill="mining", crafting_level=10),
        "iron_pickaxe": ItemStats(code="iron_pickaxe", level=10, type_="weapon",
                                  crafting_skill="weaponcrafting", crafting_level=10),
        "adventurer_boots": ItemStats(code="adventurer_boots", level=15, type_="boots",
                                      crafting_skill="gearcrafting", crafting_level=15),
    }
    gd._crafting_recipes = {
        "small_antidote": {"sap": 1},
        "cooked_wolf_meat": {"raw_wolf_meat": 1},
        "cooked_chicken": {"raw_chicken": 1},
        "cooked_beef": {"raw_beef": 1},
        "cooked_gudgeon": {"gudgeon": 1},
        "cooked_porkchop": {"raw_porkchop": 1},
        "iron_bar": {"iron_ore": 10},
        "iron_pickaxe": {"iron_bar": 8},
        "adventurer_boots": {"wolf_hair": 5},
    }
    gd._bank_location = BANK_LOC
    gd._bank_capacity = 200
    return gd


def _live_state() -> object:
    return make_state(level=11, skills=LIVE_SKILLS, inventory_max=120,
                      bank_items=dict(LIVE_BANK))


# (code, worth_keeping, drained, deposits?)
LIVE_VERDICTS = [
    # NOTHING near-term consumes sap (alchemy 3 vs recipes at 20/30/40), but a
    # reachable recipe consumes exactly ONE -> keep 1, shed the other 703.
    ("sap", 1, 703, False),
    ("raw_wolf_meat", 1, 509, False),
    # cooking 1 CAN cook a chicken today: the near-term cap (1 x batch buffer 5,
    # floored at the safety floor 3) is 5 -> keep 5.
    ("raw_chicken", 5, 272, False),
    ("raw_beef", 1, 161, False),
    ("gudgeon", 5, 143, False),
    # THE NO-OVER-SHEDDING CASE: mining 11 reaches iron_bar@10, whose chain wants
    # 80 iron_ore, so the near-term cap is 80 x 5 = 400. 130 banked is UNDER the
    # cap -> nothing drains and the route still DEPOSITS.
    ("iron_ore", 400, 0, True),
    ("wolf_hair", 5, 124, False),
    ("raw_porkchop", 1, 103, False),
]


@pytest.mark.parametrize(("code", "keep", "drained", "deposits"), LIVE_VERDICTS)
def test_live_bank_pile_valuation_and_route(code, keep, drained, deposits):
    gd = _live_gd()
    state = _live_state()
    assert worth_keeping(code, state, gd, NO_PROFILE_CONTEXT) == keep
    assert bank_drain_excess(state, gd, NO_PROFILE_CONTEXT).get(code, 0) == drained
    action = overstock_disposal(code, 5, state, gd, bank_accessible=True,
                                ctx=NO_PROFILE_CONTEXT)
    expected = DepositItemAction if deposits else DeleteItemAction
    assert isinstance(action, expected)


def test_the_anti_livelock_invariant_holds_over_the_live_bank():
    """`drained(code) > 0 ⇒ route(code) ≠ DEPOSIT` — the invariant that makes
    hoisting the drain safe (part 2). Before the unification EVERY one of these
    piles violated it: `bank_drain_excess` licensed the whole pile and
    `disposal_route` sent it straight back to the bank."""
    gd = _live_gd()
    state = _live_state()
    drained = bank_drain_excess(state, gd, NO_PROFILE_CONTEXT)
    assert drained, "the drain must actually fire, or the invariant is vacuous"
    for code, qty in drained.items():
        assert qty > 0
        action = overstock_disposal(code, qty, state, gd, bank_accessible=True,
                                    ctx=NO_PROFILE_CONTEXT)
        assert not isinstance(action, DepositItemAction), code


def test_the_drain_is_monotone_in_the_state_the_withdrawal_produces():
    """The other half of the invariant (`withdrawn_is_never_redeposited`): after
    the drain withdraws its licence, the SAME code routed from the post-withdraw
    state still refuses DEPOSIT. This is the cycle that actually ran: withdraw
    703 sap, discard-guard fires, route says DEPOSIT, repeat forever."""
    gd = _live_gd()
    state = _live_state()
    drained = bank_drain_excess(state, gd, NO_PROFILE_CONTEXT)
    for code, qty in drained.items():
        post_bank = dict(LIVE_BANK)
        post_bank[code] = post_bank[code] - qty
        post = make_state(level=11, skills=LIVE_SKILLS, inventory_max=120,
                          inventory={code: qty}, bank_items=post_bank)
        action = overstock_disposal(code, qty, post, gd, bank_accessible=True,
                                    ctx=NO_PROFILE_CONTEXT)
        assert not isinstance(action, DepositItemAction), code
