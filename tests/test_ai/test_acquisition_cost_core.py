"""Route-aware acquisition cost — the pure AND/OR walk.

Every case here is stated against the SOUNDNESS CONTRACT in
`ai/acquisition_cost_core`: the result must be a LOWER bound on the length of
any plan that obtains the item, because every consumer prunes with it. Where a
modelling choice could go either way it is resolved DOWNWARD, and the tests say
which direction they are protecting.
"""

from artifactsmmo_cli.ai.acquisition_cost_core import (
    UNOBTAINABLE_PER_UNIT,
    RouteOption,
    acquisition_cost,
)

UNBOUNDED = 10**9


def gather(venue: str, yield_per: int = 1) -> RouteOption:
    return RouteOption(kind="gather", venue=venue, actions_per_application=1,
                       yield_per=yield_per, capacity=UNBOUNDED)


def withdraw(stock: int) -> RouteOption:
    return RouteOption(kind="withdraw", venue="bank", actions_per_application=1,
                       yield_per=1, capacity=stock)


def craft(venue: str, inputs: dict[str, int], yield_per: int = 1) -> RouteOption:
    return RouteOption(kind="craft", venue=venue, actions_per_application=1,
                       yield_per=yield_per, capacity=UNBOUNDED, inputs=inputs)


def buy(venue: str, currency: str, price: int) -> RouteOption:
    return RouteOption(kind="buy", venue=venue, actions_per_application=1,
                       yield_per=1, capacity=UNBOUNDED,
                       inputs={currency: price})


def test_an_item_with_no_route_is_unobtainable_not_free() -> None:
    """THE DEFECT THIS MODULE EXISTS TO FIX, in one assertion.

    `min_plan_length` charges 1 gather for anything absent from `recipes`, so a
    50,000-gold vendor item priced at 2. Here an item nothing can produce costs
    a bound large enough to prune the chain that contains it."""
    assert acquisition_cost("mystery", 1, {}, {}) == UNOBTAINABLE_PER_UNIT
    assert acquisition_cost("mystery", 3, {}, {}) == 3 * UNOBTAINABLE_PER_UNIT


def test_unobtainable_is_finite_so_two_bad_chains_still_compare() -> None:
    """Not infinity, deliberately. A caller ranking candidates must get a total
    order over unobtainable chains rather than a pile of ties, so the OTHER work
    in the chain still shows through."""
    options = {"gadget": [craft("workshop", {"mystery": 1, "ore": 1})],
               "ore": [gather("ore_node")]}
    cheap = acquisition_cost("mystery", 1, {}, {})
    with_extra = acquisition_cost("gadget", 1, options, {})
    assert with_extra > cheap
    assert with_extra < 2 * UNOBTAINABLE_PER_UNIT


def test_one_gather_route_costs_the_walk_plus_the_gathers() -> None:
    """1 hop to the node, then one gather per unit."""
    options = {"ore": [gather("ore_node")]}
    assert acquisition_cost("ore", 1, options, {}) == 2
    assert acquisition_cost("ore", 5, options, {}) == 6


def test_multi_yield_resources_need_fewer_gathers() -> None:
    """`ceil(units / yield_per)` — the tighter, still-sound bound
    `ceil_gathers` already applies. Five units off a 3-yield node is two
    gathers, not five."""
    options = {"ore": [gather("ore_node", yield_per=3)]}
    assert acquisition_cost("ore", 5, options, {}) == 1 + 2


def test_a_venue_is_walked_to_once_however_many_applications() -> None:
    """THE TRAVEL RULE. A plan that gathers twenty ore walks to the node once.
    Counting a hop per application would make travel scale with quantity, which
    is both wrong and an over-estimate — the direction the contract forbids."""
    options = {"ore": [gather("ore_node")]}
    assert acquisition_cost("ore", 20, options, {}) == 1 + 20


def test_two_distinct_venues_cost_two_hops() -> None:
    """...and the second venue is only paid because it is DIFFERENT. This is
    what makes `venue` a code rather than a boolean."""
    options = {
        "blade": [craft("smithy", {"ore": 1, "wood": 1})],
        "ore": [gather("ore_node")],
        "wood": [gather("forest")],
    }
    # smithy + ore_node + forest = 3 hops, 1 craft, 2 gathers.
    assert acquisition_cost("blade", 1, options, {}) == 3 + 1 + 2


def test_materials_sharing_a_venue_pay_one_hop_between_them() -> None:
    """Two materials from the same node is one walk. The visited set is threaded
    through the whole walk for exactly this."""
    options = {
        "blade": [craft("smithy", {"ore": 1, "clay": 1})],
        "ore": [gather("pit")],
        "clay": [gather("pit")],
    }
    # smithy + pit = 2 hops, 1 craft, 2 gathers.
    assert acquisition_cost("blade", 1, options, {}) == 2 + 1 + 2


def test_the_walk_picks_the_cheapest_route() -> None:
    """The OR arm. A bank withdraw beats a deep craft, and the walk takes it
    without being told which route kind to prefer — `kind` decides nothing
    here, so adding a route cannot silently reorder anything."""
    options = {
        "bar": [withdraw(stock=5), craft("smithy", {"ore": 10})],
        "ore": [gather("pit")],
    }
    assert acquisition_cost("bar", 1, options, {}) == 2   # hop + withdraw


