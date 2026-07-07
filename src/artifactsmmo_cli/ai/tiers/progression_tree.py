"""The progression-tree selector (spec 2026-07-06): trunk -> branch -> target.

Phase 4b: THE decision engine — `StrategyEngine.decide` delegates here.
Consumes the same helpers the flat ranking used, so the cutover swapped the
decision procedure, not the data sources.

Value semantics only — nothing here compares reprs with the Lean model
(that lockstep lives at the pure-core level in progression_tree_core.py).

`strategy` is imported as a MODULE (attribute access at call time) because
the dependency is now circular: strategy.decide delegates to `decide_tree`
while this module consumes strategy's RootScore/StrategyDecision/
actionable_step. Module-style access on both sides keeps either import
order sound (nothing is dereferenced until after both modules finish
executing)."""

from collections.abc import Callable
from fractions import Fraction

from artifactsmmo_cli.ai.equipped_potion import equipped_potion_qty
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers import strategy
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


def has_structural_upgrade(state: WorldState, game_data: GameData,
                            objective: CharacterObjective) -> bool:
    """True when a positive-gain STRUCTURAL upgrade is reachable — the
    tier-aware leg of band adequacy (2026-07-07 live-shadow correction: a
    FILLED slot holding under-tier gear must not read as adequate; an empty
    slot is just the gain-from-zero special case). Utility/potion targets
    deliberately excluded: consumable restock must never break adequacy or
    the empty-slot churn loop re-enters through the branch switch."""
    return bool(_structural_candidates(state, game_data, objective))


def _utility_candidates(state: WorldState, game_data: GameData,
                         objective: CharacterObjective) -> list[GearCandidate]:
    """Semantics item 2 (utility slots): skip already-provisioned potions
    (equipped_potion_qty > 0 — refill churn is the guard's job, not the
    tree's); else weight by the hp_restore family (the only family
    utility_potion_targets emits today — see potion_type_weight's docstring
    for when boost/resist targets join this path). Same `gain > 0` guard
    _structural_candidates has: a zero-weighted family (unmodeled) or a
    zero-value item must never arm the gear branch or appear as a
    candidate."""
    candidates = []
    for slot, code in objective.utility_potion_targets(state).items():
        if equipped_potion_qty(state, code) > 0:
            continue
        stats = game_data.item_stats(code)
        if stats is None:
            continue
        gain = potion_type_weight("hp_restore") * Fraction(equip_value(stats))
        if gain > 0:
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
                       ordered: list[GearCandidate]) -> "list[strategy.RootScore]":
    """Semantics item 7: one row per gear candidate, best-first. Contribution
    mirrors score in every row (no separate weighting exists in this display
    path — the trunk row does the same: contribution == score == Fraction(1))."""
    rows = []
    for candidate in ordered:
        root = _candidate_root(candidate)
        step = strategy.actionable_step(root, state, game_data) or root
        rows.append(strategy.RootScore(
            root_repr=repr(root), category="gear", contribution=candidate.gain,
            cost=0, score=candidate.gain, step_repr=repr(step)))
    return rows


def _candidate_fallbacks(state: WorldState, game_data: GameData,
                         ordered: list[GearCandidate],
                         skip: GearCandidate | None = None,
                         ) -> tuple[list[MetaGoal], list[MetaGoal]]:
    """Root/step pairs for `ordered` (pick order), skipping `skip` (the
    candidate already promoted to chosen_root, when there is one). Shared by
    both branches: the GEAR arm skips its own pick, the XP arm skips nothing
    (the trunk — not a candidate — is the chosen decision there)."""
    roots: list[MetaGoal] = []
    steps: list[MetaGoal] = []
    for candidate in ordered:
        if candidate == skip:
            continue
        root = _candidate_root(candidate)
        step = strategy.actionable_step(root, state, game_data) or root
        roots.append(root)
        steps.append(step)
    return roots, steps


