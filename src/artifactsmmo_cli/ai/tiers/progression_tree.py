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

from collections.abc import Callable, Mapping
from fractions import Fraction
from types import MappingProxyType

from artifactsmmo_cli.ai.decisions.root import RootResolution, resolve_root
from artifactsmmo_cli.ai.equipment.slot_occupancy import may_displace
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.requirement_graph_memo import CHAR_XP, SKILL_PREFIX
from artifactsmmo_cli.ai.requirement_projections import requirement_closure
from artifactsmmo_cli.ai.role_alignment import role_alignment_pure
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.tiers import strategy
from artifactsmmo_cli.ai.tiers.achievability_core import achievability_pure
from artifactsmmo_cli.ai.tiers.branch_objective import (
    finite_j,
)
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.progression_choice import ProgressionCandidate
from artifactsmmo_cli.ai.tiers.progression_tree_core import (
    _NO_SYNERGY,
    GearCandidate,
    potion_type_weight,
)
from artifactsmmo_cli.ai.tiers.pursuit_value import pursuit_value
from artifactsmmo_cli.ai.tiers.synergy_core import synergy_pure
from artifactsmmo_cli.ai.weapon_winnability import marginal_weapon_winnability
from artifactsmmo_cli.ai.world_state import WorldState

_NO_FOCUS: Mapping[tuple[str, str], int] = MappingProxyType({})
"""Immutable empty-focus default (mirrors the `NO_PROFILE_CONTEXT` convention):
avoids a mutable `{}` default (ruff B006). `decide_tree` only reads it
(`.get`), never mutates it — the anti-starvation ledger is owned and mutated
by `GamePlayer` (Task 6)."""

_NO_J: Mapping[str, int] = MappingProxyType({})
"""Immutable empty J map — 'the objective was not consulted'. Every lookup misses
and the display rows carry `j=None`, which is exactly the store-less case."""

_NO_SEATS: Mapping[str, int] = MappingProxyType({})
"""Immutable empty-seats default (sibling of `_NO_FOCUS`): the d'Hondt seat
accumulator for the focus-aging interleave. `decide_tree` only reads it
(`.get`), never mutates it — the accumulator is owned and bumped by
`GamePlayer._interleave_seats` in lockstep with the focus ledger (Task 12).
Empty seats + unaged focus reproduce the plain `gear_target_pick` argmax, so
every default-arg caller is unaffected."""


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
    list than the decision does. `commands/objective.py` reproduces the
    objective's ranking outside the bot, and a hand-rolled
    `_structural_candidates(...) + _utility_candidates(...)` there would be a
    second producer of the same list — the failure this repo has shipped twice
    (`feedback_two_plan_producers`). One concatenation, one caller each side.

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
# reachable lines. They are NOT the wave-3b deletion list: that is the public
# schema (`RootScore.j` / `.reachable_level`, `StrategyDecision.aged_pick` /
# `.j_ranking`) and `J` itself, which still have live readers here and in the
# TUI. Leaving dead private helpers behind to be tidied later is how this repo
# grew `distance_cost_pure` — proved, differential-tested, and called by
# nothing (`feedback_proof_over_an_uncalled_helper`).


def _j_by_identity(
    ranking: "list[ProgressionCandidate]") -> Mapping[str, int]:
    """Each root's unified-objective value, keyed as `j_ranking` names it.

    Candidates outside the finite band are OMITTED rather than mapped to a
    number: `J` is void for them (`finite_j`), and a row reporting `j=None` says
    "the objective could not price this" where a 0 would claim it priced it at
    nothing. Written as a
    loop rather than a comprehension so `finite_j` is called once per candidate
    and the result type is honestly `int`."""
    out: dict[str, int] = {}
    for candidate in ranking:
        value = finite_j(candidate)
        if value is not None:
            out[candidate.identity] = value
    return out


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


#: The char-level trunk's requirement, as a demand multiset member: it always
#: demands character progression. A gear candidate whose closure routes through
#: monster drops carries a `char_xp` token too, so it overlaps the trunk and is
#: nudged up — the "L50 slightly favoured" preference, mechanical not tuned.
_TRUNK_DEMAND: Mapping[str, int] = MappingProxyType({CHAR_XP: 1})


