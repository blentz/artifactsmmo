"""Equippable-routing helpers shared by `strategy_driver.py` and
`decisions/obtain_item.py`.

Extracted from `strategy_driver.py` (Task 5, PF-2 wiring) so that
`decisions/obtain_item.py` can depend on these functions without
`strategy_driver.py` depending back on `decisions/obtain_item.py` --
`objective_step_goal`'s `ObtainItem` arm now calls
`resolve_node(obtain_item_decision(...))`, and `obtain_item_decision`'s
`Decision`s call `_equippable_goal` / `_gather_step_target_is_root` /
`_recipe_has_combat_drop_input`. Both modules importing this one (instead of
each other) breaks the cycle that direction would otherwise create.
`strategy_driver.py` still uses `_gather_goal_for_unreachable_equippable`
directly (the `GEAR_REVIEW` guard branch) and imports it back from here.
"""

from artifactsmmo_cli.ai.currency_grind_target import currency_grind_target_pure
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gather_step_target import gather_step_target
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.objective import _permanent_vendor_purchases
from artifactsmmo_cli.ai.tiers.strategy import actionable_step
from artifactsmmo_cli.ai.world_state import WorldState


def _gather_step_target_is_root(tgt_code: str, root_code: str) -> bool:
    """True when `gather_step_target` targeted the ROOT itself by name.

    Shared by every one of `gather_step_target`'s callers
    (`grep -rn "gather_step_target(" src/` — two direct call sites:
    `_gather_goal_for_unreachable_equippable` and `objective_step_goal`) so
    the check exists exactly once rather than as a re-typed `== root_code`
    at each site — the `ai/gather_skill_gate.py` failure mode this repo
    documents (one predicate, two sites, drift).

    A `True` result is `gather_step_target`'s own contract, not the
    caller's: its module docstring states as a PRECONDITION of ITS caller
    that "when the root chain IS depth-reachable the caller never reaches
    here" — i.e. this is a signal to plan the root directly (e.g.
    `UpgradeEquipment`), never license to wrap the root in a second
    `GatherMaterials` pass over itself. `GatherMaterialsGoal`'s
    `relevant_actions` search a WIDER action pool (recycle sources,
    currency legs) than `UpgradeEquipmentGoal`'s closure-locked one, so
    "wrap and gather" is not merely redundant — measured on the real
    321-recipe catalog (R2D2, empty bank), direct vs. wrapped:

        wooden_staff     5,839 / 0.50s   vs  102,286 / 11.0s
        feather_coat    81,690 / 15.3s   vs   76,213 / 15.3s
        leather_gloves  47,288 / 15.2s   vs   43,412 / 15.3s

    all three finding no plan either way. Only `wooden_staff` is actually
    faster direct (20x); `feather_coat`/`leather_gloves` exceed the search
    budget regardless of which goal is planned — this predicate is NEUTRAL
    for those two, not a fix, and they remain unsolved (a residual for the
    spec, not this function)."""
    return tgt_code == root_code


