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

from artifactsmmo_cli.ai.decisions.root import RootResolution, resolve_root
from artifactsmmo_cli.ai.equipment.slot_occupancy import may_displace
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.tiers import strategy
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.progression_tree_core import (
    GearCandidate,
    potion_type_weight,
)
from artifactsmmo_cli.ai.tiers.pursuit_value import pursuit_value
from artifactsmmo_cli.ai.weapon_winnability import marginal_weapon_winnability
from artifactsmmo_cli.ai.world_state import WorldState


def _already_owned(code: str, state: WorldState) -> bool:
    """The character holds a copy (bag or bank) — so the only work this gear
    candidate still represents is the EQUIP, which is `pick_loadout`'s call.
    An UNOWNED candidate is left alone: acquiring it is real work that
    terminates, and by the time it lands this gate applies."""
    return (state.inventory.get(code, 0) > 0
            or (state.bank_items or {}).get(code, 0) > 0)


def _structural_candidates(state: WorldState, game_data: GameData,
                            objective: CharacterObjective) -> list[GearCandidate]:
    """Semantics item 2 (structural slots): near-term gear whose pursuit_value
    strictly beats the currently-equipped item, weight 1 (no scaling).

    Scored on `pursuit_value` (combat-dominant efficiency budget), NOT the flat
    `equip_value`: cross-slot GAIN ranking (`focus_aging_order`) must let a
    combat weapon outrank a pure-utility artifact instead of chasing the
    prospecting artifact that flat equip_value mistakenly scored highest
    (the cross-slot bug). Both the candidate stats AND the current-equipped
    baseline (`_item_value`, also pursuit_value) are on the SAME ruler, so
    the gain is consistent.

    OCCUPANCY DEFERRAL: a candidate the character ALREADY OWNS whose slot is
    already OCCUPIED buys nothing but the equip itself, and that equip is
    `pick_loadout`'s call, not this ruler's. Admitted only when it
    `may_displace` the incumbent (see `equipment/slot_occupancy`) — otherwise
    the tree proposes a swap the combat picker reverses next cycle (live
    2026-08-04: `life_amulet` +10000 here, `fire_and_earth_amulet` +42000
    there, alternating forever). Dropping the candidate rather than merely
    refusing the action also keeps it out of the ranking, so it cannot sit
    there as a permanently-unservable root starving the interleave."""
    candidates = []
    for slot, code in objective.near_term_gear(state).items():
        stats = game_data.item_stats(code)
        if stats is None:
            continue
        # Weapon-slot winnability guard: pursuit_value/equip_value is damage-type
        # BLIND, so it would arm a high-attack weapon that beats FEWER monsters
        # (live: fire_bow, attack fire 17, over the equipped copper_axe, attack
        # earth 5 — the local monsters resist fire, so the bot ground weaponcrafting
        # toward a COMBAT DOWNGRADE). predict_win/pick_loadout is already
        # damage-optimal PER MONSTER, so a weapon is worth grinding toward only if
        # OWNING it unlocks a monster the character cannot beat now. Suppress a
        # zero-marginal weapon target; every other slot keeps pursuit_value ranking.
        if (stats.type_ == "weapon"
                and marginal_weapon_winnability(code, state, game_data) <= 0):
            continue
        incumbent = state.equipment.get(slot)
        if incumbent is not None and _already_owned(code, state):
            incumbent_stats = game_data.item_stats(incumbent)
            if incumbent_stats is not None and not may_displace(stats, incumbent_stats):
                continue
        current_value = objective._item_value(incumbent)
        gain = Fraction(pursuit_value(stats) - current_value)
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


_UTILITY_SLOT_QTY_ATTR = {
    "utility1_slot": "utility1_slot_quantity",
    "utility2_slot": "utility2_slot_quantity",
}
"""Per-slot quantity field, mirrored from equipped_potion.py's `_QTY_ATTR`
(not imported — that map is keyed the same way but private to its module).
Used by `_utility_candidates` for the PER-SLOT stock check: unlike
`equipped_potion_qty` (which sums both slots for a given code — the churn
guard other consumers rely on and must not change), the tree needs to know
whether THIS slot specifically is already stocked, so a fill in slot 1 never
blocks a candidate for the still-empty slot 2."""


