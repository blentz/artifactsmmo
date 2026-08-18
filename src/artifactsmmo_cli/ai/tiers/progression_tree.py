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
    TRUNK_IDENTITY,
    branch_from_ranking,
    branch_ranking,
    candidate_identity,
    finite_j,
    justifying_identities,
)
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ObtainItem, ReachCharLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.progression_choice import ProgressionCandidate
from artifactsmmo_cli.ai.tiers.progression_tree_core import (
    _NO_SYNERGY,
    FOCUS_FLAT,
    Branch,
    GearCandidate,
    branch_pick_pure,
    focus_aging_order,
    focus_aging_pick,
    milestone_pure,
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


def _candidate_root(candidate: GearCandidate) -> ObtainItem:
    return ObtainItem(code=candidate.code, quantity=1, slot=candidate.slot)


def _j_by_identity(
    ranking: "list[ProgressionCandidate]") -> Mapping[str, int]:
    """Each root's unified-objective value, keyed as `j_ranking` names it.

    Candidates outside the finite band are OMITTED rather than mapped to a
    number: `J` is void for them (`finite_j`), and a row reporting `j=None` says
    "the objective could not price this" where a 0 would claim it priced it at
    nothing. Those roots are covered by `_reach_by_identity` instead. Written as a
    loop rather than a comprehension so `finite_j` is called once per candidate
    and the result type is honestly `int`."""
    out: dict[str, int] = {}
    for candidate in ranking:
        value = finite_j(candidate)
        if value is not None:
            out[candidate.identity] = value
    return out


def _reach_by_identity(
    ranking: "list[ProgressionCandidate]") -> Mapping[str, int]:
    """Reachable level for each root `J` cannot price — the complement of
    `_j_by_identity`, so between them every root gets a figure on ONE of the two
    scales and none falls back to the legacy `score`.

    Only the unpriceable ones are included. A finite-band root has a `J` and does
    not need this, and giving it both would invite a reader to compare a level
    against a cycle count — a third scale in the same column, which is the whole
    problem repeating."""
    out: dict[str, int] = {}
    for candidate in ranking:
        if finite_j(candidate) is None:
            out[candidate.identity] = candidate.reachable_level
    return out


def _gear_ranking_rows(state: WorldState, game_data: GameData,
                       ordered: list[GearCandidate],
                       ctx: SelectionContext = NO_PROFILE_CONTEXT,
                       j_by_identity: Mapping[str, int] = _NO_J,
                       reach_by_identity: Mapping[str, int] = _NO_J,
                       ) -> "list[strategy.RootScore]":
    """Semantics item 7: one row per gear candidate, best-first. Contribution
    mirrors score in every row (no separate weighting exists in this display
    path — the trunk row does the same: contribution == score == Fraction(1)).

    `j_by_identity` carries each candidate's unified-objective value into the
    display so a reader can see the scale the pivot actually used, instead of
    inferring a verdict from `score` — which is `pursuit_value` here and a bare
    `Fraction(1)` on the trunk row, two scales that share a column and nothing
    else. Empty (the default) leaves every `j` None, which is what every caller
    without a learning store gets."""
    rows = []
    for candidate in ordered:
        root = _candidate_root(candidate)
        step = strategy.actionable_step(root, state, game_data, ctx) or root
        rows.append(strategy.RootScore(
            root_repr=repr(root), category="gear", contribution=candidate.gain,
            cost=0, score=candidate.gain, step_repr=repr(step),
            j=j_by_identity.get(candidate_identity(candidate)),
            reachable_level=reach_by_identity.get(candidate_identity(candidate))))
    return rows


def _candidate_fallbacks(state: WorldState, game_data: GameData,
                         ordered: list[GearCandidate],
                         skip: GearCandidate | None = None,
                         ctx: SelectionContext = NO_PROFILE_CONTEXT,
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
        step = strategy.actionable_step(root, state, game_data, ctx) or root
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


def decide_tree(state: WorldState, game_data: GameData,
                objective: CharacterObjective,
                band_adequate: bool = False,
                step_servable: Callable[[MetaGoal, MetaGoal], bool] | None = None,
                ctx: SelectionContext = NO_PROFILE_CONTEXT,
                focus: Mapping[tuple[str, str], int] = _NO_FOCUS,
                seats: Mapping[str, int] = _NO_SEATS,
                committed_root_code: str | None = None,
                enable_synergy: bool = False,
                store: LearningStore | None = None,
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
    tests that don't exercise plannability) — see `_servable_promotion`.

    `ctx` (the caller's per-cycle `SelectionContext`) is caller-supplied the
    same way — the player wires the real per-cycle context in; it defaults to
    `NO_PROFILE_CONTEXT`, reproducing the pre-epic descent for every caller
    that doesn't wire it in. Forwarded to every `actionable_step` call so the
    descent stops at a node with any ready `ai/obtain_sources` route instead
    of falling into its recipe (one-obtain-model epic, Task 5 — subsuming the
    recycle-as-acquisition epic's bespoke `recoverable` map).

    `focus`/`seats` (arbiter anti-starvation epic, Task 4; Task 12 perf) drive
    the pick/order aging: `focus` is the caller's per-(slot, code) commitment
    ledger (how many consecutive cycles that candidate has been the committed
    root — see `focus_aging_pick`'s `falloff`), `seats` is the caller's
    incremental d'Hondt seat accumulator (one seat bumped per aged decision,
    reset in lockstep with `focus`) feeding the single-step interleave
    `dhondt_step`. Both default to the empty-focus / empty-seats case, which
    `focus_aging_pick`/`focus_aging_order` guarantee is bit-identical to the
    plain `gear_target_pick` argmax (the old `_ordered` display order it
    replaces) — every existing caller that doesn't wire the ledger in is
    unaffected."""
    trunk = ReachCharLevel(level=milestone_pure(state.level))

    candidates = objective_candidates(state, game_data, objective)
    gear_target_exists = candidates != []

    # THE PIVOT. With a learning store the branch is chosen by the unified
    # objective `J` (`tiers/branch_objective`): every gear root and the xp trunk
    # get one projection to level 50, priced in one currency — actions — and the
    # cheapest wins. Without a store there is nothing to project against, so the
    # legacy boolean pivot stands (see `StrategyEngine.decide`'s `store`).
    #
    # `band_adequate` is NOT consulted on the `J` path and that is the point: it
    # was a PROXY for "gear has stopped paying", and its switch
    # (`winnable AND NOT has_structural_upgrade`) never flipped against a 50-level
    # catalogue — GEAR in 2950 of 2950 cycles, zero character levels gained in 13h.
    # `J` measures the same thing directly. It stays a live parameter because the
    # store-less path still reads it.
    j_ranking = (branch_ranking(state, game_data, candidates, store, ctx)
                 if store is not None else None)
    branch = (branch_from_ranking(j_ranking) if j_ranking is not None
              else branch_pick_pure(band_adequate, gear_target_exists))

    # THE GEAR BRANCH MAY ONLY PURSUE A CANDIDATE THAT JUSTIFIED CHOOSING IT.
    # `J` names the gear roots that beat the trunk; the five selection factors
    # below then order THOSE, keeping their calibration but losing the freedom to
    # commit to a root the objective has just shown buys no progression.
    #
    # Live R2D2 2026-08-07: `J` chose GEAR because `greater_wooden_staff` raised
    # the reachable level 18 -> 25, and `focus_aging_pick` — ranking on gain, with
    # `aged_pick` null, so not even the focus ledger — committed to
    # `adventurer_vest`, reach 18 and the dearest candidate on the board. HAL hit
    # the same board the same cycle and picked the staff. Two selectors answering
    # two different questions, and only one of them was looking at level 50.
    #
    # `eligible` is the whole list whenever the filter cannot apply — the XP
    # branch (nothing to pursue), no store (no ranking), or the degenerate case of
    # a GEAR verdict with an empty justifying set, which `branch_from_ranking`
    # cannot produce but which must not silently empty the candidate list if it
    # ever did. Every one of those reduces to the pre-filter behaviour exactly.
    justifying = (justifying_identities(j_ranking)
                  if j_ranking is not None and branch is Branch.GEAR else frozenset())
    eligible = [c for c in candidates if candidate_identity(c) in justifying] or candidates
    # The rest stay reachable as LAST-RESORT fallbacks, behind the trunk (below):
    # dropping them outright would remove options the servability walk relies on
    # when both the justifying pick and the trunk turn out unservable.
    demoted = [c for c in candidates if c not in eligible]

    # Synergy weighting (spec 2026-07-19 §3): the third selection factor after
    # magnitude (gain) and staleness (falloff). Computed once here and shared by
    # every candidate; `enable_synergy` is the caller's opt-in (the player wires
    # it) so every unit caller stays byte-identical on the inert `_NO_SYNERGY`
    # default — the §3.8 kill switch.
    synergy = (_synergy_map(candidates, committed_root_code, state, game_data)
               if enable_synergy else _NO_SYNERGY)

    # Achievability weighting (effort-to-reach, the fourth selection factor):
    # scored once here, relative to the cheapest candidate in THIS decision
    # (see `_achievability_map`'s docstring). Unlike synergy there is no
    # opt-in flag — the empty-candidates case already collapses to `{}`
    # (inert), and a non-empty candidate list always has a well-defined
    # cheapest member, so there is no unready-data case to gate on.
    achievability = _achievability_map(candidates, state, game_data)

    # Role alignment (the fifth selection factor): damp a candidate whose
    # producing skill this character's role does not own, so a role-holder
    # prefers the chain its own skills already serve and leaves the rest to the
    # sibling that claimed them. The owned skills come off the per-cycle
    # `SelectionContext` (`GamePlayer._selection_context` resolves `self._role`
    # against `role_catalog.ROLES_BY_NAME` and binds the result) — the same
    # channel `supply_target` uses, so no second coordination seam exists.
    # `ctx.role_skills` empty — every single-character run, and any character
    # that holds no lease this cycle — yields `{}`, i.e. the inert four-factor
    # product exactly.
    role = _role_map(candidates, ctx.role_skills, game_data)

    # Aging pick/order run over `eligible`, not `candidates`: the objective has
    # already ruled the rest out for THIS branch, and letting them into the argmax
    # is exactly how the branch's justification and the pursued root came apart.
    # With no filter applied `eligible is candidates`, so every existing caller is
    # byte-identical — including the seat ledger, since these are still the same
    # two calls on the same list.
    ordered = focus_aging_order(eligible, focus, seats, synergy, achievability, role)
    pick = (focus_aging_pick(eligible, focus, seats, synergy, achievability, role)
            if eligible else None)
    if eligible:
        # Drift-risk hardening: the display order's element 0 must always
        # agree with the aging pick — focus_aging_order is built FROM
        # focus_aging_pick (Task 3), so this is a same-cycle consistency
        # check, not a separate authority.
        assert ordered[0] == pick, (
            "focus_aging_order(...)[0] must equal focus_aging_pick(...) — "
            "focus_aging_order is built from focus_aging_pick; the display "
            "path may never disagree with it"
        )

    # Task 12 (candidate-scoped aged verdict): the gear pick went through the
    # focus-aging INTERLEAVE this decision IFF the gear branch is chosen AND
    # some candidate has aged past the flat window — the negation of
    # `focus_aging_pick`'s fast-path condition, over the SAME candidates. The
    # player gates its d'Hondt seat bump on this (not on a whole-ledger scan),
    # so a stale ledger entry for a root that has LEFT the candidate set (e.g.
    # its slot got filled by equipping owned gear — no level-up, no equippable
    # craft, so no focus reset) can no longer make the player consume a seat on
    # a cycle that actually took the fast path. `all(...)` is over the non-empty
    # candidate list whenever the branch is GEAR (gear_target_exists holds).
    # The synergy AND achievability clauses both mirror `focus_aging_pick`'s
    # widened fast-path guard: a pick steered by synergy OR achievability
    # (weights differ with nothing stale) IS an aged decision, so the player
    # bumps a seat for it — otherwise the interleave schedule and the seat
    # ledger would disagree. Omitting the achievability clause here would be
    # the identical trap `focus_aging_pick`'s own fix addresses: a pick
    # steered purely by achievability, with focus and synergy both inert,
    # would read as NOT aged and silently starve the seat ledger.
    #
    # The ROLE clause is the same clause a third time, added when the factor
    # went live (Task 14). While `_role_map` returned nothing this mirror was
    # correct by accident — no caller passed a role — and the moment one did,
    # a role-steered pick (focus, synergy and achievability all inert) would
    # have taken the d'Hondt interleave inside `focus_aging_pick` while
    # reading as NOT aged here, so the player would skip its seat bump and the
    # interleave schedule and the seat ledger would drift apart. This guard
    # must stay clause-for-clause identical to `focus_aging_pick`'s.
    #
    # It must also scan the SAME LIST. Since the unified objective filters the
    # candidates handed to `focus_aging_pick`, this mirror reads `eligible` too —
    # scanning the full `candidates` would let a stale or synergy-carrying entry
    # that `J` excluded from the pick declare the decision aged, and the player
    # would consume a d'Hondt seat for an interleave that never ran. That is the
    # same list-mismatch drift the paragraphs above describe, arriving by a new
    # route.
    aged_pick = branch is Branch.GEAR and not (
        all(focus.get((c.slot, c.code), 0) <= FOCUS_FLAT for c in eligible)
        and all(synergy.get((c.slot, c.code), Fraction(1)) == Fraction(1)
                for c in eligible)
        and all(achievability.get((c.slot, c.code), Fraction(1)) == Fraction(1)
                for c in eligible)
        and all(role.get((c.slot, c.code), Fraction(1)) == Fraction(1)
                for c in eligible))

    fallback_roots: list[MetaGoal]
    fallback_steps: list[MetaGoal]

    if branch is Branch.GEAR:
        assert pick is not None  # gear_target_exists guarantees a non-empty list
        chosen_root: MetaGoal = _candidate_root(pick)
        chosen_step: MetaGoal = strategy.actionable_step(
            chosen_root, state, game_data, ctx) or chosen_root
        # Semantics item 6, CORRECTED 2026-07-27: the remaining gear candidates
        # in pick order FIRST, then the other branch (xp trunk) last.
        #
        # The trunk sat at index 0 until a live trace measured the cost. When
        # the chosen gear step is unservable, `_servable_promotion` walks this
        # list and takes the FIRST servable pair — so a single unservable gear
        # step abandoned the whole gear branch for XP grinding while servable
        # gear candidates sat behind the trunk, unreached. Robby, 2026-07-27:
        # 9 of 15 cycles ran ReachCharLevel with 7 structural candidates live
        # and band_adequate False, i.e. with the tree's own branch verdict
        # saying GEAR.
        #
        # The trunk stays in the list, just last: when EVERY gear pair is
        # unservable the promotion still reaches it, so a fully-blocked gear
        # branch yields to XP exactly as before rather than deadlocking.
        # Yielding the branch is the last resort, not the first.
        #
        # The candidates the objective DEMOTED come after the trunk, not before
        # it. They are still reachable, so a board where the justifying pick and
        # the trunk are both unservable cannot deadlock — but a candidate `J` has
        # shown buys no progression must never be tried ahead of simply grinding.
        extra_roots, extra_steps = _candidate_fallbacks(
            state, game_data, ordered, skip=pick, ctx=ctx)
        demoted_roots, demoted_steps = _candidate_fallbacks(
            state, game_data, demoted, ctx=ctx)
        fallback_roots = [*extra_roots, trunk, *demoted_roots]
        fallback_steps = [*extra_steps, trunk, *demoted_steps]
    else:
        # XP branch: the trunk IS the chosen decision. Any gear candidates
        # (possible now that band_adequate is caller-supplied: adequate band
        # with upgrades still on offer) must not be silently dropped —
        # Phase-2 final-review finding — so they survive as fallbacks, in
        # pick order, so the arbiter can still fall back to gear when the
        # trunk step yields no goal.
        chosen_root = trunk
        chosen_step = trunk
        fallback_roots, fallback_steps = _candidate_fallbacks(
            state, game_data, ordered, ctx=ctx)

    # The tree's OWN pick, before servability can displace it. Kept so the
    # trace can tell "the tree chose this" apart from "the tree chose something
    # else and promotion landed here" — indistinguishable in the 2026-07-27
    # trace, which logged `chosen_root_servable: true` for a promoted trunk and
    # made 9 cycles of fallback-walking read as a branch decision.
    tree_pick_root = chosen_root
    if step_servable is not None:
        chosen_root, chosen_step, fallback_roots, fallback_steps = _servable_promotion(
            chosen_root, chosen_step, fallback_roots, fallback_steps, step_servable)
    promoted_from = tree_pick_root if chosen_root is not tree_pick_root else None

    # Each root's unified-objective value, keyed the way `j_ranking` names them,
    # so the display can show the scale the pivot actually decided on. `score`
    # stays exactly what it was — `pursuit_value` for gear, the constant 1 for the
    # trunk — because it is a HIGHER-IS-BETTER field and `J` is lower-is-better;
    # folding one into the other would be a sign error dressed up as a tidy-up,
    # which is the defect class this whole objective exists to retire.
    j_by_identity = _j_by_identity(j_ranking) if j_ranking else _NO_J
    reach_by_identity = _reach_by_identity(j_ranking) if j_ranking else _NO_J
    trunk_row = strategy.RootScore(
        root_repr=repr(trunk), category="char_level", contribution=Fraction(1),
        cost=0, score=Fraction(1), step_repr=repr(trunk),
        j=j_by_identity.get(TRUNK_IDENTITY),
        reachable_level=reach_by_identity.get(TRUNK_IDENTITY))
    # The display ranking keeps EVERY candidate, demoted ones included — it is a
    # diagnostic, and a reader comparing it against `j_ranking` needs to see the
    # roots the objective ruled out, not a list quietly pruned to the survivors.
    ranking = [trunk_row,
               *_gear_ranking_rows(state, game_data, [*ordered, *demoted], ctx,
                                   j_by_identity, reach_by_identity)]

    # interrupt/desired_state are trace-shape compatibility only: RestoreHP
    # preemption lives in the engine-independent arbiter guard ladder, and
    # no consumer reads desired_state off the decision post-flip.
    return strategy.StrategyDecision(
        interrupt=None,
        chosen_root=chosen_root,
        chosen_step=chosen_step,
        desired_state={},
        ranking=ranking,
        fallback_steps=fallback_steps,
        fallback_roots=fallback_roots,
        aged_pick=aged_pick,
        promoted_from=promoted_from,
        j_ranking=j_ranking or [],
    )