def _gather_goal_for_unreachable_equippable(
    code: str, state: WorldState, game_data: GameData, equip_max_depth: int,
    ctx: SelectionContext = NO_PROFILE_CONTEXT,
    step: ObtainItem | None = None,
) -> GatherMaterialsGoal | None:
    """Build a budget-FEASIBLE GatherMaterials goal for a depth-unreachable
    equippable `code` (its full craft chain exceeds `equip_max_depth`), or
    `None` when `_gather_step_target_is_root` says `gather_step_target`
    targeted `code` itself — see that function's docstring for why, and for
    the measurements backing it. `None` means: don't wrap the root in a
    second `GatherMaterials` pass over itself; the caller must fall through
    to its own reachable-root goal (`_equippable_goal`'s `upgrade`, the
    `GEAR_REVIEW` guard's `committed`, `objective_step_goal`'s `upgrade`).

    `step` is the caller's already-computed `actionable_step` result, passed
    so the traversal runs once per decision instead of twice (once to decide
    whether to route here, once inside). `None` means "derive it here" — kept
    for callers that have not computed it themselves.

    `ctx` (the caller's per-cycle `SelectionContext`) is forwarded to
    `actionable_step` so the routed step stops at a node with any ready
    `ai/obtain_sources` route instead of falling into its recipe
    (one-obtain-model epic, Task 5; originally the recycle-as-acquisition
    epic's bespoke `recoverable` map). Defaults to `NO_PROFILE_CONTEXT` for
    every caller that doesn't wire it in.

    The naive fallback — GatherMaterials(code, code's DIRECT recipe) — must plan a
    chain that gathers `min_gathers(code)` raw units THROUGH the multi-level recipe;
    for a from-scratch DEEP chain (empty bank, e.g. steel_boots ← 6 steel_bar ←
    8 iron_bar ← 10 iron_ore = 480 raw) the GOAP search over the gather/craft/deposit
    interleavings EXPLODES super-linearly (measured offline: 655k nodes / 90s timeout
    / plan_len 0 at qty 480; live: 1M+ nodes). Piece A (bank-credited shopping_list)
    prunes NOTHING here — there is no bank stock to credit.

    The fix is the SAME macro/micro bound Piece C wired into `objective_step_goal`:
    route to the strategy's DEEPEST actionable step (the raw base material), whose
    gather is FLAT (`min_gathers == qty`, no recipe sub-tree to interleave) and
    therefore LINEAR in the planner (measured offline: ~38 nodes/unit, 18k nodes /
    0.8s at qty 480 — well within budget). Gathering the leaf makes real incremental
    progress; once it accumulates the next recipe level becomes the actionable step,
    and UpgradeEquipment fires the craft+equip when the materials are in hand. The
    macro PLAN (gather leaf → craft up the chain → equip) is reached by REPEATED
    cycle execution; each cycle descends to micro only for the committed flat batch.

    Reuses the proved cores `actionable_step`
    (formal/Formal/StrategyTraversal.lean `actStep`) + `gather_step_target`
    (formal/Formal/StepDispatch.lean `gatherTarget_*`): the routed step is a genuine
    prerequisite ON the root's recipe path and never harder than the declined root,
    so PlannerAdmissibility is preserved (a reachable root is never abandoned)."""
    owned: dict[str, int] = dict(state.inventory)
    for owned_code, qty in (state.bank_items or {}).items():
        owned[owned_code] = owned.get(owned_code, 0) + qty
    resolved = step if step is not None else actionable_step(
        ObtainItem(code=code, quantity=1), state, game_data, ctx)
    if isinstance(resolved, ObtainItem) and resolved.code != code:
        tgt_code, tgt_qty = gather_step_target(
            code, resolved.code, resolved.quantity,
            game_data.crafting_recipes, owned, equip_max_depth,
            game_data.max_gather_yield)
        if _gather_step_target_is_root(tgt_code, code):
            return None
        return GatherMaterialsGoal(target_item=tgt_code, needed={tgt_code: tgt_qty})
    # No deeper actionable step (the root itself is the actionable leaf, or the
    # chain is cyclically blocked): fall back to the direct recipe. `_equippable_goal`
    # never reaches here recipe-less — its `if recipe:` guard filters that before
    # calling in. `map_guard`'s GEAR_REVIEW branch makes no such guarantee:
    # `find_upgrade_target` can surface a BANK-ONLY item via `_find_inventory_upgrade`
    # (inventory OR bank, no recipe required — see that method's docstring), and the
    # GEAR_REVIEW gate at `:335` checks `state.inventory` but not the bank, while
    # `_materials_in_hand` requires `bool(recipe)` and so also fails. A bank-only
    # recipe-less equippable (46 of the real ones have no recipe, e.g.
    # `corrupted_skull`/`life_crystal`/`forest_ring`) therefore DOES reach this
    # line with `recipe = {}`, returning `GatherMaterialsGoal(code, {})`. Not a
    # soundness break: that goal's own `is_satisfied` short-circuits True for a
    # target held in inventory OR bank when the target is not itself a key of
    # `needed` (see `GatherMaterialsGoal.is_satisfied`'s docstring) — `needed={}`
    # makes that always the case here, so it fires zero actions rather than a
    # wrong one. Whether the bank-held item then actually gets withdrawn and
    # equipped is a different goal's job, not this fallback's. Neither caller
    # consults `is_plannable` to decide whether to call in.
    recipe = game_data.crafting_recipe(code) or {}
    return GatherMaterialsGoal(target_item=code, needed=dict(recipe))