def test_a_capacity_bounded_route_falls_back_for_the_remainder() -> None:
    """A half-full bank produces a MIXED plan: withdraw what is there, make the
    rest. Neither an over-optimistic 'withdraw it all' nor a pessimistic
    'ignore the bank'."""
    options = {
        "bar": [withdraw(stock=2), craft("smithy", {"ore": 3})],
        "ore": [gather("pit")],
    }
    # 4 bars: bank hop + 2 withdraws, then smithy hop + 2 crafts,
    # pit hop + 6 gathers.
    assert acquisition_cost("bar", 4, options, {}) == (1 + 2) + (1 + 2) + (1 + 6)


def test_held_copies_are_consumed_before_any_route() -> None:
    """Holdings are free, and they are SPENT — the next need cannot claim the
    same unit."""
    options = {"ore": [gather("pit")]}
    assert acquisition_cost("ore", 3, options, {"ore": 3}) == 0
    assert acquisition_cost("ore", 5, options, {"ore": 3}) == 1 + 2


def test_a_sibling_branch_cannot_reuse_a_consumed_unit() -> None:
    """The invariant that keeps this a bound on ONE coherent plan rather than on
    an optimistic superposition of plans. One held ore satisfies one input, and
    the other input must still be obtained."""
    options = {
        "blade": [craft("smithy", {"ore": 1, "clay": 1})],
        "ore": [gather("pit")],
        "clay": [gather("pit")],
    }
    both_held = acquisition_cost("blade", 1, options, {"ore": 1, "clay": 1})
    one_held = acquisition_cost("blade", 1, options, {"ore": 1})
    assert both_held == 1 + 1          # smithy hop + craft
    assert one_held == 1 + 1 + 1 + 1   # + pit hop + one gather


def test_a_purchase_pays_for_its_currency() -> None:
    """A buy is priced as the purchase PLUS obtaining what it is priced in —
    the term `min_plan_length` has no way to express, and the reason a
    50,000-gold backpack currently costs 2."""
    options = {
        "medal": [buy("vendor", "ticket", 100)],
        "ticket": [gather("ticket_node")],
    }
    # vendor hop + purchase + ticket_node hop + 100 gathers.
    assert acquisition_cost("medal", 1, options, {}) == 1 + 1 + 1 + 100


def test_a_purchase_is_cheap_when_the_currency_is_already_held() -> None:
    """Same route, currency in the bag: the chain collapses to the walk and the
    purchase. The cost tracks the WORK REMAINING, not a static price tag."""
    options = {
        "medal": [buy("vendor", "ticket", 100)],
        "ticket": [gather("ticket_node")],
    }
    assert acquisition_cost("medal", 1, options, {"ticket": 100}) == 2


def test_a_drop_farm_costs_its_expected_kills() -> None:
    """DROP carries whole-loop cycles per application, pre-rounded by the
    wrapper, so a 1-in-30 drop is priced as the farm it is rather than as one
    gather."""
    options = {"hair": [RouteOption(kind="drop", venue="wolf",
                                    actions_per_application=60, yield_per=1,
                                    capacity=UNBOUNDED)]}
    assert acquisition_cost("hair", 1, options, {}) == 1 + 60


def test_a_cyclic_route_graph_terminates_conservatively() -> None:
    """An item bought with a currency bought with that item. Fuel runs out and
    the remaining need is charged as unobtainable — large, which prunes, which
    is the safe direction for a cycle nothing can actually serve."""
    options = {
        "a": [buy("v", "b", 1)],
        "b": [buy("v", "a", 1)],
    }
    cost = acquisition_cost("a", 1, options, {})
    assert cost >= UNOBTAINABLE_PER_UNIT


def test_the_callers_mappings_are_never_mutated() -> None:
    """`owned` is credited on a private copy. A caller that priced two
    candidates in a row would otherwise see the second charged against holdings
    the first had already spent."""
    owned = {"ore": 3}
    options = {"ore": [gather("pit")]}
    acquisition_cost("ore", 5, options, owned)
    assert owned == {"ore": 3}


def test_an_unchosen_route_leaves_nothing_behind() -> None:
    """Each OR branch is costed from the SAME entry state on its own copy.

    Two recipes for the same bar, and only three ore held. The GREEDY one is
    costed first and would consume all three; the frugal one needs two and
    should still find them. If the rejected branch's consumption leaked, the
    frugal route would be priced as if the bag were empty — smithy hop + craft +
    pit hop + 2 gathers = 5 — and the walk would report 5 for a plan that
    costs 2.

    The first version of this test used a craft-vs-withdraw pair that happened
    to TIE at 2, so it passed with the argmin inverted and was proving
    nothing."""
    options = {
        "bar": [craft("smithy", {"ore": 5}), craft("smithy", {"ore": 2})],
        "ore": [gather("pit")],
    }
    assert acquisition_cost("bar", 1, options, {"ore": 3}) == 2


def test_deeper_chains_cost_strictly_more() -> None:
    """Monotonicity sanity: adding a tier of crafting cannot make an item
    cheaper. A ranking built on a bound that is not monotone in chain depth
    would prefer deeper chains, which is the `acquire_steps` defect class this
    project has already hit three times."""
    shallow = {"bar": [craft("smithy", {"ore": 1})], "ore": [gather("pit")]}
    deep = {"bar": [craft("smithy", {"ingot": 1})],
            "ingot": [craft("smithy", {"ore": 1})],
            "ore": [gather("pit")]}
    assert acquisition_cost("bar", 1, deep, {}) > acquisition_cost("bar", 1, shallow, {})