def _skill_gate_levels(code: str, game_data: GameData) -> Mapping[str, int]:
    """The real per-skill gate `code`'s closure demands: for each craft/gather
    skill touched by ANY closure item, the MAX required level among those
    items — you must reach the highest gate to use the skill at all, so max
    is the honest requirement (not sum, not min).

    Fix round 1 (critical finding): `_effort_for` used to reuse `code`'s OWN
    `item_stats(code).crafting_level` as `need` for every `skill:<name>`
    token in its multiset, whatever skill that token actually came from —
    correct only for the one token matching `code`'s own craft skill, wrong
    for everything gathered (e.g. life_ring's `skill:mining` token is really
    gated at mining 10, from `iron_ore`/`iron_bar`, not jewelrycrafting 15).
    `requirement_multiset_for` deliberately discards the per-item level when
    it collapses a skill to a token (`requirement_graph_memo.py` keeps only
    the skill NAME), so the level cannot be recovered from its output — this
    reads it straight from the graph's `craft_skill`/`gather_skill` maps,
    which still carry it."""
    graph = game_data.requirement_graph.graph()
    levels: dict[str, int] = {}
    for item in requirement_closure(graph, [code]):
        for gate in (graph.craft_skill.get(item), graph.gather_skill.get(item)):
            if gate is not None:
                skill, level = gate
                levels[skill] = max(levels.get(skill, 0), level)
    return levels


def _effort_for(code: str, state: WorldState, game_data: GameData) -> int:
    """UNMET demand for one unit of `code`: how much work is actually LEFT.

    Total demand ranks by price tag, not difficulty — life_ring demands 2000
    gold, which is no work at all to a character holding 12382. Subtracting
    holdings is what makes this an effort measure rather than a cost sheet.

    Token handling:
      * `skill:<name>` — the LEVEL DEFICIT against that skill's own real gate
        in `code`'s closure (`_skill_gate_levels`), not the token count and
        NOT `code`'s own craft level. A 5-level gap is real work; being
        already at level is none. This is the distinction the whole factor
        turns on: a skill-gapped candidate must read cheaper than a
        currency-gated one, not equally blocked.
      * `char_xp` — SKIPPED. It marks drop-routed work for synergy alignment;
        it is not a unit of demand and would inflate every drop-routed
        candidate.
      * everything else — an item quantity, credited against inventory + bank.
    """
    held = dict(state.inventory or {})
    for item, qty in (state.bank_items or {}).items():
        held[item] = held.get(item, 0) + qty
    held["gold"] = state.gold + (state.bank_gold or 0)
    gate_levels = _skill_gate_levels(code, game_data)

    effort = 0
    for token, qty in game_data.requirement_graph.requirement_multiset_for(code).items():
        if token == CHAR_XP:
            continue
        if token.startswith(SKILL_PREFIX):
            skill = token[len(SKILL_PREFIX):]
            need = gate_levels.get(skill, 0)
            effort += max(0, need - state.skills.get(skill, 0))
            continue
        effort += max(0, qty - held.get(token, 0))
    return effort


def _synergy_map(candidates: list[GearCandidate],
                 committed_root_code: str | None,
                 state: WorldState,
                 game_data: GameData) -> Mapping[tuple[str, str], Fraction]:
    """The per-candidate synergy multiplier (spec 2026-07-19 §3.6/§3.10): the
    demand-weighted fraction of a candidate's own ENRICHED requirement multiset
    that OTHER live roots also demand (leave-one-out), mapped through
    `synergy_pure` into [S_MIN, 1]. Keyed `(slot, code)` like the focus ledger.

    The multiset spans items (quantities) AND synthetic tokens — `skill:<name>`
    (closure items gated by that craft/gather skill) and `char_xp` (DROP leaves)
    — so alignment counts skill and character-level overlap, not just shared
    materials (`RequirementGraphMemo.requirement_multiset_for`).

    Two-pass: build each member's multiset once, SUM into `total`, then score
    each candidate `shared / own` where a token is shared iff some OTHER member
    still demands it after the candidate's own copy is removed
    (`total[i] - own[i] > 0`) — the leave-one-out subtraction. Members are the
    sibling candidates, the char-level trunk (always — `char_xp`), the committed
    root, and the current task: an items/gather task by its full enriched
    requirement, a monsters-task by `char_xp` (it produces char progression, not
    items). The committed root is usually ALSO a sibling candidate, so its demand
    enters `total` twice — deliberate: it biases toward finishing what is started
    (§3.6), and a candidate that IS the committed root overlaps itself through
    that second copy. O(N) walks (memoized on the graph), not O(N^2)."""
    if not candidates:
        return _NO_SYNERGY
    memo = game_data.requirement_graph
    own: dict[tuple[str, str], Mapping[str, int]] = {
        (c.slot, c.code): memo.requirement_multiset_for(c.code) for c in candidates}
    members: list[Mapping[str, int]] = list(own.values())
    members.append(_TRUNK_DEMAND)
    if committed_root_code is not None:
        members.append(memo.requirement_multiset_for(committed_root_code))
    if state.task_code is not None:
        if state.task_type == "monsters":
            members.append(_TRUNK_DEMAND)   # combat task -> char progression
        else:
            members.append(memo.requirement_multiset_for(state.task_code))
    total: dict[str, int] = {}
    for demand in members:
        for item, qty in demand.items():
            total[item] = total.get(item, 0) + qty
    out: dict[tuple[str, str], Fraction] = {}
    for key, demand in own.items():
        own_total = sum(demand.values())
        shared = sum(qty for item, qty in demand.items()
                     if total[item] - qty > 0)
        out[key] = synergy_pure(shared, own_total)
    return out