def _equippable_goal(code: str, slot: str, state: WorldState, game_data: GameData,
                     ctx: SelectionContext = NO_PROFILE_CONTEXT) -> Goal:
    """Map an equippable target to UpgradeEquipment when it is reachable, else to
    GatherMaterials for the strategy's next achievable step toward it.

    Routes on the STEP, not on a depth-bound proxy for it. `is_plannable`
    compares `min_plan_length` against `max_depth` 32, and `min_plan_length`
    maxes at 15 across all 321 real recipes (see `UpgradeEquipmentGoal.max_depth`'s
    SECOND RESIDUAL), so it never rejects — using it as a trigger here was dead
    code: the arbiter planned a 100,080-node search that timed out instead of
    the 2-node gather `actionable_step` had already identified. `is_plannable`
    is still consulted elsewhere as a waste-avoidance filter; it is not used
    by this function.

    The direct question this function asks is the one the helper asks
    internally: is the deepest achievable node (`actionable_step`) something
    OTHER than the goal itself? If not — the root's own direct prerequisites
    are already satisfied, or the traversal is cyclically blocked / every
    branch dead-ends (`actionable_step` returns `None`) — return
    `UpgradeEquipment` directly; a dead-ended chain is a bounded, fast-failing
    search, not a soundness break (see `test_objective_step_equippable_dead_ends_admit_the_root_cheaply`).
    Otherwise route to `_gather_goal_for_unreachable_equippable`'s flat-leaf
    step. The helper itself returns `None` (not a wrapped goal) when
    `gather_step_target` decides the root's own gather cost already fits
    `equip_max_depth` — see the helper's docstring for why that must be
    handled there, not re-checked here — and this function falls through to
    `upgrade` on that signal too. Self-corrects both ways across cycles —
    materials missing routes to the gather (which does craft, not just
    gather; the equip follows on a later cycle once the item is owned),
    materials banked or carried leafs at the root and fires the craft+equip —
    so there is no threshold to tune and no bound to rot.

    `ctx` is forwarded to `_gather_goal_for_unreachable_equippable`
    (one-obtain-model epic, Task 5); defaults to `NO_PROFILE_CONTEXT`.

    THIS FUNCTION IS THE PRODUCER OF "PURSUE THIS UPGRADE"; the goal's
    `value()` is NOT. `UpgradeEquipmentGoal.value` asks a different question —
    are the committed target's materials in hand — so a dead-ended target
    returned here reports 0.0. That is a report, not a second firing decision,
    and the sweep that establishes it (62 of 488 attempts at priority 0.0, all
    with `plan_len == 0`, none selected, 2026-08-25) is written up at that
    method. If the routing above ever admits a materials-short-but-gatherable
    target into `UpgradeEquipment`, the two DO become two producers and that
    census has to be re-run."""
    upgrade = UpgradeEquipmentGoal(initial_equipment=state.equipment, committed_target=(code, slot))
    owned = (state.inventory.get(code, 0) > 0
             or (state.bank_items or {}).get(code, 0) > 0)
    if (game_data.crafting_recipe(code) is None and not owned
            and game_data.npc_purchases(code)):
        # UNOWNED, recipe-less, NPC-buy-only equippable (sandwhisper_bag):
        # UpgradeEquipment's closure lock restricts planning to the recipe
        # closure's crafts/gathers/withdraws + the equip — for a recipe-less
        # vendor item that set is EMPTY, so its search died at 2 nodes even
        # at full capability (probe 2026-07-06 @L50: plan_len=0 — a dead
        # gear root), while is_plannable over-admitted it ("recipe-less
        # needs at most one gather" assumes a gather exists). Route the
        # ACQUISITION through GatherMaterials, whose currency injection
        # (task #13) emits Fight xN (drop-farm capable) -> NpcBuy; once the
        # item is in hand this branch is skipped and UpgradeEquipment fires
        # the equip — one stepwise leg per cycle, as with every other root.
        #
        # UNAFFORDABLE item-currency: accumulate the currency in BATCHES via
        # `currency_grind_target_pure` — a one-shot plan for a 230-coin price
        # is ~120 fights deep and dies on max_depth (sandwhisper_bag probe
        # @L50: 28K nodes, plan_len=0), so the target must stay shallow. It
        # was `held + 1`, which stayed shallow but re-armed on EVERY
        # acquisition; since `needed` is part of the goal's identity that
        # churned the repr each cycle and reset sticky-commit keying. The
        # batch milestone is absolute, so it holds still within a batch while
        # still never running more than one batch ahead of `held`. Cheapest
        # PERMANENT located vendor decides the price (semantic key; event/
        # unlocated vendors mirror currency_demand's exclusion). Gold-priced
        # items skip the accumulation (gold is earned by normal play, not a
        # gatherable item) and fall through to the buy attempt.
        bank = state.bank_items or {}
        # A currency that accrues passively from normal combat (like gold, and like
        # event_ticket, which drops from 56/58 monsters) is NOT farmed on a
        # dedicated grind — it is earned while levelling. Excluding it here drops
        # through to the plain buy attempt, which is unplannable until affordable,
        # so the arbiter falls back to levelling (which accrues the currency). The
        # item is then bought once ordinary play has paid for it. (§synergy live
        # diagnosis 2026-07-23: over-boosted event_ticket grind out-ranked xp.)
        purchases = [(price, currency)
                     for price, currency in _permanent_vendor_purchases(code, game_data)
                     if currency != "gold"
                     and not game_data.currency_accrues_passively(currency)]
        if purchases:
            price, currency = min(purchases)
            held = state.inventory.get(currency, 0) + bank.get(currency, 0)
            if held < price:
                return GatherMaterialsGoal(
                    target_item=currency,
                    needed={currency: currency_grind_target_pure(held, price)})
        return GatherMaterialsGoal(target_item=code, needed={code: 1})
    # Route on the STEP, not on a depth-bound proxy for it. `is_plannable`
    # compares min_plan_length against max_depth 32, and min_plan_length maxes
    # at 15 across all 321 real recipes (see UpgradeEquipmentGoal.max_depth's
    # SECOND RESIDUAL), so it never rejects and this routing was dead — the
    # arbiter planned a 100,080-node search that timed out instead of the
    # 2-node gather `actionable_step` had already identified.
    #
    # The direct question is the one the helper asks internally: is the deepest
    # achievable node something OTHER than the goal itself? It self-corrects in
    # both directions — materials missing routes to the gather, materials
    # banked or carried leafs at the root and fires the craft — so there is no
    # threshold to tune and no bound to rot.
    step = actionable_step(ObtainItem(code=code, quantity=1), state, game_data, ctx)
    if not (isinstance(step, ObtainItem) and step.code != code):
        return upgrade
    recipe = game_data.crafting_recipe(code) or {}
    if recipe:
        # Depth-UNREACHABLE from-scratch deep chain: route to the FLAT deepest
        # actionable step instead of GatherMaterials(code, DIRECT recipe), whose
        # plan must gather through the multi-level recipe and explodes the GOAP
        # search (see _gather_goal_for_unreachable_equippable).
        routed = _gather_goal_for_unreachable_equippable(
            code, state, game_data, upgrade.max_depth, ctx, step=step)
        # None means gather_step_target decided the root itself fits the
        # depth budget (see the helper's docstring) -- plan it directly.
        return routed if routed is not None else upgrade
    # Unreachable in practice: `recipe` is only falsy for a recipe-less code,
    # and a recipe-less item's requirement-graph node has no outgoing edges
    # (`requirement_edges` returns {} — see `requirement_projections.py`), so
    # `actionable_step` can never descend PAST a recipe-less root: it either
    # returns the root itself (satisfied/producible) or None (blocked),
    # both of which are caught by the `not (isinstance(step, ObtainItem)
    # and step.code != code)` guard above and return `upgrade` before this
    # line. `step.code != code` therefore implies a non-empty recipe. Kept
    # as a total-function fallback.
    return upgrade  # pragma: no cover


def _recipe_has_combat_drop_input(
    code: str, game_data: GameData, visited: frozenset[str] = frozenset()) -> bool:
    """True when `code`'s recipe closure contains a PURE monster-drop leaf — an
    input obtained only by fighting (e.g. feather <- chicken), neither craftable
    nor a resource-node drop. Such an input forces the whole-chain GOAP plan to
    interleave fights with gathers/crafts, exploding the search; the caller routes
    to flat per-input steps instead. Cycle-safe."""
    if code in visited:
        return False
    recipe = game_data.crafting_recipe(code)
    if recipe is None:
        return (bool(game_data.monsters_dropping(code))
                and code not in game_data.gatherable_drop_items())
    nxt = visited | {code}
    return any(_recipe_has_combat_drop_input(mat, game_data, nxt) for mat in recipe)