def _utility_candidates(state: WorldState, game_data: GameData,
                         objective: CharacterObjective) -> list[GearCandidate]:
    """Semantics item 2 (utility slots): skip a slot that is ITSELF already
    stocked (`state.utility1_slot_quantity`/`utility2_slot_quantity` > 0 —
    refill churn is the guard's job, not the tree's) — a per-slot check, not
    `equipped_potion_qty`'s any-slot sum, so utility1 being stocked no longer
    blacks out utility2's candidate (GAP-5). Weight by the hp_restore family
    (the only family utility_potion_targets emits today — see
    potion_type_weight's docstring for when boost/resist targets join this
    path). Same `gain > 0` guard _structural_candidates has: a zero-weighted
    family (unmodeled) or a zero-value item must never arm the gear branch or
    appear as a candidate.

    Scored on `pursuit_value`, the SAME ruler `_structural_candidates` uses.
    The two candidate lists are merged into one argmax by `_gear_ranking_rows`
    / `focus_aging_order`, so scoring them on different rulers made that
    comparison meaningless — for years the potion branch rode a ruler ~500x
    smaller than its competitor's. A potion carries no efficiency stat, so
    `pursuit_value == 1000 * equip_value` for it exactly; the switch changes no
    potion-vs-potion or potion-vs-gear VERDICT that held before, it only makes
    the merged ranking a comparison of like with like."""
    candidates = []
    for slot, code in objective.utility_potion_targets(state).items():
        if getattr(state, _UTILITY_SLOT_QTY_ATTR[slot]) > 0:
            continue
        stats = game_data.item_stats(code)
        if stats is None:
            continue
        gain = potion_type_weight("hp_restore") * Fraction(pursuit_value(stats))
        if gain > 0:
            candidates.append(GearCandidate(slot=slot, code=code, gain=gain, level=stats.level))
    return candidates


def objective_candidates(state: WorldState, game_data: GameData,
                          objective: CharacterObjective) -> list[GearCandidate]:
    """The candidate set the unified objective ranks: structural slots plus
    utility slots, in that order.

    Extracted from `decide_tree` so a DIAGNOSTIC cannot assemble a different
    list than the decision does: a hand-rolled
    `_structural_candidates(...) + _utility_candidates(...)` elsewhere would be
    a second producer of the same list — the failure this repo has shipped
    twice (`feedback_two_plan_producers`). One concatenation, one caller each
    side.

    WAVE 3b: the diagnostic this existed to serve — the `objective` CLI — was
    retired, so `src/` no longer calls this. It is kept because the two builders
    are private and this is the only honest way to assemble their concatenation
    from outside; the slot-coverage suite asserts against it.

    Order is load-bearing and must not be sorted here: `rank_candidates` breaks
    ties by INPUT POSITION (S-008), so reordering this list silently reorders
    the ranking."""
    return (_structural_candidates(state, game_data, objective)
            + _utility_candidates(state, game_data, objective))


# WAVE 3a deleted four private helpers from here — `_candidate_root`,
# `_reach_by_identity`, `_gear_ranking_rows` and `_candidate_fallbacks`. All
# four existed only to assemble `decide_tree`'s scored display rows and its
# candidate-ordered fallback pairs, and the resolution walk builds both from
# `RootResolution` instead, so as of this commit they had zero callers and zero
# reachable lines.
#
# WAVE 3b deleted `StrategyDecision.desired_state` and `.j_ranking`, and
# `RootScore.cost` / `.contribution` / `.instrumental` (re-derived deletion
# list, 2026-08-24, §3 rows 1/2/3/5/7). `j_ranking` had zero PRODUCERS —
# nothing in `src/` ever assigned it, so it was permanently `[]` — and its one
# reader was `StrategyDecision.to_trace` (`strategy.py`), which iterated the
# empty list and called `finite_j` on each element; that block went with the
# field, and with it `strategy.py`'s imports of `finite_j` and
# `ProgressionCandidate`.
# `RootScore.j` and `.reachable_level` are UNCHANGED — spec §1.4 keeps those
# two, they were folded into the wave-3b table's row count (9/10/11) not this
# one. `StrategyDecision.aged_pick` is unchanged too: it is reconnected and
# live (row 6) — `GamePlayer._charge_focus` reads it every cycle — and stays
# set from `resolution.aged` in `decide_tree` below.
#
# WAVE 3b task 4 then deleted the whole ranking substrate that had been left
# stranded by THE FLIP (re-derived list §3 rows 8/9/10/11/12/16 and §5): the
# modules `tiers/achievability_core`, `ai/role_alignment`,
# `tiers/branch_objective`, `tiers/progression_choice` and
# `tiers/horizon_contribution`, and from this file `_j_by_identity`,
# `_synergy_map`, `_achievability_map`, `_role_map`, `_effort_for`,
# `_skill_gate_levels` and `_synergy_map`'s private `_TRUNK_DEMAND` datum. Each
# had zero production callers: the only occurrence of every one of those names
# in `src/` was its own definition. `tiers/synergy_core` STAYS — it has live
# non-ranking consumers at `tiers/taskmaster_choice.py` and `tiers/means_worth.py`.


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


