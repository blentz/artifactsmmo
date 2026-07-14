"""The destruction licence (`ai/destructive_license`): the shared action pool's
Recycle / NpcSell / Delete answer to the keep authority, or they are not in the pool.

The bug this closes (whole-branch review, finding 1): `actions/factory.py` held a
`protected_codes = protected_gear or (target_gear | target_tools)` frozenset — a
keep-ALL code-set, the type the item-protection-authority epic exists to kill — and it
guarded the RECYCLE emission only. The Delete and NpcSell emissions had no protection at
all, and `Goal.relevant_actions` DEFAULTS to the whole pool, so a goal with no business
destroying anything (CompleteTask, AcceptTask, ClaimPending, …) could satisfy
`FightAction`'s `inventory_free >= 1` precondition by DELETING an item — and
`player_helpers.delete_cost` prices a SELLABLE item (25) BELOW an ingredient (50), which
made the working copper_axe a PREFERRED victim.
"""

import dataclasses
import inspect

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.destructive_license import (
    destructive_demand,
    license_destructive_actions,
    licensed_quantity,
    licensed_recycle_quantity,
)
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from tests.test_ai.fixtures import make_state


def _ctx(**kw: object) -> SelectionContext:
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None,
                gear_review_active=False)
    base.update(kw)
    return SelectionContext(**base)


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon",
                                subtype="tool", skill_effects={"woodcutting": -10},
                                crafting_skill="weaponcrafting", crafting_level=1),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                crafting_skill="mining", crafting_level=1),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"copper_axe": {"copper_bar": 6},
                            "copper_bar": {"copper_ore": 6}}
    gd._workshop_locations = {"weaponcrafting": (3, 1), "mining": (1, 5)}
    gd.world.bank_tile = (4, 0)
    gd.world.taskmaster_tile = (0, 4)
    return gd


def test_the_working_tool_gets_no_destructive_action_at_all():
    """THE REPRO. Bank locked, bag full, a Fight to plan: the planner used to free
    the slot with `DeleteItemAction(copper_axe)` — the character's only woodcutting
    tool, and the CHEAPEST victim on offer. The authority keeps 1 axe
    (`WORKING_KIT` on both caps), so the licence emits NO destructive action for it:
    the planner cannot reach for what is not in the pool."""
    gd = _gd()
    state = make_state(level=10, inventory={"copper_axe": 1, "copper_ore": 3})
    pool = [
        DeleteItemAction(code="copper_axe", quantity=1, cost_weight=25.0),
        RecycleAction(code="copper_axe", quantity=1, workshop_location=(3, 1)),
        NpcSellAction(npc_code="merchant", item_code="copper_axe", quantity=1,
                      npc_location=(1, 1)),
    ]
    assert license_destructive_actions(pool, state, gd, _ctx()) == []
    assert licensed_quantity("copper_axe", state, gd, _ctx()) == 0


def test_the_surplus_above_both_caps_keeps_its_destructive_actions():
    """The licence is a cap, not a ban: 18 axes held means 17 may go, so the pool
    keeps its quantity=1 routes (this is the hoard the epic exists to shed).

    Recycle now routes through `licensed_recycle_quantity`, which agrees with
    `licensed_quantity` here (no bank copies, so the bank route contributes
    nothing new) but STAMPS the surviving action with `bag_floor = keep_in_bag`
    (1, WORKING_KIT) — so the kept action is `dataclasses.replace(pool[0],
    bag_floor=1)`, not the unstamped input object."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 18})
    ctx = _ctx()
    assert licensed_quantity("copper_axe", state, gd, ctx) == 17
    pool = [RecycleAction(code="copper_axe", quantity=1, workshop_location=(3, 1))]
    kept = license_destructive_actions(pool, state, gd, ctx)
    assert kept == [dataclasses.replace(pool[0], bag_floor=1)]


def test_a_quantity_above_the_licence_is_refused():
    """The check is per-QUANTITY, not per-code: a batch bigger than the authority
    licenses is not admitted. The surviving action is stamped with its bag_floor
    (WORKING_KIT keeps 1 in-bag), same reasoning as the test above."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 3})
    ctx = _ctx()
    assert licensed_quantity("copper_axe", state, gd, ctx) == 2
    ok = RecycleAction(code="copper_axe", quantity=2, workshop_location=(3, 1))
    too_many = RecycleAction(code="copper_axe", quantity=3, workshop_location=(3, 1))
    kept = license_destructive_actions([ok, too_many], state, gd, ctx)
    assert kept == [dataclasses.replace(ok, bag_floor=1)]


def test_an_unheld_code_is_licensed_for_nothing():
    """Every destructive route in the pool is BAG-side, so a code with nothing in the
    bag can never be destroyed this cycle — and skipping the keep walk for it is what
    keeps the per-cycle filter cheap over a catalog-wide NpcSell/Recycle menu."""
    gd = _gd()
    state = make_state(level=10, inventory={})
    sell = NpcSellAction(npc_code="merchant", item_code="copper_bar", quantity=1,
                         npc_location=(1, 1))
    assert licensed_quantity("copper_bar", state, gd, _ctx()) == 0
    assert license_destructive_actions([sell], state, gd, _ctx()) == []


