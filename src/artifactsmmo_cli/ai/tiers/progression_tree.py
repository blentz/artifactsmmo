"""The progression-tree selector (spec 2026-07-06): trunk -> branch -> target.

Phase 4b: THE decision engine — `StrategyEngine.decide` delegates here.

The Phase-4b cutover swapped the decision procedure, not the data sources: it
kept consuming the same helpers the flat ranking had. That is no longer true of
the RANKING helpers — wave 3a's resolution walk stopped calling them and wave 3b
deleted them (see the WAVE 3b note above `_resolution_rows`). What still
holds, and is why the cutover was safe, is the CANDIDATE side: the builder
below and `pursuit_value` are the same ones the flat ranking read, so the walk
ranks the same facts about the same world.
`_utility_candidates` and its caller `objective_candidates` were the OTHER
builder — utility-slot candidates, weighted by `potion_type_weight` — but
wave 3b deleted both: decide_tree stopped reading them in wave 3a (potions no
longer become roots or fallback roots, only equipment slots do) and the
diagnostic CLI that read the concatenation directly was retired in wave 3b,
leaving zero callers.

Value semantics only — nothing here compares reprs with a Lean model.
Plan C Task 4 deleted `_structural_candidates` and `has_structural_upgrade`,
the band-adequacy leg whose last caller (`player._tree_band_adequate`) was
already uncalled.

`strategy` is imported as a MODULE (attribute access at call time) because
the dependency is now circular: strategy.decide delegates to `decide_tree`
while this module consumes strategy's RootScore/StrategyDecision/
actionable_step. Module-style access on both sides keeps either import
order sound (nothing is dereferenced until after both modules finish
executing)."""

from fractions import Fraction

# MODULE import, not `from ... import RootResolution, resolve_root`, and for
# the reason `decisions/root.py:61-70` gives about `level_skill`: the two
# modules import each other, so whichever is reached first executes while the
# other is half built and a NAME import raises ImportError. root.py already
# used the idiom for its side; this is the other side, and it was latent until
# something imported `decisions.root` FIRST (wave 4 does, from a scenario
# test). Binding the module defers the lookup to call time.
from artifactsmmo_cli.ai.decisions import root as _root
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.tiers import strategy
from artifactsmmo_cli.ai.tiers.meta_goal import StepDecline, no_decline
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import WorldState

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
# one. `StrategyDecision.aged_pick` outlived them until Phase 4-2b-ii deleted
# the focus-aging interleave it reported.
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
# non-ranking consumer at `tiers/taskmaster_choice.py` (`tiers/means_worth.py` retired).


def _resolution_rows(state: WorldState, game_data: GameData,
                     resolution: "_root.RootResolution",
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
    alternative was NOT produced by that trail — it is one of the groups
    `resolve_root` offers (see `RootResolution`), and
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
                step_decline: StepDecline = no_decline,
                ctx: SelectionContext = NO_PROFILE_CONTEXT,
                history: LearningStore | None = None,
                ) -> "strategy.StrategyDecision":
    """THE FLIP (wave 3a, spec §5.2): the root is RESOLVED, not ranked.

    `resolve_root` walks the graph in `ai/decisions/root.py` from
    `WhichPieceIsNext` to one root `MetaGoal`. That replaces the argmax
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
    here). `.aged_pick` went in Phase 4-2b-ii with the interleave it reported.

    What SURVIVES, and must:

    * `step_decline` — the cycle's answer for a root's step, handed to the walk
      so a gear target whose step cannot be served never heads it (Phase 3-2).
      It replaced `step_servable` + `_servable_promotion`, which promoted past
      an unservable pick AFTER the walk, on `is_plannable`'s verdict (a second
      model that refused goals the walk serves). The feather_coat livelock
      (2026-06-20) it guarded against is closed the same way: the woodcutting-
      gated step declines, so the target cannot head the walk.
    * `fallback_roots` / `fallback_steps` — NOT display (spec §2.1).
      `objective_step_goal` still returns None for a resolved root, and
      `_resolve_step_goal` walks past that. The walk re-derives the pairs from
      `RootResolution.alternatives`, trunk last (2026-07-27: a trunk at index 0
      swallowed the whole gear branch).
    """
    resolution = _root.resolve_root(state, game_data, objective, ctx, history,
                                    step_decline)
    chosen_root = resolution.root
    chosen_step = (
        (strategy.actionable_step(chosen_root, state, game_data, ctx)
         or chosen_root)
        if chosen_root is not None else None)
    fallback_roots = list(resolution.alternatives)
    fallback_steps = [strategy.actionable_step(alt, state, game_data, ctx) or alt
                      for alt in resolution.alternatives]

    # interrupt is trace-shape compatibility only: RestoreHP preemption lives
    # in the engine-independent arbiter guard ladder.
    return strategy.StrategyDecision(
        interrupt=None,
        chosen_root=chosen_root,
        chosen_step=chosen_step,
        ranking=_resolution_rows(state, game_data, resolution, ctx),
        fallback_steps=fallback_steps,
        fallback_roots=fallback_roots,
        declined=resolution.declined,
        blocked_target=resolution.blocked_target,
    )


