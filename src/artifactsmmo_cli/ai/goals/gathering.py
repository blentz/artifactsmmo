"""Gathering goal: accumulate materials needed to craft an upgrade."""

from fractions import Fraction

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.ge_fill_sell import GeFillSellOrderAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.buy_source_venue import BuyVenue, choose_buy_venue
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.craft_vs_buy import GOLD_RESERVE, Method, acquisition_method
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gather_selection import GatherCandidate, select_gather_source
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.monster_drop_selection import (
    MonsterDropCandidate,
    select_monster_for_drop,
)
from artifactsmmo_cli.ai.nearest_tile import nearest_or_error
from artifactsmmo_cli.ai.priority_band import clamp_into_band
from artifactsmmo_cli.ai.recipe_closure import closure_demand, recipe_closure
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


class GatherMaterialsGoal(Goal):
    """Gather resources needed to craft a specific upgrade item."""

    def __init__(self, target_item: str, needed: dict[str, int]) -> None:
        self._target_item = target_item
        self._needed = needed  # {material_code: quantity_needed}

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

    def relevant_actions(self, actions: list[Action], state: WorldState, game_data: GameData) -> list[Action]:
        """Restrict planning to gather/smelt/deposit/withdraw — excludes
        combat and unrelated gathers. Withdraw is included so a material
        already banked is pulled rather than re-gathered."""
        needed_resources, craftable_mats = recipe_closure(game_data, self._needed)
        # Withdraw-eligible item codes: drops of needed resources (leaf raw
        # materials) + the craftable intermediates themselves.
        withdrawable: set[str] = set(craftable_mats) | set(self._needed)
        for res in needed_resources:
            drop = game_data.resource_drop_item(res)
            if drop is not None:
                withdrawable.add(drop)
        # Run-17 trace 2026-06-12 c94: GatherMaterials(feather_coat) was
        # unplannable with 9 feathers IN THE BANK — feather is a MONSTER drop
        # (neither craftable nor a resource drop), so the sets above missed it
        # and Withdraw(feather) never entered a plan. Every material in the
        # full recipe closure (closure_demand includes such leaf inputs) must
        # be withdrawable.
        chain: dict[str, int] = {}
        for code, qty in self._needed.items():
            closure_demand(code, qty, game_data, chain, frozenset())
        withdrawable |= set(chain)

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

        result: list[Action] = []
        for action in actions:
            if (
                isinstance(action, GatherAction)
                and game_data.resource_drop_item(action.resource_code) in covered
            ):
                # Drop item fully bank/inventory-covered — withdraw, don't gather.
                continue
            if (
                "recovery" in action.tags
                or "deposit" in action.tags
                or (isinstance(action, GatherAction) and action.resource_code in needed_resources)
                or (isinstance(action, CraftAction) and action.code in craftable_mats)
                or (isinstance(action, WithdrawItemAction) and action.code in withdrawable)
            ):
                result.append(action)

        # Yield-aware narrowing: when a needed item is the PRIMARY drop of >1
        # resource present in `result`, keep only the source minimizing expected
        # gathers (proved in formal/Formal/GatherSelection.lean). Single-source
        # items and non-gather actions are untouched; an unknown drop table
        # fail-opens (no narrowing).
        gathers = [a for a in result if isinstance(a, GatherAction)]
        by_item: dict[str, list[GatherAction]] = {}
        for a in gathers:
            drop = game_data.resource_drop_item(a.resource_code)
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
        for item in self._needed:
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
                result.append(winner_fights[chosen])

        # Craft-vs-buy: offer an NpcBuy alternative for a needed item that is
        # NPC-sold, affordable above GOLD_RESERVE, and strictly cheaper to buy than
        # craft (proved in formal/Formal/CraftVsBuy.lean). The least-cost planner
        # then picks buy-vs-make. Items with no seller / unaffordable / pricier are
        # left craft-only.
        for item, qty in self._needed.items():
            sellers = game_data.npcs_selling_item(item)
            if not sellers:
                continue
            if acquisition_method(item, qty, state, game_data, GOLD_RESERVE) is not Method.BUY:
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

    def is_plannable(self, state: WorldState, game_data: GameData,
                     history: LearningStore | None = None) -> bool:
        """Fail fast when satisfaction requires CRAFTING the target and the
        crafting skill is below the recipe gate — CraftAction.is_applicable
        blocks the craft, so no plan exists. Trace 2026-06-11 18:10: the
        fallback GatherMaterials(feather_coat) (materials owned, gearcrafting
        2 < 5) burned 97k-99k nodes / the full 90s budget to plan_len 0 on
        every probe cycle. Materials-only goals (finished target not among
        `needed`) stay plannable — gathering inputs never needs the gated
        final craft."""
        if self._target_item not in self._needed:
            return True
        stats = game_data.item_stats(self._target_item)
        if (stats is None or not stats.crafting_skill
                or state.skills.get(stats.crafting_skill, 1) >= stats.crafting_level):
            return True
        bank = state.bank_items or {}
        owned = (state.inventory.get(self._target_item, 0)
                 + bank.get(self._target_item, 0))
        return owned >= self._needed[self._target_item]

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"inventory": self._needed}

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