def _servable_promotion(
    chosen_root: MetaGoal, chosen_step: MetaGoal,
    fallback_roots: list[MetaGoal], fallback_steps: list[MetaGoal],
    step_servable: Callable[[MetaGoal, MetaGoal], bool],
) -> tuple[MetaGoal, MetaGoal, list[MetaGoal], list[MetaGoal]]:
    """Servability demotion (the legacy decide()'s `step_servable` role,
    surviving the flip — dropping it risks the plannability livelocks the
    filter exists to prevent, e.g. feather_coat 2026-06-20): when the chosen
    (root, step) is unservable, walk the fallback pairs IN ORDER to the first
    servable pair and promote it to chosen. Demoted pairs (the original
    chosen, then any skipped fallbacks) stay in the fallback lists after the
    promoted one — original priority order minus the promotion. All
    unservable: keep the original choice (the arbiter's doomed-memo handles
    it, as today)."""
    if step_servable(chosen_root, chosen_step):
        return chosen_root, chosen_step, fallback_roots, fallback_steps
    idx = next(
        (i for i, pair in enumerate(zip(fallback_roots, fallback_steps, strict=True))
         if step_servable(*pair)),
        None)
    if idx is None:
        return chosen_root, chosen_step, fallback_roots, fallback_steps
    promoted_root, promoted_step = fallback_roots[idx], fallback_steps[idx]
    demoted_roots = [chosen_root, *fallback_roots[:idx], *fallback_roots[idx + 1:]]
    demoted_steps = [chosen_step, *fallback_steps[:idx], *fallback_steps[idx + 1:]]
    return promoted_root, promoted_step, demoted_roots, demoted_steps


def decide_tree(state: WorldState, game_data: GameData,
                objective: CharacterObjective,
                band_adequate: bool = False,
                step_servable: Callable[[MetaGoal, MetaGoal], bool] | None = None,
                ) -> "strategy.StrategyDecision":
    """The tree assembly: trunk milestone, gear/xp branch pivot, and the
    chosen root/step — composing the Task-1 pure cores exactly per the
    2026-07-06 BINDING semantics. Phase 4b: this IS the decision engine
    (`StrategyEngine.decide` delegates here).

    `band_adequate` is caller-supplied (the player wires the real
    progression-band verdict in; it defaults to False, reproducing the
    Phase-2 interim stand-in `band_adequate = candidates == []` exactly for
    every band-less caller). `gear_target_exists = candidates != []` stays
    computed internally — it is a structural fact about this decide_tree
    call, not something a caller could second-guess.

    `step_servable` is the per-cycle plannability predicate (None in unit
    tests that don't exercise plannability) — see `_servable_promotion`."""
    trunk = ReachCharLevel(level=milestone_pure(state.level))

    candidates = _structural_candidates(state, game_data, objective) \
        + _utility_candidates(state, game_data, objective)
    gear_target_exists = candidates != []
    branch = branch_pick_pure(band_adequate, gear_target_exists)

    ordered = _ordered(candidates)
    pick = gear_target_pick(candidates) if candidates else None
    if candidates:
        # Drift-risk hardening: the display order's element 0 must always
        # agree with the proven core's argmax — gear_target_pick is the
        # authority, _ordered is a display convenience over the same rule.
        assert ordered[0] == pick, (
            "_ordered(candidates)[0] must equal gear_target_pick(candidates) — "
            "gear_target_pick is the proven authority; the display path may "
            "never disagree with it"
        )

    fallback_roots: list[MetaGoal]
    fallback_steps: list[MetaGoal]

    if branch is Branch.GEAR:
        assert pick is not None  # gear_target_exists guarantees a non-empty list
        chosen_root: MetaGoal = _candidate_root(pick)
        chosen_step: MetaGoal = strategy.actionable_step(chosen_root, state, game_data) or chosen_root
        # Semantics item 6: the other branch (xp trunk) first, then the
        # remaining gear candidates in pick order, each its own root/step.
        extra_roots, extra_steps = _candidate_fallbacks(state, game_data, ordered, skip=pick)
        fallback_roots = [trunk, *extra_roots]
        fallback_steps = [trunk, *extra_steps]
    else:
        # XP branch: the trunk IS the chosen decision. Any gear candidates
        # (possible now that band_adequate is caller-supplied: adequate band
        # with upgrades still on offer) must not be silently dropped —
        # Phase-2 final-review finding — so they survive as fallbacks, in
        # pick order, so the arbiter can still fall back to gear when the
        # trunk step yields no goal.
        chosen_root = trunk
        chosen_step = trunk
        fallback_roots, fallback_steps = _candidate_fallbacks(state, game_data, ordered)

    if step_servable is not None:
        chosen_root, chosen_step, fallback_roots, fallback_steps = _servable_promotion(
            chosen_root, chosen_step, fallback_roots, fallback_steps, step_servable)

    trunk_row = strategy.RootScore(
        root_repr=repr(trunk), category="char_level", contribution=Fraction(1),
        cost=0, score=Fraction(1), step_repr=repr(trunk))
    ranking = [trunk_row, *_gear_ranking_rows(state, game_data, ordered)]

    return strategy.StrategyDecision(
        interrupt=None,
        chosen_root=chosen_root,
        chosen_step=chosen_step,
        desired_state={},
        ranking=ranking,
        fallback_steps=fallback_steps,
        fallback_roots=fallback_roots,
    )
