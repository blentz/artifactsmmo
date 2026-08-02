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

from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.supply_bank import SupplyBankGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective

_ORE = "supply_ore"
_BAR = "supply_bar"


def _gd() -> GameData:
    """One gatherable ore, one bar crafted from it, a bank and a workshop.

    Deliberately minimal: nothing here protects the ore from being banked
    (no task, no crafting target, no consumable), so `select_bank_deposits`
    reports it as surplus and `DepositAllAction` is the plan's final leg —
    the same shape a supply producer is in live, where `_own_unmet_demand`
    has already netted out everything the producer needs for itself.
    """
    gd = GameData()
    gd._item_stats = {
        _ORE: ItemStats(code=_ORE, level=1, type_="resource", subtype="mining"),
        _BAR: ItemStats(code=_BAR, level=1, type_="resource", subtype="craft",
                        crafting_skill="mining", crafting_level=1),
    }
    gd._crafting_recipes = {_BAR: {_ORE: 4}}
    gd._resource_drops = {"supply_rocks": _ORE}
    gd._resource_skill = {"supply_rocks": ("mining", 1)}
    gd._resource_locations = {"supply_rocks": [(3, 3)]}
    gd._workshop_locations = {"mining": (2, 2)}
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
           inventory: dict[str, int] | None = None):
    return scenario_state(
        ScenarioCharacter(name="producer", level=10, skills={"mining": 5},
                          inventory=dict(inventory or {}),
                          inventory_max=60, inventory_slots_max=60,
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

    Pins the defect quantitatively: the plan A* actually returns for a
    realistic demand is longer than `Goal.max_depth` (15), so with the base
    bound `plan_length_le_max_depth` made it unreachable by construction."""
    gd = _gd()
    state = _state(gd, bank={})
    goal = SupplyBankGoal(item_code=_ORE, quantity=20, demand=20)

    plan = GOAPPlanner().plan(state, goal, _actions(gd, state), gd)

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
    assert sum(isinstance(a, GatherAction) for a in plan) == 8, (
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
    assert sum(isinstance(a, GatherAction) for a in plan) == 6


def test_no_heuristic_override() -> None:
    """Deliberate: the default 0.0 (Dijkstra) is the only estimate this goal can
    claim is both admissible AND consistent. Recorded as a test so a future
    override is a conscious decision with its own admissibility argument."""
    gd = _gd()
    state = _state(gd, bank={})
    goal = SupplyBankGoal(item_code=_ORE, quantity=20, demand=20)

    assert goal.heuristic(state, gd) == 0.0
