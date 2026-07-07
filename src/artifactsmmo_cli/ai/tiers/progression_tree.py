"""The progression-tree selector (spec 2026-07-06): trunk -> branch -> target.

Phase 2: standalone assembly, NOT wired into StrategyEngine.decide (Phase 3
shadows it there). Consumes the same helpers the flat ranking uses, so the
cutover swaps the decision procedure, not the data sources.

Value semantics only — nothing here compares reprs with the Lean model
(that lockstep lives at the pure-core level in progression_tree_core.py)."""

from fractions import Fraction

from artifactsmmo_cli.ai.equipped_potion import equipped_potion_qty
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ObtainItem, ReachCharLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.progression_tree_core import (
    Branch,
    GearCandidate,
    branch_pick_pure,
    gear_target_pick,
    milestone_pure,
    potion_type_weight,
)
from artifactsmmo_cli.ai.tiers.strategy import RootScore, StrategyDecision, actionable_step
from artifactsmmo_cli.ai.world_state import WorldState


def _structural_candidates(state: WorldState, game_data: GameData,
                            objective: CharacterObjective) -> list[GearCandidate]:
    """Semantics item 2 (structural slots): near-term gear whose equip_value
    strictly beats the currently-equipped item, weight 1 (no scaling)."""
    candidates = []
    for slot, code in objective.near_term_gear(state).items():
        stats = game_data.item_stats(code)
        if stats is None:
            continue
        current_value = objective._item_value(state.equipment.get(slot))
        gain = Fraction(equip_value(stats) - current_value)
        if gain > 0:
            candidates.append(GearCandidate(slot=slot, code=code, gain=gain, level=stats.level))
    return candidates


def _utility_candidates(state: WorldState, game_data: GameData,
                         objective: CharacterObjective) -> list[GearCandidate]:
    """Semantics item 2 (utility slots): skip already-provisioned potions
    (equipped_potion_qty > 0 — refill churn is the guard's job, not the
    tree's); else weight by the hp_restore family (the only family
    utility_potion_targets emits today — see potion_type_weight's docstring
    for when boost/resist targets join this path)."""
    candidates = []
    for slot, code in objective.utility_potion_targets(state).items():
        if equipped_potion_qty(state, code) > 0:
            continue
        stats = game_data.item_stats(code)
        if stats is None:
            continue
        gain = potion_type_weight("hp_restore") * Fraction(equip_value(stats))
        candidates.append(GearCandidate(slot=slot, code=code, gain=gain, level=stats.level))
    return candidates


def _ordered(candidates: list[GearCandidate]) -> list[GearCandidate]:
    """The same canonical total order gear_target_pick's argmax uses: biggest
    weighted gain, then higher item level, then code/slot as pure
    disambiguators. Element 0 is exactly what gear_target_pick returns —
    reusing this order lets the remaining fallbacks fall out for free."""
    return sorted(candidates, key=lambda c: (-c.gain, -c.level, c.code, c.slot))


def _candidate_root(candidate: GearCandidate) -> ObtainItem:
    return ObtainItem(code=candidate.code, quantity=1, slot=candidate.slot)


def _gear_ranking_rows(state: WorldState, game_data: GameData,
                       ordered: list[GearCandidate]) -> list[RootScore]:
    """Semantics item 7: one row per gear candidate, best-first. Contribution
    mirrors score in every row (no separate weighting exists in this display
    path — the trunk row does the same: contribution == score == Fraction(1))."""
    rows = []
    for candidate in ordered:
        root = _candidate_root(candidate)
        step = actionable_step(root, state, game_data) or root
        rows.append(RootScore(
            root_repr=repr(root), category="gear", contribution=candidate.gain,
            cost=0, score=candidate.gain, step_repr=repr(step)))
    return rows


def decide_tree(state: WorldState, game_data: GameData,
                objective: CharacterObjective) -> StrategyDecision:
    """The Phase-2 tree assembly: trunk milestone, gear/xp branch pivot, and
    the chosen root/step — composing the Task-1 pure cores exactly per the
    2026-07-06 BINDING semantics."""
    trunk = ReachCharLevel(level=milestone_pure(state.level))

    candidates = _structural_candidates(state, game_data, objective) \
        + _utility_candidates(state, game_data, objective)
    gear_target_exists = candidates != []
    band_adequate = candidates == []
    branch = branch_pick_pure(band_adequate, gear_target_exists)

    ordered = _ordered(candidates)
    fallback_roots: list[MetaGoal] = []
    fallback_steps: list[MetaGoal] = []

    if branch is Branch.GEAR:
        pick = gear_target_pick(candidates)
        assert pick is not None  # gear_target_exists guarantees a non-empty list
        chosen_root: MetaGoal = _candidate_root(pick)
        chosen_step: MetaGoal = actionable_step(chosen_root, state, game_data) or chosen_root
        # Semantics item 6: the other branch (xp trunk) first, then the
        # remaining gear candidates in pick order, each its own root/step.
        fallback_roots.append(trunk)
        fallback_steps.append(trunk)
        for candidate in ordered:
            if candidate == pick:
                continue
            root = _candidate_root(candidate)
            step = actionable_step(root, state, game_data) or root
            fallback_roots.append(root)
            fallback_steps.append(step)
    else:
        # XP branch: band_adequate implies candidates == [] (branch_pick_pure's
        # truth table), so there is no gear pick to offer as a fallback —
        # "impossible by rule" per semantics item 6.
        chosen_root = trunk
        chosen_step = trunk

    trunk_row = RootScore(
        root_repr=repr(trunk), category="char_level", contribution=Fraction(1),
        cost=0, score=Fraction(1), step_repr=repr(trunk))
    ranking = [trunk_row, *_gear_ranking_rows(state, game_data, ordered)]

    return StrategyDecision(
        interrupt=None,
        chosen_root=chosen_root,
        chosen_step=chosen_step,
        desired_state={},
        ranking=ranking,
        fallback_steps=fallback_steps,
        fallback_roots=fallback_roots,
    )