def _resolution_rows(state: WorldState, game_data: GameData,
                     resolution: RootResolution,
                     ctx: SelectionContext) -> "list[strategy.RootScore]":
    """One row per resolved node, chosen first, alternatives after.

    `score` is dropped to the constant `Fraction(1)` on every row rather than
    removed: `RootScoreView.score` is a required float on a Pydantic model that
    the TUI log pane and two test modules pin, and changing the snapshot schema
    is a separate change from changing the decision (spec §1.4). `j` /
    `reachable_level` are left None because no objective priced these rows.
    `contribution`, `cost` and `instrumental` (wave 3b, spec row 1/2/3) were
    deleted from `RootScore` entirely — zero production readers, and
    `instrumental` had zero writers too.

    The row's real content is `category`. For the CHOSEN root it is the
    resolution trail: the ordered `Decision.name`s the walk actually visited, a
    named path a reader can follow, which is what they wanted from the number
    and never got. For an alternative it is `alternative · <kind>`, because an
    alternative was NOT produced by that trail — it is the ordered remainder of
    `WhichSlotIsFurthestBehind` plus the trunk (see `RootResolution`), and
    stamping the chosen root's path onto it would claim a derivation that never
    happened. One vocabulary, two honest values.
    """
    rows: list[strategy.RootScore] = []
    chosen = [] if resolution.root is None else [resolution.root]
    for index, root in enumerate([*chosen, *resolution.alternatives]):
        step = strategy.actionable_step(root, state, game_data, ctx) or root
        category = (" → ".join(resolution.trail) if index == 0 and chosen
                    else f"alternative · {strategy.root_category(root)}")
        rows.append(strategy.RootScore(
            root_repr=repr(root), category=category, score=Fraction(1),
            step_repr=repr(step)))
    return rows


def decide_tree(state: WorldState, game_data: GameData,
                objective: CharacterObjective,
                step_servable: Callable[[MetaGoal, MetaGoal], bool] | None = None,
                ctx: SelectionContext = NO_PROFILE_CONTEXT,
                history: LearningStore | None = None,
                ) -> "strategy.StrategyDecision":
    """THE FLIP (wave 3a, spec §5.2): the root is RESOLVED, not ranked.

    `resolve_root` walks the five-node graph in `ai/decisions/root.py` from
    `IsMyGearBehindMyTier` to one root `MetaGoal`. That replaces the argmax
    this function used to run — a scored competition between two unrelated
    scales sharing one column (live 2026-08-08: gear showed 2.6e8 against the
    trunk's 1.0 while `J` had them within 0.006% of each other, trunk winning).

    Six parameters went with the ranking, because nothing survives that could
    read them: `band_adequate` (the boolean pivot's input), `focus` and `seats`
    (the aging/d'Hondt interleave), `committed_root_code` and `enable_synergy`
    (the synergy weighting), and `store` — renamed `history` here, since it is
    no longer the unified objective's projection input but the same learning
    store every other `Decision` in the codebase already takes under that name.
    Spec §5.2 keeps `band_adequate` in the signature and then never reads it;
    an unused parameter is dead surface that the next reader has to disprove,
    so it is dropped. `StrategyDecision.j_ranking` took its field default for
    the same reason — the ranking that produced it is gone — and wave 3b
    deleted the field entirely, along with `.desired_state` (always `{}`
    here). `.aged_pick` is NOT the same story: it is reconnected and live
    (spec row 6), so it is set from `resolution.aged` below, not defaulted.

    What SURVIVES, and must:

    * `step_servable` and `_servable_promotion` — the plannability demotion.
      Verbatim: it is a pure function over four lists and knows nothing about
      scoring. Dropping it reinstates the feather_coat livelock (2026-06-20).
    * `fallback_roots` / `fallback_steps` — NOT display (spec §2.1).
      `objective_step_goal` still returns None for a resolved root, and
      `_resolve_step_goal` walks past that. The walk re-derives the pairs from
      `RootResolution.alternatives`, trunk last (2026-07-27: a trunk at index 0
      swallowed the whole gear branch).
    * `promoted_from` — the tree's own pick when promotion displaced it.
    """
    resolution = resolve_root(state, game_data, objective, ctx, history)
    chosen_root = resolution.root
    chosen_step = (
        (strategy.actionable_step(chosen_root, state, game_data, ctx)
         or chosen_root)
        if chosen_root is not None else None)
    fallback_roots = list(resolution.alternatives)
    fallback_steps = [strategy.actionable_step(alt, state, game_data, ctx) or alt
                      for alt in resolution.alternatives]

    tree_pick_root = chosen_root
    if (step_servable is not None and chosen_root is not None
            and chosen_step is not None):
        chosen_root, chosen_step, fallback_roots, fallback_steps = _servable_promotion(
            chosen_root, chosen_step, fallback_roots, fallback_steps, step_servable)
    promoted_from = tree_pick_root if chosen_root is not tree_pick_root else None

    # interrupt is trace-shape compatibility only: RestoreHP preemption lives
    # in the engine-independent arbiter guard ladder.
    return strategy.StrategyDecision(
        interrupt=None,
        chosen_root=chosen_root,
        chosen_step=chosen_step,
        ranking=_resolution_rows(state, game_data, resolution, ctx),
        fallback_steps=fallback_steps,
        fallback_roots=fallback_roots,
        # Set by the ONE node that takes the interleave, not re-derived here.
        # The old `aged_pick` was a clause-for-clause MIRROR of
        # `focus_aging_pick`'s fast-path guard, carrying its own drift warning
        # and two mutation anchors; a single producer cannot drift from itself.
        aged_pick=resolution.aged,
        promoted_from=promoted_from,
    )