def _achievability_map(candidates: list[GearCandidate], state: WorldState,
                       game_data: GameData) -> Mapping[tuple[str, str], Fraction]:
    """Per-candidate effort multiplier, keyed `(slot, code)` like `focus` and
    `synergy`. Scored RELATIVE to the cheapest candidate in this decision, so
    the factor has no absolute effort scale."""
    if not candidates:
        return {}
    efforts = {(c.slot, c.code): _effort_for(c.code, state, game_data) for c in candidates}
    floor = min(efforts.values())
    return {key: achievability_pure(effort, floor) for key, effort in efforts.items()}


def _role_map(candidates: list[GearCandidate], owned_skills: frozenset[str],
              game_data: GameData) -> Mapping[tuple[str, str], Fraction]:
    """Per-candidate role-fit multiplier, keyed `(slot, code)` like `focus`,
    `synergy` and `achievability` — the FIFTH selection factor
    (emergent-specialization spec; `role_alignment.py` holds the pure core).

    Takes the role's OWNED SKILLS directly rather than a role name — the
    caller (`decide_tree`, off `ctx.role_skills`) already has them, resolved
    once by `GamePlayer._selection_context` against `role_catalog.
    ROLES_BY_NAME`. Resolving a name here instead would re-import
    `role_catalog` into this module, reviving the circular import
    `role_catalog -> tiers.skill_classes -> tiers.__init__ -> tiers.strategy
    -> tiers.progression_tree -> role_catalog` (2026-08-01 fix) — and it would
    duplicate the exact lookup `GamePlayer` already performs to populate
    `ctx.role_skills`.

    `{}` whenever this character holds no role, which is every
    single-character run: an empty map makes every `role.get(...)` lookup read
    `Fraction(1)`, so `_scaled_weights` and both aging-guard fast paths are
    byte-identical to the four-factor product. That is the `_NO_ROLE` sentinel
    semantics reproduced exactly, and it is what keeps the no-role path
    unchanged rather than merely close. `owned_skills` is the unambiguous
    "no role" signal here: `role_catalog.role_skills(role)` is never empty for
    a real `Role` (every role owns at least its `craft` skill), so an empty
    frozenset can only mean the caller resolved no role at all.

    The candidate's own producing skill comes from `GameData.producing_skill`
    (craft skill if craftable, else the gathering skill of a resource that
    drops it) — the SAME accessor `GamePlayer._update_coordination` routes
    sibling demand with, so a candidate is judged on-role here by exactly the
    rule that decides which role would be asked to supply it. An item with no
    known producing skill reads as ALIGNED, never MISALIGNED: no signal must
    never become a penalty (see `role_alignment_pure`)."""
    if not owned_skills:
        return {}
    return {(c.slot, c.code): role_alignment_pure(
        owned_skills, game_data.producing_skill(c.code)) for c in candidates}


def _resolution_rows(state: WorldState, game_data: GameData,
                     resolution: RootResolution,
                     ctx: SelectionContext) -> "list[strategy.RootScore]":
    """One row per resolved node, chosen first, alternatives after.

    `score` is dropped to the constant `Fraction(1)` on every row rather than
    removed: `RootScoreView.score` is a required float on a Pydantic model that
    the TUI log pane and two test modules pin, and changing the snapshot schema
    is a separate change from changing the decision (spec §1.4). `contribution`
    and `cost` are constants for the same reason — the spec's own consumer
    inventory records ZERO readers for both — and `j` / `reachable_level` are
    left None because no objective priced these rows.

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
            root_repr=repr(root), category=category,
            contribution=Fraction(1), cost=0, score=Fraction(1),
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
    so it is dropped. `StrategyDecision.aged_pick` and `.j_ranking` now take
    their field defaults for the same reason — the ranking that produced them
    is gone; the fields themselves are deleted in wave 3b.

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

    # interrupt/desired_state are trace-shape compatibility only: RestoreHP
    # preemption lives in the engine-independent arbiter guard ladder, and
    # no consumer reads desired_state off the decision.
    return strategy.StrategyDecision(
        interrupt=None,
        chosen_root=chosen_root,
        chosen_step=chosen_step,
        desired_state={},
        ranking=_resolution_rows(state, game_data, resolution, ctx),
        fallback_steps=fallback_steps,
        fallback_roots=fallback_roots,
        promoted_from=promoted_from,
    )


