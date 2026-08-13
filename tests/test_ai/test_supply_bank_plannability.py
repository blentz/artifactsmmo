"""Planner-level tests for `SupplyBankGoal` — the ones that RUN A* over it.

Every other SupplyBankGoal test (test_supply_bank_goal.py) asserts on the
goal's own accessors in isolation, and that is exactly how a structurally
unplannable goal shipped. `is_satisfied` targets an absolute BANKED count; the
only bank-increasing action the factory offers A* is `DepositAllAction`
(actions/factory.py — `DepositItemAction` is built only by disposal_route and
never enters the pool), so every satisfying plan is roughly `demand` mints plus
a deposit. With the inherited `Goal.max_depth` of 15,
`PlannerDepthBound.plan_length_le_max_depth` then guaranteed NO plan could
exist once demand passed ~14 — and the demand actually published is a full
`closure_demand(root, 1, ...)`, which for copper_boots is ~80 gathers.

The project's recorded lesson is that a goal test which never invokes the
planner proves nothing. These drive the REAL `GOAPPlanner` over the REAL
`build_actions` pool.
"""

from itertools import pairwise

from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.supply_bank import SupplyBankGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective

_ORE = "supply_ore"
_BAR = "supply_bar"
_HELM = "supply_helm"


def _gd() -> GameData:
    """One gatherable ore, one bar crafted from it, a helm crafted from the bar,
    a bank and a workshop.

    Deliberately minimal: nothing here protects the ore from being banked
    (no task, no crafting target, no consumable), so `select_bank_deposits`
    reports it as surplus and `DepositAllAction` is the plan's final leg —
    the same shape a supply producer is in live, where `_own_unmet_demand`
    has already netted out everything the producer needs for itself.

    The helm is EQUIPPABLE and that is load-bearing, not decoration:
    `build_actions` emits a `WithdrawItemAction` for a material only when the
    material sits in some EQUIPPABLE's recipe closure (factory.py — the
    per-craft and residual withdraw passes both key off
    `materials_to_withdraw`, seeded from items with an equip slot). Without a
    slotted item downstream, the ore has no withdraw in the pool at all and
    every "the plan must not withdraw the target" assertion below would pass
    vacuously. Live, the supply demand EXISTS because a sibling is building
    gear, so the equippable is always there.
    """
    gd = GameData()
    gd._item_stats = {
        _ORE: ItemStats(code=_ORE, level=1, type_="resource", subtype="mining"),
        _BAR: ItemStats(code=_BAR, level=1, type_="resource", subtype="craft",
                        crafting_skill="mining", crafting_level=1),
        _HELM: ItemStats(code=_HELM, level=1, type_="helmet",
                         crafting_skill="gearcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {_BAR: {_ORE: 4}, _HELM: {_BAR: 2}}
    gd._resource_drops = {"supply_rocks": _ORE}
    gd._resource_skill = {"supply_rocks": ("mining", 1)}
    gd._resource_locations = {"supply_rocks": [(3, 3)]}
    gd._workshop_locations = {"mining": (2, 2), "gearcrafting": (2, 2)}
    gd._bank_location = (0, 0)
    gd._taskmaster_location = (1, 1)
    return gd


def _deep_chain_gd() -> GameData:
    """`_gd` plus a two-level chain: 11 ore per mid_part, 11 mid_part per
    deep_widget — 121 gathers and 12 crafts for a single unit, comfortably past
    the 100-action depth floor."""
    gd = _gd()
    for code in ("mid_part", "deep_widget"):
        gd._item_stats[code] = ItemStats(code=code, level=1, type_="resource",
                                         subtype="craft", crafting_skill="mining",
                                         crafting_level=1)
    gd._crafting_recipes["mid_part"] = {_ORE: 11}
    gd._crafting_recipes["deep_widget"] = {"mid_part": 11}
    return gd


def _state(gd: GameData, *, bank: dict[str, int] | None = None,
           inventory: dict[str, int] | None = None, bag: int = 60,
           name: str = "producer"):
    """`bag` is the bag capacity. The default 60 is the historical fixture size;
    the livelock tests below pass 120 — the capacity R2D2 actually had in the
    live trace, and the one that makes "withdraw the WHOLE banked stock, gather,
    re-deposit it all" fit in the bag at all. At 60 the drain plan is refused by
    `has_room` rather than by any rule about supplying, and the regression test
    would pass for the wrong reason."""
    return scenario_state(
        ScenarioCharacter(name=name, level=10, skills={"mining": 5},
                          inventory=dict(inventory or {}),
                          inventory_max=bag, inventory_slots_max=bag,
                          bank=dict(bank) if bank is not None else None),
        gd)


def _actions(gd: GameData, state) -> list:
    objective = CharacterObjective.from_game_data(gd)
    return build_actions(gd, state, objective, bank_accessible=True,
                         task_exchange_min_coins=0)


def test_planner_produces_a_plan_for_a_realistic_demand() -> None:
    """THE headline. 20 units of sibling demand, empty bank: A* must return a
    real plan, not the empty list the shipped goal returned for every demand
    above ~14."""
    gd = _gd()
    state = _state(gd, bank={})
    goal = SupplyBankGoal(item_code=_ORE, quantity=20, demand=20)
    assert goal.is_satisfied(state) is False, "fixture must start with a real deficit"
    assert goal.is_plannable(state, gd) is True

    planner = GOAPPlanner()
    plan = planner.plan(state, goal, _actions(gd, state), gd)

    assert not planner.last_stats.timed_out, "must be a real search, not a budget artifact"
    assert plan, "a 20-unit sibling demand must be plannable"
    assert any(isinstance(a, GatherAction) for a in plan), "the plan must mint the units"
    assert isinstance(plan[-1], DepositAllAction), "the plan must end by BANKING them"


def test_the_plan_is_longer_than_the_inherited_depth_bound() -> None:
    """The depth raise is load-bearing, not decorative.

    Pins the defect quantitatively: the plan A* actually returns is longer than
    `Goal.max_depth` (15), so with the base bound
    `plan_length_le_max_depth` made it unreachable by construction.

    The demand here is 480, not the 20 this test used before closure sizing
    landed: a gather now carries the whole inventory-bounded batch, so 20 units
    plan in TWO legs (`Gather(×20)`, `DepositAll`) and could no longer exhibit
    the defect. What the bound binds against is now the number of
    gather-till-full/deposit ROUNDS, so the demand has to exceed eight bagfuls
    before the satisfying plan passes 15 legs. Restated at that demand rather
    than deleted — the override still decides reachability, just further out."""
    gd = _gd()
    state = _state(gd, bank={})
    goal = SupplyBankGoal(item_code=_ORE, quantity=480, demand=480)

    planner = GOAPPlanner()
    plan = planner.plan(state, goal, _actions(gd, state), gd)

    assert not planner.last_stats.timed_out
    assert len(plan) > Goal.max_depth.fget(goal), (  # type: ignore[attr-defined]
        "the satisfying plan must exceed the inherited bound, or this goal was "
        "never actually broken and the fix is untested")


def test_planner_banks_the_remainder_when_the_bank_is_partly_stocked() -> None:
    """Only the DEFICIT is produced, and the banked copies of the target do not
    poison the search.

    `fully_covered_materials` credits bank stock, so leaving the target's own
    12 banked units in the state makes the outstanding 8 look "fully covered",
    prunes the ore's gather, and leaves A* nothing but Withdraw->Deposit — a
    null cycle that can never raise the banked count. `_production_state`
    removes exactly those copies."""
    gd = _gd()
    state = _state(gd, bank={_ORE: 12})
    goal = SupplyBankGoal(item_code=_ORE, quantity=20, demand=8)
    assert goal.is_satisfied(state) is False

    planner = GOAPPlanner()
    plan = planner.plan(state, goal, _actions(gd, state), gd)

    assert not planner.last_stats.timed_out
    assert plan, "the outstanding 8 units must still be plannable"
    assert sum(a.quantity for a in plan if isinstance(a, GatherAction)) == 8, (
        "exactly the deficit is minted — not the full 20, not zero")


def test_planner_plans_a_crafted_supply_target() -> None:
    """A craft target, not just a raw resource: the closure's gather AND the
    craft have to be admitted, and the bar has to reach the bank."""
    gd = _gd()
    state = _state(gd, bank={}, inventory={_ORE: 16})
    goal = SupplyBankGoal(item_code=_BAR, quantity=4, demand=4)

    planner = GOAPPlanner()
    plan = planner.plan(state, goal, _actions(gd, state), gd)

    assert not planner.last_stats.timed_out
    assert plan, "a crafted supply target must be plannable"
    assert isinstance(plan[-1], DepositAllAction)


def test_banked_inputs_count_toward_the_depth_bound() -> None:
    """The depth bound credits what the bank can supply.

    Every banked code EXCEPT the target itself is a real, withdrawable input, so
    it shortens the minimum plan. The SAME target that is correctly refused from
    an empty bank (the test below) becomes reachable once its intermediates are
    banked — ignoring the bank here would prune a goal the fleet has already
    done the work for."""
    gd = _deep_chain_gd()
    goal = SupplyBankGoal(item_code="deep_widget", quantity=1, demand=1)

    assert goal.is_plannable(_state(gd, bank={}), gd) is False
    assert goal.is_plannable(_state(gd, bank={"mid_part": 11}), gd) is True


def test_relevant_actions_scopes_the_search_to_the_closure_plus_deposit() -> None:
    """The action set the planner sees is the target's closure plus the
    deposit, not the whole pool (which live is ~1800 actions and, with no
    heuristic, an unscoped Dijkstra)."""
    gd = _gd()
    state = _state(gd, bank={})
    goal = SupplyBankGoal(item_code=_ORE, quantity=20, demand=20)
    actions = _actions(gd, state)

    admitted = goal.relevant_actions(actions, state, gd)

    assert len(admitted) < len(actions), "scoping must actually narrow the pool"
    assert any(isinstance(a, DepositAllAction) for a in admitted), (
        "the deposit is the only bank-increasing edge — dropping it makes the "
        "goal unsatisfiable by construction")
    assert any(isinstance(a, GatherAction) and a.resource_code == "supply_rocks"
               for a in admitted)


def test_relevant_actions_on_a_satisfied_goal_still_returns_a_usable_set() -> None:
    """`GOAPPlanner.plan` calls `relevant_actions` BEFORE it pops the root, so a
    satisfied goal reaches it with a zero deficit.

    A `needed` of 0 is a degenerate demand: the closure walk reports every
    material fully covered, which prunes the target's own gather and hands back
    an action set that could not satisfy the goal if the root check had gone the
    other way. `_production_goal`'s floor keeps the set honest."""
    gd = _gd()
    state = _state(gd, bank={_ORE: 20})
    goal = SupplyBankGoal(item_code=_ORE, quantity=20, demand=20)
    assert goal.is_satisfied(state) is True

    admitted = goal.relevant_actions(_actions(gd, state), state, gd)

    assert any(isinstance(a, GatherAction) and a.resource_code == "supply_rocks"
               for a in admitted)
    assert any(isinstance(a, DepositAllAction) for a in admitted)


def test_unreachable_depth_is_refused_before_the_search() -> None:
    """`is_plannable` fails when even the raised `max_depth` cannot hold the
    chain — the `min_plan_length` bound `UpgradeEquipmentGoal` uses.

    A single unit of `deep_widget` needs 11 x 11 = 121 ore gathers plus 12
    crafts; `max_depth` for demand 1 is the 100 floor, so no plan of length
    <= max_depth can exist and running A* is pure waste."""
    gd = _deep_chain_gd()
    goal = SupplyBankGoal(item_code="deep_widget", quantity=1, demand=1)

    assert goal.is_plannable(_state(gd, bank={}), gd) is False


def test_a_satisfied_goal_is_plannable() -> None:
    """Satisfied short-circuit: nothing to search for, and the arbiter must not
    read "unplannable" as "broken"."""
    gd = _gd()
    goal = SupplyBankGoal(item_code=_ORE, quantity=5, demand=5)

    assert goal.is_plannable(_state(gd, bank={_ORE: 5}), gd) is True


def test_an_already_banked_unaffordable_item_is_still_plannable() -> None:
    """The satisfied short-circuit is load-bearing, not decorative.

    The demand is already met from the bank, but the item is NPC-only and the
    character cannot afford another copy — so the delegated currency-leaf gate
    says "no plan can acquire this". Without the short-circuit that verdict
    would be reported for a goal that needs no plan at all."""
    gd = _gd()
    gd._item_stats["rare_rune"] = ItemStats(code="rare_rune", level=20, type_="rune")
    gd._npc_stock = {"rune_vendor": {"rare_rune": 20000}}
    gd._npc_buy_currency = {"rune_vendor": {"rare_rune": "gold"}}
    gd._npc_locations = {"rune_vendor": (8, 13)}
    state = _state(gd, bank={"rare_rune": 2})
    goal = SupplyBankGoal(item_code="rare_rune", quantity=2, demand=2)
    assert goal.is_satisfied(state) is True
    assert goal._production_goal(state).is_plannable(
        goal._production_state(state), gd) is False, (
        "fixture must make the delegate refuse, or this proves nothing")

    assert goal.is_plannable(state, gd) is True


def test_an_unaffordable_buy_only_target_is_refused_before_the_search() -> None:
    """The delegated currency-leaf gate, on a goal that IS unsatisfied.

    A buy-only supply target the character cannot pay for has no acquisition
    edge in the admitted action set, so no plan can reach it — and the depth
    bound cannot see that (a single unbought unit is one action long)."""
    gd = _gd()
    gd._item_stats["rare_rune"] = ItemStats(code="rare_rune", level=20, type_="rune")
    gd._npc_stock = {"rune_vendor": {"rare_rune": 20000}}
    gd._npc_buy_currency = {"rune_vendor": {"rare_rune": "gold"}}
    gd._npc_locations = {"rune_vendor": (8, 13)}
    state = _state(gd, bank={})
    goal = SupplyBankGoal(item_code="rare_rune", quantity=2, demand=2)
    assert goal.is_satisfied(state) is False

    assert goal.is_plannable(state, gd) is False


def test_max_depth_tracks_demand_not_the_bank_inflated_quantity() -> None:
    """`quantity` is `banked + demand`, so a well-stocked bank would inflate the
    search depth without adding a single action to plan."""
    stocked = SupplyBankGoal(item_code=_ORE, quantity=508, demand=8)
    bare = SupplyBankGoal(item_code=_ORE, quantity=8, demand=8)

    assert stocked.max_depth == bare.max_depth
    assert SupplyBankGoal(item_code=_ORE, quantity=90, demand=90).max_depth == 9000


def test_an_unvisited_bank_still_plans_the_full_quantity() -> None:
    """`bank_items is None` is "never visited", and `DepositAllAction.apply`
    rebuilds the bank from `dict(state.bank_items or {})` — so inside the
    search an unvisited bank genuinely starts empty and the whole quantity has
    to be produced."""
    gd = _gd()
    state = _state(gd, bank=None)
    goal = SupplyBankGoal(item_code=_ORE, quantity=6, demand=6)

    planner = GOAPPlanner()
    plan = planner.plan(state, goal, _actions(gd, state), gd)

    assert plan, "an unvisited bank must not make the goal unplannable"
    assert sum(a.quantity for a in plan if isinstance(a, GatherAction)) == 6


def _target_withdraws(actions: list, code: str) -> list:
    return [a for a in actions
            if isinstance(a, WithdrawItemAction) and a.code == code]


def test_the_plan_never_withdraws_the_item_it_is_supplying() -> None:
    """THE LIVELOCK (live trace 2026-08-04 01:11, R2D2 — 38 of 83 cycles were
    no-op bank traffic against the per-IP rate budget this feature exists to
    conserve).

    A goal satisfied by "the item is IN THE BANK" must never source that item
    FROM the bank: `Withdraw` then `DepositAll` returns the banked count to
    exactly where it started. A* nonetheless preferred it, because
    `GatherAction.cost` charges `_BANKED_REGATHER_PENALTY` (100.0) per gather
    while ANY of the drop is banked — so emptying the bank at 2.0 per withdraw
    bought 100.0 back on each of the 26 remaining gathers, making
    "drain, gather, re-deposit" the genuinely LEAST-COST satisfying plan.

    The fixture is the live shape: a stocked bank, a bag already holding some
    of the target, and a real deficit on top."""
    gd = _gd()
    state = _state(gd, bank={_ORE: 59}, inventory={_ORE: 20}, bag=120)
    goal = SupplyBankGoal(item_code=_ORE, quantity=105, demand=46)
    actions = _actions(gd, state)
    assert _target_withdraws(actions, _ORE), (
        "the pool must OFFER a withdraw of the target, or this proves nothing")

    planner = GOAPPlanner()
    plan = planner.plan(state, goal, actions, gd)

    assert not planner.last_stats.timed_out
    assert plan, "the goal must still be plannable without its own withdraw"
    assert _target_withdraws(plan, _ORE) == [], (
        "the producer withdrew the item it is supposed to be supplying")
    assert sum(a.quantity for a in plan if isinstance(a, GatherAction)) == 26, (
        "exactly the deficit is minted: 105 banked target - 59 banked - 20 held")
    assert isinstance(plan[-1], DepositAllAction)


def test_the_plan_reaches_the_target_and_never_lowers_the_banked_count() -> None:
    """Behavioural, not structural: simulate the whole plan and watch the bank.

    A withdraw of the target shows up here as a DIP in `bank_items[_ORE]` —
    the exact signature of the live churn, where the recomputed
    `banked + demand` target marched 118, 117, 116, 109, ... as the producer
    ate its own stock. Monotone non-decreasing, ending at the target, is the
    property the goal actually promises."""
    gd = _gd()
    state = _state(gd, bank={_ORE: 59}, inventory={_ORE: 20}, bag=120)
    goal = SupplyBankGoal(item_code=_ORE, quantity=105, demand=46)

    plan = GOAPPlanner().plan(state, goal, _actions(gd, state), gd)
    assert plan

    banked = [(state.bank_items or {}).get(_ORE, 0)]
    for action in plan:
        assert action.is_applicable(state, gd), f"{action!r} must be executable"
        state = action.apply(state, gd)
        banked.append((state.bank_items or {}).get(_ORE, 0))

    assert all(b <= nxt for b, nxt in pairwise(banked)), (
        f"the banked count must never fall while SUPPLYING the bank: {banked}")
    assert goal.is_satisfied(state), "the plan must actually reach the target"


def test_relevant_actions_refuses_the_target_withdraw_but_keeps_the_inputs() -> None:
    """The exclusion is surgical. Supplying the BAR must still withdraw banked
    ORE — a supply job legitimately consumes banked INPUTS, and that withdraw is
    the delegate's whole point. Only the target's own withdraw is a null cycle."""
    gd = _gd()
    state = _state(gd, bank={_ORE: 40, _BAR: 3})
    goal = SupplyBankGoal(item_code=_BAR, quantity=7, demand=4)
    actions = _actions(gd, state)
    assert _target_withdraws(actions, _BAR), "the pool must offer the bar withdraw"

    admitted = goal.relevant_actions(actions, state, gd)

    assert _target_withdraws(admitted, _BAR) == [], "the target's withdraw is a no-op"
    assert _target_withdraws(admitted, _ORE), (
        "a banked INPUT must stay withdrawable, or crafted supply targets regress")


def test_a_banked_input_is_withdrawn_for_a_crafted_supply_target() -> None:
    """The same claim at the planner, not the action set: with the ore banked
    and the bag empty, the least-cost way to bank 4 bars is to withdraw the ore
    and craft — the plan must actually take it."""
    gd = _gd()
    state = _state(gd, bank={_ORE: 40})
    goal = SupplyBankGoal(item_code=_BAR, quantity=4, demand=4)

    planner = GOAPPlanner()
    plan = planner.plan(state, goal, _actions(gd, state), gd)

    assert not planner.last_stats.timed_out
    assert plan, "a crafted target fed from banked inputs must be plannable"
    assert _target_withdraws(plan, _ORE), (
        "the banked ore must be withdrawn, not re-gathered")
    assert isinstance(plan[-1], DepositAllAction)


def test_two_producers_of_the_same_item_do_not_churn_the_bank() -> None:
    """The observed two-character scenario: R2D2 and a sibling both hold
    `miner` and both serve iron_ore, so each one's withdraw lowered the other's
    recomputed `banked + demand` target and the pair traded the same stock back
    and forth without ever producing anything.

    Both producers plan against the SAME bank; neither plan may take a unit of
    the target out of it."""
    gd = _gd()
    bank = {_ORE: 59}
    first = _state(gd, bank=bank, inventory={_ORE: 20}, bag=120, name="r2d2")
    second = _state(gd, bank=bank, inventory={}, bag=120, name="sibling")
    goal = SupplyBankGoal(item_code=_ORE, quantity=105, demand=46)

    plans = [GOAPPlanner().plan(s, goal, _actions(gd, s), gd)
             for s in (first, second)]

    for plan in plans:
        assert plan, "both producers must still have real work to do"
        assert _target_withdraws(plan, _ORE) == [], (
            "two producers of one item must not trade its banked stock")
        assert any(isinstance(a, GatherAction) for a in plan), (
            "a producer's plan must MINT units, not shuffle them")


def test_no_heuristic_override() -> None:
    """Deliberate: the default 0.0 (Dijkstra) is the only estimate this goal can
    claim is both admissible AND consistent. Recorded as a test so a future
    override is a conscious decision with its own admissibility argument."""
    gd = _gd()
    state = _state(gd, bank={})
    goal = SupplyBankGoal(item_code=_ORE, quantity=20, demand=20)

    assert goal.heuristic(state, gd) == 0.0
