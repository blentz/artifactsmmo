"""Gathering goal: accumulate materials needed to craft an upgrade."""

from fractions import Fraction

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction, _nearest
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gather_selection import GatherCandidate, select_gather_source
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.priority_band import clamp_into_band
from artifactsmmo_cli.ai.recipe_closure import recipe_closure
from artifactsmmo_cli.ai.scalar_priority import yield_bonus_for_goal
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
            recipe = game_data._crafting_recipes.get(mat) or {}
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

        result: list[Action] = []
        for action in actions:
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
                    loc = _nearest(a.locations, state)
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
        return result

    @property
    def max_depth(self) -> int:
        # Deep chains (3+ levels) can require dozens of steps per unit.
        # Use a generous multiplier so the planner budget (2s) is the real cutoff.
        total_units = sum(self._needed.values())
        return max(100, total_units * 100)

    def is_satisfied(self, state: WorldState) -> bool:
        bank = state.bank_items or {}
        return all(
            state.inventory.get(mat, 0) + bank.get(mat, 0) >= qty
            for mat, qty in self._needed.items()
        )

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"inventory": self._needed}

    def __repr__(self) -> str:
        return f"GatherMaterials({self._target_item})"