def test_the_bag_cap_bounds_a_destruction_even_when_ownership_allows_it():
    """`min(bankable, destroyable)`, not `destroyable` alone: 1 axe in the bag and 5
    in the bank leaves 5 destroyable by OWNERSHIP, but the bag must keep its working
    copy (WORKING_KIT), so the BAG-side routes may take none of it. Banking that copy
    was the correct move — eating it was not."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 1}, bank_items={"copper_axe": 5})
    ctx = _ctx()
    assert licensed_quantity("copper_axe", state, gd, ctx) == 0


def test_non_destructive_actions_pass_through_untouched():
    gd = _gd()
    state = make_state(level=10, inventory={"copper_axe": 1})
    pool = [RestAction(), FightAction(monster_code="chicken",
                                      locations=frozenset({(0, 1)}))]
    assert license_destructive_actions(pool, state, gd, _ctx()) == pool
    assert destructive_demand(RestAction()) is None


def test_the_factory_no_longer_carries_a_code_set_protection():
    """`build_actions` used to skip the RECYCLE emission for
    `target_gear | target_tools` — the LAST `frozenset[str]` protection in the
    codebase, and the one `inventory_keep`'s docstring claimed was gone. The menu is
    now emitted whole and LICENSED downstream (in `StrategyArbiter.select`), so the
    factory takes no protection argument at all and skips no code."""
    assert "protected_gear" not in inspect.signature(build_actions).parameters
    gd = _gd()
    state = make_state(level=10, inventory={"copper_axe": 1})
    objective = CharacterObjective(
        target_char_level=50, target_skill_levels={}, target_gear={},
        _game_data=gd, target_tools={"woodcutting": "copper_axe"})
    recycles = {a.code for a in build_actions(gd, state, objective,
                                              bank_accessible=True,
                                              task_exchange_min_coins=0)
                if isinstance(a, RecycleAction)}
    # The axe is the objective's TOOL target — the old code-set skipped its Recycle
    # (and hoarded all 18 copies). The menu now carries it; the licence decides.
    assert "copper_axe" in recycles


def test_bank_only_recycle_source_is_licensed():
    """7 fishing_net in the BANK, none in the bag. The old bag short-circuit
    (`licensed_quantity`) dropped the RecycleAction entirely, making
    Withdraw -> Recycle unplannable — the MAIN path now that DEPOSIT_FULL banks
    the surplus. `fishing_net` is unregistered in `_gd()` on purpose: it carries
    no WORKING_KIT/gear protection at all, so this proves the pure bank route."""
    gd = _gd()
    state = make_state(level=10, inventory={}, bank_items={"fishing_net": 7})
    ctx = _ctx()
    assert licensed_recycle_quantity("fishing_net", state, gd, ctx) == 7
    pool = [RecycleAction(code="fishing_net", quantity=1, workshop_location=(2, 1))]
    kept = license_destructive_actions(pool, state, gd, ctx)
    assert [a.code for a in kept] == ["fishing_net"]
    assert kept[0].bag_floor == 0


def test_licensed_recycle_is_stamped_with_the_bag_floor():
    """1 working copper_axe in the bag (WORKING_KIT keeps 1 in-bag), 17 more in
    the bank. The action SURVIVES (a bank copy is destroyable) but carries floor
    1, so the WORKING copy cannot be consumed — GOAP must withdraw a bank copy
    first. This is the safety property: liveness (a bank route exists) AND
    safety (the bag floor blocks the current bag) proven together."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 1}, bank_items={"copper_axe": 17})
    ctx = _ctx()
    assert licensed_recycle_quantity("copper_axe", state, gd, ctx) == 17
    pool = [RecycleAction(code="copper_axe", quantity=1, workshop_location=(3, 1))]
    kept = license_destructive_actions(pool, state, gd, ctx)
    assert len(kept) == 1
    assert kept[0].bag_floor == 1
    assert kept[0].is_applicable(state, gd) is False


def test_fully_protected_code_gets_no_recycle_at_all():
    """1 copper_axe owned total, and it IS the WORKING_KIT tool: destroyable ==
    0. No bank copy, no bankable copy -> NO RecycleAction at all. The
    anti-tool-melting property: admitting a bank route must never admit a code
    whose only copy is the one the gather re-arm needs."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 1})
    ctx = _ctx()
    assert licensed_recycle_quantity("copper_axe", state, gd, ctx) == 0
    pool = [RecycleAction(code="copper_axe", quantity=1, workshop_location=(3, 1))]
    assert license_destructive_actions(pool, state, gd, ctx) == []


def test_npc_sell_keeps_the_bag_side_rule():
    """Only RECYCLE gains the bank route. A bank-only code is still unsellable
    — selling has not become a second acquisition route."""
    gd = _gd()
    state = make_state(level=10, inventory={}, bank_items={"fishing_net": 7})
    ctx = _ctx()
    pool = [NpcSellAction(npc_code="merchant", item_code="fishing_net",
                          quantity=1, npc_location=(1, 1))]
    assert license_destructive_actions(pool, state, gd, ctx) == []


def test_npc_sell_survives_licensing_for_a_bag_side_surplus():
    """The positive counterpart to `test_npc_sell_keeps_the_bag_side_rule` above,
    and to `test_the_surplus_above_both_caps_keeps_its_destructive_actions` (same
    18-copper_axe setup, both caps cleared). Recycle split into its own branch
    ending in `continue` when it gained the bank route; this proves the ORIGINAL
    bag-side rule still admits a surviving NpcSell/Delete action through the
    final `kept.append(action)` path — that path is not dead, and a code with
    surplus above both `keep_in_bag` and `keep_owned` still gets to sell it."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 18})
    ctx = _ctx()
    assert licensed_quantity("copper_axe", state, gd, ctx) == 17
    pool = [NpcSellAction(npc_code="merchant", item_code="copper_axe", quantity=1,
                          npc_location=(1, 1))]
    assert license_destructive_actions(pool, state, gd, ctx) == pool
