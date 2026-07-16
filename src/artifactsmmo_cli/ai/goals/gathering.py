"""Gathering goal: accumulate materials needed to craft an upgrade."""

import dataclasses
from fractions import Fraction

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.ge_fill_sell import GeFillSellOrderAction
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.actions.withdraw_gold import WithdrawGoldAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.buy_source_venue import BuyVenue, choose_buy_venue
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.craft_vs_buy import Method, acquisition_method
from artifactsmmo_cli.ai.forced_craft_grind import forced_craft_grind
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gather_selection import GatherCandidate, select_gather_source
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.currency_demand import analyze_currency_leaves
from artifactsmmo_cli.ai.grey_farm import grey_farm_allowed
from artifactsmmo_cli.ai.intermediate_batch import size_intermediate_craft
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.monster_drop_selection import (
    MonsterDropCandidate,
    select_monster_for_drop,
)
from artifactsmmo_cli.ai.nearest_tile import nearest_or_error
from artifactsmmo_cli.ai.priority_band import clamp_into_band
from artifactsmmo_cli.ai.progression_reserve import reserve_floor
from artifactsmmo_cli.ai.recipe_closure import (
    closure_demand,
    gather_serves_closure,
    recipe_closure,
)
from artifactsmmo_cli.ai.scalar_priority import yield_bonus_for_goal
from artifactsmmo_cli.ai.shopping_list import fully_covered_materials
from artifactsmmo_cli.ai.world_state import WorldState

# Band constants — Phase-17 wiring of scalar_yield as a discretionary-band
# priority signal. Ceiling stays strictly below the survival floor (70) so
# the Phase-1 invariant (no learned bonus can reorder a discretionary goal
# above a survival goal) is preserved by construction.
PRIORITY_FLOOR = 1.0
"""Band floor — matches the existing `max(1.0, ...)` lower bound on the base
ramp so cold goals (history=None) preserve the pre-Phase-17 priority."""

PRIORITY_CEILING = 50.0
"""Band ceiling — strictly below SURVIVAL_FLOOR=70. Subsumes the existing
ramp (which capped at 40.0) plus an above-baseline scalar bonus head-room."""


def _skill_open(resource_code: str, state: WorldState, game_data: GameData) -> bool:
    """True iff the resource's skill gate is open against the FIXED initial
    `state` passed to `relevant_actions`. Gathers alone never raise a skill
    (they raise skill XP server-side, not planner-tracked levels), so a gather whose
    gate is closed here cannot become applicable via gathering. Admitting one
    unconditionally is branching waste — and worse, it can WIN the yield
    narrowing below and displace a workable source (derived 2026-07-08:
    salmon_spot, the rate-best small_pearls dropper at 1/100, is fishing-40-
    gated; at fishing 30 it beat bass_spot in select_gather_source and the
    pearl plan died at one node). A skill-closed gather is therefore admitted
    ONLY through the `openable_locked_gathers` fallback below — when the
    LevelSkill action can raise the gate mid-search (`LevelSkill.apply` DOES
    mutate `state.skills`) and the drop has no open source, so the plan is
    LevelSkill→Gather rather than a wasted branch. Mirrors
    GatherAction.is_applicable's skill arm (default level 1) without its
    transient inventory-space arm — bag pressure changes in-plan."""
    req = game_data.resource_skill_level(resource_code)
    return req is None or state.skills.get(req[0], 1) >= req[1]


def level_below_and_grindable(req: tuple[str, int], state: WorldState,
                              game_data: GameData) -> bool:
    """True when the character is UNDER the gather-skill gate `req` = (skill,
    level) and that level is reachable by a LevelSkill grind (level within the
    server skill ceiling). Gates the fallback admission of a skill-locked gather
    to ones a LevelSkill can actually open — a source gated above
    max_skill_level stays excluded (no route), preserving _skill_open's
    permanently-closed exclusion."""
    skill, level = req
    return (state.skills.get(skill, 1) < level
            and level <= game_data.max_skill_level)


class GatherMaterialsGoal(Goal):
    """Gather resources needed to craft a specific upgrade item."""

    def __init__(self, target_item: str, needed: dict[str, int],
                 skill_grind: bool = False) -> None:
        self._target_item = target_item
        self._needed = needed  # {material_code: quantity_needed}
        # skill_grind: this is a perpetual skill-XP grind gather (needed target is
        # `held + 1`, never satisfied) whose DROP is a byproduct, not a demand.
        # The deposit/discard protection profile caps its bag reserve so surplus
        # banks (re-withdrawable) instead of choking the bag — see
        # `strategy_driver._step_protection_profile`. Not part of goal identity
        # (repr/serialize) — the `needed` map already distinguishes instances.
        self.skill_grind = skill_grind

    @property
    def needed(self) -> dict[str, int]:
        """The accumulation map this goal drives toward. The arbiter merges it
        into the deposit/discard protection profile while the goal is the
        resolved objective step (trace 2026-06-11 22:36 cycle 30: discard
        deleted this goal's own target item)."""
        return dict(self._needed)

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        base = self._compute_base_value(state, game_data)
        if history is None:
            return base
        # Existing efficiency multiplier — preserves the prior "slow goal gets
        # de-ranked" behaviour.
        avg_cycles = history.goal_avg_cycles_to_satisfy(repr(self), window=20)
        if avg_cycles is None or avg_cycles == 0:
            ramped = base
        else:
            efficiency = min(1.0, 5.0 / avg_cycles)
            ramped = base * efficiency
        if ramped <= 0.0:
            # Satisfied / malformed needed — keep the original zero return.
            return ramped
        # Phase-17: route the proved scalar_yield projection through the
        # band-clamp as an OPTIONAL bonus on top of the existing ramp.
        # Total bonus = (ramped - PRIORITY_FLOOR) + scalar-derived bonus.
        # clamp_into_band(floor, ceiling, bonus) returns
        # `min(ceiling, max(floor, floor + bonus))`, so the result stays in
        # [PRIORITY_FLOOR, PRIORITY_CEILING]; with PRIORITY_CEILING < 70 this
        # preserves the Phase-1 survival-floor invariant for ANY scalar.
        scalar_bonus = yield_bonus_for_goal(repr(self), state, game_data, history)
        total_bonus = Fraction(ramped) - Fraction(PRIORITY_FLOOR) + scalar_bonus
        clamped = clamp_into_band(
            Fraction(PRIORITY_FLOOR), Fraction(PRIORITY_CEILING), total_bonus,
        )
        return float(clamped)

    def _compute_base_value(self, state: WorldState, game_data: GameData) -> float:
        if self.is_satisfied(state):
            return 0.0
        total_needed = sum(self._needed.values())
        # Guard: a malformed `needed` (e.g. mixed-sign quantities summing to 0)
        # would otherwise raise ZeroDivisionError below. The early `is_satisfied`
        # return only saves the all-non-positive case; non-positive total with at
        # least one positive entry still reaches here.
        if total_needed <= 0:
            return 0.0
        bank = state.bank_items or {}
        total_effective = 0.0
        for mat, qty_needed in self._needed.items():
            have_direct = state.inventory.get(mat, 0) + bank.get(mat, 0)
            total_effective += min(have_direct, qty_needed)
            # Count intermediate materials that can be crafted into mat (float for smooth gradient)
            recipe = game_data.crafting_recipe(mat) or {}
            for intermediate, qty_per in recipe.items():
                have_inter = state.inventory.get(intermediate, 0) + bank.get(intermediate, 0)
                if qty_per > 0:
                    craftable = min(have_inter / qty_per, qty_needed - min(have_direct, qty_needed))
                    total_effective += craftable
        fraction_remaining = 1.0 - total_effective / total_needed
        return max(1.0, 40.0 * fraction_remaining)

    def heuristic(self, state: WorldState, game_data: GameData) -> float:
        """Same admissible+consistent skill-grind term as
        `UpgradeEquipmentGoal.heuristic`, keyed on this goal's OWN
        `_target_item` (rather than an upgrade-selection lookup): a
        GatherMaterials search toward a craft-only, skill-gated material
        takes the forced `LevelSkill` edge first instead of exhausting the
        cheap gather/withdraw frontier first (BUG B). 0 when satisfied,
        owned, skill-met, or the target has a non-craft route — see
        `forced_craft_grind`'s admissibility guard."""
        if self.is_satisfied(state):
            return 0.0
        needed = self._needed.get(self._target_item, 1)
        grind = forced_craft_grind(self._target_item, needed, state, game_data)
        if grind is None:
            return 0.0
        skill, level = grind
        return LevelSkill(skill=skill, target_level=level).cost(state, game_data)

    def relevant_actions(self, actions: list[Action], state: WorldState, game_data: GameData) -> list[Action]:
        """Restrict planning to gather/smelt/deposit/withdraw — excludes
        combat and unrelated gathers. Withdraw is included so a material
        already banked is pulled rather than re-gathered."""
        needed_resources, craftable_mats = recipe_closure(game_data, self._needed)
        # Withdraw-eligible item codes: the craftable intermediates + the
        # needed items themselves; every LEAF material arrives via the
        # closure-demand union below (chain covers all closure materials, so
        # the historical per-resource primary-drop loop was redundant — and
        # with GAP-7's widened needed_resources it would have admitted junk
        # withdraws: the PRIMARY drop of a secondarily-needed resource, e.g.
        # bass for a small_pearls closure, is not a closure material).
        withdrawable: set[str] = set(craftable_mats) | set(self._needed)
        # Run-17 trace 2026-06-12 c94: GatherMaterials(feather_coat) was
        # unplannable with 9 feathers IN THE BANK — feather is a MONSTER drop
        # (neither craftable nor a resource drop), so the sets above missed it
        # and Withdraw(feather) never entered a plan. Every material in the
        # full recipe closure (closure_demand includes such leaf inputs) must
        # be withdrawable.
        chain: dict[str, int] = {}
        for code, qty in self._needed.items():
            closure_demand(code, qty, game_data, chain, frozenset())
        # Currency-earning for must-buy items (#13): a non-craftable NPC-only item
        # paid in a NON-GOLD currency (e.g. greater_lifesteal_rune ←
        # sandwhisper_coin) is only buyable once the currency is on hand. Add the
        # currency's demand (unit_price × qty) into the closure so the monster-drop
        # Fight emission below FARMS it (sandwhisper_coin is a sea_marauder drop)
        # → the planner chains Fight×N → NpcBuy. Skip when a permanent GOLD vendor
        # exists (gold needs no farming) or the item is craftable.
        for code, qty in list(self._needed.items()):
            if game_data.crafting_recipe(code) is not None:
                continue
            perm = [(price, cur) for npc, price, cur in game_data.npc_purchases(code)
                    if not game_data.is_event_npc(npc) and game_data.npc_location(npc) is not None]
            if not perm or any(cur == "gold" for _price, cur in perm):
                continue
            unit_price, currency = min(perm, key=lambda pc: pc[0])
            chain[currency] = chain.get(currency, 0) + unit_price * qty
        withdrawable |= set(chain)

        # Recycle-as-acquisition: a licensed RecycleAction whose recipe yields a
        # closure material is a SOURCE for that material, not merely disposal.
        # Live 2026-07-13: the bot chopped 50 ash_wood at 1/cycle to craft 5
        # ash_plank while holding 7 fishing_net — whose recipe IS 6 ash_plank each.
        # Recycle costs 7.00 and returns 3 planks; a gather costs 25.00 and returns
        # ONE ash_wood, of which TEN make one plank.
        #
        # Safety is structural, not conventional: this pool has ALREADY been filtered
        # by `license_destructive_actions` at StrategyArbiter.select, so the recycles
        # visible here are exactly the ones the keep authority permits (and each
        # carries its `bag_floor`, so the working tool is unreachable). Admission can
        # only fail to admit a licensed recycle — it cannot invent an unlicensed one.
        # Derived from the RecycleActions ACTUALLY IN THE POOL, not a scan over ALL
        # known recipes: the factory only ever emits a RecycleAction for an
        # EQUIPPABLE code, so scanning every recipe over-admits non-equippable
        # source codes (ash_plank, hardwood_plank, sap, ...) that can NEVER have a
        # licensed recycle — measured 68 over-admitted sources on a deep gear-chain
        # closure. A code with no licensed RecycleAction in the pool has no recycle
        # to feed, so withdrawing it as a "source" buys nothing and only enlarges
        # the search. Both admission arms (this one and the Recycle arm below) key
        # off this SAME pool-derived set, so they agree about what a "source" is.
        closure_materials = set(chain) | set(self._needed)
        recycle_sources: set[str] = set()
        for action in actions:
            if not isinstance(action, RecycleAction):
                continue
            source_recipe = game_data.crafting_recipe(action.code) or {}
            if set(source_recipe) & closure_materials:
                recycle_sources.add(action.code)
        # The SOURCE is UPSTREAM of the closure (fishing_net is not in the ash_plank
        # closure), so the closure-built `withdrawable` set misses it. Without this a
        # bank-only source is admitted as a recycle whose feeding withdraw is not, and
        # the Withdraw -> Recycle chain — the MAIN path, since DEPOSIT_FULL banks the
        # surplus — is unplannable.
        withdrawable |= recycle_sources

        # Bank-aware gather pruning: the shopping_list credits inventory+bank at
        # every recipe level; a chain material with NET 0 is fully covered, so the
        # bot should WITHDRAW it, not re-gather. Prune the gather whose drop is
        # fully covered (the withdraw stays). A material with any net deficit keeps
        # its gather, so a reachable plan is never pruned. This bounds the GOAP
        # search that the 43-step / 21.7k-node GatherMaterials plans exploded into
        # (live Robby trace) when the bank already held the materials.
        owned: dict[str, int] = dict(state.inventory)
        for code, qty in (state.bank_items or {}).items():
            owned[code] = owned.get(code, 0) + qty
        covered: set[str] = set()
        for item, qty in self._needed.items():
            covered |= fully_covered_materials(item, qty, game_data.crafting_recipes, owned)

        # Gather re-arm: admit the per-skill loadout optimizer for every skill
        # this goal will gather with, so the planner can equip a better owned
        # tool and shed GATHER_LOADOUT_PENALTY from each subsequent gather.
        # Without it the penalty had no action that could remove it and the
        # re-arm was inert — trace 2026-07-05 16:22: copper_pickaxe ferried to
        # the bag, then every cycle still mined with copper_dagger.
        needed_skills: set[str] = set()
        for res in needed_resources:
            skill_req = game_data.resource_skill_level(res)
            if skill_req is not None:
                needed_skills.add(skill_req[0])

        # LevelSkill admission scope: a skill-grind action only serves THIS goal
        # when a closure craftable is gated behind that exact (skill, level) and
        # the character is under it. Without this scope the unconditional
        # `skill_grind` tag admission fanned EVERY emitted LevelSkill (one per
        # craft level in the whole recipe table) into every GatherMaterials
        # search — a pure gold-buy closure (l30 lifesteal_rune) has no craftable
        # yet inherited ~15 useless LevelSkill branches, enlarging the search
        # enough to time out under load (test_slot_scenario_search_is_bounded
        # [l30_rune_fill], activation regression 2026-07-12). Mirrors the
        # OptimizeLoadout `needed_skills` scoping just above.
        gated_skill_levels: set[tuple[str, int]] = set()
        for code in set(craftable_mats) | set(self._needed):
            stats = game_data.item_stats(code)
            if (stats is not None and stats.crafting_skill
                    and game_data.crafting_recipe(code) is not None
                    and state.skills.get(stats.crafting_skill, 1)
                    < stats.crafting_level):
                gated_skill_levels.add((stats.crafting_skill, stats.crafting_level))

        # Gather-skill-gate openings (P3b completion): a closure material whose
        # ONLY gather source is skill-locked (iron_ore ← iron_rocks, mining 10)
        # is unreachable by gathering alone. Mirror the craft-skill gate — admit
        # a LevelSkill(skill->level) that opens it plus the locked gather itself
        # (the gather's own is_applicable enforces the raised skill mid-search,
        # so it fires only after LevelSkill). Restricted to drops with NO
        # currently-open source: a workable open source must never be displaced
        # by a locked one that would force a needless grind (the fishing-40
        # salmon vs fishing-30 bass narrowing hazard, _skill_open docstring).
        open_drops: set[str] = set()
        locked_by_drop: dict[str, list[tuple[str, str, int]]] = {}
        for action in actions:
            if not isinstance(action, GatherAction):
                continue
            if not gather_serves_closure(action.resource_code,
                                         action.drop_item_override,
                                         game_data.resource_drops, chain):
                continue
            drop = (action.drop_item_override
                    or game_data.resource_drop_item(action.resource_code))
            if drop is None or drop in covered:
                continue
            if _skill_open(action.resource_code, state, game_data):
                open_drops.add(drop)
                continue
            req = game_data.resource_skill_level(action.resource_code)
            # _skill_open above returned False, so this gather IS skill-gated —
            # req is non-None (an unskilled gather reads as open, not gated).
            assert req is not None
            if level_below_and_grindable(req, state, game_data):
                locked_by_drop.setdefault(drop, []).append(
                    (action.resource_code, req[0], req[1]))
        openable_locked_gathers: set[str] = set()
        for drop, locked in locked_by_drop.items():
            if drop in open_drops:
                continue  # a workable open source exists — no forced grind
            for res, skill, level in locked:
                openable_locked_gathers.add(res)
                gated_skill_levels.add((skill, level))

        result: list[Action] = []
        for action in actions:
            if (
                isinstance(action, GatherAction)
                and (action.drop_item_override
                     or game_data.resource_drop_item(action.resource_code)) in covered
            ):
                # EFFECTIVE drop item (override for a targeted secondary-drop
                # gather, else the primary) fully bank/inventory-covered —
                # withdraw, don't gather.
                continue
            # GAP-7 admission precision: a gather enters the plan iff its
            # EFFECTIVE drop is a closure material (gather_serves_closure),
            # not merely because its resource is in needed_resources — the
            # widened resource set would otherwise fan every drop-variant of
            # a secondarily-needed resource into the search (the
            # CraftPotionsGoal node-cap flood, derived 2026-07-08).
            if isinstance(action, CraftAction) and action.code in craftable_mats:
                result.append(size_intermediate_craft(action, chain, state, game_data))
            elif (
                (isinstance(action, RecycleAction) and action.code in recycle_sources)
                or "recovery" in action.tags
                or "deposit" in action.tags
                or ("skill_grind" in action.tags
                    and (getattr(action, "skill", ""),
                         getattr(action, "target_level", 0)) in gated_skill_levels)
                or (isinstance(action, GatherAction) and gather_serves_closure(
                    action.resource_code, action.drop_item_override,
                    game_data.resource_drops, chain)
                    and (_skill_open(action.resource_code, state, game_data)
                         or action.resource_code in openable_locked_gathers))
                or (isinstance(action, WithdrawItemAction) and action.code in withdrawable)
                or (isinstance(action, OptimizeLoadoutAction)
                    and action.target_skill in needed_skills)
            ):
                result.append(action)

        # Yield-aware narrowing: when a needed item is the EFFECTIVE drop of >1
        # gather present in `result` (primary drop, or the targeted secondary
        # of a drop_item_override variant — GAP-7), keep only the source
        # minimizing expected gathers (proved in
        # formal/Formal/GatherSelection.lean). Single-source items and
        # non-gather actions are untouched; an unknown drop table fail-opens
        # (no narrowing).
        gathers = [a for a in result if isinstance(a, GatherAction)]
        by_item: dict[str, list[GatherAction]] = {}
        for a in gathers:
            drop = a.drop_item_override or game_data.resource_drop_item(a.resource_code)
            if drop is not None:
                by_item.setdefault(drop, []).append(a)
        drop_losers: set[int] = set()
        for item, group in by_item.items():
            if len(group) < 2:
                continue
            candidates: list[GatherCandidate] = []
            valid = True
            for a in group:
                row = next((r for r in game_data.resource_drop_table(a.resource_code) if r[0] == item), None)
                if row is None:
                    valid = False
                    break
                _code, rate, mn, mx = row
                if a.locations:
                    loc = nearest_or_error(state.x, state.y, a.locations, "gather")
                    dist = abs(loc[0] - state.x) + abs(loc[1] - state.y)
                else:
                    dist = 0
                candidates.append(GatherCandidate(
                    resource_code=a.resource_code, rate=rate, min_quantity=mn,
                    max_quantity=mx, distance=dist))
            if not valid:
                continue
            winner = select_gather_source(item, candidates)
            for a in group:
                if a.resource_code != winner:
                    drop_losers.add(id(a))
        if drop_losers:
            result = [a for a in result if id(a) not in drop_losers]

        # Monster-drop emission + narrowing (the live caller of the proved
        # select_monster_for_drop core, formal/Formal/MonsterDropSelection.lean).
        # For a needed item that is a monster drop, enumerate the FightAction for
        # every WINNABLE monster dropping it, build a MonsterDropCandidate per
        # monster (rate/min/max from the drop table, distance = nearest spawn),
        # pick the expected-kills-optimal winner and keep ONLY that FightAction
        # (drop the dominated ones). Mirrors the GatherSelection narrowing above:
        # kills replace gathers; monsters replace resource nodes. An item with no
        # winnable dropper contributes no FightAction (it also reads as
        # not-producible in tiers/strategy._producible, so no unreachable plan).
        fights_by_code: dict[str, FightAction] = {
            a.monster_code: a for a in actions if isinstance(a, FightAction)
        }
        # Emit a fight for EVERY monster-drop in the full recipe closure, not just
        # top-level needed items. feather_coat (needed={feather_coat:1}) is crafted,
        # not dropped; its feather input is a chicken drop deep in the closure. The
        # old `for item in self._needed` missed it, so Fight(chicken) never entered
        # the action set and GatherMaterials(feather_coat) planned to plan_len=0 — the
        # bot then char-grinded slimes instead of hunting chickens (trace 2026-06-20).
        # `chain` is the closure demand (built above for `withdrawable`); non-drop
        # items (feather_coat, ash_plank) have no droppers and are skipped.
        for item in chain:
            droppers = game_data.monsters_dropping(item)
            if not droppers:
                continue
            drop_candidates: list[MonsterDropCandidate] = []
            winner_fights: dict[str, FightAction] = {}
            for monster_code, rate, mn, mx in droppers:
                fight = fights_by_code.get(monster_code)
                if fight is None:
                    continue
                if not is_winnable(state, game_data, monster_code):
                    continue
                if fight.locations:
                    loc = nearest_or_error(state.x, state.y, fight.locations, "gather")
                    dist = abs(loc[0] - state.x) + abs(loc[1] - state.y)
                else:
                    dist = 0
                drop_candidates.append(MonsterDropCandidate(
                    monster_code=monster_code, rate=rate,
                    min_quantity=mn, max_quantity=mx, distance=dist))
                winner_fights[monster_code] = fight
            if not drop_candidates:
                continue
            chosen = select_monster_for_drop(item, drop_candidates)
            if chosen is not None and chosen in winner_fights:
                fight = winner_fights[chosen]
                emitted = False
                if game_data.xp_per_kill(chosen, state.level) > 0:
                    result.append(fight)
                    emitted = True
                elif grey_farm_allowed(item, state, game_data):
                    # GREY dropper (zero xp at this level): the plain fight is
                    # inapplicable (xpPositive gate), so a recipe demand could
                    # never hunt its drops — live Robby L12 could not gather
                    # feathers from L1 chickens. Emit the drop-farm variant,
                    # but only under the policy: the drop serves a recipe AND
                    # the next-tier recipe is too far a grind away; when a
                    # same-family recipe is within reach, grinding the skill
                    # beats farming greys, and no fight is emitted.
                    result.append(dataclasses.replace(fight, drop_farm=True))
                    emitted = True
                if emitted:
                    # Companion combat swap so A* can satisfy FightAction's
                    # hard optimal-loadout gate: the drop Fight is
                    # inapplicable while a suboptimal weapon is equipped, and
                    # without a swap action in the goal's own menu the goal
                    # is unplannable for the drop demand (any bag occupancy —
                    # Task 6b). Self-guarding: OptimizeLoadout.is_applicable
                    # is False when the loadout is already optimal (empty
                    # _swap_plan), so A* sequences it only when a swap is
                    # actually needed. At a full bag it is slot-gated; the
                    # relief guard preempts across cycles (see
                    # slot-exhaustion fix).
                    result.append(OptimizeLoadoutAction(
                        target_monster_code=chosen, game_data=game_data))

        # C4 Task 1: emit NpcBuy for deep recipe-closure leaves that are
        # currency-bought. A top-level needed item is handled below; a TRANSITIVE
        # ingredient (e.g. jasper_crystal in satchel's recipe) is only in `chain`,
        # not in self._needed. Without this, the planner never sees a way to
        # acquire the leaf and the target is unreachable.
        # Conditions: leaf is non-craftable, not a resource drop, not a monster
        # drop, has a permanent vendor (exclude event NPCs + unlocated).
        for item, qty in chain.items():
            if item in self._needed:
                continue  # top-level items handled by the existing loop below
            if (game_data.crafting_recipe(item) is None
                    and item not in game_data.resource_drops.values()
                    and not game_data.monsters_dropping(item)):
                for npc_code, _price, _currency in game_data.npc_purchases(item):
                    if game_data.is_event_npc(npc_code) or game_data.npc_location(npc_code) is None:
                        continue
                    result.append(NpcBuyAction(npc_code=npc_code, item_code=item,
                                               npc_location=game_data.npc_location(npc_code),
                                               quantity=qty))

        # Craft-vs-buy: offer an NpcBuy alternative for a needed item that is
        # NPC-sold, affordable above the progression reserve floor, and strictly cheaper to buy than
        # craft (proved in formal/Formal/CraftVsBuy.lean). The least-cost planner
        # then picks buy-vs-make. Items with no seller / unaffordable / pricier are
        # left craft-only.
        for item, qty in self._needed.items():
            craftable = game_data.crafting_recipe(item) is not None
            if not craftable:
                # NON-craftable NPC-sold item (rune / bag / artifact — no recipe,
                # not gathered/dropped): BUY is the ONLY acquisition method, so
                # offer it unconditionally. Without this the craft-vs-buy gate
                # returned CRAFT (a non-craftable item looks "cheap to gather")
                # and the slot was unreachable (task #12 phase 6). Offer EVERY
                # vendor via the CURRENCY-AWARE npc_purchases so the planner can
                # pick one whose currency the character can afford —
                # NpcBuyAction.is_applicable gates each on the right currency (gold
                # vs sandwhisper_coin etc.). NOT npcs_selling_item: that is gold-only
                # (#15) and would drop the special-currency vendors this path needs.
                for npc_code, _price, _currency in game_data.npc_purchases(item):
                    result.append(NpcBuyAction(npc_code=npc_code, item_code=item,
                                               npc_location=game_data.npc_location(npc_code),
                                               quantity=qty))
                continue
            # Craftable AND GOLD-sold: only offer NpcBuy when buying beats crafting
            # (proved cheaper_acquisition). npcs_selling_item is gold-only, so the
            # gold-reserve comparison in acquisition_method is sound (#15).
            sellers = game_data.npcs_selling_item(item)
            if not sellers:
                continue
            if acquisition_method(item, qty, state, game_data,
                                  reserve_floor(state, game_data, item)) is not Method.BUY:
                continue
            npc_code, npc_price = min(sellers, key=lambda np: np[1])
            result.append(NpcBuyAction(npc_code=npc_code, item_code=item,
                                       npc_location=game_data.npc_location(npc_code),
                                       quantity=qty))
            # Immediate-fill GE buy source (DUAL of the discard_overstock GE
            # liquidation): when a standing GE SELL order is strictly cheaper than
            # the NPC buy price AND can supply the whole qty in one fill, also offer
            # a GeFillSellOrder. buy_source_venue → GE (gated by choose_buy_venue,
            # proved in formal/Formal/BuySourceVenue.lean) is the decision; the
            # least-cost planner then picks GE vs NPC buy. We only fill an EXISTING
            # order — never post a new one.
            ge_loc = game_data.grand_exchange_location()
            order = game_data.ge_best_sell_order(item)
            ge_price: int | None = None
            if order is not None and order[2] >= qty:
                ge_price = order[1]
            if ge_loc is not None and order is not None and \
                    choose_buy_venue(npc_price, ge_price) is BuyVenue.GE:
                order_id, price, _order_qty = order
                result.append(GeFillSellOrderAction(
                    order_id=order_id, item_code=item, price=price,
                    quantity=qty, ge_location=ge_loc,
                ))

        # Gold ferry for the buy edges above (GAP-3, 2026-07-08): gold is NOT
        # an inventory item — NpcBuyAction's gold gate reads POCKET gold only,
        # while is_plannable's affordability (analyze_currency_leaves) credits
        # pocket + KNOWN bank gold. When the pocket alone cannot pay for the
        # closure's gold-buy leaves, admit ONE deficit-sized WithdrawGold so
        # the plan can chain WithdrawGold → NpcBuy (admit/emit symmetry —
        # without this edge, a pocket-short/bank-rich state is admitted by
        # is_plannable but the search has no gold source and dies at 0-length).
        # Resized from a factory-emitted action so bank location/accessibility
        # survive; capped at the KNOWN bank balance (a None bank ferries
        # nothing — WithdrawGoldAction.is_applicable rejects it anyway).
        deficit = analyze_currency_leaves(self._needed, state, game_data).gold_deficit
        if deficit > 0 and state.bank_gold is not None and state.bank_gold > 0:
            template = next(
                (a for a in actions if isinstance(a, WithdrawGoldAction)), None)
            if template is not None:
                result.append(dataclasses.replace(
                    template, quantity=min(deficit, state.bank_gold)))

        return result

    @property
    def max_depth(self) -> int:
        # Deep chains (3+ levels) can require dozens of steps per unit.
        # Use a generous multiplier so the planner budget (2s) is the real cutoff.
        total_units = sum(self._needed.values())
        return max(100, total_units * 100)

    def is_satisfied(self, state: WorldState) -> bool:
        bank = state.bank_items or {}
        # Already have the FINISHED target item (inventory + bank)? Then
        # gathering materials to craft ANOTHER is redundant — the objective
        # withdraws the existing copy instead. Without this short-circuit, a
        # sticky-committed GatherMaterials(fishing_net) keeps grinding ash_wood
        # for a second fishing_net even though one already sits in the bank
        # (this goal's is_satisfied only tracked the recipe MATERIALS, not the
        # finished item, so it never noticed the banked copy).
        #
        # Only for FINISHED targets (target not among the needed materials).
        # When the target IS the needed material — the raw-material form
        # gather_step_target emits, e.g. GatherMaterials(copper_ore,
        # {copper_ore: 10}) — one stray ore must not satisfy a request for
        # ten (trace 2026-06-11 18:10: the routed copper_ore goal was
        # silently skipped as satisfied all run; zero mining happened).
        if (self._target_item not in self._needed
                and state.inventory.get(self._target_item, 0)
                + bank.get(self._target_item, 0) >= 1):
            return True
        return all(
            state.inventory.get(mat, 0) + bank.get(mat, 0) >= qty
            for mat, qty in self._needed.items()
        )

    def _currency_leaves_affordable(self, state: WorldState, game_data: GameData) -> bool:
        """Return False if any currency-buy leaf in the recipe closure is
        unaffordable — killing the search early (currency_afford_plannable_pure
        proved sound: an unaffordable NpcBuy is inapplicable, and
        GatherMaterials.relevant_actions emits no action that earns the currency,
        so no plan can acquire the leaf).

        Mirrors the closure build in relevant_actions exactly: iterate
        self._needed.items(), accumulate closure_demand per item into one shared
        `chain` dict. A leaf is a currency-buy leaf when:
          - no crafting recipe (recipe is None), AND
          - not a resource drop, AND
          - no monster drops it, AND
          - at least one NPC sells it (npc_purchases non-empty).

        For each such leaf, affordability = any vendor offers it at a currency
        price the character can cover (inv + bank >= price * closure_qty). Uses
        the cheapest-first ordering from npc_purchases and accepts the first
        affordable vendor. If no vendor is affordable, the leaf prunes the goal.
        """
        return not analyze_currency_leaves(self._needed, state, game_data).blocked

    def is_plannable(self, state: WorldState, game_data: GameData,
                     history: LearningStore | None = None) -> bool:
        """Fast-fail only when a currency-buy leaf in the recipe closure is
        unaffordable (C4 Task 5): no plan can acquire a jasper_crystal-style
        leaf without the requisite currency, so pruning discards nothing
        reachable.

        Under-skill craft goals are NOT pruned here (LevelSkill epic P2): the
        planner admits LevelSkill into the GatherMaterials action set, so an
        under-skill target is now reachable via a grind->craft sequence. The
        former crafting-skill fast-fail (which pruned such goals) is retired."""
        return self._currency_leaves_affordable(state, game_data)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"inventory": self._needed}

    def serialize(self) -> dict[str, object]:
        return {"type": "GatherMaterialsGoal",
                "target_item": self._target_item,
                "needed": dict(self._needed)}

    def __repr__(self) -> str:
        # `needed` is part of the goal's IDENTITY: sticky commitment
        # (arbiter select) and fallback dedupe both key on repr. Omitting it
        # let GatherMaterials(copper_bar, needed={copper_bar: 5}) — the
        # committed objective step — collide with the skill-grind craft-one
        # GatherMaterials(copper_bar, needed={copper_bar: 1}); the sticky
        # pass then planned the 1-bar variant and the 5-bar objective
        # silently evaporated at 1/5 bars (trace 2026-06-11 18:46 cycle 15).
        needed = ",".join(f"{code}:{qty}" for code, qty in sorted(self._needed.items()))
        return f"GatherMaterials({self._target_item}, {{{needed}}})"
